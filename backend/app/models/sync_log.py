import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, ForeignKey, BigInteger, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from app.database import Base


class ShopifySyncLog(Base):
    __tablename__ = "shopify_sync_log"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    product_id = Column(UUID(as_uuid=True), ForeignKey("products.id", ondelete="CASCADE"),
                        nullable=True)
    operation = Column(String(50))
    # create | update | delete | price_update | inventory_update
    status = Column(String(50))  # success | failed | skipped
    shopify_id = Column(BigInteger)
    request_payload = Column(JSONB)
    response_body = Column(JSONB)
    error_message = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    product = relationship("Product", back_populates="sync_logs")
