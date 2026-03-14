import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from app.database import Base


class ScrapeSession(Base):
    __tablename__ = "scrape_sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    supplier_id = Column(UUID(as_uuid=True), ForeignKey("suppliers.id"), nullable=False)
    import_job_id = Column(UUID(as_uuid=True), ForeignKey("import_jobs.id"), nullable=True)
    url = Column(Text)
    status = Column(String(50), default="running")  # running | done | failed
    pages_scraped = Column(Integer, default=0)
    products_found = Column(Integer, default=0)
    raw_data = Column(JSONB, default=list)  # array of scraped product objects
    error_details = Column(Text)
    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime)

    supplier = relationship("Supplier", back_populates="scrape_sessions")
