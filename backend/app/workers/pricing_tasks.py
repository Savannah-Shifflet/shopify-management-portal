import logging
from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="app.workers.pricing_tasks.check_all_supplier_prices")
def check_all_supplier_prices():
    """Check all suppliers due for a price check."""
    from app.database import SessionLocal
    from app.models.supplier import Supplier
    from sqlalchemy import or_

    db = SessionLocal()
    try:
        suppliers = db.query(Supplier).filter(
            Supplier.monitor_enabled == True,
            or_(
                Supplier.last_scraped_at == None,
                # Due check: compare in Python since interval arithmetic differs by DB
            ),
        ).all()

        now = datetime.utcnow()
        due = []
        for s in suppliers:
            if s.last_scraped_at is None:
                due.append(s)
            else:
                minutes_since = (now - s.last_scraped_at).total_seconds() / 60
                if minutes_since >= s.monitor_interval:
                    due.append(s)

        for supplier in due:
            check_supplier_price_changes.delay(str(supplier.id))

        return {"checked": len(due)}
    finally:
        db.close()


@celery_app.task(name="app.workers.pricing_tasks.check_supplier_price_changes", bind=True)
def check_supplier_price_changes(self, supplier_id: str):
    """Scrape supplier prices and detect changes."""
    from playwright.sync_api import sync_playwright
    from app.database import SessionLocal
    from app.models.supplier import Supplier
    from app.models.product import Product

    db = SessionLocal()
    try:
        supplier = db.query(Supplier).filter(Supplier.id == UUID(supplier_id)).first()
        if not supplier or not supplier.website_url:
            return {"error": "Supplier not found or no URL"}

        config = supplier.scrape_config or {}
        price_selector = config.get("price_selector", ".price, [data-price]")
        sku_selector = config.get("sku_selector", "[data-sku], .sku")
        product_selector = config.get("product_selector", "article, .product")

        scraped = []
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(supplier.website_url, timeout=15000)
            page.wait_for_load_state("networkidle", timeout=10000)

            items = page.query_selector_all(product_selector)
            for item in items[:100]:  # cap at 100 items for price-only check
                sku_el = item.query_selector(sku_selector)
                price_el = item.query_selector(price_selector)
                if price_el:
                    scraped.append({
                        "sku": sku_el.inner_text().strip() if sku_el else None,
                        "price": price_el.inner_text().strip(),
                    })
            browser.close()

        changes_detected = 0
        for item in scraped:
            if not item.get("price"):
                continue
            price_str = item["price"].replace("$", "").replace(",", "").strip()
            try:
                new_price = Decimal(price_str.split()[0])
            except Exception:
                continue

            # Find matching product by SKU
            products = []
            if item.get("sku"):
                from app.models.variant import ProductVariant
                variants = db.query(ProductVariant).filter(ProductVariant.sku == item["sku"]).all()
                products = [db.query(Product).filter(Product.id == v.product_id).first() for v in variants]

            for product in products:
                if product and product.supplier_id == supplier.id:
                    if _detect_price_change(product, new_price, supplier.id, db):
                        changes_detected += 1

        supplier.last_scraped_at = datetime.utcnow()
        db.commit()

        return {"scraped": len(scraped), "changes": changes_detected}

    except Exception as exc:
        logger.error(f"Price check failed for supplier {supplier_id}: {exc}")
        raise self.retry(exc=exc, countdown=300)
    finally:
        db.close()


def _detect_price_change(product, new_price: Decimal, supplier_id, db) -> bool:
    """Detect and handle a price change. Returns True if change was detected."""
    from app.models.pricing import PricingAlert
    from app.models.supplier import Supplier

    old_price = product.supplier_price
    if old_price is None or old_price == new_price:
        return False

    change_pct = abs((new_price - old_price) / old_price * 100) if old_price else Decimal("100")

    supplier = db.query(Supplier).filter(Supplier.id == supplier_id).first()
    auto_threshold = Decimal(supplier.auto_approve_threshold or "0") if supplier else Decimal("0")

    if change_pct <= auto_threshold:
        # Auto-apply
        product.supplier_price = new_price
        product.supplier_price_at = datetime.utcnow()
        if product.use_supplier_price:
            product.base_price = new_price
        from app.services.pricing_service import calculate_retail_price
        result = calculate_retail_price(new_price, supplier_id, product.product_type, product.tags or [], db)
        for variant in product.variants:
            variant.price = result["price"]

        alert = PricingAlert(
            user_id=product.user_id,
            product_id=product.id,
            supplier_id=supplier_id,
            old_price=old_price,
            new_price=new_price,
            change_pct=change_pct,
            status="auto_applied",
        )
        db.add(alert)
        from app.workers.sync_tasks import sync_price_update_only
        sync_price_update_only.delay(str(product.id))
    else:
        # Create pending alert
        alert = PricingAlert(
            user_id=product.user_id,
            product_id=product.id,
            supplier_id=supplier_id,
            old_price=old_price,
            new_price=new_price,
            change_pct=change_pct,
            status="pending",
        )
        db.add(alert)

    db.flush()
    return True


@celery_app.task(name="app.workers.pricing_tasks.apply_due_schedules")
def apply_due_schedules():
    """Activate pending schedules and revert completed ones."""
    from app.database import SessionLocal
    from app.models.pricing import PricingSchedule
    from app.models.product import Product
    from app.models.variant import ProductVariant

    db = SessionLocal()
    now = datetime.utcnow()
    try:
        # Activate pending schedules
        pending = db.query(PricingSchedule).filter(
            PricingSchedule.status == "pending",
            PricingSchedule.starts_at <= now,
        ).all()

        for schedule in pending:
            _apply_schedule(schedule, db)

        # Revert completed schedules
        active = db.query(PricingSchedule).filter(
            PricingSchedule.status == "active",
            PricingSchedule.ends_at != None,
            PricingSchedule.ends_at <= now,
        ).all()

        for schedule in active:
            _revert_schedule(schedule, db)

        db.commit()
        return {"activated": len(pending), "reverted": len(active)}
    finally:
        db.close()


def _apply_schedule(schedule, db):
    from app.models.product import Product
    from app.models.variant import ProductVariant
    from app.workers.sync_tasks import sync_price_update_only

    variants = _get_target_variants(schedule, db)
    for variant in variants:
        schedule.original_price = variant.price
        new_price = _calculate_schedule_price(variant.price, schedule)
        if schedule.price_action == "compare_at":
            variant.compare_at_price = variant.price
            variant.price = new_price
        else:
            variant.compare_at_price = variant.price
            variant.price = new_price

    schedule.status = "active"
    if schedule.product_id:
        sync_price_update_only.delay(str(schedule.product_id))


def _revert_schedule(schedule, db):
    from app.workers.sync_tasks import sync_price_update_only

    variants = _get_target_variants(schedule, db)
    for variant in variants:
        if schedule.original_price:
            variant.price = schedule.original_price
            variant.compare_at_price = None

    schedule.status = "completed"
    if schedule.product_id:
        sync_price_update_only.delay(str(schedule.product_id))


def _get_target_variants(schedule, db):
    from app.models.variant import ProductVariant
    from app.models.product import Product

    if schedule.variant_id:
        v = db.query(ProductVariant).filter(ProductVariant.id == schedule.variant_id).first()
        return [v] if v else []
    if schedule.product_id:
        return db.query(ProductVariant).filter(ProductVariant.product_id == schedule.product_id).all()
    return []


def _calculate_schedule_price(original: Decimal, schedule) -> Decimal:
    val = Decimal(str(schedule.price_value))
    if schedule.price_action == "set":
        return val
    if schedule.price_action == "percent_off":
        return original * (1 - val / 100)
    if schedule.price_action == "fixed_off":
        return max(original - val, Decimal("0"))
    return original


@celery_app.task(name="app.workers.pricing_tasks.sync_use_supplier_prices")
def sync_use_supplier_prices(supplier_id: Optional[str] = None):
    """Queue individual price-sync tasks for all products tracking supplier prices."""
    from app.database import SessionLocal
    from app.models.product import Product

    db = SessionLocal()
    try:
        q = db.query(Product).filter(
            Product.use_supplier_price == True,
            Product.source_url != None,
        )
        if supplier_id:
            q = q.filter(Product.supplier_id == UUID(supplier_id))
        products = q.all()
        for product in products:
            sync_single_supplier_price.delay(str(product.id))
        return {"queued": len(products)}
    finally:
        db.close()


@celery_app.task(name="app.workers.pricing_tasks.sync_single_supplier_price", bind=True, max_retries=2)
def sync_single_supplier_price(self, product_id: str):
    """Scrape the product's source URL for its current price and update base_price."""
    from playwright.sync_api import sync_playwright
    from app.database import SessionLocal
    from app.models.product import Product

    db = SessionLocal()
    try:
        product = db.query(Product).filter(Product.id == UUID(product_id)).first()
        if not product or not product.source_url or not product.use_supplier_price:
            return {"skipped": True}

        config = {}
        if product.supplier_id:
            from app.models.supplier import Supplier
            supplier = db.query(Supplier).filter(Supplier.id == product.supplier_id).first()
            if supplier:
                config = supplier.scrape_config or {}

        price_selector = config.get(
            "price_selector",
            "[itemprop='price'], .product__price, .price, .product-price, [data-price]",
        )

        new_price = None
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(user_agent="Mozilla/5.0 (compatible; ProductBot/1.0)")
            page.goto(product.source_url, wait_until="domcontentloaded", timeout=20000)
            try:
                page.wait_for_load_state("networkidle", timeout=5000)
            except Exception:
                pass

            price_el = page.query_selector(price_selector)
            if price_el:
                raw = price_el.get_attribute("content") or price_el.inner_text()
                price_str = raw.replace("$", "").replace(",", "").strip()
                try:
                    new_price = Decimal(price_str.split()[0])
                except Exception:
                    pass
            browser.close()

        if new_price is None:
            return {"updated": False, "reason": "price not found"}

        changed = product.supplier_price != new_price
        product.supplier_price = new_price
        product.supplier_price_at = datetime.utcnow()
        product.base_price = new_price  # use_supplier_price=True means base follows supplier
        db.commit()
        return {"updated": True, "changed": changed, "price": str(new_price)}

    except Exception as exc:
        db.rollback()
        logger.error(f"sync_single_supplier_price failed for {product_id}: {exc}")
        raise self.retry(exc=exc, countdown=60)
    finally:
        db.close()
