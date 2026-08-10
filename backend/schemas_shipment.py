"""Schemas for Phase 3-9 outbound shipments."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class ShipmentCreateIn(BaseModel):
    user_id: int
    entry_ids: list[int] = Field(..., min_length=1)
    note: Optional[str] = None


class ShipmentUpdateIn(BaseModel):
    status: Optional[str] = None
    shipping_carrier: Optional[str] = None
    tracking_number: Optional[str] = None
    shipping_method: Optional[str] = None
    note: Optional[str] = None
    postal_code: Optional[str] = None
    country: Optional[str] = None
    region: Optional[str] = None
    city: Optional[str] = None
    address_line1: Optional[str] = None
    address_line2: Optional[str] = None
    recipient_name: Optional[str] = None
    phone_number: Optional[str] = None


class ShipmentItemOut(BaseModel):
    id: int
    item_type: str
    oripa_entry_id: Optional[int] = None
    entry_label: Optional[str] = None
    oripa_id: Optional[int] = None
    linked_product_id: Optional[int] = None
    linked_product_name: Optional[str] = None


class ShipmentOut(BaseModel):
    id: int
    user_id: int
    status: str
    shipping_carrier: Optional[str] = None
    tracking_number: Optional[str] = None
    shipping_method: Optional[str] = None
    shipped_at: Optional[datetime] = None
    recipient_name: Optional[str] = None
    postal_code: Optional[str] = None
    region: Optional[str] = None
    city: Optional[str] = None
    address_line1: Optional[str] = None
    address_line2: Optional[str] = None
    phone_number: Optional[str] = None
    note: Optional[str] = None
    entry_labels: list[str] = []
    items: list[ShipmentItemOut] = []
    created_at: datetime
    updated_at: datetime


class ShipmentListOut(BaseModel):
    total: int
    items: list[ShipmentOut]


class ShipmentLogOut(BaseModel):
    id: int
    event_type: str
    from_status: Optional[str] = None
    to_status: Optional[str] = None
    tracking_number: Optional[str] = None
    shipping_carrier: Optional[str] = None
    admin_user_id: Optional[int] = None
    note: Optional[str] = None
    created_at: datetime


class ShipmentBarcodeOut(BaseModel):
    id: int
    scan_token: str
    human_readable: Optional[str] = None
    shipment_id: int
    is_active: bool
