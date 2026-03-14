import uuid
from datetime import datetime
from sqlalchemy import Column, String, Boolean, Integer, DateTime, ForeignKey, Text, Numeric
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY
from sqlalchemy.orm import relationship
from app.database import Base


class Supplier(Base):
    __tablename__ = "suppliers"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    name = Column(String(255), nullable=False)
    website_url = Column(Text)
    # CSS selectors / XPath / pagination rules for scraping
    scrape_config = Column(JSONB, default=dict)
    # Default markup rules for this supplier
    pricing_config = Column(JSONB, default=dict)
    # Auto-approve price changes below this threshold (percent)
    auto_approve_threshold = Column(String(10), default="0")
    monitor_enabled = Column(Boolean, default=True)
    monitor_interval = Column(Integer, default=1440)  # minutes
    last_scraped_at = Column(DateTime)
    notes = Column(Text)

    # Fulfillment & listing settings
    free_shipping = Column(Boolean, default=False)
    avg_fulfillment_days = Column(Integer)          # typical days to ship
    google_listings_approved = Column(Boolean, default=False)

    # CRM — contacts list: [{name, email, phone, role}]
    contacts = Column(JSONB, default=list)
    # CRM — notes log: [{text, created_at}]
    crm_notes = Column(JSONB, default=list)

    # SRM fields
    status = Column(String(50), default="LEAD", index=True)  # LEAD|CONTACTED|NEGOTIATING|APPROVED|REJECTED|INACTIVE
    company_email = Column(String(255))           # primary contact email (unique within user)
    contact_name = Column(String(255))
    phone = Column(String(100))
    product_categories = Column(ARRAY(String), default=list)
    follow_up_date = Column(DateTime, nullable=True)
    approved_at = Column(DateTime, nullable=True)

    # Commercial terms
    payment_terms = Column(String(100))            # e.g. "Net 30"
    min_order_qty = Column(Integer)
    lead_time_days = Column(Integer)
    return_policy = Column(Text)
    map_enforced = Column(Boolean, default=False)
    warranty_info = Column(Text)

    # MAP & pricing
    map_price = Column(Numeric(10, 2))            # global supplier MAP (can be overridden per product)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="suppliers")
    products = relationship("Product", back_populates="supplier", lazy="dynamic")
    pricing_rules = relationship("PricingRule", back_populates="supplier", lazy="dynamic")
    scrape_sessions = relationship("ScrapeSession", back_populates="supplier", lazy="dynamic")
    detail_scrape_logs = relationship("DetailScrapeLog", back_populates="supplier", lazy="dynamic")
    emails = relationship("SupplierEmail", back_populates="supplier", lazy="dynamic", cascade="all, delete-orphan")
    documents = relationship("SupplierDocument", back_populates="supplier", lazy="dynamic", cascade="all, delete-orphan")
    checklist_items = relationship("SupplierChecklistItem", back_populates="supplier", lazy="dynamic", cascade="all, delete-orphan")
    reorders = relationship("ReorderLog", back_populates="supplier", lazy="dynamic", cascade="all, delete-orphan")
