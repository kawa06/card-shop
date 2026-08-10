"""Phase 3-9 customer-facing Oripa schemas — NEVER include linked product/content fields."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class OripaPublicOut(BaseModel):
    id: int
    title: str
    description: Optional[str] = None
    price_per_entry: float
    total_entries: int
    remaining_entries: int
    status: str
    sale_start_at: Optional[datetime] = None
    sale_end_at: Optional[datetime] = None
    max_entries_per_purchase: int


class OripaPublicListOut(BaseModel):
    total: int
    items: list[OripaPublicOut]


class OripaPurchaseIn(BaseModel):
    quantity: int = Field(..., ge=1, le=1000)
    idempotency_key: Optional[str] = Field(None, max_length=128)
    points_to_use: int = Field(0, ge=0)
    coupon_code: Optional[str] = Field(None, max_length=64)


class OripaEntryPublicOut(BaseModel):
    """Numbers only — no product linkage."""

    id: int
    oripa_id: int
    oripa_title: Optional[str] = None
    entry_label: str
    assignment_status: str
    shipment_status: str
    assigned_at: Optional[datetime] = None
    purchase_id: Optional[int] = None


class OripaPurchaseResultOut(BaseModel):
    purchase_id: int
    oripa_id: int
    quantity: int
    entry_labels: list[str] = []
    status: str
    order_id: Optional[int] = None
    checkout_url: Optional[str] = None
    session_id: Optional[str] = None
    payment_status: Optional[str] = None


class OripaHeldListOut(BaseModel):
    total: int
    items: list[OripaEntryPublicOut]
