"""Points ledger: accounts, reservations, earn/use/expire with idempotency."""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Any

from fastapi import HTTPException
from sqlalchemy.orm import Session

import models_points
from services.point_calculator import points_to_yen

# Transaction types (strict enum strings)
TX_EARN = "earn"
TX_USE = "use"
TX_REFUND = "refund"
TX_EXPIRE = "expire"
TX_ADMIN_GRANT = "admin_grant"
TX_ADMIN_DEDUCT = "admin_deduct"
TX_ADJUSTMENT = "adjustment"
TX_CANCEL_RESTORE = "cancel_restore"
TX_PAYMENT_RESTORE = "payment_restore"
TX_RESERVE = "reserve"
TX_RELEASE = "release"

CREDIT_TYPES = {TX_EARN, TX_REFUND, TX_ADMIN_GRANT, TX_CANCEL_RESTORE, TX_PAYMENT_RESTORE, TX_RELEASE}
DEBIT_TYPES = {TX_USE, TX_EXPIRE, TX_ADMIN_DEDUCT, TX_ADJUSTMENT, TX_RESERVE}


def _utcnow() -> datetime:
    return datetime.utcnow()


def _serialize_account(account: models_points.PointAccount) -> dict[str, Any]:
    return {
        "available_points": account.available_points,
        "reserved_points": account.reserved_points,
        "lifetime_earned": account.lifetime_earned,
        "lifetime_used": account.lifetime_used,
    }


def _write_audit(
    db: Session,
    *,
    action: str,
    target_user_id: int,
    actor_admin_user_id: int | None,
    transaction_id: int | None,
    before: dict | None,
    after: dict | None,
    reason: str | None,
) -> None:
    db.add(
        models_points.PointAuditLog(
            actor_admin_user_id=actor_admin_user_id,
            action=action,
            target_user_id=target_user_id,
            transaction_id=transaction_id,
            before_json=json.dumps(before, ensure_ascii=False) if before else None,
            after_json=json.dumps(after, ensure_ascii=False) if after else None,
            reason=reason,
        )
    )


def get_or_create_account(db: Session, user_id: int, *, for_update: bool = False) -> models_points.PointAccount:
    query = db.query(models_points.PointAccount).filter(models_points.PointAccount.user_id == user_id)
    if for_update:
        query = query.with_for_update()
    account = query.first()
    if account is None:
        account = models_points.PointAccount(user_id=user_id)
        db.add(account)
        db.flush()
        if for_update:
            account = (
                db.query(models_points.PointAccount)
                .filter(models_points.PointAccount.user_id == user_id)
                .with_for_update()
                .first()
            )
    return account


def get_transaction_by_key(db: Session, idempotency_key: str) -> models_points.PointTransaction | None:
    return (
        db.query(models_points.PointTransaction)
        .filter(models_points.PointTransaction.idempotency_key == idempotency_key)
        .first()
    )


def _lot_sort_key(lot: models_points.PointExpirationLot) -> tuple:
    if lot.expires_at is None:
        return (1, datetime.max)
    return (0, lot.expires_at)


def _allocate_from_lots(db: Session, user_id: int, amount: int) -> list[dict[str, int]]:
    if amount <= 0:
        return []
    lots = (
        db.query(models_points.PointExpirationLot)
        .filter(
            models_points.PointExpirationLot.user_id == user_id,
            models_points.PointExpirationLot.remaining_amount > 0,
        )
        .with_for_update()
        .all()
    )
    lots.sort(key=_lot_sort_key)
    remaining = amount
    allocations: list[dict[str, int]] = []
    for lot in lots:
        if remaining <= 0:
            break
        if lot.expires_at is not None and lot.expires_at <= _utcnow():
            continue
        take = min(lot.remaining_amount, remaining)
        if take <= 0:
            continue
        lot.remaining_amount -= take
        remaining -= take
        allocations.append({"lot_id": lot.id, "amount": take})
    if remaining > 0:
        raise HTTPException(status_code=400, detail="ポイント残高が不足しています")
    return allocations


def _restore_lot_allocations(db: Session, allocations: list[dict[str, int]]) -> None:
    for entry in allocations:
        lot = (
            db.query(models_points.PointExpirationLot)
            .filter(models_points.PointExpirationLot.id == entry["lot_id"])
            .with_for_update()
            .first()
        )
        if lot:
            lot.remaining_amount += int(entry["amount"])


def _create_transaction(
    db: Session,
    *,
    user_id: int,
    tx_type: str,
    amount: int,
    balance_after: int,
    idempotency_key: str,
    source_type: str | None = None,
    source_id: int | None = None,
    expires_at: datetime | None = None,
    created_by: int | None = None,
    metadata: dict | None = None,
) -> models_points.PointTransaction:
    existing = get_transaction_by_key(db, idempotency_key)
    if existing:
        return existing
    tx = models_points.PointTransaction(
        user_id=user_id,
        type=tx_type,
        amount=amount,
        balance_after=balance_after,
        source_type=source_type,
        source_id=source_id,
        idempotency_key=idempotency_key,
        expires_at=expires_at,
        created_by=created_by,
        metadata_json=json.dumps(metadata, ensure_ascii=False) if metadata else None,
    )
    db.add(tx)
    db.flush()
    return tx


def _credit_points(
    db: Session,
    account: models_points.PointAccount,
    amount: int,
    *,
    tx_type: str,
    idempotency_key: str,
    source_type: str | None = None,
    source_id: int | None = None,
    expiration_days: int | None = None,
    created_by: int | None = None,
    metadata: dict | None = None,
) -> models_points.PointTransaction:
    if amount <= 0:
        raise HTTPException(status_code=400, detail="ポイント数は1以上である必要があります")
    existing = get_transaction_by_key(db, idempotency_key)
    if existing:
        return existing

    expires_at = None
    if expiration_days is not None and expiration_days > 0:
        expires_at = _utcnow() + timedelta(days=expiration_days)

    account.available_points += amount
    account.lifetime_earned += amount
    tx = _create_transaction(
        db,
        user_id=account.user_id,
        tx_type=tx_type,
        amount=amount,
        balance_after=account.available_points,
        idempotency_key=idempotency_key,
        source_type=source_type,
        source_id=source_id,
        expires_at=expires_at,
        created_by=created_by,
        metadata=metadata,
    )
    db.add(
        models_points.PointExpirationLot(
            user_id=account.user_id,
            transaction_id=tx.id,
            original_amount=amount,
            remaining_amount=amount,
            expires_at=expires_at,
        )
    )
    return tx


def reserve_points_for_order(
    db: Session,
    *,
    user_id: int,
    order_id: int,
    amount: int,
    idempotency_key: str | None = None,
) -> models_points.PointReservation:
    if amount <= 0:
        raise HTTPException(status_code=400, detail="利用ポイントは1以上である必要があります")
    key = idempotency_key or f"reserve:order:{order_id}"

    existing_res = (
        db.query(models_points.PointReservation)
        .filter(models_points.PointReservation.idempotency_key == key)
        .first()
    )
    if existing_res:
        return existing_res

    existing_order_res = (
        db.query(models_points.PointReservation)
        .filter(models_points.PointReservation.order_id == order_id)
        .first()
    )
    if existing_order_res:
        return existing_order_res

    account = get_or_create_account(db, user_id, for_update=True)
    if account.available_points < amount:
        raise HTTPException(status_code=400, detail="ポイント残高が不足しています")

    allocations = _allocate_from_lots(db, user_id, amount)
    account.available_points -= amount
    account.reserved_points += amount

    _create_transaction(
        db,
        user_id=user_id,
        tx_type=TX_RESERVE,
        amount=amount,
        balance_after=account.available_points,
        idempotency_key=key,
        source_type="order",
        source_id=order_id,
        metadata={"reserved_total": account.reserved_points},
    )

    reservation = models_points.PointReservation(
        user_id=user_id,
        order_id=order_id,
        amount=amount,
        status="pending",
        lot_allocations_json=json.dumps(allocations),
        idempotency_key=key,
    )
    db.add(reservation)
    db.flush()
    return reservation


def confirm_points_for_order(
    db: Session,
    *,
    user_id: int,
    order_id: int,
    idempotency_key: str | None = None,
) -> models_points.PointTransaction | None:
    key = idempotency_key or f"use:order:{order_id}"
    existing = get_transaction_by_key(db, key)
    if existing:
        return existing

    reservation = (
        db.query(models_points.PointReservation)
        .filter(
            models_points.PointReservation.order_id == order_id,
            models_points.PointReservation.user_id == user_id,
        )
        .with_for_update()
        .first()
    )
    if reservation is None:
        return None
    if reservation.status == "confirmed":
        return get_transaction_by_key(db, key)
    if reservation.status == "released":
        return None

    account = get_or_create_account(db, user_id, for_update=True)
    amount = reservation.amount
    if account.reserved_points < amount:
        raise HTTPException(status_code=409, detail="予約ポイントの整合性エラー")

    account.reserved_points -= amount
    account.lifetime_used += amount
    reservation.status = "confirmed"

    return _create_transaction(
        db,
        user_id=user_id,
        tx_type=TX_USE,
        amount=amount,
        balance_after=account.available_points,
        idempotency_key=key,
        source_type="order",
        source_id=order_id,
    )


def release_points_for_order(
    db: Session,
    *,
    user_id: int,
    order_id: int,
    idempotency_key: str | None = None,
) -> models_points.PointTransaction | None:
    key = idempotency_key or f"release:order:{order_id}"
    existing = get_transaction_by_key(db, key)
    if existing:
        return existing

    reservation = (
        db.query(models_points.PointReservation)
        .filter(
            models_points.PointReservation.order_id == order_id,
            models_points.PointReservation.user_id == user_id,
        )
        .with_for_update()
        .first()
    )
    if reservation is None:
        return None
    if reservation.status == "released":
        return get_transaction_by_key(db, key)
    if reservation.status == "confirmed":
        return None

    allocations = json.loads(reservation.lot_allocations_json or "[]")
    _restore_lot_allocations(db, allocations)

    account = get_or_create_account(db, user_id, for_update=True)
    amount = reservation.amount
    account.reserved_points = max(0, account.reserved_points - amount)
    account.available_points += amount
    reservation.status = "released"

    return _create_transaction(
        db,
        user_id=user_id,
        tx_type=TX_RELEASE,
        amount=amount,
        balance_after=account.available_points,
        idempotency_key=key,
        source_type="order",
        source_id=order_id,
    )


def earn_points_for_order(
    db: Session,
    *,
    user_id: int,
    order_id: int,
    amount: int,
    expiration_days: int | None,
    idempotency_key: str | None = None,
) -> models_points.PointTransaction | None:
    if amount <= 0:
        return None
    key = idempotency_key or f"earn:order:{order_id}"
    account = get_or_create_account(db, user_id, for_update=True)
    return _credit_points(
        db,
        account,
        amount,
        tx_type=TX_EARN,
        idempotency_key=key,
        source_type="order",
        source_id=order_id,
        expiration_days=expiration_days,
    )


def restore_used_points_for_order(
    db: Session,
    *,
    user_id: int,
    order_id: int,
    amount: int,
    idempotency_key: str | None = None,
) -> models_points.PointTransaction | None:
    if amount <= 0:
        return None
    key = idempotency_key or f"cancel_restore:order:{order_id}"
    account = get_or_create_account(db, user_id, for_update=True)
    return _credit_points(
        db,
        account,
        amount,
        tx_type=TX_CANCEL_RESTORE,
        idempotency_key=key,
        source_type="order",
        source_id=order_id,
        expiration_days=None,
        metadata={"reason": "order_cancelled"},
    )


def reverse_earned_points_for_order(
    db: Session,
    *,
    user_id: int,
    order_id: int,
    earn_amount: int,
    idempotency_key: str | None = None,
) -> models_points.PointTransaction | None:
    if earn_amount <= 0:
        return None
    key = idempotency_key or f"reverse_earn:order:{order_id}"
    existing = get_transaction_by_key(db, key)
    if existing:
        return existing

    account = get_or_create_account(db, user_id, for_update=True)
    reversible = min(earn_amount, account.available_points)
    if reversible <= 0:
        tx = _create_transaction(
            db,
            user_id=user_id,
            tx_type=TX_ADJUSTMENT,
            amount=0,
            balance_after=account.available_points,
            idempotency_key=key,
            source_type="order",
            source_id=order_id,
            metadata={
                "requested_reverse": earn_amount,
                "reversed": 0,
                "reason": "insufficient_available_for_reversal",
            },
        )
        return tx

    _allocate_from_lots(db, user_id, reversible)
    account.available_points -= reversible
    account.lifetime_earned = max(0, account.lifetime_earned - reversible)

    return _create_transaction(
        db,
        user_id=user_id,
        tx_type=TX_ADJUSTMENT,
        amount=reversible,
        balance_after=account.available_points,
        idempotency_key=key,
        source_type="order",
        source_id=order_id,
        metadata={
            "requested_reverse": earn_amount,
            "reversed": reversible,
            "partial": reversible < earn_amount,
        },
    )


def admin_grant_points(
    db: Session,
    *,
    user_id: int,
    amount: int,
    reason: str,
    admin_user_id: int,
    expiration_days: int | None = None,
    idempotency_key: str,
) -> models_points.PointTransaction:
    if not reason.strip():
        raise HTTPException(status_code=400, detail="理由は必須です")
    account = get_or_create_account(db, user_id, for_update=True)
    before = _serialize_account(account)
    tx = _credit_points(
        db,
        account,
        amount,
        tx_type=TX_ADMIN_GRANT,
        idempotency_key=idempotency_key,
        expiration_days=expiration_days,
        created_by=admin_user_id,
        metadata={"reason": reason},
    )
    after = _serialize_account(account)
    _write_audit(
        db,
        action="admin_grant",
        target_user_id=user_id,
        actor_admin_user_id=admin_user_id,
        transaction_id=tx.id,
        before=before,
        after=after,
        reason=reason,
    )
    return tx


def admin_deduct_points(
    db: Session,
    *,
    user_id: int,
    amount: int,
    reason: str,
    admin_user_id: int,
    idempotency_key: str,
) -> models_points.PointTransaction:
    if not reason.strip():
        raise HTTPException(status_code=400, detail="理由は必須です")
    if amount <= 0:
        raise HTTPException(status_code=400, detail="減算ポイントは1以上である必要があります")

    existing = get_transaction_by_key(db, idempotency_key)
    if existing:
        return existing

    account = get_or_create_account(db, user_id, for_update=True)
    before = _serialize_account(account)
    if account.available_points < amount:
        raise HTTPException(status_code=400, detail="保有ポイントを超える減算はできません")

    _allocate_from_lots(db, user_id, amount)
    account.available_points -= amount
    account.lifetime_used += amount

    tx = _create_transaction(
        db,
        user_id=user_id,
        tx_type=TX_ADMIN_DEDUCT,
        amount=amount,
        balance_after=account.available_points,
        idempotency_key=idempotency_key,
        created_by=admin_user_id,
        metadata={"reason": reason},
    )
    after = _serialize_account(account)
    _write_audit(
        db,
        action="admin_deduct",
        target_user_id=user_id,
        actor_admin_user_id=admin_user_id,
        transaction_id=tx.id,
        before=before,
        after=after,
        reason=reason,
    )
    return tx


def expire_due_points(db: Session, *, user_id: int | None = None) -> int:
    """Expire lots past their expiry. Returns count of expired point units."""
    now = _utcnow()
    query = db.query(models_points.PointExpirationLot).filter(
        models_points.PointExpirationLot.remaining_amount > 0,
        models_points.PointExpirationLot.expires_at.isnot(None),
        models_points.PointExpirationLot.expires_at <= now,
    )
    if user_id is not None:
        query = query.filter(models_points.PointExpirationLot.user_id == user_id)

    lots = query.with_for_update().all()
    expired_total = 0
    for lot in lots:
        amount = lot.remaining_amount
        if amount <= 0:
            continue
        key = f"expire:lot:{lot.id}"
        if get_transaction_by_key(db, key):
            lot.remaining_amount = 0
            continue

        account = get_or_create_account(db, lot.user_id, for_update=True)
        deduct = min(amount, account.available_points)
        lot.remaining_amount = 0
        if deduct <= 0:
            _create_transaction(
                db,
                user_id=lot.user_id,
                tx_type=TX_EXPIRE,
                amount=amount,
                balance_after=account.available_points,
                idempotency_key=key,
                source_type="lot",
                source_id=lot.id,
                metadata={"expired_unavailable": amount - deduct},
            )
            continue

        account.available_points -= deduct
        expired_total += deduct
        _create_transaction(
            db,
            user_id=lot.user_id,
            tx_type=TX_EXPIRE,
            amount=deduct,
            balance_after=account.available_points,
            idempotency_key=key,
            source_type="lot",
            source_id=lot.id,
        )
    return expired_total


def get_account_summary(db: Session, user_id: int) -> models_points.PointAccount:
    expire_due_points(db, user_id=user_id)
    return get_or_create_account(db, user_id)


def get_expiring_soon_points(db: Session, user_id: int, within_days: int = 30) -> int:
    expire_due_points(db, user_id=user_id)
    deadline = _utcnow() + timedelta(days=within_days)
    lots = (
        db.query(models_points.PointExpirationLot)
        .filter(
            models_points.PointExpirationLot.user_id == user_id,
            models_points.PointExpirationLot.remaining_amount > 0,
            models_points.PointExpirationLot.expires_at.isnot(None),
            models_points.PointExpirationLot.expires_at <= deadline,
        )
        .all()
    )
    return sum(lot.remaining_amount for lot in lots)
