import uuid
from datetime import datetime
from sqlalchemy import Column, String, Text, DateTime, ForeignKey, Date
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from app.database import Base

class ReorderLog(Base):
    __tablename__ = "reorder_logs"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    supplier_id = Column(UUID(as_uuid=True), ForeignKey("suppliers.id"), nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    po_number = Column(String(100))
    order_date = Column(Date)
    expected_delivery = Column(Date)
    status = Column(String(50), default="Pending")  # Pending|Shipped|Received|Cancelled
    line_items = Column(JSONB, default=list)  # [{product_id, product_title, qty, unit_cost}]
    notes = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    supplier = relationship("Supplier", back_populates="reorders")
    user = relationship("User")
