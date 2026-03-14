import uuid
from datetime import datetime
from sqlalchemy import Column, String, Text, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.database import Base

class AuditLog(Base):
    __tablename__ = "audit_logs"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    action_type = Column(String(100), nullable=False)  # e.g. SUPPLIER_STATUS_CHANGE, EMAIL_SENT, PRODUCT_UPDATED
    entity_type = Column(String(100))  # Supplier, Product, ReorderLog, etc.
    entity_id = Column(String(255))
    description = Column(Text)

    user = relationship("User")
