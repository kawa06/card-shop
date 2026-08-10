"""Phase 3-9 oripa → shipment assignment (CAS, no double-ship)."""

from __future__ import annotations

import secrets
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

import models
import models_oripa
import models_shipment
from services.oripa_admin import OripaError, write_oripa_audit
from services.oripa_constants import (
    ENTRY_ASSIGNMENT_ASSIGNED,
    ENTRY_SHIPMENT_HELD,
    ENTRY_SHIPMENT_PENDING,
    ENTRY_SHIPMENT_SHIPPED,
    format_entry_number,
)

SHIPMENT_STATUSES = {
    "unshipped",
    "preparing",
    "packing",
    "shipped",
    "in_transit",
    "delivered",
    "received",
    "cancelled",
}


def append_shipment_log(
    db: Session,
    *,
    shipment: models_shipment.Shipment,
    event_type: str,
    from_status: Optional[str] = None,
    to_status: Optional[str] = None,
    tracking_number: Optional[str] = None,
    shipping_carrier: Optional[str] = None,
    admin_user_id: Optional[int] = None,
    note: Optional[str] = None,
) -> models_shipment.ShipmentLog:
    row = models_shipment.ShipmentLog(
        shipment_id=shipment.id,
        event_type=event_type,
        from_status=from_status,
        to_status=to_status,
        tracking_number=tracking_number if tracking_number is not None else shipment.tracking_number,
        shipping_carrier=shipping_carrier if shipping_carrier is not None else shipment.shipping_carrier,
        admin_user_id=admin_user_id,
        note=note,
    )
    db.add(row)
    db.flush()
    return row


def ensure_shipment_barcode(db: Session, *, shipment: models_shipment.Shipment) -> models_shipment.ShipmentBarcode:
    existing = (
        db.query(models_shipment.ShipmentBarcode)
        .filter(
            models_shipment.ShipmentBarcode.shipment_id == shipment.id,
            models_shipment.ShipmentBarcode.is_active.is_(True),
        )
        .first()
    )
    if existing:
        return existing
    token = secrets.token_urlsafe(24)
    row = models_shipment.ShipmentBarcode(
        scan_token=token,
        barcode_type="shipment_fulfillment",
        shipment_id=shipment.id,
        human_readable=f"SHP-{shipment.id}",
        is_active=True,
    )
    db.add(row)
    db.flush()
    return row


def create_oripa_shipment(
    db: Session,
    *,
    user_id: int,
    entry_ids: list[int],
    actor_admin_user_id: Optional[int] = None,
    note: Optional[str] = None,
) -> models_shipment.Shipment:
    return create_consolidated_shipment(
        db,
        user_id=user_id,
        entry_ids=entry_ids,
        order_ids=None,
        actor_admin_user_id=actor_admin_user_id,
        note=note,
    )


def create_consolidated_shipment(
    db: Session,
    *,
    user_id: int,
    entry_ids: Optional[list[int]] = None,
    order_ids: Optional[list[int]] = None,
    actor_admin_user_id: Optional[int] = None,
    note: Optional[str] = None,
) -> models_shipment.Shipment:
    """Create one physical package from held oripa entries and/or unpaid-not-shipped orders.

    Shipping-fee policy (Phase 3-9 minimal):
    - No automatic refund/recharge of order.shipping_fee when consolidating.
    - Already-paid order shipping fees stay as-is; consolidation is ops-only.
    """
    entry_ids = list(entry_ids or [])
    order_ids = list(order_ids or [])
    if not entry_ids and not order_ids:
        raise OripaError("発送する番号または注文を選択してください")
    if len(set(entry_ids)) != len(entry_ids):
        raise OripaError("番号の重複があります")
    if len(set(order_ids)) != len(order_ids):
        raise OripaError("注文の重複があります")

    user = db.query(models.User).filter(models.User.id == user_id).first()
    if user is None:
        raise OripaError("ユーザーが見つかりません", status_code=404)

    entries: list[models_oripa.OripaEntry] = []
    if entry_ids:
        entries = (
            db.query(models_oripa.OripaEntry)
            .filter(models_oripa.OripaEntry.id.in_(entry_ids))
            .with_for_update()
            .all()
        )
        if len(entries) != len(entry_ids):
            raise OripaError("一部の番号が見つかりません", status_code=404)
        for entry in entries:
            if entry.assigned_user_id != user_id:
                raise OripaError("他ユーザーの番号は発送できません", status_code=403)
            if entry.assignment_status != ENTRY_ASSIGNMENT_ASSIGNED:
                raise OripaError(f"未割当の番号は発送できません: {format_entry_number(entry.entry_number)}")
            if entry.shipment_status != ENTRY_SHIPMENT_HELD or entry.shipment_id is not None:
                raise OripaError(
                    f"保管中でない番号は発送できません: {format_entry_number(entry.entry_number)}",
                    status_code=409,
                )

    orders: list[models.Order] = []
    order_items: list[models.OrderItem] = []
    if order_ids:
        orders = (
            db.query(models.Order)
            .filter(models.Order.id.in_(order_ids))
            .with_for_update()
            .all()
        )
        if len(orders) != len(order_ids):
            raise OripaError("一部の注文が見つかりません", status_code=404)
        shippable = {"unshipped", "preparing", "packing"}
        for order in orders:
            if order.user_id != user_id:
                raise OripaError("他ユーザーの注文はまとめ発送できません", status_code=403)
            if (order.payment_status or "").lower() != "paid":
                raise OripaError(f"未払い注文はまとめ発送できません: order={order.id}", status_code=409)
            if order.status == models.OrderStatus.cancelled:
                raise OripaError(f"取消済み注文はまとめられません: order={order.id}", status_code=409)
            status = (order.shipping_status or "unshipped").lower()
            if status not in shippable:
                raise OripaError(f"発送済み/取消の注文はまとめられません: order={order.id}", status_code=409)
            if status == "shipped":
                raise OripaError(f"発送済み注文は不可: order={order.id}", status_code=409)
            items = (
                db.query(models.OrderItem)
                .filter(models.OrderItem.order_id == order.id)
                .with_for_update()
                .all()
            )
            if not items:
                raise OripaError(f"注文明細が空です: order={order.id}")
            for oi in items:
                exists = (
                    db.query(models_shipment.ShipmentItem.id)
                    .filter(models_shipment.ShipmentItem.order_item_id == oi.id)
                    .first()
                )
                if exists:
                    raise OripaError(f"既に別Shipmentに含まれる明細です: order_item={oi.id}", status_code=409)
            order_items.extend(items)

    shipment = models_shipment.Shipment(
        user_id=user_id,
        status="unshipped",
        postal_code=user.postal_code,
        country=user.country,
        region=user.region,
        city=user.city,
        address_line1=user.address_line1,
        address_line2=user.address_line2,
        recipient_name=user.name,
        phone_number=user.phone_number,
        note=note,
    )
    db.add(shipment)
    db.flush()

    for entry in entries:
        updated = (
            db.query(models_oripa.OripaEntry)
            .filter(
                models_oripa.OripaEntry.id == entry.id,
                models_oripa.OripaEntry.shipment_status == ENTRY_SHIPMENT_HELD,
                models_oripa.OripaEntry.shipment_id.is_(None),
                models_oripa.OripaEntry.assigned_user_id == user_id,
            )
            .update(
                {
                    models_oripa.OripaEntry.shipment_status: ENTRY_SHIPMENT_PENDING,
                    models_oripa.OripaEntry.shipment_id: shipment.id,
                    models_oripa.OripaEntry.updated_at: datetime.utcnow(),
                },
                synchronize_session=False,
            )
        )
        if updated != 1:
            raise OripaError(
                f"番号の同時発送競合: {format_entry_number(entry.entry_number)}",
                status_code=409,
            )
        db.add(
            models_shipment.ShipmentItem(
                shipment_id=shipment.id,
                item_type="oripa_entry",
                oripa_entry_id=entry.id,
            )
        )

    for oi in order_items:
        db.add(
            models_shipment.ShipmentItem(
                shipment_id=shipment.id,
                item_type="order_item",
                order_item_id=oi.id,
            )
        )

    # Mark linked orders as preparing (do not change paid amounts / shipping_fee)
    for order in orders:
        if (order.shipping_status or "unshipped") == "unshipped":
            order.shipping_status = "preparing"
        if order.status in (models.OrderStatus.pending, models.OrderStatus.processing):
            order.status = models.OrderStatus.processing

    append_shipment_log(
        db,
        shipment=shipment,
        event_type="created",
        to_status=shipment.status,
        admin_user_id=actor_admin_user_id,
        note=f"entries={entry_ids}; orders={order_ids}",
    )
    ensure_shipment_barcode(db, shipment=shipment)
    write_oripa_audit(
        db,
        action="shipment.create",
        actor_admin_user_id=actor_admin_user_id,
        after={
            "shipment_id": shipment.id,
            "entry_ids": entry_ids,
            "order_ids": order_ids,
            "user_id": user_id,
            "shipping_fee_policy": "no_refund_no_recharge",
        },
    )
    db.flush()
    return shipment


def update_shipment(
    db: Session,
    shipment_id: int,
    *,
    actor_admin_user_id: Optional[int] = None,
    **fields,
) -> models_shipment.Shipment:
    shipment = (
        db.query(models_shipment.Shipment)
        .filter(models_shipment.Shipment.id == shipment_id)
        .with_for_update()
        .first()
    )
    if shipment is None:
        raise OripaError("Shipment が見つかりません", status_code=404)

    data = {k: v for k, v in fields.items() if v is not None or k in fields}
    # allow explicit null? use exclude_unset at route layer
    prev_status = shipment.status
    prev_tracking = shipment.tracking_number

    if "status" in fields and fields["status"] is not None:
        if fields["status"] not in SHIPMENT_STATUSES:
            raise OripaError("無効な発送ステータスです")
        # Prevent re-ship notify loop: already shipped stays shipped unless cancelled
        if shipment.status == "shipped" and fields["status"] == "shipped":
            pass
        shipment.status = fields["status"]

    for key in (
        "shipping_carrier",
        "tracking_number",
        "shipping_method",
        "note",
        "postal_code",
        "country",
        "region",
        "city",
        "address_line1",
        "address_line2",
        "recipient_name",
        "phone_number",
    ):
        if key in fields:
            setattr(shipment, key, fields[key])

    first_ship = False
    if shipment.status == "shipped":
        if shipment.shipped_at is None:
            shipment.shipped_at = datetime.utcnow()
            first_ship = True
        if actor_admin_user_id and shipment.shipped_by_admin_id is None:
            shipment.shipped_by_admin_id = actor_admin_user_id
        # Mark entries shipped once
        db.query(models_oripa.OripaEntry).filter(
            models_oripa.OripaEntry.shipment_id == shipment.id,
            models_oripa.OripaEntry.shipment_status == ENTRY_SHIPMENT_PENDING,
        ).update(
            {
                models_oripa.OripaEntry.shipment_status: ENTRY_SHIPMENT_SHIPPED,
                models_oripa.OripaEntry.updated_at: datetime.utcnow(),
            },
            synchronize_session=False,
        )
        # Sync linked normal orders (fulfillment status only; no fee changes)
        if first_ship:
            order_item_ids = [
                row.order_item_id
                for row in db.query(models_shipment.ShipmentItem)
                .filter(
                    models_shipment.ShipmentItem.shipment_id == shipment.id,
                    models_shipment.ShipmentItem.item_type == "order_item",
                )
                .all()
                if row.order_item_id is not None
            ]
            if order_item_ids:
                order_ids = {
                    oi.order_id
                    for oi in db.query(models.OrderItem)
                    .filter(models.OrderItem.id.in_(order_item_ids))
                    .all()
                }
                for oid in order_ids:
                    order = db.query(models.Order).filter(models.Order.id == oid).first()
                    if order is None:
                        continue
                    order.shipping_status = "shipped"
                    if order.status != models.OrderStatus.cancelled:
                        order.status = models.OrderStatus.shipped
                    order.tracking_number = shipment.tracking_number or order.tracking_number
                    order.shipping_carrier = shipment.shipping_carrier or order.shipping_carrier
                    if order.shipped_at is None:
                        order.shipped_at = shipment.shipped_at
                    if actor_admin_user_id and order.shipped_by_admin_id is None:
                        order.shipped_by_admin_id = actor_admin_user_id

    if shipment.status in ("preparing", "packing") and prev_status == "unshipped":
        ensure_shipment_barcode(db, shipment=shipment)

    status_changed = prev_status != shipment.status
    tracking_changed = prev_tracking != shipment.tracking_number
    if status_changed or tracking_changed or data:
        append_shipment_log(
            db,
            shipment=shipment,
            event_type="shipping_updated",
            from_status=prev_status,
            to_status=shipment.status,
            admin_user_id=actor_admin_user_id,
        )

    write_oripa_audit(
        db,
        action="shipment.update",
        actor_admin_user_id=actor_admin_user_id,
        after={
            "shipment_id": shipment.id,
            "status": shipment.status,
            "tracking_number": shipment.tracking_number,
            "first_ship": first_ship,
        },
    )
    db.flush()
    return shipment


def list_shipment_items(db: Session, shipment_id: int) -> list[models_shipment.ShipmentItem]:
    return (
        db.query(models_shipment.ShipmentItem)
        .filter(models_shipment.ShipmentItem.shipment_id == shipment_id)
        .order_by(models_shipment.ShipmentItem.id.asc())
        .all()
    )


def shipment_entry_labels(db: Session, shipment_id: int) -> list[str]:
    rows = (
        db.query(models_oripa.OripaEntry)
        .filter(models_oripa.OripaEntry.shipment_id == shipment_id)
        .order_by(models_oripa.OripaEntry.entry_number.asc())
        .all()
    )
    return [format_entry_number(r.entry_number) for r in rows]
