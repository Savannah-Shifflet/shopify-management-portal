import logging
from datetime import datetime
from uuid import UUID

from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="app.workers.sync_tasks.sync_product_to_shopify", bind=True, max_retries=3)
def sync_product_to_shopify(self, product_id: str):
    """Full product sync to Shopify (create or update) via GraphQL."""
    from app.database import SessionLocal
    from app.models.product import Product
    from app.models.sync_log import ShopifySyncLog
    from app.models.user import User
    from app.utils.shopify_client import ShopifyClient

    db = SessionLocal()
    try:
        product = db.query(Product).filter(Product.id == UUID(product_id)).first()
        if not product:
            return {"error": "Product not found"}

        user = db.query(User).filter(User.id == product.user_id).first()
        client = ShopifyClient.from_user(user, db=db)

        # For updates, pre-fetch Shopify product to reconcile unmatched variant IDs.
        if product.shopify_product_id:
            try:
                shopify_current = client.get_product(product.shopify_product_id)
                sv_by_id = {sv["id"]: sv for sv in shopify_current.get("variants", [])}
                sv_by_sku = {sv["sku"]: sv for sv in shopify_current.get("variants", []) if sv.get("sku")}
                sv_by_pos = {i + 1: sv for i, sv in enumerate(shopify_current.get("variants", []))}
                changed = False
                for lv in product.variants:
                    if lv.shopify_variant_id and lv.shopify_variant_id in sv_by_id:
                        continue  # already matched
                    match = sv_by_sku.get(lv.sku or "") or sv_by_pos.get(lv.position or 1)
                    if match:
                        lv.shopify_variant_id = match["id"]
                        changed = True
                if changed:
                    db.flush()
            except Exception as prefetch_err:
                logger.warning(f"Pre-fetch for {product_id} failed (non-fatal): {prefetch_err}")

        payload = ShopifyClient.build_payload(product, product.variants, product.images)
        payload_hash = ShopifyClient.payload_hash(payload)

        # Skip if unchanged
        if product.shopify_hash == payload_hash and product.sync_status == "synced":
            return {"status": "skipped", "reason": "no changes"}

        if product.shopify_product_id:
            response = client.update_product(
                product.shopify_product_id, product, product.variants, product.images
            )
            operation = "update"
        else:
            response = client.create_product(product, product.variants, product.images)
            operation = "create"

        shopify_product = response.get("product", {})
        product.shopify_product_id = shopify_product.get("id")
        product.sync_status = "synced"
        product.synced_at = datetime.utcnow()
        product.shopify_hash = payload_hash

        if product.status == "approved":
            product.status = "synced"

        # Update shopify_variant_ids from response
        returned_variants = shopify_product.get("variants", [])
        for rv, lv in zip(returned_variants, product.variants):
            if rv.get("id"):
                lv.shopify_variant_id = rv["id"]

        log = ShopifySyncLog(
            user_id=product.user_id,
            product_id=product.id,
            operation=operation,
            status="success",
            shopify_id=product.shopify_product_id,
            request_payload=payload,
            response_body=shopify_product,
        )
        db.add(log)
        db.commit()

        return {"status": "success", "shopify_id": product.shopify_product_id}

    except Exception as exc:
        db.rollback()
        logger.error(f"Sync failed for {product_id}: {exc}")
        try:
            product = db.query(Product).filter(Product.id == UUID(product_id)).first()
            if product:
                product.sync_status = "failed"
                log = ShopifySyncLog(
                    user_id=product.user_id,
                    product_id=product.id,
                    operation="sync",
                    status="failed",
                    error_message=str(exc),
                )
                db.add(log)
                db.commit()
        except Exception:
            pass
        raise self.retry(exc=exc, countdown=2 ** self.request.retries * 60)
    finally:
        db.close()


@celery_app.task(name="app.workers.sync_tasks.sync_price_update_only")
def sync_price_update_only(product_id: str):
    """Lightweight: update only variant prices via Shopify GraphQL."""
    from app.database import SessionLocal
    from app.models.product import Product
    from app.models.user import User
    from app.utils.shopify_client import ShopifyClient

    db = SessionLocal()
    try:
        product = db.query(Product).filter(Product.id == UUID(product_id)).first()
        if not product or not product.shopify_product_id:
            return {"status": "skipped", "reason": "no shopify_product_id"}

        user = db.query(User).filter(User.id == product.user_id).first()
        client = ShopifyClient.from_user(user, db=db)
        variants = [
            {
                "shopify_variant_id": v.shopify_variant_id,
                "price": float(v.price),
                "compare_at_price": float(v.compare_at_price) if v.compare_at_price else None,
            }
            for v in product.variants
            if v.shopify_variant_id
        ]

        if not variants:
            return {"status": "skipped", "reason": "no synced variants"}

        result = client.update_variant_prices(product.shopify_product_id, variants)
        return {"status": "success", "result": result}

    except Exception as exc:
        logger.error(f"Price sync failed for {product_id}: {exc}")
        raise
    finally:
        db.close()


@celery_app.task(name="app.workers.sync_tasks.retry_failed_syncs")
def retry_failed_syncs():
    """Hourly: retry products stuck in failed sync state."""
    from app.database import SessionLocal
    from app.models.product import Product

    db = SessionLocal()
    try:
        products = db.query(Product).filter(Product.sync_status == "failed").limit(20).all()
        for p in products:
            sync_product_to_shopify.delay(str(p.id))
        return {"retried": len(products)}
    finally:
        db.close()
