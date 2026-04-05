"""
Shopify OAuth 2.0 install flow.

Flow:
  1. GET /api/v1/auth/shopify?shop=merchant.myshopify.com
     → Validate shop, generate state, redirect to Shopify authorization page
  2. Shopify redirects back:
     GET /api/v1/auth/shopify/callback?shop=...&code=...&state=...&hmac=...
     → Validate HMAC + state, exchange code for permanent token, fetch shop info,
       upsert User row, issue our JWT, redirect browser to frontend callback page

State storage: in-memory dict with TTL.
  Fine for single-instance. For multi-instance: move to Redis
  (REDIS_URL is already available in settings).
"""

import hashlib
import hmac as hmac_lib
import secrets
import time
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models.user import User
from app.routers.auth import _create_token

router = APIRouter(prefix="/api/v1/auth", tags=["shopify-oauth"])

# Scopes required by the app
SCOPES = ",".join([
    "read_products",
    "write_products",
    "read_inventory",
    "write_inventory",
    "read_orders",
    "read_webhooks",
    "write_webhooks",
])

# ---------------------------------------------------------------------------
# State store — CSRF protection
# ---------------------------------------------------------------------------

_STATE_TTL = 600  # 10 minutes
_pending_states: dict[str, tuple[str, float]] = {}  # state -> (shop, expires_at)


def _store_state(state: str, shop: str) -> None:
    now = time.time()
    # Prune expired entries to prevent unbounded growth
    expired = [k for k, (_, exp) in _pending_states.items() if exp < now]
    for k in expired:
        del _pending_states[k]
    _pending_states[state] = (shop, now + _STATE_TTL)


def _pop_state(state: str) -> str | None:
    """Remove and return the shop for this state, or None if missing/expired."""
    entry = _pending_states.pop(state, None)
    if entry is None:
        return None
    shop, expires_at = entry
    if time.time() > expires_at:
        return None
    return shop


# ---------------------------------------------------------------------------
# HMAC validation
# ---------------------------------------------------------------------------

def _validate_hmac(all_params: dict[str, str], secret: str) -> bool:
    """
    Validate Shopify HMAC per OAuth spec:
    Sort all params except 'hmac', join as key=value&..., HMAC-SHA256 with client secret.
    """
    provided = all_params.get("hmac", "")
    message = "&".join(
        f"{k}={v}" for k, v in sorted(all_params.items()) if k != "hmac"
    )
    digest = hmac_lib.new(
        secret.encode("utf-8"), message.encode("utf-8"), hashlib.sha256
    ).hexdigest()
    return hmac_lib.compare_digest(digest, provided)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/shopify")
def shopify_install(shop: str = Query(..., description="The merchant's .myshopify.com domain")):
    """
    Step 1 — Initiate OAuth.
    Redirect merchant's browser to Shopify's authorization page.
    Called from the settings page or an App Store install link.
    """
    shop = shop.strip().lower().removeprefix("https://").removeprefix("http://").rstrip("/")
    if not shop.endswith(".myshopify.com"):
        raise HTTPException(400, "shop must be a .myshopify.com domain (e.g. mystore.myshopify.com)")

    if not settings.shopify_client_id:
        raise HTTPException(500, "SHOPIFY_CLIENT_ID is not configured")

    state = secrets.token_urlsafe(16)
    _store_state(state, shop)

    redirect_uri = f"{settings.app_url}/api/v1/auth/shopify/callback"
    params = urlencode({
        "client_id": settings.shopify_client_id,
        "scope": SCOPES,
        "redirect_uri": redirect_uri,
        "state": state,
    })
    return RedirectResponse(f"https://{shop}/admin/oauth/authorize?{params}")


@router.get("/shopify/callback")
def shopify_callback(
    shop: str = Query(...),
    code: str = Query(...),
    state: str = Query(...),
    hmac: str = Query(...),
    db: Session = Depends(get_db),
):
    """
    Step 2 — Handle Shopify's redirect after merchant approves the app.
    Validates HMAC + state, exchanges code for access token, upserts User, issues JWT.
    """
    # --- CSRF check ---
    expected_shop = _pop_state(state)
    if expected_shop != shop:
        raise HTTPException(400, "Invalid or expired OAuth state — please try connecting again")

    # --- HMAC validation ---
    if not _validate_hmac({"shop": shop, "code": code, "state": state, "hmac": hmac},
                          settings.shopify_client_secret):
        raise HTTPException(400, "HMAC validation failed — request may have been tampered with")

    # --- Exchange code for permanent access token ---
    try:
        token_resp = httpx.post(
            f"https://{shop}/admin/oauth/access_token",
            json={
                "client_id": settings.shopify_client_id,
                "client_secret": settings.shopify_client_secret,
                "code": code,
            },
            timeout=10,
        )
    except httpx.RequestError as exc:
        raise HTTPException(502, f"Network error contacting Shopify: {exc}") from exc

    if token_resp.status_code != 200:
        raise HTTPException(502, "Shopify rejected the access token exchange")

    access_token = token_resp.json().get("access_token")
    if not access_token:
        raise HTTPException(502, "No access_token in Shopify response")

    # --- Fetch shop info (owner email + name) ---
    try:
        shop_resp = httpx.get(
            f"https://{shop}/admin/api/2025-01/shop.json",
            headers={"X-Shopify-Access-Token": access_token},
            timeout=10,
        )
        shop_info = shop_resp.json().get("shop", {}) if shop_resp.status_code == 200 else {}
    except httpx.RequestError:
        shop_info = {}

    owner_email = (
        shop_info.get("email")
        or f"oauth+{shop.replace('.myshopify.com', '')}@producthub.local"
    )
    owner_name = shop_info.get("shop_owner") or shop_info.get("name") or shop

    # --- Upsert User ---
    # Priority: find by shop domain → find by email → create new
    user = db.query(User).filter(User.shopify_store == shop).first()
    if not user:
        user = db.query(User).filter(User.email == owner_email).first()

    if user:
        user.shopify_store = shop
        user.shopify_token = access_token
    else:
        user = User(
            shopify_store=shop,
            shopify_token=access_token,
            email=owner_email,
            name=owner_name,
        )
        db.add(user)

    db.commit()
    db.refresh(user)

    # --- Issue our JWT and redirect browser to frontend ---
    jwt_token = _create_token(str(user.id))
    return RedirectResponse(
        f"{settings.frontend_url}/auth/shopify/callback?token={jwt_token}"
    )
