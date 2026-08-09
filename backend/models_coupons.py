"""Phase 3-5: Coupon models (additive only)."""

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


class Coupon(Base):
    __tablename__ = "coupons"
    __table_args__ = (
        UniqueConstraint("code", name="uq_coupons_code"),
        Index("ix_coupons_active_ends", "is_active", "ends_at"),
    )

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(64), nullable=False, index=True)
    name = Column(String(128), nullable=False)
    description = Column(Text, nullable=True)
    coupon_type = Column(String(32), nullable=False, index=True)  # fixed_amount|percent|free_shipping
    audience = Column(String(16), nullable=False, default="public")  # public|assigned
    amount_yen = Column(Integer, nullable=True)
    percent_off = Column(Integer, nullable=True)
    max_discount_yen = Column(Integer, nullable=True)
    min_subtotal_yen = Column(Integer, default=0, nullable=False)
    max_uses_total = Column(Integer, nullable=True)
    max_uses_per_user = Column(Integer, default=1, nullable=False)
    starts_at = Column(DateTime, nullable=True)
    ends_at = Column(DateTime, nullable=True)
    card_ids_json = Column(Text, nullable=True)
    category_ids_json = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class CouponAssignment(Base):
    __tablename__ = "coupon_assignments"
    __table_args__ = (
        UniqueConstraint("coupon_id", "user_id", name="uq_coupon_assignments_coupon_user"),
        Index("ix_coupon_assignments_user", "user_id"),
    )

    id = Column(Integer, primary_key=True, index=True)
    coupon_id = Column(Integer, ForeignKey("coupons.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    assigned_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    assigned_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    note = Column(Text, nullable=True)


class CouponRedemption(Base):
    __tablename__ = "coupon_redemptions"
    __table_args__ = (
        UniqueConstraint("order_id", name="uq_coupon_redemptions_order_id"),
        UniqueConstraint("idempotency_key", name="uq_coupon_redemptions_idempotency_key"),
        Index("ix_coupon_redemptions_user_coupon", "user_id", "coupon_id"),
    )

    id = Column(Integer, primary_key=True, index=True)
    coupon_id = Column(Integer, ForeignKey("coupons.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False)
    discount_amount = Column(Integer, default=0, nullable=False)
    shipping_discount = Column(Integer, default=0, nullable=False)
    status = Column(String(16), default="reserved", nullable=False, index=True)
    idempotency_key = Column(String(128), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class CouponAuditLog(Base):
    __tablename__ = "coupon_audit_logs"
    __table_args__ = (Index("ix_coupon_audit_logs_created", "created_at"),)

    id = Column(Integer, primary_key=True, index=True)
    actor_admin_user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    action = Column(String(64), nullable=False, index=True)
    coupon_id = Column(Integer, ForeignKey("coupons.id"), nullable=True, index=True)
    target_user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    before_json = Column(Text, nullable=True)
    after_json = Column(Text, nullable=True)
    reason = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
