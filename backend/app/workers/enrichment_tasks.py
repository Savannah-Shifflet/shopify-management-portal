import asyncio
import logging
from datetime import datetime
from uuid import UUID

from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


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

        result = asyncio.get_event_loop().run_until_complete(
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
            product.title = result["title"]  # direct write — user opted in
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

        if product.status == "draft":
            product.status = "enriched"

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
