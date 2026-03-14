from __future__ import annotations
from datetime import datetime
from typing import Optional
from uuid import UUID
from pydantic import BaseModel


class SyncRequest(BaseModel):
    product_ids: list[UUID]


class SyncLogOut(BaseModel):
    id: UUID
    product_id: Optional[UUID] = None
    operation: Optional[str] = None
    status: Optional[str] = None
    shopify_id: Optional[int] = None
    error_message: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class SyncStatusResponse(BaseModel):
    never_synced: int
    pending: int
    synced: int
    out_of_sync: int
    failed: int
    shopify_connected: bool
