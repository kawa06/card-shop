"""Admin email management schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class EmailBrandSettingsOut(BaseModel):
    logo_url: Optional[str] = None
    sender_name: Optional[str] = None
    brand_color: Optional[str] = None
    footer_text: Optional[str] = None
    sns_links_json: Optional[str] = None
    terms_url: Optional[str] = None
    contact_url: Optional[str] = None
    privacy_url: Optional[str] = None
    company_name: Optional[str] = None
    company_address: Optional[str] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    email_signature_html: Optional[str] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class EmailBrandSettingsUpdate(BaseModel):
    logo_url: Optional[str] = None
    sender_name: Optional[str] = None
    brand_color: Optional[str] = None
    footer_text: Optional[str] = None
    sns_links_json: Optional[str] = None
    terms_url: Optional[str] = None
    contact_url: Optional[str] = None
    privacy_url: Optional[str] = None
    company_name: Optional[str] = None
    company_address: Optional[str] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    email_signature_html: Optional[str] = None


class EmailTemplateCreate(BaseModel):
    template_key: str = Field(..., min_length=3, max_length=64, pattern=r"^[a-z][a-z0-9_]*$")
    category: str = Field(..., min_length=2, max_length=32)
    name: str = Field(..., min_length=1, max_length=128)
    subject: str = Field(..., min_length=1, max_length=255)
    preheader: Optional[str] = None
    html_body: str = Field(..., min_length=1)
    text_body: Optional[str] = None
    variables_hint: Optional[str] = None
    is_active: bool = True


class EmailTemplateDuplicateIn(BaseModel):
    new_template_key: str = Field(..., min_length=3, max_length=64, pattern=r"^[a-z][a-z0-9_]*$")
    name: str | None = None
    category: str | None = None


class EmailTemplateOut(BaseModel):
    id: int
    template_key: str
    category: str
    name: str
    subject: str
    preheader: Optional[str] = None
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
    preheader: Optional[str] = None
    html_body: Optional[str] = None
    text_body: Optional[str] = None
    variables_hint: Optional[str] = None
    is_active: Optional[bool] = None


class EmailTemplatePreviewIn(BaseModel):
    variables: dict[str, Any] = Field(default_factory=dict)
    subject: Optional[str] = None
    preheader: Optional[str] = None
    html_body: Optional[str] = None
    text_body: Optional[str] = None
    force_dark: bool = False


class EmailTemplatePreviewOut(BaseModel):
    subject: str
    preheader: Optional[str] = None
    html: str


class EmailTemplateVariablesOut(BaseModel):
    variables: list[str]
    aliases: dict[str, str]
    sample: dict[str, str]


class EmailCampaignOut(BaseModel):
    id: int
    template_key: str
    subject: str
    html_body: str
    reference_type: Optional[str] = None
    reference_id: Optional[str] = None
    target_description: Optional[str] = None
    recipient_count: int
    success_count: int
    failed_count: int
    status: str
    send_mode: str
    scheduled_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_by_user_id: Optional[int] = None
    created_at: datetime
    error_message: Optional[str] = None

    class Config:
        from_attributes = True


class EmailCampaignDetailOut(EmailCampaignOut):
    send_logs: list["EmailSendLogOut"] = Field(default_factory=list)


class AnnouncementEmailPreviewOut(BaseModel):
    subject: str
    html: str
    text: str = ""
    recipient_count: int
    target_description: str
    recipients_sample: list[str] = Field(default_factory=list)
    template_key: str = "broadcast_notice_important"
    template_name: str = ""
    audience_key: str = "all_verified"
    image_urls: list[str] = Field(default_factory=list)


class AnnouncementEmailSendIn(BaseModel):
    send_mode: str = "immediate"
    scheduled_at: Optional[datetime] = None
    idempotency_key: Optional[str] = None
    confirm: bool = False
    audience_key: Optional[str] = None
    audience_params: dict[str, Any] = Field(default_factory=dict)
    template_key: Optional[str] = None


class EmailTestSendIn(BaseModel):
    to_email: str
    variables: dict[str, Any] = Field(default_factory=dict)


class BuybackEmailAutoSendOut(BaseModel):
    settings: dict[str, bool]


class BuybackEmailAutoSendUpdateIn(BaseModel):
    settings: dict[str, bool] = Field(default_factory=dict)


class KycEmailAutoSendOut(BaseModel):
    settings: dict[str, bool]


class KycEmailAutoSendUpdateIn(BaseModel):
    settings: dict[str, bool] = Field(default_factory=dict)


class MemberEmailAutoSendOut(BaseModel):
    settings: dict[str, bool]


class MemberEmailAutoSendUpdateIn(BaseModel):
    settings: dict[str, bool] = Field(default_factory=dict)


class AdminMemberResendEmailIn(BaseModel):
    event_key: str
    verify_url: str | None = None
    reset_url: str | None = None


class LoyaltyEmailAutoSendOut(BaseModel):
    settings: dict[str, bool]


class LoyaltyEmailAutoSendUpdateIn(BaseModel):
    settings: dict[str, bool] = Field(default_factory=dict)


class AdminLoyaltyResendEmailIn(BaseModel):
    event_key: str


class InquiryEmailAutoSendOut(BaseModel):
    settings: dict[str, bool]


class InquiryEmailAutoSendUpdateIn(BaseModel):
    settings: dict[str, bool] = Field(default_factory=dict)


class AdminInquiryResendEmailIn(BaseModel):
    event_key: str
    reply_text: str | None = None


class AdminNotifyEmailAutoSendOut(BaseModel):
    settings: dict[str, bool]


class AdminNotifyEmailAutoSendUpdateIn(BaseModel):
    settings: dict[str, bool] = Field(default_factory=dict)


class AdminNotifyChannelOut(BaseModel):
    settings: dict[str, str]


class AdminNotifyChannelUpdateIn(BaseModel):
    settings: dict[str, str] = Field(default_factory=dict)


class AdminNotifyRecipientsOut(BaseModel):
    settings: dict[str, dict]


class AdminNotifyRecipientsUpdateIn(BaseModel):
    settings: dict[str, dict] = Field(default_factory=dict)


class AdminNotifyResendIn(BaseModel):
    event_key: str


class AdminInAppNotificationOut(BaseModel):
    id: int
    event_key: str
    title: str
    body: str
    reference_type: str | None = None
    reference_id: str | None = None
    is_read: bool
    read_at: datetime | None = None
    created_at: datetime

    class Config:
        from_attributes = True


class AdminIdentityResendEmailIn(BaseModel):
    event_key: str
    force: bool = True


class EmailSendLogOut(BaseModel):
    id: int
    template_key: Optional[str] = None
    campaign_id: Optional[int] = None
    recipient: str
    subject: str
    status: str
    provider_message_id: Optional[str] = None
    error_message: Optional[str] = None
    reference_type: Optional[str] = None
    reference_id: Optional[str] = None
    is_test: bool
    sent_by_user_id: Optional[int] = None
    retry_count: int = 0
    next_retry_at: Optional[datetime] = None
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
