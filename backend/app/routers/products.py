import logging
from typing import Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
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

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/products", tags=["products"])


# ── Product list ───────────────────────────────────────────────────────────────

@router.get("/", response_model=ProductListResponse)
def list_products(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=10000),
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

    # Fetch store settings once for low_stock_threshold
    from app.models.store_settings import StoreSettings
    store_settings = db.query(StoreSettings).filter(
        StoreSettings.user_id == current_user.id
    ).first()
    low_stock_threshold = (store_settings.low_stock_threshold if store_settings and store_settings.low_stock_threshold is not None else 5)

    items = []
    for p in products:
        thumbnail = p.images[0].src if p.images else None

        # US-203: margin calculation
        margin_pct = None
        if p.cost_price and p.base_price and p.base_price > 0:
            margin_pct = float((p.base_price - p.cost_price) / p.base_price * 100)

        # US-301: low stock flag (sum across variants)
        is_low_stock = None
        if p.variants:
            total_inventory = sum(v.inventory_quantity for v in p.variants)
            is_low_stock = total_inventory <= low_stock_threshold

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
                margin_pct=margin_pct,
                is_low_stock=is_low_stock,
                applied_template_id=p.applied_template_id,
            )
        )

    import math
    pages = max(1, math.ceil(total / page_size))
    return ProductListResponse(items=items, total=total, page=page, page_size=page_size, pages=pages)


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
    response: Response,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    product = db.query(Product).filter(
        Product.id == product_id, Product.user_id == current_user.id
    ).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    update_data = payload.model_dump(exclude_unset=True)

    # Capture price snapshots before any mutation so we can diff after
    _price_snapshot = {
        "base_price": product.base_price,
        "cost_price": product.cost_price,
        "supplier_price": product.supplier_price,
    }

    # Apply AI field acceptance (universal utility — handles all accept_ai_* flags)
    from app.services.ai_acceptance import apply_ai_acceptance, SYNC_TRIGGER_FIELDS
    ai_changed = apply_ai_acceptance(product, update_data)

    for field, value in update_data.items():
        setattr(product, field, value)

    # If content changed (directly or via AI acceptance) and was synced, mark out of sync
    direct_content_change = any(f in update_data for f in SYNC_TRIGGER_FIELDS | {"vendor", "product_type"})
    if product.sync_status == "synced" and (direct_content_change or ai_changed & SYNC_TRIGGER_FIELDS):
        product.sync_status = "out_of_sync"

    # Sync variant prices when base_price is set while supplier price tracking is on,
    # or when tracking is first enabled (so variants immediately reflect the new price).
    if (
        product.use_supplier_price
        and product.base_price
        and ("base_price" in update_data or "use_supplier_price" in update_data)
    ):
        from app.models.variant import ProductVariant as _PV
        if product.supplier_id:
            from app.services.pricing_service import calculate_retail_price
            try:
                result = calculate_retail_price(
                    product.base_price, product.supplier_id,
                    product.product_type, product.tags or [], db,
                )
                for v in product.variants:
                    v.price = result["price"]
            except Exception:
                for v in product.variants:
                    v.price = product.base_price
        else:
            for v in product.variants:
                v.price = product.base_price

    # US-202: MAP enforcement
    price_fields_updated = any(f in update_data for f in ("base_price", "compare_at_price"))
    if price_fields_updated and product.map_price is not None:
        new_base = product.base_price
        new_compare = product.compare_at_price
        map_price = product.map_price
        map_violated = (
            (new_base is not None and new_base < map_price) or
            (new_compare is not None and new_compare < map_price)
        )
        if map_violated:
            # Check store settings for hard block
            from app.models.store_settings import StoreSettings
            from app.models.audit_log import AuditLog
            from datetime import datetime as _dt

            store = db.query(StoreSettings).filter(
                StoreSettings.user_id == current_user.id
            ).first()

            # Log MAP violation to audit_log
            try:
                violation_log = AuditLog(
                    user_id=current_user.id,
                    action_type="map_violation",
                    entity_type="Product",
                    entity_id=str(product_id),
                    description=(
                        f"MAP violation: base_price={new_base}, compare_at_price={new_compare}, "
                        f"map_price={map_price}"
                    ),
                    timestamp=_dt.utcnow(),
                )
                db.add(violation_log)
            except Exception:
                logger.warning("Failed to log MAP violation to audit_log", exc_info=True)

            if store and store.map_hard_block:
                db.rollback()
                raise HTTPException(status_code=422, detail="Price is below MAP")

            # Soft warning: save but set header
            response.headers["X-MAP-Warning"] = "true"

    # Record price history for any price fields that changed
    _price_fields_to_track = {
        "base_price": ("retail", None),
        "cost_price": ("cost", None),
        "supplier_price": ("supplier", product.supplier_id),
    }
    for field, (price_type, supplier_id) in _price_fields_to_track.items():
        if field in update_data:
            old_val = _price_snapshot[field]
            new_val = getattr(product, field)
            if old_val != new_val and new_val is not None:
                from app.services.pricing_service import record_price_history
                record_price_history(
                    db, product.id, old_val, new_val,
                    source="manual", price_type=price_type,
                    supplier_id=supplier_id,
                )

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
            if p.status != "archived":
                p.status = "active"
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
            p.enrichment_status = "pending"
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

    # ── Shopify product ID reconciliation ────────────────────────────────────────
    # Collect secondary shopify IDs before they're cascade-deleted
    orphaned_shopify_ids: list[int] = []
    for sec in secondaries:
        if not sec.shopify_product_id:
            continue
        if not primary.shopify_product_id:
            # Primary has no Shopify link — inherit secondary's so sync updates the
            # existing product and pull-from-Shopify matches by ID (no re-import).
            primary.shopify_product_id = sec.shopify_product_id
            primary.shopify_hash = None  # force re-sync with merged content
        else:
            # Both have Shopify products — queue deletion of the orphaned secondary
            # so pull-from-Shopify doesn't re-create it as a duplicate.
            orphaned_shopify_ids.append(sec.shopify_product_id)

    # Mark primary out-of-sync (content changed via merge) and clear hash so
    # sync_tasks doesn't skip it due to a stale matching hash.
    primary.shopify_hash = None
    if primary.sync_status == "synced":
        primary.sync_status = "out_of_sync"

    # ── Delete secondaries (cascades remaining orphan images/variants) ───────────
    for sec in secondaries:
        db.delete(sec)

    db.commit()

    # Queue Shopify deletions after commit (IDs are stable, secondaries gone locally)
    if orphaned_shopify_ids:
        from app.workers.sync_tasks import delete_shopify_product
        for shopify_id in orphaned_shopify_ids:
            delete_shopify_product.delay(str(primary.user_id), shopify_id)

    return {"primary_id": str(primary.id), "merged": len(secondary_ids)}


# ── Variants ───────────────────────────────────────────────────────────────────

@router.get("/{product_id}/variants", response_model=list[VariantOut])
def list_variants(
    product_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _get_product_or_404(product_id, current_user.id, db)
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
    product = _get_product_or_404(product_id, current_user.id, db)
    variant = db.query(ProductVariant).filter(
        ProductVariant.id == variant_id, ProductVariant.product_id == product_id
    ).first()
    if not variant:
        raise HTTPException(status_code=404, detail="Variant not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(variant, field, value)
    if product.sync_status == "synced":
        product.sync_status = "out_of_sync"
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
    _get_product_or_404(product_id, current_user.id, db)
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
    _get_product_or_404(product_id, current_user.id, db)
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
    product = _get_product_or_404(product_id, current_user.id, db)
    image = db.query(ProductImage).filter(
        ProductImage.id == image_id, ProductImage.product_id == product_id
    ).first()
    if not image:
        raise HTTPException(status_code=404, detail="Image not found")

    shopify_image_id = image.shopify_image_id
    db.delete(image)

    # If the image was synced to Shopify, delete it there immediately
    if shopify_image_id and product.shopify_product_id:
        try:
            from app.utils.shopify_client import ShopifyClient
            client = ShopifyClient.from_user(current_user, db=db)
            client.delete_product_image(shopify_image_id)
        except Exception as e:
            # Shopify deletion failed — mark product out of sync so it gets reconciled on next sync
            import logging
            logging.getLogger(__name__).warning(f"Shopify image delete failed (marking out_of_sync): {e}")
            product.sync_status = "out_of_sync"

    db.commit()


# ── Price history ──────────────────────────────────────────────────────────────

@router.get("/{product_id}/price-history")
def price_history(
    product_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _get_product_or_404(product_id, current_user.id, db)
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
