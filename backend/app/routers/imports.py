import json
import os
import shutil
from uuid import UUID
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.config import settings
from app.dependencies import get_current_user
from app.models.import_job import ImportJob
from app.models.user import User
from app.schemas.import_job import ImportJobOut, ScrapeJobRequest, ColumnMapSuggestRequest, ColumnMapSuggestResponse

router = APIRouter(prefix="/api/v1/imports", tags=["imports"])


def _save_upload(file: UploadFile) -> str:
    os.makedirs(settings.storage_path, exist_ok=True)
    dest = os.path.join(settings.storage_path, file.filename)
    with open(dest, "wb") as f:
        shutil.copyfileobj(file.file, f)
    return dest


@router.post("/csv", response_model=ImportJobOut, status_code=status.HTTP_201_CREATED)
async def import_csv(
    file: UploadFile = File(...),
    supplier_id: Optional[str] = Form(None),
    column_mapping: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    path = _save_upload(file)
    mapping = json.loads(column_mapping) if column_mapping else None
    job = ImportJob(
        user_id=current_user.id,
        supplier_id=UUID(supplier_id) if supplier_id else None,
        job_type="csv" if file.filename.endswith(".csv") else "excel",
        status="queued",
        source_file=path,
        column_mapping=mapping,
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    from app.workers.import_tasks import process_csv_import
    task = process_csv_import.delay(str(job.id))
    job.celery_task_id = task.id
    db.commit()
    db.refresh(job)
    return job


@router.post("/pdf", response_model=ImportJobOut, status_code=status.HTTP_201_CREATED)
async def import_pdf(
    file: UploadFile = File(...),
    supplier_id: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    path = _save_upload(file)
    job = ImportJob(
        user_id=current_user.id,
        supplier_id=UUID(supplier_id) if supplier_id else None,
        job_type="pdf",
        status="queued",
        source_file=path,
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    from app.workers.import_tasks import process_pdf_import
    task = process_pdf_import.delay(str(job.id))
    job.celery_task_id = task.id
    db.commit()
    db.refresh(job)
    return job


@router.post("/scrape", response_model=ImportJobOut, status_code=status.HTTP_201_CREATED)
def start_scrape(
    payload: ScrapeJobRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not payload.supplier_id and not payload.url:
        raise HTTPException(status_code=400, detail="supplier_id or url required")
    job = ImportJob(
        user_id=current_user.id,
        supplier_id=payload.supplier_id,
        job_type="scrape",
        status="queued",
        source_url=payload.url,
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    from app.workers.scrape_tasks import scrape_supplier_catalog
    task = scrape_supplier_catalog.delay(
        str(payload.supplier_id) if payload.supplier_id else None,
        payload.url,
        str(job.id),
    )
    job.celery_task_id = task.id
    db.commit()
    db.refresh(job)
    return job


@router.post("/images", response_model=ImportJobOut, status_code=status.HTTP_201_CREATED)
async def import_images(
    files: list[UploadFile] = File(...),
    supplier_id: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    paths = [_save_upload(f) for f in files]
    job = ImportJob(
        user_id=current_user.id,
        supplier_id=UUID(supplier_id) if supplier_id else None,
        job_type="image_batch",
        status="queued",
        total_rows=len(paths),
        source_file=",".join(paths),
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    from app.workers.import_tasks import process_image_batch
    task = process_image_batch.delay(str(job.id), paths)
    job.celery_task_id = task.id
    db.commit()
    db.refresh(job)
    return job


@router.get("/jobs", response_model=list[ImportJobOut])
def list_jobs(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return db.query(ImportJob).filter(
        ImportJob.user_id == current_user.id
    ).order_by(ImportJob.created_at.desc()).limit(50).all()


@router.get("/jobs/{job_id}", response_model=ImportJobOut)
def get_job(
    job_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    job = db.query(ImportJob).filter(
        ImportJob.id == job_id, ImportJob.user_id == current_user.id
    ).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.post("/csv/column-map", response_model=ColumnMapSuggestResponse)
async def suggest_column_map(payload: ColumnMapSuggestRequest):
    from app.services.enrichment_service import suggest_csv_column_mapping
    result = await suggest_csv_column_mapping(payload.headers, payload.sample_rows)
    return result
