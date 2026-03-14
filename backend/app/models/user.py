import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False, index=True)
    name = Column(String(255))
    hashed_password = Column(String(255))
    shopify_store = Column(String(255))
    shopify_token = Column(String)  # encrypted in prod
    shopify_token_expires_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    products = relationship("Product", back_populates="user", lazy="dynamic")
    suppliers = relationship("Supplier", back_populates="user", lazy="dynamic")
    import_jobs = relationship("ImportJob", back_populates="user", lazy="dynamic")
    description_templates = relationship("DescriptionTemplate", back_populates="user", lazy="dynamic")
