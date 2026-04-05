import base64
import hashlib
import hmac
import json
import logging
from typing import Optional

from fastapi import APIRouter, Header, HTTPException, Request
from sqlalchemy.orm import Session

from app.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/webhooks", tags=["webhooks"])


def _verify_hmac(body: bytes, hmac_header: Optional[str], secret: str = "") -> bool:
    """Verify Shopify HMAC-SHA256 signature."""
    if not secret:
        return True  # not configured — skip verification in dev
    if not hmac_header:
        return False
    digest = hmac.new(secret.encode(), body, hashlib.sha256).digest()
    computed = base64.b64encode(digest).decode()
    return hmac.compare_digest(computed, hmac_header)


def _verify_webhook_hmac(body: bytes, hmac_header: Optional[str]) -> bool:
    """Verify regular webhook signature using SHOPIFY_WEBHOOK_SECRET."""
    return _verify_hmac(body, hmac_header, getattr(settings, "shopify_webhook_secret", ""))


def _verify_gdpr_hmac(body: bytes, hmac_header: Optional[str]) -> bool:
    """
    Verify GDPR mandatory webhook signature.
    Shopify signs these with the app's CLIENT SECRET (not the webhook secret).
    """
    return _verify_hmac(body, hmac_header, settings.shopify_client_secret)


@router.post("/shopify/products/update")
async def product_updated(
    request: Request,
    x_shopify_hmac_sha256: Optional[str] = Header(None),
):
    body = await request.body()
    if not _verify_webhook_hmac(body, x_shopify_hmac_sha256):
        raise HTTPException(status_code=401, detail="Invalid HMAC")

    try:
        data = json.loads(body)
        shopify_id = data.get("id")
        logger.info(f"Shopify products/update webhook received for id={shopify_id}")
        # Future: update local product record
    except Exception as e:
        logger.warning(f"Failed to parse products/update webhook: {e}")

    return {"ok": True}


@router.post("/shopify/products/delete")
async def product_deleted(
    request: Request,
    x_shopify_hmac_sha256: Optional[str] = Header(None),
):
    body = await request.body()
    if not _verify_webhook_hmac(body, x_shopify_hmac_sha256):
        raise HTTPException(status_code=401, detail="Invalid HMAC")

    try:
        data = json.loads(body)
        shopify_id = data.get("id")
        logger.info(f"Shopify products/delete webhook received for id={shopify_id}")
    except Exception as e:
        logger.warning(f"Failed to parse products/delete webhook: {e}")

    return {"ok": True}


@router.post("/shopify/orders/create")
async def order_created(
    request: Request,
    x_shopify_hmac_sha256: Optional[str] = Header(None),
):
    body = await request.body()
    if not _verify_webhook_hmac(body, x_shopify_hmac_sha256):
        raise HTTPException(status_code=401, detail="Invalid HMAC")

    try:
        data = json.loads(body)
        order_id = data.get("id")
        logger.info(f"Shopify orders/create webhook received for id={order_id}")
    except Exception as e:
        logger.warning(f"Failed to parse orders/create webhook: {e}")

    return {"ok": True}


# ---------------------------------------------------------------------------
# GDPR mandatory webhooks (required for Shopify App Store)
#
# These are signed with the app's CLIENT SECRET (not shopify_webhook_secret).
# Register all three URLs in the Shopify Partner Dashboard under
# App setup → GDPR mandatory webhooks.
#
# Shopify requirements:
#   - Respond with 200 within 5 seconds
#   - Process customers/redact and shop/redact within 30 days
#   - For customers/data_request: provide customer data (or confirm none held)
# ---------------------------------------------------------------------------

@router.post("/shopify/gdpr/customers/data_request")
async def gdpr_customers_data_request(
    request: Request,
    x_shopify_hmac_sha256: Optional[str] = Header(None),
):
    """
    Shopify sends this when a customer requests their data under GDPR/CCPA.
    ProductHub stores no customer PII — only merchant (shop owner) data.
    We log the request and acknowledge immediately.
    """
    body = await request.body()
    if not _verify_gdpr_hmac(body, x_shopify_hmac_sha256):
        raise HTTPException(status_code=401, detail="Invalid HMAC")

    try:
        data = json.loads(body)
        logger.info(
            f"GDPR customers/data_request: shop={data.get('shop_domain')} "
            f"customer_id={data.get('customer', {}).get('id')} — "
            "no customer PII stored in ProductHub"
        )
    except Exception as e:
        logger.warning(f"Failed to parse customers/data_request: {e}")

    return {"ok": True}


@router.post("/shopify/gdpr/customers/redact")
async def gdpr_customers_redact(
    request: Request,
    x_shopify_hmac_sha256: Optional[str] = Header(None),
):
    """
    Shopify sends this when a customer requests deletion of their data.
    ProductHub stores no customer PII — only merchant data keyed by shop domain.
    We log the request and acknowledge immediately.
    """
    body = await request.body()
    if not _verify_gdpr_hmac(body, x_shopify_hmac_sha256):
        raise HTTPException(status_code=401, detail="Invalid HMAC")

    try:
        data = json.loads(body)
        logger.info(
            f"GDPR customers/redact: shop={data.get('shop_domain')} "
            f"customer_id={data.get('customer', {}).get('id')} — "
            "no customer PII stored in ProductHub"
        )
    except Exception as e:
        logger.warning(f"Failed to parse customers/redact: {e}")

    return {"ok": True}


@router.post("/shopify/gdpr/shop/redact")
async def gdpr_shop_redact(
    request: Request,
    x_shopify_hmac_sha256: Optional[str] = Header(None),
):
    """
    Shopify sends this 48 hours after a merchant uninstalls the app.
    We must delete all data associated with the shop within 30 days.
    Queues a Celery task to cascade-delete the merchant's User and all owned records.
    """
    body = await request.body()
    if not _verify_gdpr_hmac(body, x_shopify_hmac_sha256):
        raise HTTPException(status_code=401, detail="Invalid HMAC")

    try:
        data = json.loads(body)
        shop_domain = data.get("shop_domain")
        shop_id = data.get("shop_id")

        if not shop_domain:
            logger.warning("GDPR shop/redact received without shop_domain")
            return {"ok": True}

        logger.info(f"GDPR shop/redact queued for shop={shop_domain} id={shop_id}")

        from app.workers.gdpr_tasks import redact_shop_data
        redact_shop_data.delay(shop_domain=shop_domain, shop_id=shop_id)

    except Exception as e:
        logger.error(f"Failed to queue shop/redact for processing: {e}")
        raise HTTPException(status_code=500, detail="Failed to queue shop redaction")

    return {"ok": True}
