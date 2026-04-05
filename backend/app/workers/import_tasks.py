import asyncio
import base64
import logging
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="app.workers.import_tasks.process_csv_import", bind=True)
def process_csv_import(self, job_id: str):
    """Parse CSV/Excel file and create product records."""
    import pandas as pd
    from app.database import SessionLocal
    from app.models.import_job import ImportJob
    from app.models.product import Product
    from app.models.variant import ProductVariant

    db = SessionLocal()
    try:
        job = db.query(ImportJob).filter(ImportJob.id == UUID(job_id)).first()
        if not job:
            return {"error": "Job not found"}

        job.status = "running"
        job.started_at = datetime.utcnow()
        db.commit()

        path = job.source_file
        if path.endswith((".xlsx", ".xls")):
            df = pd.read_excel(path)
        else:
            df = pd.read_csv(path)

        mapping = job.column_mapping or {}
        job.total_rows = len(df)
        db.commit()

        errors = []
        success = 0

        for idx, row in df.iterrows():
            try:
                # Apply column mapping or use column names directly
                def get_field(field_name):
                    for col, mapped in mapping.items():
                        if mapped == field_name and col in row:
                            return row[col]
                    # Try direct match
                    for col in df.columns:
                        if col.lower().strip() == field_name.lower():
                            return row[col]
                    return None

                title = get_field("title")
                if not title or str(title).strip() == "":
                    errors.append({"row": idx + 2, "error": "Missing title"})
                    continue

                sku = get_field("sku")
                # Upsert by SKU if supplier and SKU match
                product = None
                if sku and job.supplier_id:
                    from app.models.variant import ProductVariant as PV
                    existing_variant = db.query(PV).filter(PV.sku == str(sku)).first()
                    if existing_variant:
                        product = db.query(Product).filter(
                            Product.id == existing_variant.product_id
                        ).first()

                if not product:
                    product = Product(
                        user_id=job.user_id,
                        supplier_id=job.supplier_id,
                        title=str(title).strip(),
                        raw_title=str(title).strip(),
                        raw_description=str(get_field("description") or ""),
                        vendor=str(get_field("vendor") or ""),
                        product_type=str(get_field("product_type") or ""),
                        source_type=job.job_type,
                        status="draft",
                        sync_status="never_synced",
                    )
                    price_val = get_field("price")
                    if price_val:
                        try:
                            product.base_price = Decimal(str(price_val).replace("$", "").replace(",", ""))
                        except Exception:
                            pass
                    cost_val = get_field("cost")
                    if cost_val:
                        try:
                            product.cost_price = Decimal(str(cost_val).replace("$", "").replace(",", ""))
                        except Exception:
                            pass
                    db.add(product)
                    db.flush()

                    variant = ProductVariant(
                        product_id=product.id,
                        sku=str(sku) if sku else None,
                        barcode=str(get_field("barcode") or ""),
                        price=product.base_price or Decimal("0"),
                        cost=product.cost_price,
                        position=1,
                    )
                    db.add(variant)

                success += 1
                job.processed_rows = idx + 1
                job.success_rows = success
                if (idx + 1) % 100 == 0:
                    db.commit()

            except Exception as e:
                errors.append({"row": idx + 2, "error": str(e)})

        job.status = "done" if not errors else "partial"
        job.error_rows = len(errors)
        job.error_details = errors[:100]  # cap stored errors
        job.completed_at = datetime.utcnow()
        db.commit()

        return {"success": success, "errors": len(errors)}

    except Exception as exc:
        db.rollback()
        try:
            job = db.query(ImportJob).filter(ImportJob.id == UUID(job_id)).first()
            if job:
                job.status = "failed"
                job.error_details = [{"error": str(exc)}]
                db.commit()
        except Exception:
            pass
        logger.error(f"CSV import {job_id} failed: {exc}")
        raise
    finally:
        db.close()


@celery_app.task(name="app.workers.import_tasks.process_pdf_import", bind=True)
def process_pdf_import(self, job_id: str):
    """Parse PDF catalog using PyMuPDF + Claude extraction."""
    import fitz  # PyMuPDF
    from app.database import SessionLocal
    from app.models.import_job import ImportJob
    from app.models.product import Product
    from app.models.variant import ProductVariant
    from app.services.enrichment_service import extract_products_from_pdf_page

    db = SessionLocal()
    try:
        job = db.query(ImportJob).filter(ImportJob.id == UUID(job_id)).first()
        if not job:
            return {"error": "Job not found"}

        job.status = "running"
        job.started_at = datetime.utcnow()
        db.commit()

        doc = fitz.open(job.source_file)
        all_products = []
        chunk_size = 4  # process 4 pages at a time

        for start in range(0, len(doc), chunk_size):
            chunk_products = []
            for page_num in range(start, min(start + chunk_size, len(doc))):
                page = doc[page_num]
                text = page.get_text()
                # Render page as image for Claude vision
                mat = fitz.Matrix(1.5, 1.5)
                pix = page.get_pixmap(matrix=mat)
                img_bytes = pix.tobytes("jpeg")
                img_b64 = base64.standard_b64encode(img_bytes).decode()

                try:
                    products = asyncio.get_event_loop().run_until_complete(
                        extract_products_from_pdf_page(text, img_b64)
                    )
                    chunk_products.extend(products)
                except Exception as e:
                    logger.warning(f"Page {page_num} extraction failed: {e}")

            all_products.extend(chunk_products)

        doc.close()

        job.total_rows = len(all_products)
        db.commit()

        success = 0
        for prod_data in all_products:
            try:
                product = Product(
                    user_id=job.user_id,
                    supplier_id=job.supplier_id,
                    title=prod_data.get("title", "Unknown Product"),
                    raw_title=prod_data.get("title"),
                    raw_description=prod_data.get("description"),
                    vendor=prod_data.get("vendor"),
                    product_type=prod_data.get("product_type"),
                    source_type="pdf",
                    status="draft",
                    sync_status="never_synced",
                )
                if prod_data.get("price"):
                    try:
                        product.base_price = Decimal(str(prod_data["price"]).replace("$", "").replace(",", ""))
                    except Exception:
                        pass
                if prod_data.get("cost"):
                    try:
                        product.cost_price = Decimal(str(prod_data["cost"]).replace("$", "").replace(",", ""))
                    except Exception:
                        pass
                db.add(product)
                db.flush()

                variant = ProductVariant(
                    product_id=product.id,
                    sku=prod_data.get("sku"),
                    price=product.base_price or Decimal("0"),
                    cost=product.cost_price,
                    position=1,
                )
                db.add(variant)
                success += 1
            except Exception as e:
                logger.warning(f"Failed to create product from PDF data: {e}")

        job.success_rows = success
        job.processed_rows = len(all_products)
        job.status = "done"
        job.completed_at = datetime.utcnow()
        db.commit()

        return {"products_extracted": success}

    except Exception as exc:
        db.rollback()
        logger.error(f"PDF import {job_id} failed: {exc}")
        try:
            job = db.query(ImportJob).filter(ImportJob.id == UUID(job_id)).first()
            if job:
                job.status = "failed"
                job.error_details = [{"error": str(exc)}]
                db.commit()
        except Exception:
            pass
        raise
    finally:
        db.close()


@celery_app.task(name="app.workers.import_tasks.process_image_batch", bind=True)
def process_image_batch(self, job_id: str, image_paths: list[str]):
    """Process a batch of product images using Claude Vision."""
    import asyncio
    from app.database import SessionLocal
    from app.models.import_job import ImportJob
    from app.models.product import Product
    from app.models.image import ProductImage
    from app.models.variant import ProductVariant
    from app.services.enrichment_service import enrich_product_with_ai

    db = SessionLocal()
    try:
        job = db.query(ImportJob).filter(ImportJob.id == UUID(job_id)).first()
        if not job:
            return {"error": "Job not found"}

        job.status = "running"
        job.started_at = datetime.utcnow()
        db.commit()

        success = 0
        for path in image_paths:
            try:
                result = asyncio.get_event_loop().run_until_complete(
                    enrich_product_with_ai(
                        raw_title=None,
                        raw_description=None,
                        source_url=None,
                        product_type=None,
                        vendor=None,
                        supplier_name=None,
                        cost_price=None,
                        existing_tags=None,
                        image_paths=[path],
                    )
                )
                product = Product(
                    user_id=job.user_id,
                    supplier_id=job.supplier_id,
                    title=result.get("title", "Product from Image"),
                    raw_title=result.get("title"),
                    ai_description=result.get("body_html"),
                    ai_tags=result.get("tags"),
                    ai_attributes=result.get("attributes"),
                    seo_title=result.get("seo_title"),
                    seo_description=result.get("seo_description"),
                    source_type="image",
                    status="draft",
                    enrichment_status="done",
                    enrichment_model="claude-sonnet-4-6",
                    enrichment_at=datetime.utcnow(),
                    sync_status="never_synced",
                )
                db.add(product)
                db.flush()

                variant = ProductVariant(product_id=product.id, price=Decimal("0"), position=1)
                db.add(variant)

                image = ProductImage(product_id=product.id, src=path, position=1)
                db.add(image)

                success += 1
                job.processed_rows += 1
                job.success_rows = success
                db.commit()

            except Exception as e:
                logger.warning(f"Image batch: failed on {path}: {e}")
                job.error_rows += 1
                db.commit()

        job.status = "done"
        job.completed_at = datetime.utcnow()
        db.commit()

        return {"products_created": success}

    except Exception as exc:
        db.rollback()
        logger.error(f"Image batch {job_id} failed: {exc}")
        raise
    finally:
        db.close()
