import uuid
from datetime import datetime
from sqlalchemy import Column, String, Text, Numeric, DateTime, ForeignKey, BigInteger, ARRAY, Boolean
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from app.database import Base


class Product(Base):
    __tablename__ = "products"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    supplier_id = Column(UUID(as_uuid=True), ForeignKey("suppliers.id"), nullable=True)
    shopify_product_id = Column(BigInteger, unique=True, nullable=True, index=True)

    # Shopify-aligned status (mirrors Shopify product status)
    status = Column(String(50), default="draft", index=True)
    # draft | active | archived

    # Main product fields (user-edited / accepted from AI)
    title = Column(String(500), nullable=False)
    body_html = Column(Text)
    vendor = Column(String(255))
    product_type = Column(String(255))
    handle = Column(String(255))
    tags = Column(ARRAY(String))

    # Raw sourced data (never overwritten after import)
    raw_title = Column(String(500))
    raw_description = Column(Text)
    source_url = Column(Text)
    source_type = Column(String(50))  # manual | csv | pdf | scrape | image

    # AI enrichment fields (separate from main fields — never auto-applied without user acceptance)
    ai_title = Column(String(500))
    ai_description = Column(Text)
    ai_tags = Column(ARRAY(String))
    ai_attributes = Column(JSONB, default=dict)
    seo_title = Column(String(255))
    seo_description = Column(String(500))
    enrichment_status = Column(String(50), default="not_started")
    # not_started | pending | running | done | failed
    enrichment_model = Column(String(100))
    enrichment_at = Column(DateTime)
    applied_template_id = Column(UUID(as_uuid=True), ForeignKey("description_templates.id", ondelete="SET NULL"), nullable=True)

    # Pricing
    cost_price = Column(Numeric(10, 2))
    map_price = Column(Numeric(10, 2))   # Minimum Advertised Price
    base_price = Column(Numeric(10, 2))
    compare_at_price = Column(Numeric(10, 2))
    supplier_price = Column(Numeric(10, 2))
    supplier_price_at = Column(DateTime)
    use_supplier_price = Column(Boolean, default=False, nullable=False)
    shipping_cost = Column(Numeric(10, 2))  # per-product shipping to bake into retail price

    # Shopify sync tracking
    sync_status = Column(String(50), default="never_synced")
    # never_synced | pending | synced | failed | out_of_sync
    synced_at = Column(DateTime)
    shopify_hash = Column(String(64))  # SHA256 of last synced payload

    # Product options (e.g. [{name: "Color", position: 1}, {name: "Size", position: 2}])
    # Maps option1/option2/option3 columns on variants to human-readable names
    options = Column(JSONB, default=list)

    # Extra metadata
    metafields = Column(JSONB, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="products")
    supplier = relationship("Supplier", back_populates="products")
    variants = relationship("ProductVariant", back_populates="product",
                            cascade="all, delete-orphan", order_by="ProductVariant.position")
    images = relationship("ProductImage", back_populates="product",
                          cascade="all, delete-orphan", order_by="ProductImage.position")
    price_history = relationship("PriceHistory", back_populates="product",
                                 cascade="all, delete-orphan")
    pricing_alerts = relationship("PricingAlert", back_populates="product",
                                  cascade="all, delete-orphan")
    pricing_schedules = relationship("PricingSchedule", back_populates="product",
                                     cascade="all, delete-orphan")
    sync_logs = relationship("ShopifySyncLog", back_populates="product",
                             cascade="all, delete-orphan")
