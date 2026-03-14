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


def _verify_hmac(body: bytes, hmac_header: Optional[str]) -> bool:
    secret = getattr(settings, "shopify_webhook_secret", "")
    if not secret:
        return True  # not configured — skip verification
    if not hmac_header:
        return False
    digest = hmac.new(secret.encode(), body, hashlib.sha256).digest()
    computed = base64.b64encode(digest).decode()
    return hmac.compare_digest(computed, hmac_header)


@router.post("/shopify/products/update")
async def product_updated(
    request: Request,
    x_shopify_hmac_sha256: Optional[str] = Header(None),
):
    body = await request.body()
    if not _verify_hmac(body, x_shopify_hmac_sha256):
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
    if not _verify_hmac(body, x_shopify_hmac_sha256):
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
    if not _verify_hmac(body, x_shopify_hmac_sha256):
        raise HTTPException(status_code=401, detail="Invalid HMAC")

    try:
        data = json.loads(body)
        order_id = data.get("id")
        logger.info(f"Shopify orders/create webhook received for id={order_id}")
    except Exception as e:
        logger.warning(f"Failed to parse orders/create webhook: {e}")

    return {"ok": True}
