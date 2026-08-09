"""Phase 3-9 Step 2: atomic random number assignment engine."""

from __future__ import annotations

import random
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

import models_oripa
from services.oripa_admin import OripaError, write_oripa_audit
from services.oripa_constants import (
    ENTRY_ASSIGNMENT_ASSIGNED,
    ENTRY_ASSIGNMENT_AVAILABLE,
    ENTRY_SHIPMENT_HELD,
    ORIPA_PURCHASE_COMPLETED,
    ORIPA_PURCHASE_FAILED,
    ORIPA_STATUS_ON_SALE,
    ORIPA_STATUS_SOLD_OUT,
    format_entry_number,
)


def _get_purchase_by_idempotency(db: Session, key: str) -> Optional[models_oripa.OripaPurchase]:
    return (
        db.query(models_oripa.OripaPurchase)
        .filter(models_oripa.OripaPurchase.idempotency_key == key)
        .first()
    )


def list_purchase_entry_numbers(db: Session, purchase_id: int) -> list[int]:
    rows = (
        db.query(models_oripa.OripaEntry.entry_number)
        .filter(models_oripa.OripaEntry.assigned_purchase_id == purchase_id)
        .order_by(models_oripa.OripaEntry.entry_number.asc())
        .all()
    )
    return [int(r[0]) for r in rows]


def assign_oripa_entries(
    db: Session,
    *,
    oripa_id: int,
    user_id: int,
    quantity: int,
    idempotency_key: Optional[str] = None,
    order_id: Optional[int] = None,
    allow_statuses: Optional[set[str]] = None,
    rng: Optional[random.Random] = None,
) -> models_oripa.OripaPurchase:
    """Atomically assign `quantity` unused entries to user.

    Idempotent when idempotency_key is provided and a completed purchase already exists.
    Caller owns the DB transaction (commit/rollback).
    """
    if int(quantity) <= 0:
        raise OripaError("quantity は 1 以上である必要があります")

    if idempotency_key:
        existing = _get_purchase_by_idempotency(db, idempotency_key)
        if existing is not None:
            if existing.status == ORIPA_PURCHASE_COMPLETED:
                return existing
            if existing.status == ORIPA_PURCHASE_FAILED:
                raise OripaError("この idempotency_key は失敗済みです", status_code=409)
            # pending leftover — treat as conflict rather than double-assign
            raise OripaError("同一 idempotency_key の購入が処理中です", status_code=409)

    oripa = (
        db.query(models_oripa.Oripa)
        .filter(models_oripa.Oripa.id == oripa_id)
        .with_for_update()
        .first()
    )
    if oripa is None:
        raise OripaError("オリパが見つかりません", status_code=404)

    allowed = allow_statuses or {ORIPA_STATUS_ON_SALE}
    if oripa.status not in allowed:
        raise OripaError(f"販売中ではありません (status={oripa.status})", status_code=409)

    max_per = int(oripa.max_entries_per_purchase or 0)
    if max_per > 0 and int(quantity) > max_per:
        raise OripaError(f"1回あたり最大 {max_per} 口までです")

    # Lock all currently available entries for this oripa (prevents concurrent double-assign).
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

    purchase = models_oripa.OripaPurchase(
        oripa_id=oripa_id,
        user_id=user_id,
        quantity=int(quantity),
        status=ORIPA_PURCHASE_COMPLETED,
        idempotency_key=idempotency_key,
        order_id=order_id,
        unit_price=float(oripa.price_per_entry),
        total_amount=float(oripa.price_per_entry) * int(quantity),
    )
    db.add(purchase)
    db.flush()

    now = datetime.utcnow()
    for entry in chosen:
        # Atomic compare-and-set: prevents double-assign even when FOR UPDATE is weak (SQLite).
        updated = (
            db.query(models_oripa.OripaEntry)
            .filter(
                models_oripa.OripaEntry.id == entry.id,
                models_oripa.OripaEntry.assignment_status == ENTRY_ASSIGNMENT_AVAILABLE,
                models_oripa.OripaEntry.assigned_user_id.is_(None),
            )
            .update(
                {
                    models_oripa.OripaEntry.assignment_status: ENTRY_ASSIGNMENT_ASSIGNED,
                    models_oripa.OripaEntry.assigned_user_id: user_id,
                    models_oripa.OripaEntry.assigned_order_id: order_id,
                    models_oripa.OripaEntry.assigned_purchase_id: purchase.id,
                    models_oripa.OripaEntry.assigned_at: now,
                    models_oripa.OripaEntry.shipment_status: ENTRY_SHIPMENT_HELD,
                    models_oripa.OripaEntry.updated_at: now,
                },
                synchronize_session=False,
            )
        )
        if int(updated or 0) != 1:
            raise OripaError("割当競合が発生しました。再試行してください", status_code=409)
        entry.assignment_status = ENTRY_ASSIGNMENT_ASSIGNED
        entry.assigned_user_id = user_id
        entry.assigned_order_id = order_id
        entry.assigned_purchase_id = purchase.id
        entry.assigned_at = now

    remaining = len(available) - int(quantity)
    if remaining <= 0 and oripa.status == ORIPA_STATUS_ON_SALE:
        oripa.status = ORIPA_STATUS_SOLD_OUT
        oripa.updated_at = now

    write_oripa_audit(
        db,
        action="oripa_entries_assigned",
        oripa_id=oripa_id,
        after={
            "purchase_id": purchase.id,
            "user_id": user_id,
            "quantity": int(quantity),
            "entry_numbers": [int(e.entry_number) for e in chosen],
            "entry_labels": [format_entry_number(e.entry_number) for e in chosen],
            "idempotency_key": idempotency_key,
        },
    )
    return purchase


def mark_purchase_failed_idempotent(
    db: Session,
    *,
    oripa_id: int,
    user_id: int,
    quantity: int,
    idempotency_key: str,
    reason: str,
) -> models_oripa.OripaPurchase:
    """Record a failed purchase attempt without assigning numbers (idempotent)."""
    existing = _get_purchase_by_idempotency(db, idempotency_key)
    if existing is not None:
        return existing
    row = models_oripa.OripaPurchase(
        oripa_id=oripa_id,
        user_id=user_id,
        quantity=int(quantity),
        status=ORIPA_PURCHASE_FAILED,
        idempotency_key=idempotency_key,
    )
    db.add(row)
    db.flush()
    write_oripa_audit(
        db,
        action="oripa_purchase_failed",
        oripa_id=oripa_id,
        after={"purchase_id": row.id, "reason": reason, "idempotency_key": idempotency_key},
        reason=reason,
    )
    return row
