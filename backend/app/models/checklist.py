import uuid
from datetime import datetime
from sqlalchemy import Column, String, Text, Boolean, Integer, ForeignKey, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.database import Base

class ChecklistTemplate(Base):
    __tablename__ = "checklist_templates"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    label = Column(String(255), nullable=False)
    order = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User")
    supplier_items = relationship("SupplierChecklistItem", back_populates="template_item", lazy="dynamic")

class SupplierChecklistItem(Base):
    __tablename__ = "supplier_checklist_items"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    supplier_id = Column(UUID(as_uuid=True), ForeignKey("suppliers.id"), nullable=False, index=True)
    template_item_id = Column(UUID(as_uuid=True), ForeignKey("checklist_templates.id"), nullable=True)
    label = Column(String(255), nullable=False)
    completed = Column(Boolean, default=False)
    notes = Column(Text)
    file_path = Column(Text)
    file_name = Column(String(255))
    created_at = Column(DateTime, default=datetime.utcnow)

    supplier = relationship("Supplier", back_populates="checklist_items")
    template_item = relationship("ChecklistTemplate", back_populates="supplier_items")
