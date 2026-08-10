"""Phase 3-10: Oripa payment reservation, Stripe confirm, release, refund retire."""

from __future__ import annotations

import random
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy.orm import Session

import models
import models_oripa
from config import settings
from services.oripa_admin import OripaError, write_oripa_audit
from services.oripa_constants import (
    ENTRY_ASSIGNMENT_ASSIGNED,
    ENTRY_ASSIGNMENT_AVAILABLE,
    ENTRY_ASSIGNMENT_RESERVED,
    ENTRY_ASSIGNMENT_RETIRED,
    ENTRY_SHIPMENT_CANCELLED,
    ENTRY_SHIPMENT_HELD,
    ORIPA_PURCHASE_CANCELLED,
    ORIPA_PURCHASE_COMPLETED,
    ORIPA_PURCHASE_FAILED,
    ORIPA_PURCHASE_PENDING,
    ORIPA_STATUS_ON_SALE,
    ORIPA_STATUS_SOLD_OUT,
    format_entry_number,
)

DEFAULT_RESERVATION_HOURS = 23


def _now() -> datetime:
    return datetime.utcnow()


def reserve_oripa_entries_for_payment(
    db: Session,
    *,
    oripa_id: int,
    user_id: int,
    quantity: int,
    idempotency_key: Optional[str] = None,
    rng: Optional[random.Random] = None,
    reservation_hours: int = DEFAULT_RESERVATION_HOURS,
) -> models_oripa.OripaPurchase:
    """Atomically reserve random available entries for unpaid checkout (not revealed)."""
    if int(quantity) <= 0:
        raise OripaError("quantity は 1 以上である必要があります")

    if idempotency_key:
        existing = (
            db.query(models_oripa.OripaPurchase)
            .filter(models_oripa.OripaPurchase.idempotency_key == idempotency_key)
            .first()
        )
        if existing is not None:
            if existing.status in (ORIPA_PURCHASE_COMPLETED, ORIPA_PURCHASE_PENDING):
                return existing
            if existing.status == ORIPA_PURCHASE_FAILED:
                raise OripaError("この idempotency_key は失敗済みです", status_code=409)
            raise OripaError(f"この idempotency_key は処理済みです ({existing.status})", status_code=409)

    oripa = (
        db.query(models_oripa.Oripa)
        .filter(models_oripa.Oripa.id == oripa_id)
        .with_for_update()
        .first()
    )
    if oripa is None:
        raise OripaError("オリパが見つかりません", status_code=404)
    if oripa.status != ORIPA_STATUS_ON_SALE:
        raise OripaError(f"販売中ではありません (status={oripa.status})", status_code=409)

    max_per = int(oripa.max_entries_per_purchase or 0)
    if max_per > 0 and int(quantity) > max_per:
        raise OripaError(f"1回あたり最大 {max_per} 口までです")

    available = (
        db.query(models_oripa.OripaEntry)
        .filter(
            models_oripa.OripaEntry.oripa_id == oripa_id,
            models_oripa.OripaEntry.assignment_status == ENTRY_ASSIGNMENT_AVAILABLE,
        )
        .with_for_update()
        .all()
    )
    if len(available) < int(quantity):
        raise OripaError("在庫不足（sold out）です", status_code=409)

    picker = rng or random.Random()
    chosen = picker.sample(available, int(quantity))
    now = _now()
    expires = now + timedelta(hours=max(1, int(reservation_hours)))
    unit = float(oripa.price_per_entry)
    total = unit * int(quantity)

    user = db.query(models.User).filter(models.User.id == user_id).first()
    if user is None:
        raise OripaError("ユーザーが見つかりません", status_code=404)

    order = models.Order(
        user_id=user_id,
        total_amount=total,
        items_subtotal=int(round(total)),
        shipping_fee=0,
        packaging_fee=0,
        discount_amount=0,
        payment_fee=0,
        payment_method="stripe_card",
        payment_status="awaiting_payment",
        status=models.OrderStatus.pending,
        shipping_status="unshipped",
        postal_code=user.postal_code,
        country=user.country,
        region=user.region,
        city=user.city,
        address_line1=user.address_line1,
        address_line2=user.address_line2,
        payment_deadline=expires,
    )
    db.add(order)
    db.flush()
    db.add(
        models.OrderItem(
            order_id=order.id,
            card_id=None,
            quantity=int(quantity),
            unit_price=unit,
            product_name=f"オリパ: {oripa.title}"[:200],
        )
    )

    purchase = models_oripa.OripaPurchase(
        oripa_id=oripa_id,
        user_id=user_id,
        quantity=int(quantity),
        status=ORIPA_PURCHASE_PENDING,
        idempotency_key=idempotency_key,
        order_id=order.id,
        unit_price=unit,
        total_amount=total,
        reserved_expires_at=expires,
    )
    db.add(purchase)
    db.flush()

    reserved_ids: list[int] = []
    for entry in chosen:
        updated = (
            db.query(models_oripa.OripaEntry)
            .filter(
                models_oripa.OripaEntry.id == entry.id,
                models_oripa.OripaEntry.assignment_status == ENTRY_ASSIGNMENT_AVAILABLE,
                models_oripa.OripaEntry.assigned_user_id.is_(None),
            )
            .update(
                {
                    models_oripa.OripaEntry.assignment_status: ENTRY_ASSIGNMENT_RESERVED,
                    models_oripa.OripaEntry.assigned_user_id: user_id,
                    models_oripa.OripaEntry.assigned_order_id: order.id,
                    models_oripa.OripaEntry.assigned_purchase_id: purchase.id,
                    models_oripa.OripaEntry.assigned_at: now,
                    models_oripa.OripaEntry.shipment_status: ENTRY_SHIPMENT_HELD,
                    models_oripa.OripaEntry.updated_at: now,
                },
                synchronize_session=False,
            )
        )
        if int(updated or 0) != 1:
            raise OripaError("予約競合が発生しました。再試行してください", status_code=409)
        reserved_ids.append(entry.id)

    remaining_available = len(available) - int(quantity)
    if remaining_available <= 0 and oripa.status == ORIPA_STATUS_ON_SALE:
        oripa.status = ORIPA_STATUS_SOLD_OUT
        oripa.updated_at = now

    write_oripa_audit(
        db,
        action="oripa_reservation_created",
        oripa_id=oripa_id,
        after={
            "purchase_id": purchase.id,
            "order_id": order.id,
            "user_id": user_id,
            "quantity": int(quantity),
            "entry_ids": reserved_ids,
            "reserved_expires_at": expires.isoformat(),
            "revealed": False,
        },
    )
    db.flush()
    return purchase


def confirm_oripa_purchase_for_order(db: Session, order: models.Order) -> list[models_oripa.OripaPurchase]:
    """Flip reserved → assigned for pending purchases on a paid order (idempotent)."""
    purchases = (
        db.query(models_oripa.OripaPurchase)
        .filter(models_oripa.OripaPurchase.order_id == order.id)
        .with_for_update()
        .all()
    )
    if not purchases:
        return []

    now = _now()
    confirmed: list[models_oripa.OripaPurchase] = []
    for purchase in purchases:
        if purchase.status == ORIPA_PURCHASE_COMPLETED:
            confirmed.append(purchase)
            continue
        if purchase.status != ORIPA_PURCHASE_PENDING:
            continue

        entries = (
            db.query(models_oripa.OripaEntry)
            .filter(models_oripa.OripaEntry.assigned_purchase_id == purchase.id)
            .with_for_update()
            .all()
        )
        for entry in entries:
            if entry.assignment_status == ENTRY_ASSIGNMENT_ASSIGNED:
                continue
            if entry.assignment_status != ENTRY_ASSIGNMENT_RESERVED:
                raise OripaError(
                    f"予約状態が不正です entry={entry.id} status={entry.assignment_status}",
                    status_code=409,
                )
            entry.assignment_status = ENTRY_ASSIGNMENT_ASSIGNED
            entry.updated_at = now

        purchase.status = ORIPA_PURCHASE_COMPLETED
        purchase.updated_at = now
        write_oripa_audit(
            db,
            action="oripa_purchase_confirmed",
            oripa_id=purchase.oripa_id,
            after={
                "purchase_id": purchase.id,
                "order_id": order.id,
                "entry_labels": [format_entry_number(e.entry_number) for e in entries],
            },
        )
        confirmed.append(purchase)
    db.flush()
    return confirmed


def release_oripa_reservations_for_order(
    db: Session,
    order: models.Order,
    *,
    reason: str = "payment_failed",
    as_expired: bool = False,
) -> None:
    """Release unpaid reservations back to available (never customer-revealed)."""
    if order.payment_status == "paid":
        return

    purchases = (
        db.query(models_oripa.OripaPurchase)
        .filter(models_oripa.OripaPurchase.order_id == order.id)
        .with_for_update()
        .all()
    )
    now = _now()
    for purchase in purchases:
        if purchase.status != ORIPA_PURCHASE_PENDING:
            continue
        entries = (
            db.query(models_oripa.OripaEntry)
            .filter(models_oripa.OripaEntry.assigned_purchase_id == purchase.id)
            .with_for_update()
            .all()
        )
        oripa_ids: set[int] = set()
        for entry in entries:
            if entry.assignment_status == ENTRY_ASSIGNMENT_RESERVED:
                entry.assignment_status = ENTRY_ASSIGNMENT_AVAILABLE
                entry.assigned_user_id = None
                entry.assigned_order_id = None
                entry.assigned_purchase_id = None
                entry.assigned_at = None
                entry.shipment_status = ENTRY_SHIPMENT_HELD
                entry.shipment_id = None
                entry.updated_at = now
                oripa_ids.add(entry.oripa_id)
            elif entry.assignment_status == ENTRY_ASSIGNMENT_ASSIGNED:
                entry.assignment_status = ENTRY_ASSIGNMENT_RETIRED
                entry.shipment_status = ENTRY_SHIPMENT_CANCELLED
                entry.updated_at = now

        purchase.status = ORIPA_PURCHASE_FAILED if not as_expired else ORIPA_PURCHASE_CANCELLED
        purchase.updated_at = now
        write_oripa_audit(
            db,
            action="oripa_reservation_released" if not as_expired else "oripa_reservation_expired",
            oripa_id=purchase.oripa_id,
            after={"purchase_id": purchase.id, "order_id": order.id, "reason": reason},
            reason=reason,
        )
        for oid in oripa_ids:
            _maybe_reopen_oripa(db, oid, now=now)
    db.flush()


def retire_oripa_for_paid_refund(db: Session, order: models.Order, *, reason: str = "refund") -> None:
    """After paid refund: retire revealed numbers (never resell)."""
    purchases = (
        db.query(models_oripa.OripaPurchase)
        .filter(models_oripa.OripaPurchase.order_id == order.id)
        .with_for_update()
        .all()
    )
    now = _now()
    for purchase in purchases:
        if purchase.status == ORIPA_PURCHASE_CANCELLED:
            continue
        entries = (
            db.query(models_oripa.OripaEntry)
            .filter(models_oripa.OripaEntry.assigned_purchase_id == purchase.id)
            .with_for_update()
            .all()
        )
        shipped = [e for e in entries if e.shipment_status == "shipped"]
        if shipped:
            write_oripa_audit(
                db,
                action="oripa_refund_blocked_shipped",
                oripa_id=purchase.oripa_id,
                after={"purchase_id": purchase.id, "shipped_entry_ids": [e.id for e in shipped]},
                reason=reason,
            )
            continue
        for entry in entries:
            if entry.assignment_status in (ENTRY_ASSIGNMENT_ASSIGNED, ENTRY_ASSIGNMENT_RESERVED):
                entry.assignment_status = ENTRY_ASSIGNMENT_RETIRED
                entry.shipment_status = ENTRY_SHIPMENT_CANCELLED
                entry.shipment_id = None
                entry.updated_at = now
        purchase.status = ORIPA_PURCHASE_CANCELLED
        purchase.updated_at = now
        write_oripa_audit(
            db,
            action="oripa_purchase_refunded_retired",
            oripa_id=purchase.oripa_id,
            after={"purchase_id": purchase.id, "order_id": order.id, "resale": False},
            reason=reason,
        )
    db.flush()


def _maybe_reopen_oripa(db: Session, oripa_id: int, *, now: datetime) -> None:
    oripa = db.query(models_oripa.Oripa).filter(models_oripa.Oripa.id == oripa_id).with_for_update().first()
    if oripa is None or oripa.status != ORIPA_STATUS_SOLD_OUT:
        return
    available = (
        db.query(models_oripa.OripaEntry.id)
        .filter(
            models_oripa.OripaEntry.oripa_id == oripa_id,
            models_oripa.OripaEntry.assignment_status == ENTRY_ASSIGNMENT_AVAILABLE,
        )
        .first()
    )
    if available:
        oripa.status = ORIPA_STATUS_ON_SALE
        oripa.updated_at = now


def expire_stale_oripa_reservations(db: Session) -> int:
    """Release pending purchases past reserved_expires_at when order still unpaid."""
    now = _now()
    pending = (
        db.query(models_oripa.OripaPurchase)
        .filter(
            models_oripa.OripaPurchase.status == ORIPA_PURCHASE_PENDING,
            models_oripa.OripaPurchase.reserved_expires_at.isnot(None),
            models_oripa.OripaPurchase.reserved_expires_at < now,
        )
        .all()
    )
    count = 0
    for purchase in pending:
        if purchase.order_id is None:
            continue
        order = db.query(models.Order).filter(models.Order.id == purchase.order_id).first()
        if order is None or order.payment_status == "paid":
            continue
        from services.order_checkout import cancel_unpaid_order

        cancel_unpaid_order(db, order, as_expired=True)
        count += 1
    return count


def list_oripa_consistency_issues(db: Session) -> list[dict]:
    """Detect reservation / payment / slot inconsistencies."""
    issues: list[dict] = []
    rows = (
        db.query(models_oripa.OripaEntry, models.Order)
        .join(models.Order, models.Order.id == models_oripa.OripaEntry.assigned_order_id)
        .filter(
            models_oripa.OripaEntry.assignment_status == ENTRY_ASSIGNMENT_RESERVED,
            models.Order.payment_status == "paid",
        )
        .all()
    )
    for entry, order in rows:
        issues.append({"type": "reserved_but_order_paid", "entry_id": entry.id, "order_id": order.id})

    rows2 = (
        db.query(models_oripa.OripaEntry, models_oripa.OripaPurchase)
        .join(
            models_oripa.OripaPurchase,
            models_oripa.OripaPurchase.id == models_oripa.OripaEntry.assigned_purchase_id,
        )
        .filter(
            models_oripa.OripaEntry.assignment_status == ENTRY_ASSIGNMENT_ASSIGNED,
            models_oripa.OripaPurchase.status == ORIPA_PURCHASE_PENDING,
        )
        .all()
    )
    for entry, purchase in rows2:
        issues.append(
            {"type": "assigned_but_purchase_pending", "entry_id": entry.id, "purchase_id": purchase.id}
        )

    for entry in (
        db.query(models_oripa.OripaEntry)
        .filter(
            models_oripa.OripaEntry.assignment_status == ENTRY_ASSIGNMENT_RESERVED,
            models_oripa.OripaEntry.assigned_order_id.is_(None),
        )
        .all()
    ):
        issues.append({"type": "reserved_without_order", "entry_id": entry.id})

    for entry, order in (
        db.query(models_oripa.OripaEntry, models.Order)
        .join(models.Order, models.Order.id == models_oripa.OripaEntry.assigned_order_id)
        .filter(
            models_oripa.OripaEntry.assignment_status == ENTRY_ASSIGNMENT_ASSIGNED,
            models.Order.payment_status != "paid",
        )
        .all()
    ):
        issues.append(
            {
                "type": "assigned_but_order_unpaid",
                "entry_id": entry.id,
                "order_id": order.id,
                "payment_status": order.payment_status,
            }
        )

    for entry in (
        db.query(models_oripa.OripaEntry)
        .filter(models_oripa.OripaEntry.assignment_status == ENTRY_ASSIGNMENT_RETIRED)
        .all()
    ):
        if entry.assigned_user_id is None and entry.assigned_purchase_id is None:
            continue
        # retired with no purchase link is odd but allowed after cleanup; flag if still "sellable" paths
        pass

    for purchase in (
        db.query(models_oripa.OripaPurchase)
        .filter(models_oripa.OripaPurchase.status == ORIPA_PURCHASE_PENDING)
        .all()
    ):
        if purchase.order_id is None:
            issues.append({"type": "pending_purchase_without_order", "purchase_id": purchase.id})
            continue
        order = db.query(models.Order).filter(models.Order.id == purchase.order_id).first()
        if order is None:
            issues.append({"type": "pending_purchase_missing_order", "purchase_id": purchase.id})
        elif order.payment_status == "paid":
            issues.append(
                {
                    "type": "payment_succeeded_purchase_pending",
                    "purchase_id": purchase.id,
                    "order_id": order.id,
                }
            )
    return issues


def build_oripa_stripe_line_items(purchase: models_oripa.OripaPurchase, oripa: models_oripa.Oripa) -> list[dict]:
    unit = int(round(float(purchase.unit_price or oripa.price_per_entry)))
    return [
        {
            "price_data": {
                "currency": "jpy",
                "product_data": {
                    "name": f"オリパ: {oripa.title}"[:120],
                    "metadata": {"oripa_id": str(oripa.id), "purchase_id": str(purchase.id)},
                },
                "unit_amount": unit,
            },
            "quantity": int(purchase.quantity),
        }
    ]
