"""Phase 3-8: Inventory alert and restock models (additive only)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)

from database import Base


class InventoryAlert(Base):
    __tablename__ = "inventory_alerts"
    __table_args__ = (
        Index("ix_inventory_alerts_product_status", "product_id", "status"),
        Index("ix_inventory_alerts_type_status", "alert_type", "status"),
        Index("ix_inventory_alerts_created", "created_at"),
    )

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("cards.id"), nullable=False, index=True)
    alert_type = Column(String(32), nullable=False, index=True)  # low_stock|out_of_stock
    stock_quantity = Column(Integer, nullable=False)
    threshold = Column(Integer, nullable=False)
    status = Column(String(16), nullable=False, default="open", index=True)  # open|resolved
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    resolved_at = Column(DateTime, nullable=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    resolved_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    metadata_json = Column(Text, nullable=True)


class InventoryRestock(Base):
    __tablename__ = "inventory_restocks"
    __table_args__ = (
        Index("ix_inventory_restocks_product_status", "product_id", "status"),
        Index("ix_inventory_restocks_created", "created_at"),
    )

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("cards.id"), nullable=False, index=True)
    requested_quantity = Column(Integer, nullable=False)
    received_quantity = Column(Integer, nullable=True)
    status = Column(String(16), nullable=False, default="requested", index=True)
    note = Column(Text, nullable=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    completed_at = Column(DateTime, nullable=True)


class InventoryAuditLog(Base):
    __tablename__ = "inventory_audit_logs"
    __table_args__ = (Index("ix_inventory_audit_logs_created", "created_at"),)

    id = Column(Integer, primary_key=True, index=True)
    actor_admin_user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    action = Column(String(64), nullable=False, index=True)
    product_id = Column(Integer, ForeignKey("cards.id"), nullable=True, index=True)
    restock_id = Column(Integer, ForeignKey("inventory_restocks.id"), nullable=True, index=True)
    alert_id = Column(Integer, ForeignKey("inventory_alerts.id"), nullable=True, index=True)
    before_json = Column(Text, nullable=True)
    after_json = Column(Text, nullable=True)
    reason = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
