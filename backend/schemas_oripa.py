"""Phase 3-9 Oripa schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class OripaCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    price_per_entry: float = Field(..., gt=0)
    total_entries: int = Field(..., ge=1, le=10000)
    status: str = "draft"
    sale_start_at: Optional[datetime] = None
    sale_end_at: Optional[datetime] = None
    max_entries_per_purchase: int = Field(10, ge=1, le=1000)


class OripaUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    price_per_entry: Optional[float] = Field(None, gt=0)
    # total_entries immutable after entry generation (enforced in service)
    status: Optional[str] = None
    sale_start_at: Optional[datetime] = None
    sale_end_at: Optional[datetime] = None
    max_entries_per_purchase: Optional[int] = Field(None, ge=1, le=1000)


class OripaOut(BaseModel):
    id: int
    title: str
    description: Optional[str] = None
    price_per_entry: float
    total_entries: int
    status: str
    sale_start_at: Optional[datetime] = None
    sale_end_at: Optional[datetime] = None
    max_entries_per_purchase: int
    created_at: datetime
    updated_at: datetime
    created_by: Optional[int] = None
    available_entries: int = 0
    assigned_entries: int = 0
    linked_entries: int = 0

    class Config:
        from_attributes = True


class OripaListOut(BaseModel):
    total: int
    items: list[OripaOut]


class OripaGenerateEntriesIn(BaseModel):
    """Generate entry numbers 1..total_entries if not already generated."""

    force: bool = False


class OripaEntryLinkIn(BaseModel):
    linked_product_id: Optional[int] = None


class OripaEntryBulkLinkIn(BaseModel):
    """Link products to consecutive entry numbers starting at start_number."""

    start_number: int = Field(..., ge=1)
    product_ids: list[int] = Field(..., min_length=1)


class OripaEntryAdminOut(BaseModel):
    """Admin-only: includes linked product (content). Never expose to customers."""

    id: int
    oripa_id: int
    entry_number: int
    entry_label: str
    linked_product_id: Optional[int] = None
    linked_product_name: Optional[str] = None
    assignment_status: str
    assigned_user_id: Optional[int] = None
    assigned_order_id: Optional[int] = None
    assigned_purchase_id: Optional[int] = None
    assigned_at: Optional[datetime] = None
    shipment_status: str
    shipment_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class OripaEntryListOut(BaseModel):
    total: int
    items: list[OripaEntryAdminOut]


class OripaPurchaseCancelIn(BaseModel):
    reason: Optional[str] = None


class OripaPurchaseOut(BaseModel):
    id: int
    oripa_id: int
    user_id: int
    quantity: int
    status: str
    idempotency_key: Optional[str] = None
    order_id: Optional[int] = None
    unit_price: Optional[float] = None
    total_amount: Optional[float] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ShipmentCancelIn(BaseModel):
    reason: Optional[str] = None
