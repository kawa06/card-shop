"""Pydantic schemas for Phase 3-1 live sales API."""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

LiveStreamStatus = Literal["draft", "scheduled", "live", "paused", "ended"]
LiveVisibility = Literal["public", "unlisted"]
LiveSenderType = Literal["customer", "staff", "admin", "system"]
LiveCommentReportStatus = Literal["open", "resolved", "dismissed"]


class LiveProductOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    stream_id: int
    card_id: int
    sort_order: int
    display_price: Optional[int] = None
    is_active: bool
    is_pinned: bool
    offers_enabled: bool = True
    card_name: Optional[str] = None
    card_image_url: Optional[str] = None
    card_price: Optional[int] = None
    created_at: datetime


class LiveStreamOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    shop_id: int
    title: str
    description: Optional[str] = None
    thumbnail_url: Optional[str] = None
    embed_url: Optional[str] = None
    status: LiveStreamStatus
    visibility: LiveVisibility
    scheduled_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    offers_enabled: bool = True
    active_product: Optional[LiveProductOut] = None
    pinned_product: Optional[LiveProductOut] = None
    product_count: int = 0
    comment_count: int = 0


class LiveStreamListOut(BaseModel):
    items: list[LiveStreamOut]
    total: int


class LiveStreamCreateIn(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=5000)
    thumbnail_url: Optional[str] = Field(None, max_length=512)
    embed_url: Optional[str] = Field(None, max_length=512)
    visibility: LiveVisibility = "public"
    scheduled_at: Optional[datetime] = None

    @field_validator("title")
    @classmethod
    def strip_title(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("title is required")
        return stripped


class LiveStreamUpdateIn(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=5000)
    thumbnail_url: Optional[str] = Field(None, max_length=512)
    embed_url: Optional[str] = Field(None, max_length=512)
    visibility: Optional[LiveVisibility] = None
    scheduled_at: Optional[datetime] = None
    status: Optional[LiveStreamStatus] = None


class LiveProductCreateIn(BaseModel):
    card_id: int = Field(..., gt=0)
    display_price: Optional[int] = Field(None, ge=0)
    sort_order: Optional[int] = Field(None, ge=0)


class LiveProductUpdateIn(BaseModel):
    display_price: Optional[int] = Field(None, ge=0)
    sort_order: Optional[int] = Field(None, ge=0)


class LiveCommentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    stream_id: int
    sender_type: LiveSenderType
    message: str
    is_pinned: bool
    created_at: datetime
    sender_name: Optional[str] = None
    user_id: Optional[int] = None


class LiveCommentListOut(BaseModel):
    items: list[LiveCommentOut]
    total: int
    next_cursor: Optional[int] = None


class LiveCommentCreateIn(BaseModel):
    message: str = Field(..., min_length=1, max_length=500)

    @field_validator("message")
    @classmethod
    def strip_message(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("message is required")
        return stripped


class LiveStaffCommentCreateIn(LiveCommentCreateIn):
    sender_type: Literal["staff", "admin"] = "staff"


class LiveCommentReportIn(BaseModel):
    reason: Optional[str] = Field(None, max_length=255)


class LiveNgWordOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    word: str
    is_active: bool
    created_at: datetime


class LiveNgWordCreateIn(BaseModel):
    word: str = Field(..., min_length=1, max_length=128)

    @field_validator("word")
    @classmethod
    def normalize_word(cls, value: str) -> str:
        stripped = value.strip().lower()
        if not stripped:
            raise ValueError("word is required")
        return stripped


class LiveModeratorOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    stream_id: Optional[int] = None
    admin_user_id: int
    admin_email: Optional[str] = None
    admin_name: Optional[str] = None
    created_at: datetime


class LiveModeratorCreateIn(BaseModel):
    admin_user_id: int = Field(..., gt=0)
    stream_id: Optional[int] = Field(None, gt=0)


class LiveUserMuteIn(BaseModel):
    user_id: int = Field(..., gt=0)
    muted_until: Optional[datetime] = None


class LiveUserBanIn(BaseModel):
    user_id: int = Field(..., gt=0)
    banned_until: Optional[datetime] = None
    reason: Optional[str] = Field(None, max_length=255)
    stream_id: Optional[int] = Field(None, gt=0)


class LiveModerationAuditOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    stream_id: Optional[int] = None
    action: str
    target_type: str
    target_id: Optional[int] = None
    admin_user_id: Optional[int] = None
    detail_json: Optional[str] = None
    created_at: datetime
