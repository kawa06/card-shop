"""Phase 3-2: Live auction domain models (additive only)."""

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


class LiveAuction(Base):
    __tablename__ = "live_auctions"

    id = Column(Integer, primary_key=True, index=True)
    stream_id = Column(Integer, ForeignKey("live_streams.id"), nullable=False, index=True)
    live_product_id = Column(Integer, ForeignKey("live_products.id"), nullable=False, index=True)
    status = Column(String(16), default="draft", nullable=False, index=True)
    start_price = Column(Integer, nullable=False)
    current_price = Column(Integer, nullable=True)
    min_bid_increment = Column(Integer, default=100, nullable=False)
    buy_now_price = Column(Integer, nullable=True)
    scheduled_start_at = Column(DateTime, nullable=True)
    scheduled_end_at = Column(DateTime, nullable=True)
    ends_at = Column(DateTime, nullable=True, index=True)
    extension_seconds = Column(Integer, default=30, nullable=False)
    auto_extend_enabled = Column(Boolean, default=True, nullable=False)
    max_extensions = Column(Integer, default=10, nullable=False)
    extension_count = Column(Integer, default=0, nullable=False)
    trigger_remaining_seconds = Column(Integer, default=30, nullable=False)
    winner_user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    winning_amount = Column(Integer, nullable=True)
    bid_count = Column(Integer, default=0, nullable=False)
    bidder_count = Column(Integer, default=0, nullable=False)
    created_by_admin_id = Column(Integer, ForeignKey("admin_users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    product = relationship("LiveProduct", foreign_keys=[live_product_id])
    bids = relationship("LiveBid", back_populates="auction", cascade="all, delete-orphan")
    purchase_right = relationship(
        "LiveAuctionPurchaseRight",
        back_populates="auction",
        uselist=False,
        cascade="all, delete-orphan",
    )


class LiveBid(Base):
    __tablename__ = "live_bids"

    id = Column(Integer, primary_key=True, index=True)
    auction_id = Column(Integer, ForeignKey("live_auctions.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    amount = Column(Integer, nullable=False)
    status = Column(String(16), default="active", nullable=False, index=True)
    idempotency_key = Column(String(64), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    auction = relationship("LiveAuction", back_populates="bids")

    __table_args__ = (
        UniqueConstraint("auction_id", "idempotency_key", name="uq_live_bids_auction_idempotency"),
    )


class LiveBidLog(Base):
    __tablename__ = "live_bid_logs"

    id = Column(Integer, primary_key=True, index=True)
    auction_id = Column(Integer, ForeignKey("live_auctions.id"), nullable=False, index=True)
    bid_id = Column(Integer, ForeignKey("live_bids.id"), nullable=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    action = Column(String(32), nullable=False, index=True)
    amount = Column(Integer, nullable=True)
    detail_json = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)


class LiveBidInvalidation(Base):
    __tablename__ = "live_bid_invalidations"

    id = Column(Integer, primary_key=True, index=True)
    bid_id = Column(Integer, ForeignKey("live_bids.id"), nullable=False, index=True)
    reason = Column(String(255), nullable=False)
    invalidated_by_admin_id = Column(Integer, ForeignKey("admin_users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class LiveAuctionExtension(Base):
    __tablename__ = "live_auction_extensions"

    id = Column(Integer, primary_key=True, index=True)
    auction_id = Column(Integer, ForeignKey("live_auctions.id"), nullable=False, index=True)
    previous_ends_at = Column(DateTime, nullable=False)
    new_ends_at = Column(DateTime, nullable=False)
    trigger_bid_id = Column(Integer, ForeignKey("live_bids.id"), nullable=True)
    extension_number = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class LiveAuctionPurchaseRight(Base):
    __tablename__ = "live_auction_purchase_rights"

    id = Column(Integer, primary_key=True, index=True)
    auction_id = Column(Integer, ForeignKey("live_auctions.id"), nullable=False, unique=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    live_product_id = Column(Integer, ForeignKey("live_products.id"), nullable=False, index=True)
    card_id = Column(Integer, ForeignKey("cards.id"), nullable=False, index=True)
    winning_price = Column(Integer, nullable=False)
    status = Column(String(16), default="active", nullable=False, index=True)
    expires_at = Column(DateTime, nullable=False, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    auction = relationship("LiveAuction", back_populates="purchase_right")


class LiveAuctionSettings(Base):
    __tablename__ = "live_auction_settings"

    id = Column(Integer, primary_key=True, index=True)
    shop_id = Column(Integer, default=1, nullable=False, unique=True, index=True)
    purchase_window_seconds = Column(Integer, default=300, nullable=False)
    default_min_bid_increment = Column(Integer, default=100, nullable=False)
    default_extension_seconds = Column(Integer, default=30, nullable=False)
    default_trigger_remaining_seconds = Column(Integer, default=30, nullable=False)
    default_max_extensions = Column(Integer, default=10, nullable=False)
    default_auto_extend_enabled = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
