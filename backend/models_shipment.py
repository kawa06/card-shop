"""Phase 3-9 outbound shipments (oripa-first; consolidatable later)."""

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


class Shipment(Base):
    """Physical outbound package independent of Order / OripaPurchase."""

    __tablename__ = "shipments"
    __table_args__ = (Index("ix_shipments_user_status", "user_id", "status"),)

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    status = Column(String(32), nullable=False, default="unshipped", index=True)
    shipping_carrier = Column(String(100), nullable=True)
    tracking_number = Column(String(100), nullable=True)
    shipping_method = Column(String(64), nullable=True)
    shipped_at = Column(DateTime, nullable=True)
    shipped_by_admin_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    # Address snapshot at create time
    postal_code = Column(String(20), nullable=True)
    country = Column(String(100), nullable=True)
    region = Column(String(100), nullable=True)
    city = Column(String(100), nullable=True)
    address_line1 = Column(String(255), nullable=True)
    address_line2 = Column(String(255), nullable=True)
    recipient_name = Column(String(100), nullable=True)
    phone_number = Column(String(40), nullable=True)
    note = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class ShipmentItem(Base):
    """Line in a shipment. Step 5: oripa_entry only; later: order_item."""

    __tablename__ = "shipment_items"
    __table_args__ = (
        UniqueConstraint("oripa_entry_id", name="uq_shipment_items_oripa_entry"),
        UniqueConstraint("order_item_id", name="uq_shipment_items_order_item"),
        Index("ix_shipment_items_shipment", "shipment_id"),
    )

    id = Column(Integer, primary_key=True, index=True)
    shipment_id = Column(Integer, ForeignKey("shipments.id", ondelete="CASCADE"), nullable=False)
    item_type = Column(String(32), nullable=False, default="oripa_entry", index=True)
    oripa_entry_id = Column(Integer, ForeignKey("oripa_entries.id"), nullable=True, index=True)
    order_item_id = Column(Integer, ForeignKey("order_items.id"), nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class ShipmentLog(Base):
    __tablename__ = "shipment_logs"

    id = Column(Integer, primary_key=True, index=True)
    shipment_id = Column(Integer, ForeignKey("shipments.id", ondelete="CASCADE"), nullable=False, index=True)
    event_type = Column(String(64), nullable=False, index=True)
    from_status = Column(String(32), nullable=True)
    to_status = Column(String(32), nullable=True)
    tracking_number = Column(String(100), nullable=True)
    shipping_carrier = Column(String(100), nullable=True)
    admin_user_id = Column(Integer, nullable=True, index=True)
    note = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)


class ShipmentBarcode(Base):
    __tablename__ = "shipment_barcodes"

    id = Column(Integer, primary_key=True, index=True)
    scan_token = Column(String(64), unique=True, nullable=False, index=True)
    barcode_type = Column(String(32), nullable=False, default="shipment_fulfillment", index=True)
    shipment_id = Column(Integer, ForeignKey("shipments.id", ondelete="CASCADE"), nullable=False, index=True)
    human_readable = Column(String(64), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    revoked_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
