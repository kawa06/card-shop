"""Phase 3-4: Points ledger models (additive only)."""

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
from sqlalchemy.orm import relationship

from database import Base


class PointAccount(Base):
    __tablename__ = "point_accounts"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False, index=True)
    available_points = Column(Integer, default=0, nullable=False)
    reserved_points = Column(Integer, default=0, nullable=False)
    lifetime_earned = Column(Integer, default=0, nullable=False)
    lifetime_used = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class PointTransaction(Base):
    __tablename__ = "point_transactions"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_point_transactions_idempotency_key"),
        Index("ix_point_transactions_user_created", "user_id", "created_at"),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    type = Column(String(32), nullable=False, index=True)
    amount = Column(Integer, nullable=False)
    balance_after = Column(Integer, nullable=False)
    source_type = Column(String(32), nullable=True)
    source_id = Column(Integer, nullable=True)
    idempotency_key = Column(String(128), nullable=False)
    expires_at = Column(DateTime, nullable=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    metadata_json = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)


class PointExpirationLot(Base):
    __tablename__ = "point_expiration_lots"
    __table_args__ = (
        Index("ix_point_expiration_lots_user_expires", "user_id", "expires_at"),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    transaction_id = Column(Integer, ForeignKey("point_transactions.id"), nullable=False, index=True)
    original_amount = Column(Integer, nullable=False)
    remaining_amount = Column(Integer, nullable=False)
    expires_at = Column(DateTime, nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    transaction = relationship("PointTransaction")


class PointReservation(Base):
    __tablename__ = "point_reservations"
    __table_args__ = (
        UniqueConstraint("order_id", name="uq_point_reservations_order_id"),
        UniqueConstraint("idempotency_key", name="uq_point_reservations_idempotency_key"),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False)
    amount = Column(Integer, nullable=False)
    status = Column(String(16), default="pending", nullable=False, index=True)
    lot_allocations_json = Column(Text, nullable=False, default="[]")
    idempotency_key = Column(String(128), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class PointSettings(Base):
    __tablename__ = "point_settings"

    id = Column(Integer, primary_key=True, default=1)
    shop_id = Column(Integer, default=1, nullable=False, unique=True)
    enabled = Column(Boolean, default=True, nullable=False)
    earn_rate_percent = Column(Integer, default=1, nullable=False)
    expiration_days = Column(Integer, nullable=True)
    max_points_per_order = Column(Integer, default=10000, nullable=False)
    max_usage_percent = Column(Integer, default=50, nullable=False)
    points_apply_to_shipping = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class PointAuditLog(Base):
    __tablename__ = "point_audit_logs"
    __table_args__ = (
        Index("ix_point_audit_logs_created", "created_at"),
    )

    id = Column(Integer, primary_key=True, index=True)
    actor_admin_user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    action = Column(String(64), nullable=False, index=True)
    target_user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    transaction_id = Column(Integer, ForeignKey("point_transactions.id"), nullable=True)
    before_json = Column(Text, nullable=True)
    after_json = Column(Text, nullable=True)
    reason = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
