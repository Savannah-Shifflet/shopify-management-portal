from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User

router = APIRouter(prefix="/api/v1/settings", tags=["settings"])


class ShopifyConnectRequest(BaseModel):
    store_domain: str  # must be the .myshopify.com domain, e.g. mystore.myshopify.com


class ShopifyStatusResponse(BaseModel):
    store_domain: str | None
    connected: bool


@router.get("/shopify", response_model=ShopifyStatusResponse)
def get_shopify_settings(current_user: User = Depends(get_current_user)):
    return ShopifyStatusResponse(
        store_domain=current_user.shopify_store,
        connected=bool(current_user.shopify_store and current_user.shopify_token),
    )


@router.post("/shopify/connect", response_model=ShopifyStatusResponse)
def connect_shopify(
    payload: ShopifyConnectRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from app.utils.shopify_client import ShopifyClient

    store = payload.store_domain.strip().removeprefix("https://").removeprefix("http://").rstrip("/")
    if not store.endswith(".myshopify.com"):
        raise HTTPException(
            status_code=400,
            detail="Store domain must be your .myshopify.com domain (e.g. mystore.myshopify.com), not a custom domain."
        )

    try:
        token, expires_at = ShopifyClient.fetch_token(store)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Verify the token works
    client = ShopifyClient(store=store, token=token)
    result = client.test_connection()
    if not result.get("connected"):
        raise HTTPException(status_code=400, detail=result.get("error", "Token obtained but connection test failed"))

    current_user.shopify_store = store
    current_user.shopify_token = token
    current_user.shopify_token_expires_at = expires_at
    db.commit()

    return ShopifyStatusResponse(store_domain=current_user.shopify_store, connected=True)


@router.post("/shopify/disconnect")
def disconnect_shopify(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    current_user.shopify_store = None
    current_user.shopify_token = None
    current_user.shopify_token_expires_at = None
    db.commit()
    return {"disconnected": True}
