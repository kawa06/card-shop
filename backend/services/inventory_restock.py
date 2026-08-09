"""Phase 3-8 restock workflow with transactional receive."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

import models
import models_inventory
from services.inventory_alerts import evaluate_card_inventory, write_inventory_audit
from services.inventory_constants import (
    RESTOCK_STATUS_CANCELLED,
    RESTOCK_STATUS_ORDERED,
    RESTOCK_STATUS_RECEIVED,
    RESTOCK_STATUS_REQUESTED,
    RESTOCK_TRANSITIONS,
)


class RestockError(Exception):
    def __init__(self, detail: str, status_code: int = 400):
        self.detail = detail
        self.status_code = status_code
        super().__init__(detail)


def _validate_transition(current: str, new_status: str) -> None:
    allowed = RESTOCK_TRANSITIONS.get(current, set())
    if new_status not in allowed:
        raise RestockError(
            f"不正な状態遷移です: {current} -> {new_status}",
            status_code=400,
        )


def create_restock(
    db: Session,
    *,
    product_id: int,
    requested_quantity: int,
    note: Optional[str] = None,
    actor_admin_user_id: Optional[int] = None,
) -> models_inventory.InventoryRestock:
    if int(requested_quantity) <= 0:
        raise RestockError("requested_quantity は 1 以上である必要があります")
    card = db.query(models.Card).filter(models.Card.id == product_id).first()
    if card is None:
        raise RestockError("商品が見つかりません", status_code=404)

    row = models_inventory.InventoryRestock(
        product_id=product_id,
        requested_quantity=int(requested_quantity),
        received_quantity=None,
        status=RESTOCK_STATUS_REQUESTED,
        note=note,
        created_by=actor_admin_user_id,
    )
    db.add(row)
    db.flush()
    write_inventory_audit(
        db,
        action="restock_created",
        actor_admin_user_id=actor_admin_user_id,
        product_id=product_id,
        restock_id=row.id,
        after={
            "requested_quantity": row.requested_quantity,
            "status": row.status,
            "note": note,
        },
    )
    return row


def update_restock(
    db: Session,
    restock_id: int,
    *,
    status: Optional[str] = None,
    requested_quantity: Optional[int] = None,
    note: Optional[str] = None,
    actor_admin_user_id: Optional[int] = None,
) -> models_inventory.InventoryRestock:
    row = (
        db.query(models_inventory.InventoryRestock)
        .filter(models_inventory.InventoryRestock.id == restock_id)
        .with_for_update()
        .first()
    )
    if row is None:
        raise RestockError("restock が見つかりません", status_code=404)

    before = {
        "status": row.status,
        "requested_quantity": row.requested_quantity,
        "note": row.note,
    }

    if row.status in (RESTOCK_STATUS_RECEIVED, RESTOCK_STATUS_CANCELLED):
        raise RestockError(f"終端状態の restock は更新できません: {row.status}")

    if requested_quantity is not None:
        if int(requested_quantity) <= 0:
            raise RestockError("requested_quantity は 1 以上である必要があります")
        row.requested_quantity = int(requested_quantity)
    if note is not None:
        row.note = note
    if status is not None and status != row.status:
        if status == RESTOCK_STATUS_RECEIVED:
            raise RestockError("received への変更は receive アクションを使用してください")
        _validate_transition(row.status, status)
        row.status = status
        if status == RESTOCK_STATUS_CANCELLED:
            row.completed_at = datetime.utcnow()
            write_inventory_audit(
                db,
                action="restock_cancelled",
                actor_admin_user_id=actor_admin_user_id,
                product_id=row.product_id,
                restock_id=row.id,
                before=before,
                after={"status": row.status},
            )
        else:
            write_inventory_audit(
                db,
                action="restock_updated",
                actor_admin_user_id=actor_admin_user_id,
                product_id=row.product_id,
                restock_id=row.id,
                before=before,
                after={
                    "status": row.status,
                    "requested_quantity": row.requested_quantity,
                    "note": row.note,
                },
            )
    else:
        write_inventory_audit(
            db,
            action="restock_updated",
            actor_admin_user_id=actor_admin_user_id,
            product_id=row.product_id,
            restock_id=row.id,
            before=before,
            after={
                "status": row.status,
                "requested_quantity": row.requested_quantity,
                "note": row.note,
            },
        )

    row.updated_at = datetime.utcnow()
    return row


def receive_restock(
    db: Session,
    restock_id: int,
    *,
    received_quantity: Optional[int] = None,
    actor_admin_user_id: Optional[int] = None,
) -> models_inventory.InventoryRestock:
    """Apply received_quantity to card stock transactionally. Idempotent."""
    row = (
        db.query(models_inventory.InventoryRestock)
        .filter(models_inventory.InventoryRestock.id == restock_id)
        .with_for_update()
        .first()
    )
    if row is None:
        raise RestockError("restock が見つかりません", status_code=404)

    # Idempotent: already received -> return without double-adding stock
    if row.status == RESTOCK_STATUS_RECEIVED:
        return row

    if row.status == RESTOCK_STATUS_CANCELLED:
        raise RestockError("cancelled の restock は receive できません")

    _validate_transition(row.status, RESTOCK_STATUS_RECEIVED)

    qty = int(received_quantity) if received_quantity is not None else int(row.requested_quantity)
    if qty <= 0:
        raise RestockError("received_quantity は 1 以上である必要があります")

    card = (
        db.query(models.Card)
        .filter(models.Card.id == row.product_id)
        .with_for_update()
        .first()
    )
    if card is None:
        raise RestockError("商品が見つかりません", status_code=404)

    before_stock = int(card.stock or 0)
    card.stock = before_stock + qty
    row.received_quantity = qty
    row.status = RESTOCK_STATUS_RECEIVED
    row.completed_at = datetime.utcnow()
    row.updated_at = datetime.utcnow()

    write_inventory_audit(
        db,
        action="restock_received",
        actor_admin_user_id=actor_admin_user_id,
        product_id=row.product_id,
        restock_id=row.id,
        before={"stock": before_stock, "status": RESTOCK_STATUS_REQUESTED},
        after={
            "stock": int(card.stock),
            "received_quantity": qty,
            "status": RESTOCK_STATUS_RECEIVED,
        },
    )

    evaluate_card_inventory(
        db,
        card.id,
        actor_admin_user_id=actor_admin_user_id,
        source="restock_received",
    )
    return row


def count_open_restocks(db: Session) -> int:
    return int(
        db.query(models_inventory.InventoryRestock)
        .filter(
            models_inventory.InventoryRestock.status.in_(
                [RESTOCK_STATUS_REQUESTED, RESTOCK_STATUS_ORDERED]
            )
        )
        .count()
        or 0
    )


def raise_http(exc: RestockError) -> None:
    raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
