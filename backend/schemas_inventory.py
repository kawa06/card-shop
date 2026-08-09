"""Phase 3-8 inventory alert / restock schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class InventoryAlertOut(BaseModel):
    id: int
    product_id: int
    product_name: Optional[str] = None
    alert_type: str
    stock_quantity: int
    threshold: int
    status: str
    created_at: datetime
    resolved_at: Optional[datetime] = None
    created_by: Optional[int] = None
    resolved_by: Optional[int] = None

    class Config:
        from_attributes = True


class InventoryAlertListOut(BaseModel):
    total: int
    items: list[InventoryAlertOut]


class InventoryRestockCreateIn(BaseModel):
    product_id: int
    requested_quantity: int = Field(..., gt=0)
    note: Optional[str] = None


class InventoryRestockUpdateIn(BaseModel):
    status: Optional[str] = None
    requested_quantity: Optional[int] = Field(None, gt=0)
    note: Optional[str] = None


class InventoryRestockReceiveIn(BaseModel):
    received_quantity: Optional[int] = Field(None, gt=0)


class InventoryRestockOut(BaseModel):
    id: int
    product_id: int
    product_name: Optional[str] = None
    requested_quantity: int
    received_quantity: Optional[int] = None
    status: str
    note: Optional[str] = None
    created_by: Optional[int] = None
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime] = None
    current_stock: Optional[int] = None

    class Config:
        from_attributes = True


class InventoryRestockListOut(BaseModel):
    total: int
    items: list[InventoryRestockOut]
