import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.database import Base


class DetailScrapeLog(Base):
    __tablename__ = "detail_scrape_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    supplier_id = Column(UUID(as_uuid=True), ForeignKey("suppliers.id"), nullable=False)
    # "approval" = triggered when user approves catalog items
    # "rescrape" = triggered via Re-scrape Products button
    triggered_by = Column(String(50), nullable=False, default="rescrape")
    item_count = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)

    supplier = relationship("Supplier", back_populates="detail_scrape_logs")
