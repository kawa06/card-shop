"""Phase 3-9 Step 8: cancel / refund / shipment recovery (no number resale)."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

import models
import models_oripa
import models_shipment
from services.oripa_admin import OripaError, write_oripa_audit
from services.oripa_constants import (
    ENTRY_ASSIGNMENT_ASSIGNED,
    ENTRY_ASSIGNMENT_RETIRED,
    ENTRY_SHIPMENT_CANCELLED,
    ENTRY_SHIPMENT_HELD,
    ENTRY_SHIPMENT_PENDING,
    ENTRY_SHIPMENT_SHIPPED,
    ORIPA_PURCHASE_CANCELLED,
    ORIPA_PURCHASE_COMPLETED,
    ORIPA_PURCHASE_FAILED,
    format_entry_number,
)
from services.oripa_shipment import append_shipment_log


def _retire_entry(
    db: Session,
    entry: models_oripa.OripaEntry,
    *,
    now: datetime,
) -> None:
    """Retire an assigned entry permanently — never return to available."""
    entry.assignment_status = ENTRY_ASSIGNMENT_RETIRED
    entry.shipment_status = ENTRY_SHIPMENT_CANCELLED
    entry.shipment_id = None
    entry.updated_at = now
    # Keep assigned_user_id / linked_product_id / entry_number for audit & fairness.


def cancel_oripa_purchase(
    db: Session,
    *,
    purchase_id: int,
    actor_admin_user_id: Optional[int] = None,
    reason: Optional[str] = None,
) -> models_oripa.OripaPurchase:
    """Cancel a completed purchase and retire all non-shipped numbers (idempotent).

    Policy:
    - Numbers already shown to the user are NEVER returned to ``available``.
    - Shipped entries block full cancel (ops must handle post-ship refund outside resale).
    - Does not invent Stripe / points / coupon partial-refund restores.
    """
    purchase = (
        db.query(models_oripa.OripaPurchase)
        .filter(models_oripa.OripaPurchase.id == purchase_id)
        .with_for_update()
        .first()
    )
    if purchase is None:
        raise OripaError("購入が見つかりません", status_code=404)

    if purchase.status == ORIPA_PURCHASE_CANCELLED:
        return purchase
    if purchase.status == ORIPA_PURCHASE_FAILED:
        raise OripaError("失敗済み購入はキャンセル対象外です", status_code=409)
    if purchase.status != ORIPA_PURCHASE_COMPLETED:
        raise OripaError(f"この購入ステータスはキャンセルできません: {purchase.status}", status_code=409)

    entries = (
        db.query(models_oripa.OripaEntry)
        .filter(models_oripa.OripaEntry.assigned_purchase_id == purchase.id)
        .with_for_update()
        .all()
    )
    shipped = [e for e in entries if e.shipment_status == ENTRY_SHIPMENT_SHIPPED]
    if shipped:
        labels = ", ".join(format_entry_number(e.entry_number) for e in shipped[:5])
        raise OripaError(
            f"発送済み番号を含む購入は自動キャンセルできません: {labels}",
            status_code=409,
        )

    now = datetime.utcnow()
    pending_shipment_ids: set[int] = set()
    retired_ids: list[int] = []
    for entry in entries:
        if entry.assignment_status != ENTRY_ASSIGNMENT_ASSIGNED:
            continue
        if entry.shipment_id is not None and entry.shipment_status == ENTRY_SHIPMENT_PENDING:
            pending_shipment_ids.add(int(entry.shipment_id))
        _retire_entry(db, entry, now=now)
        retired_ids.append(entry.id)

    for sid in pending_shipment_ids:
        _detach_retired_from_shipment(db, shipment_id=sid, actor_admin_user_id=actor_admin_user_id)

    purchase.status = ORIPA_PURCHASE_CANCELLED
    purchase.updated_at = now

    write_oripa_audit(
        db,
        action="oripa_purchase_cancelled",
        actor_admin_user_id=actor_admin_user_id,
        oripa_id=purchase.oripa_id,
        after={
            "purchase_id": purchase.id,
            "retired_entry_ids": retired_ids,
            "resale": False,
            "reason": reason,
        },
        reason=reason,
    )
    db.flush()
    return purchase


def cancel_oripa_shipment(
    db: Session,
    *,
    shipment_id: int,
    actor_admin_user_id: Optional[int] = None,
    reason: Optional[str] = None,
) -> models_shipment.Shipment:
    """Cancel an unshipped shipment and release oripa entries back to held (same user).

    Order lines are detached; order shipping_status reverts to unshipped when appropriate.
    Does not change shipping_fee / payment amounts.
    """
    shipment = (
        db.query(models_shipment.Shipment)
        .filter(models_shipment.Shipment.id == shipment_id)
        .with_for_update()
        .first()
    )
    if shipment is None:
        raise OripaError("Shipment が見つかりません", status_code=404)
    if shipment.status == "cancelled":
        return shipment
    if shipment.status in ("shipped", "in_transit", "delivered", "received"):
        raise OripaError("発送後の Shipment はキャンセルできません", status_code=409)

    prev = shipment.status
    now = datetime.utcnow()
    items = (
        db.query(models_shipment.ShipmentItem)
        .filter(models_shipment.ShipmentItem.shipment_id == shipment.id)
        .with_for_update()
        .all()
    )
    order_ids: set[int] = set()
    for item in items:
        if item.oripa_entry_id:
            entry = (
                db.query(models_oripa.OripaEntry)
                .filter(models_oripa.OripaEntry.id == item.oripa_entry_id)
                .with_for_update()
                .first()
            )
            if entry and entry.assignment_status == ENTRY_ASSIGNMENT_ASSIGNED:
                if entry.shipment_status == ENTRY_SHIPMENT_SHIPPED:
                    raise OripaError("発送済み番号が含まれるためキャンセルできません", status_code=409)
                entry.shipment_status = ENTRY_SHIPMENT_HELD
                entry.shipment_id = None
                entry.updated_at = now
        if item.order_item_id:
            oi = db.query(models.OrderItem).filter(models.OrderItem.id == item.order_item_id).first()
            if oi:
                order_ids.add(oi.order_id)
        db.delete(item)

    for oid in order_ids:
        order = db.query(models.Order).filter(models.Order.id == oid).with_for_update().first()
        if order is None:
            continue
        still = (
            db.query(models_shipment.ShipmentItem.id)
            .join(models.OrderItem, models.OrderItem.id == models_shipment.ShipmentItem.order_item_id)
            .filter(models.OrderItem.order_id == oid)
            .first()
        )
        if still is None and (order.shipping_status or "") in ("preparing", "packing", "unshipped"):
            if order.shipping_status != "shipped":
                order.shipping_status = "unshipped"

    shipment.status = "cancelled"
    shipment.updated_at = now
    append_shipment_log(
        db,
        shipment=shipment,
        event_type="cancelled",
        from_status=prev,
        to_status="cancelled",
        admin_user_id=actor_admin_user_id,
        note=reason,
    )
    write_oripa_audit(
        db,
        action="shipment.cancel",
        actor_admin_user_id=actor_admin_user_id,
        after={"shipment_id": shipment.id, "order_ids": sorted(order_ids), "reason": reason},
        reason=reason,
    )
    db.flush()
    return shipment


def _detach_retired_from_shipment(
    db: Session,
    *,
    shipment_id: int,
    actor_admin_user_id: Optional[int] = None,
) -> None:
    """Remove retired oripa items from an open shipment; cancel shipment if empty."""
    shipment = (
        db.query(models_shipment.Shipment)
        .filter(models_shipment.Shipment.id == shipment_id)
        .with_for_update()
        .first()
    )
    if shipment is None or shipment.status in ("shipped", "cancelled", "delivered", "received"):
        return

    items = (
        db.query(models_shipment.ShipmentItem)
        .filter(models_shipment.ShipmentItem.shipment_id == shipment_id)
        .all()
    )
    remaining = 0
    for item in items:
        if item.oripa_entry_id:
            entry = db.query(models_oripa.OripaEntry).filter(models_oripa.OripaEntry.id == item.oripa_entry_id).first()
            if entry and entry.assignment_status == ENTRY_ASSIGNMENT_RETIRED:
                db.delete(item)
                continue
        remaining += 1

    if remaining == 0:
        prev = shipment.status
        shipment.status = "cancelled"
        append_shipment_log(
            db,
            shipment=shipment,
            event_type="cancelled",
            from_status=prev,
            to_status="cancelled",
            admin_user_id=actor_admin_user_id,
            note="auto-cancelled after purchase cancel (empty)",
        )


def record_failed_pre_assignment(
    db: Session,
    *,
    oripa_id: int,
    user_id: int,
    quantity: int,
    idempotency_key: str,
    reason: str,
) -> models_oripa.OripaPurchase:
    """決済失敗 / 番号確定前キャンセル — 番号は一切割り当てない (idempotent)."""
    from services.oripa_assignment import mark_purchase_failed_idempotent

    return mark_purchase_failed_idempotent(
        db,
        oripa_id=oripa_id,
        user_id=user_id,
        quantity=quantity,
        idempotency_key=idempotency_key,
        reason=reason,
    )
