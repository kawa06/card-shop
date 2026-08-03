"""Email templates, delivery logs, and customer auth security models."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from database import Base


class EmailBrandSettings(Base):
    __tablename__ = "email_brand_settings"

    id = Column(Integer, primary_key=True)
    logo_url = Column(String(512), nullable=True)
    sender_name = Column(String(128), nullable=True)
    brand_color = Column(String(16), nullable=True, default="#fbbf24")
    footer_text = Column(Text, nullable=True)
    sns_links_json = Column(Text, nullable=True)
    terms_url = Column(String(512), nullable=True)
    contact_url = Column(String(512), nullable=True)
    privacy_url = Column(String(512), nullable=True)
    company_name = Column(String(128), nullable=True)
    company_address = Column(Text, nullable=True)
    contact_email = Column(String(255), nullable=True)
    contact_phone = Column(String(32), nullable=True)
    email_signature_html = Column(Text, nullable=True)
    member_email_auto_send_json = Column(Text, nullable=True)
    loyalty_email_auto_send_json = Column(Text, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class EmailTemplate(Base):
    __tablename__ = "email_templates"
    __table_args__ = (UniqueConstraint("template_key", name="uq_email_templates_key"),)

    id = Column(Integer, primary_key=True)
    template_key = Column(String(64), nullable=False, index=True)
    category = Column(String(32), nullable=False, index=True)
    name = Column(String(128), nullable=False)
    subject = Column(String(255), nullable=False)
    preheader = Column(String(255), nullable=True)
    html_body = Column(Text, nullable=False)
    text_body = Column(Text, nullable=True)
    variables_hint = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class EmailCampaign(Base):
    __tablename__ = "email_campaigns"

    id = Column(Integer, primary_key=True)
    template_key = Column(String(64), nullable=False, index=True)
    subject = Column(String(255), nullable=False)
    html_body = Column(Text, nullable=False)
    reference_type = Column(String(64), nullable=True, index=True)
    reference_id = Column(String(64), nullable=True, index=True)
    target_description = Column(String(255), nullable=True)
    audience_key = Column(String(64), nullable=True)
    audience_params_json = Column(Text, nullable=True)
    recipient_count = Column(Integer, default=0, nullable=False)
    success_count = Column(Integer, default=0, nullable=False)
    failed_count = Column(Integer, default=0, nullable=False)
    status = Column(String(16), nullable=False, default="pending", index=True)
    send_mode = Column(String(16), nullable=False, default="immediate")
    scheduled_at = Column(DateTime, nullable=True, index=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    created_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    error_message = Column(Text, nullable=True)
    idempotency_key = Column(String(64), nullable=True, unique=True, index=True)


class EmailSendLog(Base):
    __tablename__ = "email_send_logs"

    id = Column(Integer, primary_key=True)
    template_key = Column(String(64), nullable=True, index=True)
    campaign_id = Column(Integer, ForeignKey("email_campaigns.id"), nullable=True, index=True)
    recipient = Column(String(255), nullable=False, index=True)
    subject = Column(String(255), nullable=False)
    html_body_snapshot = Column(Text, nullable=True)
    status = Column(String(16), nullable=False, default="pending", index=True)
    provider_message_id = Column(String(128), nullable=True)
    error_message = Column(Text, nullable=True)
    reference_type = Column(String(64), nullable=True, index=True)
    reference_id = Column(String(64), nullable=True, index=True)
    is_test = Column(Boolean, default=False, nullable=False)
    sent_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    retry_count = Column(Integer, default=0, nullable=False)
    next_retry_at = Column(DateTime, nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)


class EmailScheduledSend(Base):
    __tablename__ = "email_scheduled_sends"

    id = Column(Integer, primary_key=True)
    template_key = Column(String(64), nullable=False, index=True)
    campaign_id = Column(Integer, ForeignKey("email_campaigns.id"), nullable=True, index=True)
    recipient = Column(String(255), nullable=True)
    variables_json = Column(Text, nullable=True)
    scheduled_at = Column(DateTime, nullable=False, index=True)
    status = Column(String(16), nullable=False, default="pending", index=True)
    sent_at = Column(DateTime, nullable=True)
    error_message = Column(Text, nullable=True)
    created_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class LoginHistory(Base):
    __tablename__ = "login_histories"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    ip_address = Column(String(64), nullable=True)
    user_agent = Column(String(512), nullable=True)
    method = Column(String(16), nullable=False, default="legacy")
    success = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    user = relationship("User", backref="login_histories")


class UserOtpChallenge(Base):
    __tablename__ = "user_otp_challenges"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    code_hash = Column(String(128), nullable=False)
    link_token_hash = Column(String(128), nullable=True)
    purpose = Column(String(32), nullable=False, default="login_2fa")
    expires_at = Column(DateTime, nullable=False, index=True)
    consumed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", backref="otp_challenges")
