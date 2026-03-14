import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from app.database import Base


class ImportJob(Base):
    __tablename__ = "import_jobs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    supplier_id = Column(UUID(as_uuid=True), ForeignKey("suppliers.id"), nullable=True)

    job_type = Column(String(50), nullable=False)
    # csv | excel | pdf | scrape | image_batch

    status = Column(String(50), default="queued")
    # queued | running | done | failed | partial

    celery_task_id = Column(String(255))
    source_file = Column(Text)   # storage path for uploaded file
    source_url = Column(Text)    # for scrape jobs

    total_rows = Column(Integer, default=0)
    processed_rows = Column(Integer, default=0)
    success_rows = Column(Integer, default=0)
    error_rows = Column(Integer, default=0)
    error_details = Column(JSONB, default=list)  # [{row, error}, ...]
    column_mapping = Column(JSONB, default=dict)  # {"col_A": "title", ...}

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    started_at = Column(DateTime)
    completed_at = Column(DateTime)

    user = relationship("User", back_populates="import_jobs")
    supplier = relationship("Supplier")
