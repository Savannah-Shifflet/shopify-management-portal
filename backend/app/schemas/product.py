from __future__ import annotations
from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, Field, computed_field


# ── Variant ──────────────────────────────────────────────────────────────────

class VariantBase(BaseModel):
    title: Optional[str] = None
    sku: Optional[str] = None
    barcode: Optional[str] = None
    option1: Optional[str] = None
    option2: Optional[str] = None
    option3: Optional[str] = None
    price: Decimal = Decimal("0.00")
    compare_at_price: Optional[Decimal] = None
    cost: Optional[Decimal] = None
    inventory_quantity: int = 0
    inventory_policy: str = "deny"
    weight: Optional[Decimal] = None
    weight_unit: str = "kg"
    requires_shipping: bool = True
    taxable: bool = True
    position: int = 1


class VariantCreate(VariantBase):
    pass


class VariantUpdate(BaseModel):
    title: Optional[str] = None
    sku: Optional[str] = None
    barcode: Optional[str] = None
    option1: Optional[str] = None
    option2: Optional[str] = None
    option3: Optional[str] = None
    price: Optional[Decimal] = None
    compare_at_price: Optional[Decimal] = None
    cost: Optional[Decimal] = None
    inventory_quantity: Optional[int] = None
    inventory_policy: Optional[str] = None
    weight: Optional[Decimal] = None
    requires_shipping: Optional[bool] = None
    taxable: Optional[bool] = None
    position: Optional[int] = None


class VariantOut(VariantBase):
    id: UUID
    product_id: UUID
    shopify_variant_id: Optional[int] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


# ── Image ─────────────────────────────────────────────────────────────────────

class ImageOut(BaseModel):
    id: UUID
    product_id: UUID
    shopify_image_id: Optional[int] = None
    src: str
    alt: Optional[str] = None
    position: int
    width: Optional[int] = None
    height: Optional[int] = None
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Product ───────────────────────────────────────────────────────────────────

class ProductBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=500)
    body_html: Optional[str] = None
    vendor: Optional[str] = None
    product_type: Optional[str] = None
    handle: Optional[str] = None
    tags: Optional[list[str]] = None
    # e.g. [{"name": "Color", "position": 1}, {"name": "Size", "position": 2}]
    options: Optional[list[dict]] = None
    cost_price: Optional[Decimal] = None
    map_price: Optional[Decimal] = None
    base_price: Optional[Decimal] = None
    compare_at_price: Optional[Decimal] = None
    shipping_cost: Optional[Decimal] = None
    metafields: Optional[dict] = None


class ProductCreate(ProductBase):
    supplier_id: Optional[UUID] = None
    source_type: str = "manual"
    variants: list[VariantCreate] = Field(default_factory=list)


class ProductUpdate(BaseModel):
    title: Optional[str] = None
    body_html: Optional[str] = None
    vendor: Optional[str] = None
    product_type: Optional[str] = None
    handle: Optional[str] = None
    tags: Optional[list[str]] = None
    options: Optional[list[dict]] = None
    status: Optional[str] = None
    supplier_id: Optional[UUID] = None
    cost_price: Optional[Decimal] = None
    map_price: Optional[Decimal] = None
    base_price: Optional[Decimal] = None
    compare_at_price: Optional[Decimal] = None
    shipping_cost: Optional[Decimal] = None
    seo_title: Optional[str] = None
    seo_description: Optional[str] = None
    metafields: Optional[dict] = None
    use_supplier_price: Optional[bool] = None
    # Direct AI field overrides (e.g. clearing after a rejected enrichment)
    ai_title: Optional[str] = None
    ai_description: Optional[str] = None
    applied_template_id: Optional[UUID] = None
    enrichment_status: Optional[str] = None
    # Accept AI suggestions into main fields
    accept_ai_title: Optional[bool] = None
    accept_ai_description: Optional[bool] = None
    accept_ai_tags: Optional[bool] = None
    accept_ai_attributes: Optional[bool] = None


class ProductOut(ProductBase):
    id: UUID
    user_id: UUID
    supplier_id: Optional[UUID] = None
    shopify_product_id: Optional[int] = None
    status: str
    source_type: Optional[str] = None
    source_url: Optional[str] = None
    ai_title: Optional[str] = None
    ai_description: Optional[str] = None
    ai_tags: Optional[list[str]] = None
    ai_attributes: Optional[dict] = None
    seo_title: Optional[str] = None
    seo_description: Optional[str] = None
    enrichment_status: str
    enrichment_at: Optional[datetime] = None
    applied_template_id: Optional[UUID] = None
    supplier_price: Optional[Decimal] = None
    supplier_price_at: Optional[datetime] = None
    use_supplier_price: bool = False
    sync_status: str
    synced_at: Optional[datetime] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    variants: list[VariantOut] = []
    images: list[ImageOut] = []

    @computed_field
    @property
    def margin_pct(self) -> Optional[float]:
        if self.cost_price and self.base_price and self.base_price > 0:
            return float((self.base_price - self.cost_price) / self.base_price * 100)
        return None

    model_config = {"from_attributes": True}


class ProductListOut(BaseModel):
    id: UUID
    title: str
    status: str
    sync_status: str
    enrichment_status: str
    product_type: Optional[str] = None
    vendor: Optional[str] = None
    base_price: Optional[Decimal] = None
    cost_price: Optional[Decimal] = None
    map_price: Optional[Decimal] = None
    shipping_cost: Optional[Decimal] = None
    supplier_price: Optional[Decimal] = None
    supplier_id: Optional[UUID] = None
    shopify_product_id: Optional[int] = None
    source_url: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    # First image thumbnail
    thumbnail: Optional[str] = None
    # AI enrichment fields (needed for template review)
    body_html: Optional[str] = None
    ai_description: Optional[str] = None
    # Template tracking
    applied_template_id: Optional[UUID] = None
    # Computed fields
    margin_pct: Optional[float] = None
    is_low_stock: Optional[bool] = None

    model_config = {"from_attributes": True}


class ProductListResponse(BaseModel):
    items: list[ProductListOut]
    total: int
    page: int
    page_size: int
    pages: int


class BulkActionRequest(BaseModel):
    product_ids: list[UUID]
    action: str  # enrich | approve | sync | delete | tag | archive
    tag: Optional[str] = None  # for tag action


class MergeOverrides(BaseModel):
    title: Optional[str] = None
    body_html: Optional[str] = None
    vendor: Optional[str] = None
    product_type: Optional[str] = None
    seo_title: Optional[str] = None
    seo_description: Optional[str] = None
    cost_price: Optional[Decimal] = None
    base_price: Optional[Decimal] = None
    compare_at_price: Optional[Decimal] = None
    # "union" = all tags; "product:<uuid>" = use that product's tags only
    tags_strategy: Optional[str] = "union"
    # "union" = all images; "product:<uuid>" = use that product's images only
    images_strategy: Optional[str] = "union"
    # If set, overrides images_strategy: the merged product will have exactly these image URLs (in order)
    image_srcs: Optional[list[str]] = None


class MergeProductsRequest(BaseModel):
    primary_id: UUID
    secondary_ids: list[UUID]  # products to merge into primary (will be deleted)
    overrides: Optional[MergeOverrides] = None
