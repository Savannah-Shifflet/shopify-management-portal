from __future__ import annotations
from datetime import datetime
from typing import Optional
from uuid import UUID
from pydantic import BaseModel


class SupplierBase(BaseModel):
    name: str
    website_url: Optional[str] = None
    scrape_config: Optional[dict] = None
    pricing_config: Optional[dict] = None
    auto_approve_threshold: str = "0"
    monitor_enabled: bool = True
    monitor_interval: int = 1440
    notes: Optional[str] = None
    free_shipping: bool = False
    avg_fulfillment_days: Optional[int] = None
    google_listings_approved: bool = False
    contacts: Optional[list] = None
    crm_notes: Optional[list] = None


class SupplierCreate(SupplierBase):
    pass


class SupplierUpdate(BaseModel):
    name: Optional[str] = None
    website_url: Optional[str] = None
    scrape_config: Optional[dict] = None
    pricing_config: Optional[dict] = None
    auto_approve_threshold: Optional[str] = None
    monitor_enabled: Optional[bool] = None
    monitor_interval: Optional[int] = None
    notes: Optional[str] = None
    free_shipping: Optional[bool] = None
    avg_fulfillment_days: Optional[int] = None
    google_listings_approved: Optional[bool] = None
    contacts: Optional[list] = None
    crm_notes: Optional[list] = None


class SupplierOut(SupplierBase):
    id: UUID
    user_id: UUID
    last_scraped_at: Optional[datetime] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    product_count: int = 0

    model_config = {"from_attributes": True}


class SupplierStats(BaseModel):
    product_count: int
    avg_supplier_price: Optional[float] = None
    avg_base_price: Optional[float] = None
    avg_margin_pct: Optional[float] = None
