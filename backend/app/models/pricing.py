import uuid
from datetime import datetime
from sqlalchemy import Column, String, Numeric, Integer, DateTime, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from app.database import Base


class PriceHistory(Base):
    __tablename__ = "price_history"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    product_id = Column(UUID(as_uuid=True), ForeignKey("products.id", ondelete="CASCADE"),
                        nullable=False)
    variant_id = Column(UUID(as_uuid=True), ForeignKey("product_variants.id"), nullable=True)
    supplier_id = Column(UUID(as_uuid=True), ForeignKey("suppliers.id"), nullable=True)
    price_type = Column(String(50))  # supplier | retail | promo
    old_price = Column(Numeric(10, 2))
    new_price = Column(Numeric(10, 2))
    change_pct = Column(Numeric(6, 3))
    source = Column(String(50))  # scrape | manual | scheduled | api
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    product = relationship("Product", back_populates="price_history")
    variant = relationship("ProductVariant")
    supplier = relationship("Supplier")


class PricingAlert(Base):
    __tablename__ = "pricing_alerts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    product_id = Column(UUID(as_uuid=True), ForeignKey("products.id", ondelete="CASCADE"),
                        nullable=False)
    variant_id = Column(UUID(as_uuid=True), ForeignKey("product_variants.id"), nullable=True)
    supplier_id = Column(UUID(as_uuid=True), ForeignKey("suppliers.id"), nullable=True)
    alert_type = Column(String(50), default="price_change")
    old_price = Column(Numeric(10, 2))
    new_price = Column(Numeric(10, 2))
    change_pct = Column(Numeric(6, 3))
    status = Column(String(50), default="pending")
    # pending | approved | rejected | auto_applied
    reviewed_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    reviewed_at = Column(DateTime)
    notes = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    product = relationship("Product", back_populates="pricing_alerts")
    variant = relationship("ProductVariant")
    supplier = relationship("Supplier")


class PricingSchedule(Base):
    __tablename__ = "pricing_schedules"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    product_id = Column(UUID(as_uuid=True), ForeignKey("products.id", ondelete="CASCADE"),
                        nullable=True)
    variant_id = Column(UUID(as_uuid=True), ForeignKey("product_variants.id"), nullable=True)
    supplier_id = Column(UUID(as_uuid=True), ForeignKey("suppliers.id"), nullable=True)
    tag_filter = Column(String(255))  # apply to all products with this tag

    schedule_type = Column(String(50), default="one_time")  # one_time | recurring
    price_action = Column(String(50))  # set | percent_off | fixed_off | compare_at
    price_value = Column(Numeric(10, 2))
    original_price = Column(Numeric(10, 2))  # cached before schedule runs

    starts_at = Column(DateTime, nullable=False)
    ends_at = Column(DateTime)
    status = Column(String(50), default="pending")
    # pending | active | completed | cancelled
    celery_task_id = Column(String(255))

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    product = relationship("Product", back_populates="pricing_schedules")
    variant = relationship("ProductVariant")
    supplier = relationship("Supplier")


class PricingRule(Base):
    __tablename__ = "pricing_rules"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    supplier_id = Column(UUID(as_uuid=True), ForeignKey("suppliers.id"), nullable=False)
    rule_name = Column(String(255))
    priority = Column(Integer, default=0)
    condition_type = Column(String(50), default="always")
    # always | cost_range | product_type | tag
    condition_value = Column(JSONB, default=dict)  # {"min": 0, "max": 50}
    markup_type = Column(String(50), default="percent")  # percent | fixed | formula
    markup_value = Column(Numeric(10, 4), default=0)
    round_to = Column(Numeric(6, 2))  # e.g. 0.99 for charm pricing
    min_price = Column(Numeric(10, 2))
    max_price = Column(Numeric(10, 2))
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    supplier = relationship("Supplier", back_populates="pricing_rules")
