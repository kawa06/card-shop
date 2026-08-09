"""Phase 3-6: Customer notification models (additive only)."""

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
    Index,
)

from database import Base


class UserNotification(Base):
    __tablename__ = "user_notifications"
    __table_args__ = (
        UniqueConstraint("dedupe_key", name="uq_user_notifications_dedupe_key"),
        Index("ix_user_notifications_user_created", "user_id", "created_at"),
        Index("ix_user_notifications_user_unread", "user_id", "is_read"),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    type = Column(String(64), nullable=False, index=True)
    category = Column(String(32), nullable=False, default="order", index=True)
    title = Column(String(255), nullable=False)
    body = Column(Text, nullable=False)
    related_entity_type = Column(String(64), nullable=True)
    related_entity_id = Column(String(64), nullable=True)
    action_url = Column(String(512), nullable=True)
    priority = Column(String(16), nullable=False, default="normal")
    channel = Column(String(16), nullable=False, default="in_app")
    is_read = Column(Boolean, default=False, nullable=False)
    read_at = Column(DateTime, nullable=True)
    metadata_json = Column(Text, nullable=True)
    dedupe_key = Column(String(191), nullable=False)
    email_status = Column(String(32), nullable=True)  # none|skipped|sent|failed
    sent_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)


class UserNotificationSettings(Base):
    """Per-user channel + category toggles (defaults all on)."""

    __tablename__ = "user_notification_settings"

    user_id = Column(Integer, ForeignKey("users.id"), primary_key=True)
    in_app_enabled = Column(Boolean, default=True, nullable=False)
    email_enabled = Column(Boolean, default=True, nullable=False)

    order_in_app = Column(Boolean, default=True, nullable=False)
    order_email = Column(Boolean, default=True, nullable=False)
    shipping_in_app = Column(Boolean, default=True, nullable=False)
    shipping_email = Column(Boolean, default=True, nullable=False)
    appraisal_in_app = Column(Boolean, default=True, nullable=False)
    appraisal_email = Column(Boolean, default=True, nullable=False)
    live_in_app = Column(Boolean, default=True, nullable=False)
    live_email = Column(Boolean, default=True, nullable=False)
    auction_in_app = Column(Boolean, default=True, nullable=False)
    auction_email = Column(Boolean, default=True, nullable=False)
    campaign_in_app = Column(Boolean, default=True, nullable=False)
    campaign_email = Column(Boolean, default=True, nullable=False)

    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
