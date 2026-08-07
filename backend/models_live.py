"""Phase 3-1: Live sales domain models (additive only)."""

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


class LiveStream(Base):
    __tablename__ = "live_streams"

    id = Column(Integer, primary_key=True, index=True)
    shop_id = Column(Integer, default=1, nullable=False, index=True)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    thumbnail_url = Column(String(512), nullable=True)
    embed_url = Column(String(512), nullable=True)
    status = Column(String(32), default="draft", nullable=False, index=True)
    visibility = Column(String(16), default="public", nullable=False)
    scheduled_at = Column(DateTime, nullable=True)
    started_at = Column(DateTime, nullable=True)
    ended_at = Column(DateTime, nullable=True)
    created_by_admin_id = Column(Integer, ForeignKey("admin_users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    offers_enabled = Column(Boolean, default=True, nullable=False)

    products = relationship(
        "LiveProduct",
        back_populates="stream",
        foreign_keys="LiveProduct.stream_id",
        cascade="all, delete-orphan",
    )
    comments = relationship("LiveComment", back_populates="stream", cascade="all, delete-orphan")


class LiveProduct(Base):
    __tablename__ = "live_products"
    __table_args__ = (UniqueConstraint("stream_id", "card_id", name="uq_live_products_stream_card"),)

    id = Column(Integer, primary_key=True, index=True)
    stream_id = Column(Integer, ForeignKey("live_streams.id"), nullable=False, index=True)
    card_id = Column(Integer, ForeignKey("cards.id"), nullable=False, index=True)
    sort_order = Column(Integer, default=0, nullable=False)
    display_price = Column(Integer, nullable=True)
    is_active = Column(Boolean, default=False, nullable=False)
    is_pinned = Column(Boolean, default=False, nullable=False)
    offers_enabled = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    stream = relationship("LiveStream", back_populates="products", foreign_keys=[stream_id])
    card = relationship("Card", foreign_keys=[card_id])


class LiveComment(Base):
    __tablename__ = "live_comments"

    id = Column(Integer, primary_key=True, index=True)
    stream_id = Column(Integer, ForeignKey("live_streams.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    sender_type = Column(String(16), default="customer", nullable=False)
    sender_admin_id = Column(Integer, ForeignKey("admin_users.id"), nullable=True)
    message = Column(Text, nullable=False)
    is_pinned = Column(Boolean, default=False, nullable=False)
    deleted_at = Column(DateTime, nullable=True)
    deleted_by_admin_id = Column(Integer, ForeignKey("admin_users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    edited_at = Column(DateTime, nullable=True)

    stream = relationship("LiveStream", back_populates="comments")
    reports = relationship("LiveCommentReport", back_populates="comment", cascade="all, delete-orphan")


class LiveCommentReport(Base):
    __tablename__ = "live_comment_reports"

    id = Column(Integer, primary_key=True, index=True)
    comment_id = Column(Integer, ForeignKey("live_comments.id"), nullable=False, index=True)
    reporter_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    reason = Column(String(255), nullable=True)
    status = Column(String(32), default="open", nullable=False, index=True)
    resolved_by_admin_id = Column(Integer, ForeignKey("admin_users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    comment = relationship("LiveComment", back_populates="reports")


class LiveUserMute(Base):
    __tablename__ = "live_user_mutes"
    __table_args__ = (UniqueConstraint("stream_id", "user_id", name="uq_live_user_mutes_stream_user"),)

    id = Column(Integer, primary_key=True, index=True)
    stream_id = Column(Integer, ForeignKey("live_streams.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    muted_until = Column(DateTime, nullable=True)
    muted_by_admin_id = Column(Integer, ForeignKey("admin_users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class LiveUserBan(Base):
    __tablename__ = "live_user_bans"

    id = Column(Integer, primary_key=True, index=True)
    stream_id = Column(Integer, ForeignKey("live_streams.id"), nullable=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    banned_until = Column(DateTime, nullable=True)
    reason = Column(String(255), nullable=True)
    banned_by_admin_id = Column(Integer, ForeignKey("admin_users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class LiveNgWord(Base):
    __tablename__ = "live_ng_words"

    id = Column(Integer, primary_key=True, index=True)
    word = Column(String(128), nullable=False, unique=True, index=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class LiveModerator(Base):
    __tablename__ = "live_moderators"
    __table_args__ = (
        UniqueConstraint("stream_id", "admin_user_id", name="uq_live_moderators_stream_admin"),
    )

    id = Column(Integer, primary_key=True, index=True)
    stream_id = Column(Integer, ForeignKey("live_streams.id"), nullable=True, index=True)
    admin_user_id = Column(Integer, ForeignKey("admin_users.id"), nullable=False, index=True)
    granted_by_admin_id = Column(Integer, ForeignKey("admin_users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class LiveModerationAuditLog(Base):
    __tablename__ = "live_moderation_audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    stream_id = Column(Integer, ForeignKey("live_streams.id"), nullable=True, index=True)
    action = Column(String(64), nullable=False)
    target_type = Column(String(32), nullable=False)
    target_id = Column(Integer, nullable=True)
    admin_user_id = Column(Integer, ForeignKey("admin_users.id"), nullable=True)
    detail_json = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
