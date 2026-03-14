from __future__ import annotations
from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID
from pydantic import BaseModel


class PricingAlertOut(BaseModel):
    id: UUID
    product_id: UUID
    product_title: Optional[str] = None
    supplier_id: Optional[UUID] = None
    supplier_name: Optional[str] = None
    alert_type: str
    old_price: Optional[Decimal] = None
    new_price: Optional[Decimal] = None
    change_pct: Optional[Decimal] = None
    status: str
    reviewed_at: Optional[datetime] = None
    notes: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class AlertReviewRequest(BaseModel):
    notes: Optional[str] = None


class PricingRuleBase(BaseModel):
    rule_name: Optional[str] = None
    priority: int = 0
    condition_type: str = "always"
    condition_value: Optional[dict] = None
    markup_type: str = "percent"
    markup_value: Decimal = Decimal("0")
    round_to: Optional[Decimal] = None
    min_price: Optional[Decimal] = None
    max_price: Optional[Decimal] = None


class PricingRuleCreate(PricingRuleBase):
    supplier_id: UUID


class PricingRuleUpdate(BaseModel):
    rule_name: Optional[str] = None
    priority: Optional[int] = None
    condition_type: Optional[str] = None
    condition_value: Optional[dict] = None
    markup_type: Optional[str] = None
    markup_value: Optional[Decimal] = None
    round_to: Optional[Decimal] = None
    min_price: Optional[Decimal] = None
    max_price: Optional[Decimal] = None


class PricingRuleOut(PricingRuleBase):
    id: UUID
    supplier_id: UUID
    created_at: datetime

    model_config = {"from_attributes": True}


class PricingScheduleBase(BaseModel):
    product_id: Optional[UUID] = None
    variant_id: Optional[UUID] = None
    supplier_id: Optional[UUID] = None
    tag_filter: Optional[str] = None
    schedule_type: str = "one_time"
    price_action: str  # set | percent_off | fixed_off | compare_at
    price_value: Decimal
    starts_at: datetime
    ends_at: Optional[datetime] = None


class PricingScheduleCreate(PricingScheduleBase):
    pass


class PricingScheduleUpdate(BaseModel):
    price_action: Optional[str] = None
    price_value: Optional[Decimal] = None
    starts_at: Optional[datetime] = None
    ends_at: Optional[datetime] = None
    status: Optional[str] = None


class PricingScheduleOut(PricingScheduleBase):
    id: UUID
    user_id: UUID
    original_price: Optional[Decimal] = None
    status: str
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class PriceCalculateRequest(BaseModel):
    cost_price: Decimal
    supplier_id: UUID
    product_type: Optional[str] = None
    tags: Optional[list[str]] = None


class PriceCalculateResponse(BaseModel):
    cost_price: Decimal
    calculated_price: Decimal
    rule_applied: Optional[str] = None
