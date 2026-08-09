"""Phase 3-9: Numbered online Oripa models (additive only)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)

from database import Base


class Oripa(Base):
    __tablename__ = "oripas"
    __table_args__ = (
        Index("ix_oripas_sale_window", "sale_start_at", "sale_end_at"),
    )

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    price_per_entry = Column(Float, nullable=False)
    total_entries = Column(Integer, nullable=False)
    status = Column(String(32), nullable=False, default="draft", index=True)
    sale_start_at = Column(DateTime, nullable=True)
    sale_end_at = Column(DateTime, nullable=True)
    max_entries_per_purchase = Column(Integer, nullable=False, default=10)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)


class OripaEntry(Base):
    __tablename__ = "oripa_entries"
    __table_args__ = (
        UniqueConstraint("oripa_id", "entry_number", name="uq_oripa_entry_number"),
        Index("ix_oripa_entries_oripa_assignment", "oripa_id", "assignment_status"),
    )

    id = Column(Integer, primary_key=True, index=True)
    oripa_id = Column(Integer, ForeignKey("oripas.id", ondelete="CASCADE"), nullable=False, index=True)
    entry_number = Column(Integer, nullable=False)
    linked_product_id = Column(Integer, ForeignKey("cards.id"), nullable=True, index=True)
    assignment_status = Column(String(32), nullable=False, default="available", index=True)
    assigned_user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    assigned_order_id = Column(Integer, ForeignKey("orders.id"), nullable=True, index=True)
    assigned_purchase_id = Column(Integer, nullable=True, index=True)
    assigned_at = Column(DateTime, nullable=True)
    shipment_status = Column(String(32), nullable=False, default="held", index=True)
    shipment_id = Column(Integer, nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class OripaAuditLog(Base):
    __tablename__ = "oripa_audit_logs"
    __table_args__ = (Index("ix_oripa_audit_logs_created", "created_at"),)

    id = Column(Integer, primary_key=True, index=True)
    actor_admin_user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    action = Column(String(64), nullable=False, index=True)
    oripa_id = Column(Integer, ForeignKey("oripas.id"), nullable=True, index=True)
    entry_id = Column(Integer, ForeignKey("oripa_entries.id"), nullable=True, index=True)
    before_json = Column(Text, nullable=True)
    after_json = Column(Text, nullable=True)
    reason = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class OripaPurchase(Base):
    """Purchase of N entries; assignment is idempotent via idempotency_key."""

    __tablename__ = "oripa_purchases"
    __table_args__ = (
        Index("ix_oripa_purchases_oripa_user", "oripa_id", "user_id"),
        Index("ix_oripa_purchases_created", "created_at"),
    )

    id = Column(Integer, primary_key=True, index=True)
    oripa_id = Column(Integer, ForeignKey("oripas.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    quantity = Column(Integer, nullable=False)
    status = Column(String(32), nullable=False, default="completed", index=True)
    # pending | completed | failed | cancelled
    idempotency_key = Column(String(128), nullable=True, unique=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=True, index=True)
    unit_price = Column(Float, nullable=True)
    total_amount = Column(Float, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
