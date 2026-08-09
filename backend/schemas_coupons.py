"""Pydantic schemas for Phase 3-5 coupons API."""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator

CouponType = Literal["fixed_amount", "percent", "free_shipping"]
CouponAudience = Literal["public", "assigned"]


class CouponOut(BaseModel):
    id: int
    code: str
    name: str
    description: Optional[str] = None
    coupon_type: str
    audience: str
    amount_yen: Optional[int] = None
    percent_off: Optional[int] = None
    max_discount_yen: Optional[int] = None
    min_subtotal_yen: int = 0
    max_uses_total: Optional[int] = None
    max_uses_per_user: int = 1
    starts_at: Optional[datetime] = None
    ends_at: Optional[datetime] = None
    card_ids: list[int] = []
    category_ids: list[int] = []
    is_active: bool = True
    created_at: datetime
    updated_at: Optional[datetime] = None
    redemption_count: int = 0

    class Config:
        from_attributes = True


class CouponCreateIn(BaseModel):
    code: str = Field(..., min_length=1, max_length=64)
    name: str = Field(..., min_length=1, max_length=128)
    description: Optional[str] = None
    coupon_type: CouponType
    audience: CouponAudience = "public"
    amount_yen: Optional[int] = Field(None, ge=0)
    percent_off: Optional[int] = Field(None, ge=1, le=100)
    max_discount_yen: Optional[int] = Field(None, ge=0)
    min_subtotal_yen: int = Field(0, ge=0)
    max_uses_total: Optional[int] = Field(None, ge=1)
    max_uses_per_user: int = Field(1, ge=1)
    starts_at: Optional[datetime] = None
    ends_at: Optional[datetime] = None
    card_ids: list[int] = []
    category_ids: list[int] = []
    is_active: bool = True

    @field_validator("code")
    @classmethod
    def normalize_code(cls, v: str) -> str:
        return v.strip().upper()


class CouponUpdateIn(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=128)
    description: Optional[str] = None
    amount_yen: Optional[int] = Field(None, ge=0)
    percent_off: Optional[int] = Field(None, ge=1, le=100)
    max_discount_yen: Optional[int] = Field(None, ge=0)
    min_subtotal_yen: Optional[int] = Field(None, ge=0)
    max_uses_total: Optional[int] = Field(None, ge=1)
    max_uses_per_user: Optional[int] = Field(None, ge=1)
    starts_at: Optional[datetime] = None
    ends_at: Optional[datetime] = None
    card_ids: Optional[list[int]] = None
    category_ids: Optional[list[int]] = None
    is_active: Optional[bool] = None
    audience: Optional[CouponAudience] = None


class CouponListOut(BaseModel):
    items: list[CouponOut]
    total: int


class CouponAssignIn(BaseModel):
    user_id: int = Field(..., gt=0)
    note: Optional[str] = None


class CouponCheckoutPreviewIn(BaseModel):
    coupon_code: str = Field(..., min_length=1, max_length=64)
    items_subtotal: int = Field(..., ge=0)
    shipping_fee: int = Field(0, ge=0)
    packaging_fee: int = Field(0, ge=0)
    cart_items: list[dict] = []  # [{card_id, category_id?, quantity, unit_price}]
    requested_points: int = Field(0, ge=0)

    @field_validator("coupon_code")
    @classmethod
    def normalize_code(cls, v: str) -> str:
        return v.strip().upper()


class CouponCheckoutPreviewOut(BaseModel):
    valid: bool
    coupon_code: Optional[str] = None
    coupon_name: Optional[str] = None
    coupon_type: Optional[str] = None
    discount_amount: int = 0
    shipping_fee_after: int = 0
    shipping_discount: int = 0
    total_yen_before_points: int = 0
    message: Optional[str] = None


class UserCouponOut(BaseModel):
    id: int
    code: str
    name: str
    description: Optional[str] = None
    coupon_type: str
    amount_yen: Optional[int] = None
    percent_off: Optional[int] = None
    max_discount_yen: Optional[int] = None
    min_subtotal_yen: int = 0
    starts_at: Optional[datetime] = None
    ends_at: Optional[datetime] = None
    assigned: bool = False
    remaining_uses_for_user: Optional[int] = None


class UserCouponListOut(BaseModel):
    items: list[UserCouponOut]
    total: int


class CouponAuditLogOut(BaseModel):
    id: int
    actor_admin_user_id: Optional[int] = None
    action: str
    coupon_id: Optional[int] = None
    target_user_id: Optional[int] = None
    before_json: Optional[str] = None
    after_json: Optional[str] = None
    reason: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True
