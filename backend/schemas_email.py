"""Admin email management schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class EmailBrandSettingsOut(BaseModel):
    logo_url: Optional[str] = None
    footer_text: Optional[str] = None
    sns_links_json: Optional[str] = None
    terms_url: Optional[str] = None
    contact_url: Optional[str] = None
    privacy_url: Optional[str] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class EmailBrandSettingsUpdate(BaseModel):
    logo_url: Optional[str] = None
    footer_text: Optional[str] = None
    sns_links_json: Optional[str] = None
    terms_url: Optional[str] = None
    contact_url: Optional[str] = None
    privacy_url: Optional[str] = None


class EmailTemplateOut(BaseModel):
    id: int
    template_key: str
    category: str
    name: str
    subject: str
    html_body: str
    text_body: Optional[str] = None
    variables_hint: Optional[str] = None
    is_active: bool
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class EmailTemplateListItem(BaseModel):
    id: int
    template_key: str
    category: str
    name: str
    subject: str
    is_active: bool
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class EmailTemplateUpdate(BaseModel):
    name: Optional[str] = None
    subject: Optional[str] = None
    html_body: Optional[str] = None
    text_body: Optional[str] = None
    variables_hint: Optional[str] = None
    is_active: Optional[bool] = None


class EmailTemplatePreviewIn(BaseModel):
    variables: dict[str, Any] = Field(default_factory=dict)


class EmailTemplatePreviewOut(BaseModel):
    subject: str
    html: str


class EmailTestSendIn(BaseModel):
    to_email: str
    variables: dict[str, Any] = Field(default_factory=dict)


class EmailSendLogOut(BaseModel):
    id: int
    template_key: Optional[str] = None
    recipient: str
    subject: str
    status: str
    provider_message_id: Optional[str] = None
    error_message: Optional[str] = None
    reference_type: Optional[str] = None
    reference_id: Optional[str] = None
    is_test: bool
    created_at: datetime

    class Config:
        from_attributes = True


class LoginHistoryOut(BaseModel):
    id: int
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    method: str
    success: bool
    created_at: datetime

    class Config:
        from_attributes = True


class TwoFactorSettingsOut(BaseModel):
    enabled: bool
    method: Optional[str] = None


class TwoFactorToggleIn(BaseModel):
    enabled: bool


class OtpVerifyIn(BaseModel):
    challenge_id: int
    code: str
    user_id: int


class AuthChallengeOut(BaseModel):
    requires_2fa: bool = True
    challenge_id: int
    user_id: int
    message: str = "認証コードをメールで送信しました"
