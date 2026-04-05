import uuid
from datetime import datetime
from sqlalchemy import Column, String, Text, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from app.database import Base

class SupplierEmail(Base):
    __tablename__ = "supplier_emails"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    supplier_id = Column(UUID(as_uuid=True), ForeignKey("suppliers.id"), nullable=False, index=True)
    direction = Column(String(20), nullable=False)  # OUTBOUND | INBOUND
    subject = Column(String(500))
    body = Column(Text)
    sent_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    attachments = Column(JSONB, default=list)  # [{name, path, mime_type}]
    message_id = Column(String(500), nullable=True, index=True)  # RFC 2822 Message-ID for dedup

    supplier = relationship("Supplier", back_populates="emails")
