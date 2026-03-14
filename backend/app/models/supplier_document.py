import uuid
from datetime import datetime
from sqlalchemy import Column, String, Text, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.database import Base

class SupplierDocument(Base):
    __tablename__ = "supplier_documents"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    supplier_id = Column(UUID(as_uuid=True), ForeignKey("suppliers.id"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    category = Column(String(100))  # Reseller Cert | Authorization Letter | W9 | MAP Agreement | Other
    file_path = Column(Text)        # local filesystem path
    file_name = Column(String(255))
    mime_type = Column(String(100))
    expires_at = Column(DateTime, nullable=True)
    uploaded_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    supplier = relationship("Supplier", back_populates="documents")
