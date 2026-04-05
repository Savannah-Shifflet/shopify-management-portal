import asyncio
import logging
from datetime import datetime
from uuid import UUID

from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)

# Default max concurrent Claude API calls in a batch.
# Free/low tier: keep at 3-5. Raise once you're on a higher Anthropic tier.
# Override via ENRICHMENT_CONCURRENCY env var or concurrency= kwarg on the task.
DEFAULT_CONCURRENCY = 5


@celery_app.task(name="app.workers.enrichment_tasks.enrich_product", bind=True, max_retries=3)
def enrich_product(self, product_id: str, fields: list | None = None, template_id: str | None = None):
    """Enrich a single product using Claude AI."""
    from app.database import SessionLocal
    from app.models.product import Product
    from app.models.supplier import Supplier
    from app.services.enrichment_service import enrich_product_with_ai

    db = SessionLocal()
    try:
        product = db.query(Product).filter(Product.id == UUID(product_id)).first()
        if not product:
            logger.error(f"Product {product_id} not found")
            return {"error": "Product not found"}

        product.enrichment_status = "running"
        db.commit()

        supplier = db.query(Supplier).filter(Supplier.id == product.supplier_id).first() if product.supplier_id else None

        image_paths = [img.src for img in product.images if img.src and not img.src.startswith("http")]

        template_sections = None
        if template_id:
            from app.models.description_template import DescriptionTemplate
            from uuid import UUID as UUIDType
            tmpl = db.query(DescriptionTemplate).filter(DescriptionTemplate.id == UUIDType(template_id)).first()
            if tmpl:
                template_sections = tmpl.sections or []

        result = asyncio.run(
            enrich_product_with_ai(
                raw_title=product.raw_title or product.title,
                raw_description=product.raw_description or product.body_html,
                source_url=product.source_url,
                product_type=product.product_type,
                vendor=product.vendor,
                supplier_name=supplier.name if supplier else None,
                cost_price=float(product.cost_price) if product.cost_price else None,
                existing_tags=product.tags,
                image_paths=image_paths,
                fields=fields,
                template_sections=template_sections,
            )
        )

        active = set(fields) if fields else {"body_html", "tags", "title", "seo_title", "seo_description"}
        if "body_html" in active and result.get("body_html"):
            product.ai_description = result["body_html"]
        if "tags" in active and result.get("tags"):
            product.ai_tags = result["tags"]
        if "title" in active and result.get("title"):
            product.ai_title = result["title"]  # staged — user must accept_ai_title to apply
        if "seo_title" in active and result.get("seo_title"):
            product.seo_title = result["seo_title"]
        if "seo_description" in active and result.get("seo_description"):
            product.seo_description = result["seo_description"]
        # Always store attributes if returned
        if result.get("attributes"):
            product.ai_attributes = result["attributes"]
        product.enrichment_status = "done"
        product.enrichment_model = "claude-sonnet-4-6"
        product.enrichment_at = datetime.utcnow()
        if template_id:
            product.applied_template_id = UUID(template_id)

        db.commit()
        return {"product_id": product_id, "status": "done"}

    except Exception as exc:
        db.rollback()
        logger.error(f"Enrichment failed for {product_id}: {exc}")
        try:
            product = db.query(Product).filter(Product.id == UUID(product_id)).first()
            if product:
                product.enrichment_status = "failed"
                db.commit()
        except Exception:
            pass
        raise self.retry(exc=exc, countdown=2 ** self.request.retries * 30)
    finally:
        db.close()


@celery_app.task(name="app.workers.enrichment_tasks.enrich_products_batch", bind=True, max_retries=0)
def enrich_products_batch(
    self,
    product_ids: list[str],
    fields: list | None = None,
    template_id: str | None = None,
    concurrency: int = DEFAULT_CONCURRENCY,
):
    """
    Enrich multiple products concurrently using asyncio.gather() + semaphore.

    All products are processed within a single asyncio event loop. The semaphore
    limits how many Claude API calls run at the same time (default 15).
    Each product gets its own DB session and updates its status independently —
    successes write immediately so the review page shows results as they arrive.

    Speed vs solo sequential:
      Solo:  N products × ~15s = hours
      Batch: ceil(N / concurrency) × ~15s — e.g. 800 products @ 15 = ~13 minutes
    """
    asyncio.run(_run_batch(product_ids, fields, template_id, concurrency))
    logger.info(f"Batch complete: {len(product_ids)} products, concurrency={concurrency}")


async def _run_batch(
    product_ids: list[str],
    fields: list | None,
    template_id: str | None,
    concurrency: int,
):
    """Async coordinator: loads template once, then fans out to per-product coroutines."""
    from app.database import SessionLocal
    from app.models.description_template import DescriptionTemplate
    from app.utils.claude_client import AsyncClaudeClient

    # Load template sections once — shared read, no write
    template_sections = None
    if template_id:
        db = SessionLocal()
        try:
            tmpl = db.query(DescriptionTemplate).filter(
                DescriptionTemplate.id == UUID(template_id)
            ).first()
            if tmpl:
                template_sections = tmpl.sections or []
        finally:
            db.close()

    # One shared async client — reuses the httpx connection pool across all calls
    client = AsyncClaudeClient()
    sem = asyncio.Semaphore(concurrency)

    tasks = [
        _enrich_one_async(pid, fields, template_id, template_sections, client, sem)
        for pid in product_ids
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    failed = sum(1 for r in results if isinstance(r, Exception))
    succeeded = len(results) - failed
    logger.info(f"Batch finished: {succeeded} succeeded, {failed} failed out of {len(product_ids)}")


async def _enrich_one_async(
    product_id: str,
    fields: list | None,
    template_id: str | None,
    template_sections: list | None,
    client,
    sem: asyncio.Semaphore,
):
    """Enrich a single product within the batch.

    Connection lifecycle is carefully scoped to avoid pool exhaustion:
    - asyncio.gather() launches ALL coroutines immediately, so if each held a
      DB connection while waiting at the semaphore we'd blow past the pool limit.
    - Instead: open DB → read data → close DB → wait for semaphore → call Claude
      → open DB → write results → close DB.
    - Max live connections at any moment = concurrency (semaphore limit), not N.
    """
    from app.database import SessionLocal
    from app.models.product import Product
    from app.models.supplier import Supplier
    from app.services.enrichment_service import enrich_product_with_ai_async

    # ── Phase 1: load product data then immediately release the connection ──
    raw_title = raw_description = source_url = product_type = vendor = None
    supplier_name = cost_price = None
    existing_tags = []
    image_paths = []

    db = SessionLocal()
    try:
        product = db.query(Product).filter(Product.id == UUID(product_id)).first()
        if not product:
            logger.warning(f"Batch: product {product_id} not found, skipping")
            return

        product.enrichment_status = "running"
        db.commit()

        supplier = (
            db.query(Supplier).filter(Supplier.id == product.supplier_id).first()
            if product.supplier_id else None
        )
        raw_title = product.raw_title or product.title
        raw_description = product.raw_description or product.body_html
        source_url = product.source_url
        product_type = product.product_type
        vendor = product.vendor
        supplier_name = supplier.name if supplier else None
        cost_price = float(product.cost_price) if product.cost_price else None
        existing_tags = product.tags
        image_paths = [img.src for img in product.images if img.src and not img.src.startswith("http")]
    except Exception as exc:
        db.rollback()
        logger.error(f"Batch: enrichment failed for {product_id}: {exc}")
        raise
    finally:
        db.close()  # ← connection returned to pool BEFORE we wait at the semaphore

    # ── Phase 2: call Claude (semaphore-limited, no DB connection held) ──
    result = None
    try:
        async with sem:
            result = await enrich_product_with_ai_async(
                raw_title=raw_title,
                raw_description=raw_description,
                source_url=source_url,
                product_type=product_type,
                vendor=vendor,
                supplier_name=supplier_name,
                cost_price=cost_price,
                existing_tags=existing_tags,
                image_paths=image_paths,
                fields=fields,
                template_sections=template_sections,
                client=client,
            )
    except Exception as exc:
        logger.error(f"Batch: enrichment failed for {product_id}: {exc}")
        db = SessionLocal()
        try:
            product = db.query(Product).filter(Product.id == UUID(product_id)).first()
            if product:
                product.enrichment_status = "failed"
                db.commit()
        except Exception:
            db.rollback()
        finally:
            db.close()
        raise

    # ── Phase 3: write results (fresh connection, returned immediately after) ──
    active = set(fields) if fields else {"body_html", "tags", "title", "seo_title", "seo_description"}
    db = SessionLocal()
    try:
        product = db.query(Product).filter(Product.id == UUID(product_id)).first()
        if not product:
            return
        if "body_html" in active and result.get("body_html"):
            product.ai_description = result["body_html"]
        if "tags" in active and result.get("tags"):
            product.ai_tags = result["tags"]
        if "title" in active and result.get("title"):
            product.ai_title = result["title"]  # staged — user must accept_ai_title to apply
        if "seo_title" in active and result.get("seo_title"):
            product.seo_title = result["seo_title"]
        if "seo_description" in active and result.get("seo_description"):
            product.seo_description = result["seo_description"]
        if result.get("attributes"):
            product.ai_attributes = result["attributes"]
        product.enrichment_status = "done"
        product.enrichment_model = "claude-sonnet-4-6"
        product.enrichment_at = datetime.utcnow()
        if template_id:
            product.applied_template_id = UUID(template_id)
        db.commit()
        logger.info(f"Batch: enriched {product_id}")
    except Exception as exc:
        db.rollback()
        logger.error(f"Batch: save failed for {product_id}: {exc}")
        # Best-effort: mark failed so the product doesn't stay stuck as 'running'
        db.close()
        try:
            db_fail = SessionLocal()
            try:
                p = db_fail.query(Product).filter(Product.id == UUID(product_id)).first()
                if p:
                    p.enrichment_status = "failed"
                    db_fail.commit()
            except Exception:
                db_fail.rollback()
            finally:
                db_fail.close()
        except Exception:
            pass
        raise
    finally:
        # close() is called explicitly above on the error path; guard against double-close
        try:
            db.close()
        except Exception:
            pass
