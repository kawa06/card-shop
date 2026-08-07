"""Pydantic schemas for Phase 3-2 live auction API."""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

LiveAuctionStatus = Literal["draft", "waiting", "running", "paused", "finished", "cancelled"]
LiveBidStatus = Literal["active", "outbid", "won", "invalidated"]


class LiveAuctionProductOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    stream_id: int
    card_id: int
    display_price: Optional[int] = None
    card_name: Optional[str] = None
    card_image_url: Optional[str] = None


class LiveAuctionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    stream_id: int
    live_product_id: int
    status: LiveAuctionStatus
    start_price: int
    current_price: Optional[int] = None
    min_bid_increment: int
    buy_now_price: Optional[int] = None
    scheduled_start_at: Optional[datetime] = None
    scheduled_end_at: Optional[datetime] = None
    ends_at: Optional[datetime] = None
    extension_seconds: int
    auto_extend_enabled: bool
    max_extensions: int
    extension_count: int
    trigger_remaining_seconds: int
    winner_user_id: Optional[int] = None
    winning_amount: Optional[int] = None
    bid_count: int
    bidder_count: int
    created_at: datetime
    updated_at: Optional[datetime] = None
    product: Optional[LiveAuctionProductOut] = None


class LiveAuctionListOut(BaseModel):
    items: list[LiveAuctionOut]
    total: int


class LiveAuctionCreateIn(BaseModel):
    live_product_id: int = Field(..., gt=0)
    start_price: int = Field(..., ge=0)
    min_bid_increment: Optional[int] = Field(None, gt=0)
    buy_now_price: Optional[int] = Field(None, gt=0)
    scheduled_start_at: Optional[datetime] = None
    scheduled_end_at: Optional[datetime] = None
    duration_seconds: Optional[int] = Field(None, gt=0)
    extension_seconds: Optional[int] = Field(None, gt=0)
    auto_extend_enabled: Optional[bool] = None
    max_extensions: Optional[int] = Field(None, ge=0)
    trigger_remaining_seconds: Optional[int] = Field(None, ge=0)


class LiveAuctionUpdateIn(BaseModel):
    start_price: Optional[int] = Field(None, ge=0)
    min_bid_increment: Optional[int] = Field(None, gt=0)
    buy_now_price: Optional[int] = Field(None, gt=0)
    scheduled_start_at: Optional[datetime] = None
    scheduled_end_at: Optional[datetime] = None
    extension_seconds: Optional[int] = Field(None, gt=0)
    auto_extend_enabled: Optional[bool] = None
    max_extensions: Optional[int] = Field(None, ge=0)
    trigger_remaining_seconds: Optional[int] = Field(None, ge=0)


class LiveAuctionStartIn(BaseModel):
    duration_seconds: Optional[int] = Field(None, gt=0)


class LiveBidOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    auction_id: int
    user_id: int
    amount: int
    status: LiveBidStatus
    created_at: datetime


class LiveBidListOut(BaseModel):
    items: list[LiveBidOut]
    total: int


class LiveBidPlaceIn(BaseModel):
    amount: int = Field(..., gt=0)
    idempotency_key: Optional[str] = Field(None, max_length=64)


class LiveBidPlaceOut(BaseModel):
    bid: LiveBidOut
    auction: LiveAuctionOut
    instant_buy: bool = False
    extended: bool = False


class LiveAuctionSettingsOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    shop_id: int
    default_min_bid_increment: int
    default_extension_seconds: int
    default_trigger_remaining_seconds: int
    default_max_extensions: int
    default_auto_extend_enabled: bool
