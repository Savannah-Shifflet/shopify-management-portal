from __future__ import annotations
from datetime import datetime
from typing import Optional
from uuid import UUID
from pydantic import BaseModel


class ImportJobOut(BaseModel):
    id: UUID
    user_id: UUID
    supplier_id: Optional[UUID] = None
    job_type: str
    status: str
    celery_task_id: Optional[str] = None
    source_file: Optional[str] = None
    source_url: Optional[str] = None
    total_rows: int
    processed_rows: int
    success_rows: int
    error_rows: int
    error_details: list[dict] = []
    column_mapping: Optional[dict] = None
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class ScrapeJobRequest(BaseModel):
    supplier_id: Optional[UUID] = None
    url: Optional[str] = None  # direct URL if no supplier configured


class ColumnMapSuggestRequest(BaseModel):
    headers: list[str]
    sample_rows: list[list[str]]  # first 3 rows


class ColumnMapSuggestResponse(BaseModel):
    mapping: dict[str, str]  # {"header_name": "product_field"}
    confidence: float
