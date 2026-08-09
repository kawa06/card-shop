"""Phase 3-7 admin analytics schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class AnalyticsKpiOut(BaseModel):
    from_at: Optional[datetime] = None
    to_at: Optional[datetime] = None
    paid_order_count: int = 0
    paid_sales_yen: int = 0
    avg_order_yen: int = 0
    coupon_discount_yen: int = 0
    points_used: int = 0
    points_earned: int = 0
    live_stream_count: int = 0
    live_live_count: int = 0
    auction_count: int = 0
    auction_sold_count: int = 0
    auction_gmv_yen: int = 0
    coupon_active_count: int = 0
    coupon_redemption_count: int = 0
    new_members: int = 0


class AnalyticsSeriesPoint(BaseModel):
    date: str
    value: int


class AnalyticsSalesRow(BaseModel):
    order_id: int
    order_number: Optional[str] = None
    user_id: int
    payment_status: Optional[str] = None
    shipping_status: Optional[str] = None
    total_amount: int
    discount_amount: int
    coupon_code: Optional[str] = None
    points_used: int
    points_earned: int
    paid_at: Optional[datetime] = None
    created_at: Optional[datetime] = None


class AnalyticsLiveRow(BaseModel):
    stream_id: int
    title: str
    status: str
    visibility: str
    product_count: int
    comment_count: int
    scheduled_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    created_at: Optional[datetime] = None


class AnalyticsAuctionRow(BaseModel):
    auction_id: int
    stream_id: int
    status: str
    start_price: int
    current_price: Optional[int] = None
    winning_amount: Optional[int] = None
    bid_count: int
    bidder_count: int
    winner_user_id: Optional[int] = None
    ends_at: Optional[datetime] = None
    created_at: Optional[datetime] = None


class AnalyticsCouponRow(BaseModel):
    coupon_id: int
    code: str
    name: str
    coupon_type: str
    audience: str
    is_active: bool
    redemption_count: int
    discount_total_yen: int
    assignment_count: int
    created_at: Optional[datetime] = None


class AnalyticsPointRow(BaseModel):
    transaction_id: int
    user_id: int
    type: str
    amount: int
    balance_after: int
    source_type: Optional[str] = None
    source_id: Optional[int] = None
    created_at: Optional[datetime] = None


class AnalyticsListOut(BaseModel):
    domain: str
    total: int
    page: int
    size: int
    sort: str
    order: str
    items: list[Any] = Field(default_factory=list)
    series: list[AnalyticsSeriesPoint] = Field(default_factory=list)
