"""Phase 3-3: Live offer domain models (additive only)."""

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


class LiveOffer(Base):
    __tablename__ = "live_offers"
    __table_args__ = (
        UniqueConstraint(
            "stream_id",
            "user_id",
            "idempotency_key",
            name="uq_live_offers_stream_user_idempotency",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    stream_id = Column(Integer, ForeignKey("live_streams.id"), nullable=False, index=True)
    live_product_id = Column(Integer, ForeignKey("live_products.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    amount = Column(Integer, nullable=False)
    status = Column(String(16), default="pending", nullable=False, index=True)
    idempotency_key = Column(String(64), nullable=True)
    review_note = Column(Text, nullable=True)
    reviewed_at = Column(DateTime, nullable=True)
    reviewed_by_admin_id = Column(Integer, ForeignKey("admin_users.id"), nullable=True)
    display_expires_at = Column(DateTime, nullable=True, index=True)
    purchase_expires_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    product = relationship("LiveProduct", foreign_keys=[live_product_id])
    purchase_right = relationship(
        "LiveOfferPurchaseRight",
        back_populates="offer",
        uselist=False,
        cascade="all, delete-orphan",
    )


class LiveOfferPurchaseRight(Base):
    __tablename__ = "live_offer_purchase_rights"

    id = Column(Integer, primary_key=True, index=True)
    offer_id = Column(Integer, ForeignKey("live_offers.id"), nullable=False, unique=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    live_product_id = Column(Integer, ForeignKey("live_products.id"), nullable=False, index=True)
    card_id = Column(Integer, ForeignKey("cards.id"), nullable=False, index=True)
    accepted_price = Column(Integer, nullable=False)
    status = Column(String(16), default="active", nullable=False, index=True)
    expires_at = Column(DateTime, nullable=False, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    offer = relationship("LiveOffer", back_populates="purchase_right")


class LiveOfferAuditLog(Base):
    __tablename__ = "live_offer_audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    stream_id = Column(Integer, ForeignKey("live_streams.id"), nullable=False, index=True)
    offer_id = Column(Integer, ForeignKey("live_offers.id"), nullable=False, index=True)
    action = Column(String(32), nullable=False, index=True)
    admin_user_id = Column(Integer, ForeignKey("admin_users.id"), nullable=True, index=True)
    before_status = Column(String(16), nullable=True)
    after_status = Column(String(16), nullable=True)
    detail_json = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)


class LiveOfferSettings(Base):
    __tablename__ = "live_offer_settings"

    id = Column(Integer, primary_key=True, index=True)
    shop_id = Column(Integer, default=1, nullable=False, unique=True, index=True)
    purchase_window_seconds = Column(Integer, default=300, nullable=False)
    display_ttl_seconds = Column(Integer, default=60, nullable=False)
    max_amount = Column(Integer, default=10000000, nullable=False)
    rate_limit_count = Column(Integer, default=10, nullable=False)
    rate_limit_window_seconds = Column(Integer, default=60, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
