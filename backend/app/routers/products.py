from typing import Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models.product import Product
from app.models.user import User
from app.models.variant import ProductVariant
from app.models.image import ProductImage
from app.models.pricing import PriceHistory
from app.schemas.product import (
    ProductCreate, ProductUpdate, ProductOut, ProductListOut,
    ProductListResponse, BulkActionRequest, MergeProductsRequest,
    VariantCreate, VariantUpdate, VariantOut,
)

router = APIRouter(prefix="/api/v1/products", tags=["products"])


# ── Product list ───────────────────────────────────────────────────────────────

@router.get("/", response_model=ProductListResponse)
def list_products(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    status: Optional[str] = None,
    sync_status: Optional[str] = None,
    enrichment_status: Optional[str] = None,
    supplier_id: Optional[UUID] = None,
    search: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = db.query(Product).filter(Product.user_id == current_user.id)

    if status:
        q = q.filter(Product.status == status)
    if sync_status:
        q = q.filter(Product.sync_status == sync_status)
    if enrichment_status:
        q = q.filter(Product.enrichment_status == enrichment_status)
    if supplier_id:
        q = q.filter(Product.supplier_id == supplier_id)
    if search:
        q = q.filter(Product.title.ilike(f"%{search}%"))

    total = q.count()
    products = (
        q.order_by(Product.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    items = []
    for p in products:
        thumbnail = p.images[0].src if p.images else None
        items.append(
            ProductListOut(
                id=p.id,
                title=p.title,
                status=p.status,
                sync_status=p.sync_status,
                enrichment_status=p.enrichment_status,
                product_type=p.product_type,
                vendor=p.vendor,
                base_price=p.base_price,
                supplier_price=p.supplier_price,
                supplier_id=p.supplier_id,
                shopify_product_id=p.shopify_product_id,
                source_url=p.source_url,
                created_at=p.created_at,
                updated_at=p.updated_at,
                thumbnail=thumbnail,
                body_html=p.body_html,
                ai_description=p.ai_description,
            )
        )

    return ProductListResponse(items=items, total=total, page=page, page_size=page_size)


# ── Product CRUD ───────────────────────────────────────────────────────────────

@router.post("/", response_model=ProductOut, status_code=status.HTTP_201_CREATED)
def create_product(
    payload: ProductCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    product = Product(
        user_id=current_user.id,
        supplier_id=payload.supplier_id,
        title=payload.title,
        raw_title=payload.title,
        body_html=payload.body_html,
        vendor=payload.vendor,
        product_type=payload.product_type,
        handle=payload.handle,
        tags=payload.tags,
        cost_price=payload.cost_price,
        base_price=payload.base_price,
        compare_at_price=payload.compare_at_price,
        metafields=payload.metafields or {},
        source_type=payload.source_type,
        status="draft",
        sync_status="never_synced",
        enrichment_status="pending",
    )
    db.add(product)
    db.flush()

    # Create default variant if none provided
    if not payload.variants:
        variant = ProductVariant(
            product_id=product.id,
            title="Default Title",
            price=payload.base_price or 0,
            position=1,
        )
        db.add(variant)
    else:
        for i, v in enumerate(payload.variants, 1):
            variant = ProductVariant(product_id=product.id, position=i, **v.model_dump())
            db.add(variant)

    db.commit()
    db.refresh(product)
    return product


# ── Duplicate SKU detection ────────────────────────────────────────────────────

@router.get("/duplicate-skus")
def find_duplicate_skus(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Return groups of products that share the same variant SKU.
    Each group: {sku, products: [{id, title, status, thumbnail, supplier_id}]}
    """
    from sqlalchemy import func

    # Find SKUs shared across multiple products for this user
    sku_groups = (
        db.query(ProductVariant.sku, func.count(ProductVariant.product_id.distinct()).label("cnt"))
        .join(Product, Product.id == ProductVariant.product_id)
        .filter(
            Product.user_id == current_user.id,
            ProductVariant.sku.isnot(None),
            ProductVariant.sku != "",
        )
        .group_by(ProductVariant.sku)
        .having(func.count(ProductVariant.product_id.distinct()) > 1)
        .all()
    )

    if not sku_groups:
        return []

    result = []
    for row in sku_groups:
        sku = row.sku
        product_ids = (
            db.query(ProductVariant.product_id)
            .join(Product, Product.id == ProductVariant.product_id)
            .filter(
                Product.user_id == current_user.id,
                ProductVariant.sku == sku,
            )
            .distinct()
            .all()
        )
        pid_list = [r.product_id for r in product_ids]
        products = db.query(Product).filter(Product.id.in_(pid_list)).all()

        product_list = []
        for p in products:
            thumbnail = p.images[0].src if p.images else None
            product_list.append({
                "id": str(p.id),
                "title": p.title,
                "status": p.status,
                "sync_status": p.sync_status,
                "supplier_id": str(p.supplier_id) if p.supplier_id else None,
                "base_price": float(p.base_price) if p.base_price else None,
                "thumbnail": thumbnail,
            })

        result.append({"sku": sku, "products": product_list})

    return result


@router.get("/{product_id}", response_model=ProductOut)
def get_product(
    product_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    product = db.query(Product).filter(
        Product.id == product_id, Product.user_id == current_user.id
    ).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return product


@router.patch("/{product_id}", response_model=ProductOut)
def update_product(
    product_id: UUID,
    payload: ProductUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    product = db.query(Product).filter(
        Product.id == product_id, Product.user_id == current_user.id
    ).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    update_data = payload.model_dump(exclude_unset=True)

    # Handle AI field acceptance
    if update_data.pop("accept_ai_description", False) and product.ai_description:
        product.body_html = product.ai_description
    if update_data.pop("accept_ai_tags", False) and product.ai_tags:
        product.tags = product.ai_tags
    if update_data.pop("accept_ai_attributes", False) and product.ai_attributes:
        if not product.metafields:
            product.metafields = {}
        product.metafields.update(product.ai_attributes)

    for field, value in update_data.items():
        setattr(product, field, value)

    # If content changed and was synced, mark out of sync
    if product.sync_status == "synced" and any(
        f in update_data for f in ["title", "body_html", "tags", "vendor", "product_type"]
    ):
        product.sync_status = "out_of_sync"

    db.commit()
    db.refresh(product)
    return product


@router.delete("/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_product(
    product_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    product = db.query(Product).filter(
        Product.id == product_id, Product.user_id == current_user.id
    ).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    product.status = "archived"
    db.commit()


# ── Sync supplier prices ───────────────────────────────────────────────────────

@router.post("/sync-supplier-prices")
def sync_supplier_prices(
    supplier_id: Optional[UUID] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Queue price re-scrapes for all products with use_supplier_price=True."""
    from app.workers.pricing_tasks import sync_use_supplier_prices
    task = sync_use_supplier_prices.delay(str(supplier_id) if supplier_id else None)
    return {"task_id": task.id, "status": "queued"}


# ── Re-scrape product details ──────────────────────────────────────────────────

@router.post("/{product_id}/rescrape")
def rescrape_product(
    product_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Queue a detail scrape (description + images) for a single existing product."""
    product = db.query(Product).filter(
        Product.id == product_id,
        Product.user_id == current_user.id,
    ).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    if not product.source_url:
        raise HTTPException(status_code=400, detail="Product has no source URL to scrape")
    from app.workers.scrape_tasks import scrape_product_details
    task = scrape_product_details.delay(str(product_id))
    return {"task_id": task.id, "status": "queued"}


# ── Bulk actions ───────────────────────────────────────────────────────────────

@router.post("/bulk")
def bulk_action(
    payload: BulkActionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    products = db.query(Product).filter(
        Product.id.in_(payload.product_ids),
        Product.user_id == current_user.id,
    ).all()

    if payload.action == "approve":
        for p in products:
            if p.status in ("draft", "enriched"):
                p.status = "approved"
    elif payload.action == "archive":
        for p in products:
            p.status = "archived"
    elif payload.action == "tag" and payload.tag:
        for p in products:
            current_tags = p.tags or []
            if payload.tag not in current_tags:
                p.tags = current_tags + [payload.tag]
    elif payload.action == "enrich":
        from app.workers.enrichment_tasks import enrich_product
        task_ids = []
        for p in products:
            task = enrich_product.delay(str(p.id))
            task_ids.append(task.id)
        db.commit()
        return {"queued": len(products), "task_ids": task_ids}
    elif payload.action == "sync":
        from app.workers.sync_tasks import sync_product_to_shopify
        task_ids = []
        for p in products:
            task = sync_product_to_shopify.delay(str(p.id))
            task_ids.append(task.id)
        db.commit()
        return {"queued": len(products), "task_ids": task_ids}
    elif payload.action == "rescrape":
        from app.workers.scrape_tasks import scrape_product_details
        task_ids = []
        for p in products:
            if p.source_url:
                task = scrape_product_details.delay(str(p.id))
                task_ids.append(task.id)
        db.commit()
        return {"queued": len(task_ids), "task_ids": task_ids}
    elif payload.action == "delete":
        for p in products:
            p.status = "archived"

    db.commit()
    return {"updated": len(products)}


# ── Merge products ─────────────────────────────────────────────────────────────

@router.post("/merge")
def merge_products(
    payload: MergeProductsRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Merge one or more products (secondaries) into a primary product.
    - Images and non-duplicate variants from secondaries are re-parented to primary.
    - Tags are unioned.
    - Missing fields (description, supplier, source_url, vendor) are filled from secondaries.
    - Price history, alerts and schedules are reassigned to primary.
    - Secondary products are deleted.
    """
    from app.models.image import ProductImage
    from app.models.variant import ProductVariant
    from app.models.pricing import PriceHistory, PricingAlert, PricingSchedule

    all_ids = [payload.primary_id] + list(payload.secondary_ids)
    products = db.query(Product).filter(
        Product.id.in_(all_ids),
        Product.user_id == current_user.id,
    ).all()

    if len(products) != len(all_ids):
        raise HTTPException(status_code=404, detail="One or more products not found")

    primary = next((p for p in products if p.id == payload.primary_id), None)
    if not primary:
        raise HTTPException(status_code=404, detail="Primary product not found")

    secondary_ids = [p.id for p in products if p.id != payload.primary_id]
    if not secondary_ids:
        raise HTTPException(status_code=400, detail="No secondary products to merge")

    ov = payload.overrides
    secondaries = [p for p in products if p.id != payload.primary_id]

    # ── Images ──────────────────────────────────────────────────────────────────
    if ov and ov.image_srcs is not None:
        # Custom list: delete all existing images on primary, recreate from URL list
        db.query(ProductImage).filter(ProductImage.product_id == primary.id).delete()
        for i, src in enumerate(ov.image_srcs, 1):
            db.add(ProductImage(product_id=primary.id, src=src, position=i))
    else:
        # Capture keep-srcs before re-parenting if strategy is per-product
        keep_srcs: set[str] = set()
        if ov and (ov.images_strategy or "union").startswith("product:"):
            keep_pid = UUID(ov.images_strategy.split(":", 1)[1])
            keep_srcs = {img.src for img in db.query(ProductImage).filter(
                ProductImage.product_id == keep_pid).all()}

        # Re-parent unique images from secondaries to primary
        existing_srcs = {img.src for img in db.query(ProductImage).filter(
            ProductImage.product_id == primary.id).all()}
        for img in db.query(ProductImage).filter(ProductImage.product_id.in_(secondary_ids)).all():
            if img.src not in existing_srcs:
                img.product_id = primary.id
                existing_srcs.add(img.src)
            # duplicate images are left on secondary and cascade-deleted

        # If per-product strategy, drop images not from the keep-product
        if keep_srcs:
            for img in db.query(ProductImage).filter(ProductImage.product_id == primary.id).all():
                if img.src not in keep_srcs:
                    db.delete(img)

    # ── Variants: re-parent non-duplicate SKUs to primary ──────────────────────
    existing_skus = {v.sku for v in db.query(ProductVariant).filter(
        ProductVariant.product_id == primary.id).all() if v.sku}
    for v in db.query(ProductVariant).filter(ProductVariant.product_id.in_(secondary_ids)).all():
        if not v.sku or v.sku not in existing_skus:
            v.product_id = primary.id
            if v.sku:
                existing_skus.add(v.sku)
        # duplicate-sku variants are left on secondary and cascade-deleted

    db.flush()  # commit re-parenting before cascade delete kicks in

    # ── Price history / alerts / schedules: reassign all to primary ─────────────
    db.query(PriceHistory).filter(PriceHistory.product_id.in_(secondary_ids)).update(
        {"product_id": primary.id}, synchronize_session="fetch")
    db.query(PricingAlert).filter(PricingAlert.product_id.in_(secondary_ids)).update(
        {"product_id": primary.id}, synchronize_session="fetch")
    db.query(PricingSchedule).filter(PricingSchedule.product_id.in_(secondary_ids)).update(
        {"product_id": primary.id}, synchronize_session="fetch")

    # ── Scalar fields: apply overrides, else auto-fill from secondaries ──────────
    SCALAR_FIELDS = ["body_html", "supplier_id", "source_url", "vendor", "product_type",
                     "seo_title", "seo_description", "cost_price", "base_price", "compare_at_price"]
    for field in SCALAR_FIELDS:
        override_val = getattr(ov, field, None) if ov else None
        if override_val is not None:
            setattr(primary, field, override_val)
        else:
            for sec in secondaries:
                if not getattr(primary, field) and getattr(sec, field):
                    setattr(primary, field, getattr(sec, field))
                    break

    # Title override (always non-null on existing products, so only set if explicitly overridden)
    if ov and ov.title is not None:
        primary.title = ov.title

    # ── Tags ─────────────────────────────────────────────────────────────────────
    tags_strategy = (ov.tags_strategy if ov else None) or "union"
    if tags_strategy == "union":
        primary.tags = list({t for p in [primary] + secondaries for t in (p.tags or [])})
    elif tags_strategy.startswith("product:"):
        source_pid = UUID(tags_strategy.split(":", 1)[1])
        source = next((p for p in [primary] + secondaries if p.id == source_pid), None)
        primary.tags = list(source.tags or []) if source else (primary.tags or [])

    # ── Delete secondaries (cascades remaining orphan images/variants) ───────────
    for sec in secondaries:
        db.delete(sec)

    db.commit()
    return {"primary_id": str(primary.id), "merged": len(secondary_ids)}


# ── Variants ───────────────────────────────────────────────────────────────────

@router.get("/{product_id}/variants", response_model=list[VariantOut])
def list_variants(
    product_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return db.query(ProductVariant).filter(
        ProductVariant.product_id == product_id
    ).order_by(ProductVariant.position).all()


@router.post("/{product_id}/variants", response_model=VariantOut,
             status_code=status.HTTP_201_CREATED)
def create_variant(
    product_id: UUID,
    payload: VariantCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _get_product_or_404(product_id, current_user.id, db)
    variant = ProductVariant(product_id=product_id, **payload.model_dump())
    db.add(variant)
    db.commit()
    db.refresh(variant)
    return variant


@router.patch("/{product_id}/variants/{variant_id}", response_model=VariantOut)
def update_variant(
    product_id: UUID,
    variant_id: UUID,
    payload: VariantUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    variant = db.query(ProductVariant).filter(
        ProductVariant.id == variant_id, ProductVariant.product_id == product_id
    ).first()
    if not variant:
        raise HTTPException(status_code=404, detail="Variant not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(variant, field, value)
    db.commit()
    db.refresh(variant)
    return variant


@router.delete("/{product_id}/variants/{variant_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_variant(
    product_id: UUID,
    variant_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    variant = db.query(ProductVariant).filter(
        ProductVariant.id == variant_id, ProductVariant.product_id == product_id
    ).first()
    if not variant:
        raise HTTPException(status_code=404, detail="Variant not found")
    db.delete(variant)
    db.commit()


# ── Images ─────────────────────────────────────────────────────────────────────

@router.get("/{product_id}/images")
def list_images(
    product_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return db.query(ProductImage).filter(
        ProductImage.product_id == product_id
    ).order_by(ProductImage.position).all()


class AddImageByUrlRequest(BaseModel):
    src: str
    alt: Optional[str] = None


@router.post("/{product_id}/images", status_code=status.HTTP_201_CREATED)
def add_image_by_url(
    product_id: UUID,
    payload: AddImageByUrlRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Add an image reference by URL (no file upload — just stores the URL)."""
    product = _get_product_or_404(product_id, current_user.id, db)
    max_pos = db.query(func.max(ProductImage.position)).filter(
        ProductImage.product_id == product.id
    ).scalar() or 0
    img = ProductImage(
        product_id=product.id,
        src=payload.src,
        alt=payload.alt or product.title,
        position=max_pos + 1,
    )
    db.add(img)
    db.commit()
    db.refresh(img)
    return img


@router.delete("/{product_id}/images/{image_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_image(
    product_id: UUID,
    image_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    image = db.query(ProductImage).filter(
        ProductImage.id == image_id, ProductImage.product_id == product_id
    ).first()
    if not image:
        raise HTTPException(status_code=404, detail="Image not found")
    db.delete(image)
    db.commit()


# ── Price history ──────────────────────────────────────────────────────────────

@router.get("/{product_id}/price-history")
def price_history(
    product_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return db.query(PriceHistory).filter(
        PriceHistory.product_id == product_id
    ).order_by(PriceHistory.created_at.asc()).limit(100).all()


# ── Helper ─────────────────────────────────────────────────────────────────────

def _get_product_or_404(product_id: UUID, user_id, db: Session) -> Product:
    product = db.query(Product).filter(
        Product.id == product_id, Product.user_id == user_id
    ).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return product
