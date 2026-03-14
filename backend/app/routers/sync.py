from typing import Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database import get_db
from app.dependencies import get_current_user
from app.models.product import Product
from app.models.variant import ProductVariant
from app.models.image import ProductImage
from app.models.sync_log import ShopifySyncLog
from app.models.user import User
from app.schemas.sync import SyncRequest, SyncLogOut, SyncStatusResponse

router = APIRouter(prefix="/api/v1/sync", tags=["sync"])


@router.get("/status", response_model=SyncStatusResponse)
def sync_status(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    def count(s):
        return db.query(func.count(Product.id)).filter(
            Product.user_id == current_user.id, Product.sync_status == s
        ).scalar()

    connected = bool(current_user.shopify_store and current_user.shopify_token)

    return SyncStatusResponse(
        never_synced=count("never_synced"),
        pending=count("pending"),
        synced=count("synced"),
        out_of_sync=count("out_of_sync"),
        failed=count("failed"),
        shopify_connected=connected,
    )


@router.post("/product/{product_id}")
def sync_single(
    product_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from app.workers.sync_tasks import sync_product_to_shopify
    product = db.query(Product).filter(
        Product.id == product_id, Product.user_id == current_user.id
    ).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    product.sync_status = "pending"
    db.commit()
    task = sync_product_to_shopify.delay(str(product_id))
    return {"task_id": task.id, "status": "queued"}


@router.post("/products")
def sync_selected(
    payload: SyncRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from app.workers.sync_tasks import sync_product_to_shopify
    task_ids = []
    for pid in payload.product_ids:
        product = db.query(Product).filter(
            Product.id == pid, Product.user_id == current_user.id
        ).first()
        if product:
            product.sync_status = "pending"
            task = sync_product_to_shopify.delay(str(pid))
            task_ids.append(task.id)
    db.commit()
    return {"queued": len(task_ids), "task_ids": task_ids}


@router.post("/all")
def sync_all(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from app.workers.sync_tasks import sync_product_to_shopify
    products = db.query(Product).filter(
        Product.user_id == current_user.id,
        Product.status == "approved",
        Product.sync_status.in_(["never_synced", "out_of_sync", "failed"]),
    ).all()
    task_ids = []
    for p in products:
        p.sync_status = "pending"
        task = sync_product_to_shopify.delay(str(p.id))
        task_ids.append(task.id)
    db.commit()
    return {"queued": len(task_ids), "task_ids": task_ids}


@router.get("/log", response_model=list[SyncLogOut])
def sync_log(
    product_id: Optional[UUID] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = db.query(ShopifySyncLog).filter(ShopifySyncLog.user_id == current_user.id)
    if product_id:
        q = q.filter(ShopifySyncLog.product_id == product_id)
    return (
        q.order_by(ShopifySyncLog.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )


@router.get("/shopify/connection")
def test_connection(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from app.utils.shopify_client import ShopifyClient
    try:
        client = ShopifyClient.from_user(current_user, db=db)
    except RuntimeError as e:
        return {"connected": False, "error": str(e)}
    return client.test_connection()


def _normalize_weight_kg(weight, unit: str) -> float | None:
    """Convert Shopify variant weight to kg (our storage unit)."""
    if weight is None:
        return None
    w = float(weight)
    unit = (unit or "kg").lower()
    if unit == "g":
        return round(w / 1000, 3)
    if unit == "lb":
        return round(w * 0.453592, 3)
    if unit == "oz":
        return round(w * 0.0283495, 3)
    return round(w, 3)  # already kg


@router.post("/shopify/pull")
def pull_from_shopify(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Import existing products from Shopify into the local DB (matched by SKU or title)."""
    from app.utils.shopify_client import ShopifyClient
    try:
        client = ShopifyClient.from_user(current_user, db=db)
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))

    shopify_products = client.get_all_products()
    created = 0
    matched = 0

    for sp in shopify_products:
        shopify_id = sp.get("id")
        title = sp.get("title", "")
        variants = sp.get("variants", [])

        # Try to match by shopify_product_id first, then by SKU
        existing = db.query(Product).filter(
            Product.user_id == current_user.id,
            Product.shopify_product_id == shopify_id,
        ).first()

        if not existing and variants:
            # Try matching by SKU from first variant
            sku = variants[0].get("sku", "")
            if sku:
                local_variant = db.query(ProductVariant).filter(
                    ProductVariant.sku == sku
                ).join(Product).filter(Product.user_id == current_user.id).first()
                if local_variant:
                    existing = local_variant.product

        # Parse tags — GraphQL returns a list; join to comma-string for storage
        raw_tags = sp.get("tags", []) or []
        if isinstance(raw_tags, str):
            raw_tags = [t.strip() for t in raw_tags.split(",") if t.strip()]
        tags_list = raw_tags

        # Parse options — [{name, position}]
        raw_options = sp.get("options", [])
        # Skip the default "Title" option that Shopify adds to simple products
        options_list = [
            {"name": o.get("name"), "position": o.get("position", i + 1)}
            for i, o in enumerate(raw_options)
            if o.get("name") and o.get("name") != "Title"
        ]

        if existing:
            # Update shopify_product_id and sync status
            existing.shopify_product_id = shopify_id
            existing.sync_status = "synced"
            existing.title = title
            existing.body_html = sp.get("body_html") or existing.body_html
            existing.vendor = sp.get("vendor") or existing.vendor
            existing.product_type = sp.get("product_type") or existing.product_type
            existing.handle = sp.get("handle") or existing.handle
            if tags_list:
                existing.tags = tags_list
            if options_list:
                existing.options = options_list
            # Update variant shopify IDs
            for sv in variants:
                sv_sku = sv.get("sku", "")
                local_v = db.query(ProductVariant).filter(
                    ProductVariant.product_id == existing.id,
                    ProductVariant.sku == sv_sku,
                ).first() if sv_sku else None
                if local_v:
                    local_v.shopify_variant_id = sv.get("id")
                    local_v.price = sv.get("price") or local_v.price
                    local_v.compare_at_price = sv.get("compare_at_price") or local_v.compare_at_price
                    local_v.inventory_quantity = sv.get("inventory_quantity", local_v.inventory_quantity)
                    local_v.barcode = sv.get("barcode") or local_v.barcode
                    local_v.option1 = sv.get("option1") or local_v.option1
                    local_v.option2 = sv.get("option2") or local_v.option2
                    local_v.option3 = sv.get("option3") or local_v.option3
                    norm_w = _normalize_weight_kg(sv.get("weight"), sv.get("weight_unit"))
                    if norm_w is not None:
                        local_v.weight = norm_w
                        local_v.weight_unit = "kg"
                    local_v.inventory_policy = sv.get("inventory_policy") or local_v.inventory_policy
                    local_v.inventory_management = sv.get("inventory_management") or local_v.inventory_management
            # Upsert images: match by shopify_image_id (primary) or base src (fallback)
            existing_imgs = db.query(ProductImage).filter(
                ProductImage.product_id == existing.id).all()
            existing_by_shopify_id = {
                img.shopify_image_id: img for img in existing_imgs if img.shopify_image_id
            }
            # Base-URL fallback: strip query string for comparison (CDN ?v= changes)
            existing_by_base_src = {
                img.src.split("?")[0]: img for img in existing_imgs
            }
            max_pos = max((img.position or 0 for img in existing_imgs), default=0)
            new_pos = max_pos
            for img in sp.get("images", []):
                img_id = img.get("id")
                src = img.get("src") or ""
                if not src:
                    continue
                base_src = src.split("?")[0]
                if img_id and img_id in existing_by_shopify_id:
                    # Known image — keep shopify_image_id current and update src
                    existing_by_shopify_id[img_id].src = src
                elif base_src in existing_by_base_src:
                    # Same file, different CDN version — update src and store shopify_image_id
                    existing_by_base_src[base_src].src = src
                    if img_id:
                        existing_by_base_src[base_src].shopify_image_id = img_id
                elif img_id:
                    # Genuinely new image
                    new_pos += 1
                    db.add(ProductImage(
                        product_id=existing.id,
                        shopify_image_id=img_id,
                        src=src,
                        alt=img.get("alt") or title,
                        position=new_pos,
                    ))
            matched += 1
        else:
            # Create new product from Shopify data
            product = Product(
                user_id=current_user.id,
                shopify_product_id=shopify_id,
                title=title,
                raw_title=title,
                body_html=sp.get("body_html") or "",
                vendor=sp.get("vendor") or "",
                product_type=sp.get("product_type") or "",
                handle=sp.get("handle") or "",
                tags=tags_list or None,
                options=options_list or None,
                status="synced",
                sync_status="synced",
                enrichment_status="pending",
                source_type="shopify_pull",
            )
            db.add(product)
            db.flush()

            for i, sv in enumerate(variants, 1):
                v = ProductVariant(
                    product_id=product.id,
                    shopify_variant_id=sv.get("id"),
                    sku=sv.get("sku") or "",
                    price=sv.get("price") or "0",
                    compare_at_price=sv.get("compare_at_price"),
                    inventory_quantity=sv.get("inventory_quantity", 0),
                    inventory_policy=sv.get("inventory_policy") or "deny",
                    inventory_management=sv.get("inventory_management"),
                    barcode=sv.get("barcode"),
                    option1=sv.get("option1"),
                    option2=sv.get("option2"),
                    option3=sv.get("option3"),
                    weight=_normalize_weight_kg(sv.get("weight"), sv.get("weight_unit")),
                    weight_unit="kg",
                    position=i,
                    title=sv.get("title") or "Default Title",
                )
                db.add(v)

            for i, img in enumerate(sp.get("images", []), 1):
                src = img.get("src") or ""
                if src:
                    db.add(ProductImage(
                        product_id=product.id,
                        shopify_image_id=img.get("id"),
                        src=src,
                        alt=img.get("alt") or title,
                        position=i,
                    ))

            created += 1

    db.commit()
    return {"pulled": len(shopify_products), "created": created, "matched": matched}
