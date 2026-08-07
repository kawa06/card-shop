"""Pydantic schemas for Phase 3-4 points API."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class PointBalanceOut(BaseModel):
    available_points: int
    reserved_points: int = 0
    lifetime_earned: int = 0
    lifetime_used: int = 0
    expiring_soon_points: int = 0


class PointTransactionOut(BaseModel):
    id: int
    type: str
    amount: int
    balance_after: int
    source_type: Optional[str] = None
    source_id: Optional[int] = None
    expires_at: Optional[datetime] = None
    created_at: datetime
    metadata_json: Optional[str] = None

    class Config:
        from_attributes = True


class PointHistoryOut(BaseModel):
    items: list[PointTransactionOut]
    total: int


class PointCheckoutPreviewIn(BaseModel):
    items_subtotal: int = Field(..., ge=0)
    shipping_fee: int = Field(0, ge=0)
    packaging_fee: int = Field(0, ge=0)
    discount_amount: int = Field(0, ge=0)
    requested_points: int = Field(0, ge=0)


class PointCheckoutPreviewOut(BaseModel):
    enabled: bool
    available_points: int
    reserved_points: int
    max_usable_points: int
    requested_points: int
    applied_points: int
    total_yen: int
    estimated_earn_points: int


class PointSettingsOut(BaseModel):
    shop_id: int
    enabled: bool
    earn_rate_percent: int
    expiration_days: Optional[int] = None
    max_points_per_order: int
    max_usage_percent: int
    points_apply_to_shipping: bool

    class Config:
        from_attributes = True


class PointSettingsUpdateIn(BaseModel):
    enabled: Optional[bool] = None
    earn_rate_percent: Optional[int] = Field(None, ge=0, le=100)
    expiration_days: Optional[int] = Field(None, ge=0)
    max_points_per_order: Optional[int] = Field(None, ge=0)
    max_usage_percent: Optional[int] = Field(None, ge=0, le=100)
    points_apply_to_shipping: Optional[bool] = None


class AdminPointGrantIn(BaseModel):
    user_id: int = Field(..., gt=0)
    amount: int = Field(..., gt=0)
    reason: str = Field(..., min_length=1, max_length=500)
    expiration_days: Optional[int] = Field(None, ge=0)
    idempotency_key: Optional[str] = Field(None, max_length=128)


class AdminPointDeductIn(BaseModel):
    user_id: int = Field(..., gt=0)
    amount: int = Field(..., gt=0)
    reason: str = Field(..., min_length=1, max_length=500)
    idempotency_key: Optional[str] = Field(None, max_length=128)


class AdminUserPointsOut(BaseModel):
    user_id: int
    email: Optional[str] = None
    name: Optional[str] = None
    available_points: int
    reserved_points: int
    lifetime_earned: int
    lifetime_used: int


class PointAuditLogOut(BaseModel):
    id: int
    actor_admin_user_id: Optional[int] = None
    action: str
    target_user_id: int
    transaction_id: Optional[int] = None
    before_json: Optional[str] = None
    after_json: Optional[str] = None
    reason: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True
