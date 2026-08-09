"""Pydantic schemas for Phase 3-6 user notifications."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class NotificationOut(BaseModel):
    id: int
    type: str
    category: str
    title: str
    body: str
    related_entity_type: Optional[str] = None
    related_entity_id: Optional[str] = None
    action_url: Optional[str] = None
    priority: str = "normal"
    channel: str = "in_app"
    is_read: bool
    read_at: Optional[datetime] = None
    email_status: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class NotificationListOut(BaseModel):
    items: list[NotificationOut]
    total: int
    unread_count: int


class UnreadCountOut(BaseModel):
    unread_count: int


class NotificationSettingsOut(BaseModel):
    in_app_enabled: bool = True
    email_enabled: bool = True
    order_in_app: bool = True
    order_email: bool = True
    shipping_in_app: bool = True
    shipping_email: bool = True
    appraisal_in_app: bool = True
    appraisal_email: bool = True
    live_in_app: bool = True
    live_email: bool = True
    auction_in_app: bool = True
    auction_email: bool = True
    campaign_in_app: bool = True
    campaign_email: bool = True

    class Config:
        from_attributes = True


class NotificationSettingsUpdateIn(BaseModel):
    in_app_enabled: Optional[bool] = None
    email_enabled: Optional[bool] = None
    order_in_app: Optional[bool] = None
    order_email: Optional[bool] = None
    shipping_in_app: Optional[bool] = None
    shipping_email: Optional[bool] = None
    appraisal_in_app: Optional[bool] = None
    appraisal_email: Optional[bool] = None
    live_in_app: Optional[bool] = None
    live_email: Optional[bool] = None
    auction_in_app: Optional[bool] = None
    auction_email: Optional[bool] = None
    campaign_in_app: Optional[bool] = None
    campaign_email: Optional[bool] = None


class AdminBroadcastNotificationIn(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    body: str = Field(..., min_length=1)
    user_id: Optional[int] = Field(None, gt=0)
    action_url: Optional[str] = Field(None, max_length=512)
    category: str = Field("campaign", max_length=32)
    type: str = Field("admin_broadcast", max_length=64)
