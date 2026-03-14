from uuid import UUID
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models.product import Product
from app.models.user import User

router = APIRouter(prefix="/api/v1/enrichment", tags=["enrichment"])

VALID_FIELDS = {"body_html", "tags", "title", "seo_title", "seo_description"}


class EnrichOptions(BaseModel):
    fields: Optional[list[str]] = None  # None = all fields
    template_id: Optional[str] = None


class BulkEnrichRequest(BaseModel):
    product_ids: list[UUID]
    fields: Optional[list[str]] = None
    template_id: Optional[str] = None


@router.post("/product/{product_id}")
def enrich_product(
    product_id: UUID,
    options: Optional[EnrichOptions] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    product = db.query(Product).filter(
        Product.id == product_id, Product.user_id == current_user.id
    ).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    product.enrichment_status = "pending"
    db.commit()

    fields = None
    template_id = None
    if options:
        fields = [f for f in (options.fields or []) if f in VALID_FIELDS] or None
        template_id = options.template_id

    from app.workers.enrichment_tasks import enrich_product as enrich_task
    task = enrich_task.delay(str(product_id), fields=fields, template_id=template_id)
    return {"task_id": task.id, "status": "queued"}


@router.post("/bulk")
def bulk_enrich(
    payload: BulkEnrichRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from app.workers.enrichment_tasks import enrich_product as enrich_task

    fields = [f for f in (payload.fields or []) if f in VALID_FIELDS] or None
    template_id = payload.template_id

    task_ids = []
    for pid in payload.product_ids:
        product = db.query(Product).filter(
            Product.id == pid, Product.user_id == current_user.id
        ).first()
        if product:
            product.enrichment_status = "pending"
            task = enrich_task.delay(str(pid), fields=fields, template_id=template_id)
            task_ids.append(task.id)
    db.commit()
    return {"queued": len(task_ids), "task_ids": task_ids}


@router.get("/status/{task_id}")
def enrichment_status(task_id: str):
    from app.workers.celery_app import celery_app
    result = celery_app.AsyncResult(task_id)
    return {
        "task_id": task_id,
        "status": result.status,
        "result": result.result if result.ready() else None,
    }
