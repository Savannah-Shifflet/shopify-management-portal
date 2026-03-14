import uuid
from datetime import datetime
from sqlalchemy import Column, String, Numeric, Integer, Boolean, DateTime, ForeignKey, BigInteger
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.database import Base


class ProductVariant(Base):
    __tablename__ = "product_variants"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    product_id = Column(UUID(as_uuid=True), ForeignKey("products.id", ondelete="CASCADE"),
                        nullable=False)
    shopify_variant_id = Column(BigInteger, unique=True, nullable=True)

    title = Column(String(255))
    sku = Column(String(255), index=True)
    barcode = Column(String(255))

    # Variant option values (e.g. "Small", "Red", "XL")
    option1 = Column(String(100))
    option2 = Column(String(100))
    option3 = Column(String(100))

    price = Column(Numeric(10, 2), nullable=False, default=0)
    compare_at_price = Column(Numeric(10, 2))
    cost = Column(Numeric(10, 2))

    inventory_quantity = Column(Integer, default=0)
    inventory_policy = Column(String(50), default="deny")  # deny | continue
    inventory_management = Column(String(50), default="shopify")

    weight = Column(Numeric(8, 3))
    weight_unit = Column(String(10), default="kg")

    requires_shipping = Column(Boolean, default=True)
    taxable = Column(Boolean, default=True)

    image_id = Column(UUID(as_uuid=True), ForeignKey("product_images.id"), nullable=True)
    position = Column(Integer, default=1)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    product = relationship("Product", back_populates="variants")
    image = relationship("ProductImage", foreign_keys=[image_id])
