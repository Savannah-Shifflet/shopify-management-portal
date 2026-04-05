import uuid
from datetime import datetime
from sqlalchemy import Column, String, Text, DateTime, ForeignKey, Boolean, Integer, Numeric
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.database import Base

class StoreSettings(Base):
    __tablename__ = "store_settings"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, unique=True)
    store_name = Column(String(255))
    owner_name = Column(String(255))
    logo_path = Column(Text)
    currency = Column(String(10), default="USD")
    timezone = Column(String(100), default="America/New_York")
    # Email settings (SMTP)
    smtp_host = Column(String(255))
    smtp_port = Column(Integer, default=587)
    smtp_user = Column(String(255))
    smtp_password = Column(Text)   # store encrypted in prod, plaintext OK for MVP
    smtp_from_name = Column(String(255))
    smtp_from_email = Column(String(255))
    # Email receiving (IMAP)
    imap_host = Column(String(255))
    imap_port = Column(Integer, default=993)
    imap_user = Column(String(255))
    imap_password = Column(Text)
    imap_folder = Column(String(255), default="INBOX")
    # MAP enforcement
    map_hard_block = Column(Boolean, default=False)  # True = block save, False = warn only
    # Low stock threshold
    low_stock_threshold = Column(Integer, default=5)
    # Global pricing defaults (used when no supplier rule matches)
    default_markup_pct = Column(Numeric(6, 2))    # e.g. 30 = 30% markup over cost
    default_shipping_cost = Column(Numeric(10, 2))  # added to cost before markup when no per-product value

    user = relationship("User")
