"""Pydantic schemas for Phase 3-3 live offer API."""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

LiveOfferStatus = Literal["pending", "accepted", "rejected", "held", "expired", "cancelled"]
LiveOfferPurchaseRightStatus = Literal["active", "used", "expired", "cancelled"]


class LiveOfferProductOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    stream_id: int
    card_id: int
    display_price: Optional[int] = None
    card_name: Optional[str] = None
    card_image_url: Optional[str] = None


class LiveOfferPublicOut(BaseModel):
    id: int
    amount: int
    status: LiveOfferStatus
    sender_name: Optional[str] = None
    live_product_id: int
    product: Optional[LiveOfferProductOut] = None
    created_at: datetime


class LiveOfferOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    stream_id: int
    live_product_id: int
    user_id: int
    amount: int
    status: LiveOfferStatus
    review_note: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    reviewed_by_admin_id: Optional[int] = None
    display_expires_at: Optional[datetime] = None
    purchase_expires_at: Optional[datetime] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    sender_name: Optional[str] = None
    product: Optional[LiveOfferProductOut] = None


class LiveOfferListOut(BaseModel):
    items: list[LiveOfferOut]
    total: int


class LiveOfferPublicListOut(BaseModel):
    items: list[LiveOfferPublicOut]
    total: int


class LiveOfferCreateIn(BaseModel):
    live_product_id: int = Field(..., gt=0)
    amount: int = Field(..., gt=0)
    idempotency_key: Optional[str] = Field(None, max_length=64)


class LiveOfferReviewIn(BaseModel):
    review_note: Optional[str] = Field(None, max_length=2000)


class LiveOfferSettingsOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    shop_id: int
    purchase_window_seconds: int
    display_ttl_seconds: int
    max_amount: int
    rate_limit_count: int
    rate_limit_window_seconds: int
    offers_enabled: bool = True


class LiveOfferSettingsPatchIn(BaseModel):
    offers_enabled: Optional[bool] = None
    purchase_window_seconds: Optional[int] = Field(None, gt=0)
    display_ttl_seconds: Optional[int] = Field(None, gt=0)
    max_amount: Optional[int] = Field(None, gt=0)
    rate_limit_count: Optional[int] = Field(None, gt=0)
    rate_limit_window_seconds: Optional[int] = Field(None, gt=0)


class LiveOfferProductOffersEnabledPatchIn(BaseModel):
    offers_enabled: bool


class LiveOfferPurchaseRightOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    offer_id: int
    user_id: int
    live_product_id: int
    card_id: int
    accepted_price: int
    status: LiveOfferPurchaseRightStatus
    expires_at: datetime
    order_id: Optional[int] = None
    created_at: datetime


class LiveOfferPurchaseIn(BaseModel):
    points_to_use: int = Field(0, ge=0)
    shipping_address: Optional[str] = None
    shipping_method: Optional[str] = None
    postal_code: Optional[str] = None
    country: Optional[str] = None
    region: Optional[str] = None
    city: Optional[str] = None
    address_line1: Optional[str] = None
    address_line2: Optional[str] = None


class LiveOfferPurchaseOut(BaseModel):
    order_id: int
    purchase_right: LiveOfferPurchaseRightOut
