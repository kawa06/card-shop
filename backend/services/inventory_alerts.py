"""Phase 3-8 inventory alert evaluation and ledger."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Optional

from sqlalchemy.orm import Session

import models
import models_inventory
from services.inventory_constants import (
    ALERT_STATUS_OPEN,
    ALERT_STATUS_RESOLVED,
    ALERT_TYPE_LOW_STOCK,
    ALERT_TYPE_OUT_OF_STOCK,
    DEFAULT_LOW_STOCK_THRESHOLD,
    INVENTORY_STATUS_IN_STOCK,
    INVENTORY_STATUS_LOW_STOCK,
    INVENTORY_STATUS_OUT_OF_STOCK,
)


def effective_threshold(card: models.Card) -> int:
    raw = getattr(card, "low_stock_threshold", None)
    if raw is None:
        return DEFAULT_LOW_STOCK_THRESHOLD
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return DEFAULT_LOW_STOCK_THRESHOLD
    return max(0, value)


def alerts_enabled(card: models.Card) -> bool:
    return bool(getattr(card, "inventory_alert_enabled", True))


def inventory_status_for_stock(stock: int, threshold: int) -> str:
    qty = int(stock or 0)
    th = int(threshold)
    if qty <= 0:
        return INVENTORY_STATUS_OUT_OF_STOCK
    if qty <= th:
        return INVENTORY_STATUS_LOW_STOCK
    return INVENTORY_STATUS_IN_STOCK


def inventory_status_for_card(card: models.Card) -> str:
    return inventory_status_for_stock(int(card.stock or 0), effective_threshold(card))


def write_inventory_audit(
    db: Session,
    *,
    action: str,
    actor_admin_user_id: Optional[int] = None,
    product_id: Optional[int] = None,
    restock_id: Optional[int] = None,
    alert_id: Optional[int] = None,
    before: Any = None,
    after: Any = None,
    reason: Optional[str] = None,
) -> models_inventory.InventoryAuditLog:
    row = models_inventory.InventoryAuditLog(
        actor_admin_user_id=actor_admin_user_id,
        action=action,
        product_id=product_id,
        restock_id=restock_id,
        alert_id=alert_id,
        before_json=None if before is None else json.dumps(before, ensure_ascii=False, default=str),
        after_json=None if after is None else json.dumps(after, ensure_ascii=False, default=str),
        reason=reason,
    )
    db.add(row)
    return row


def _open_alert(
    db: Session,
    *,
    product_id: int,
    alert_type: str,
) -> Optional[models_inventory.InventoryAlert]:
    return (
        db.query(models_inventory.InventoryAlert)
        .filter(
            models_inventory.InventoryAlert.product_id == product_id,
            models_inventory.InventoryAlert.alert_type == alert_type,
            models_inventory.InventoryAlert.status == ALERT_STATUS_OPEN,
        )
        .order_by(models_inventory.InventoryAlert.id.desc())
        .first()
    )


def _resolve_open_alerts(
    db: Session,
    *,
    product_id: int,
    alert_types: list[str],
    actor_admin_user_id: Optional[int] = None,
    reason: str = "auto_resolve",
) -> int:
    now = datetime.utcnow()
    rows = (
        db.query(models_inventory.InventoryAlert)
        .filter(
            models_inventory.InventoryAlert.product_id == product_id,
            models_inventory.InventoryAlert.alert_type.in_(alert_types),
            models_inventory.InventoryAlert.status == ALERT_STATUS_OPEN,
        )
        .all()
    )
    for row in rows:
        row.status = ALERT_STATUS_RESOLVED
        row.resolved_at = now
        row.resolved_by = actor_admin_user_id
        write_inventory_audit(
            db,
            action="inventory_alert_auto_resolved",
            actor_admin_user_id=actor_admin_user_id,
            product_id=product_id,
            alert_id=row.id,
            after={"status": ALERT_STATUS_RESOLVED, "alert_type": row.alert_type},
            reason=reason,
        )
    return len(rows)


def evaluate_card_inventory(
    db: Session,
    card_id: int,
    *,
    actor_admin_user_id: Optional[int] = None,
    source: Optional[str] = None,
) -> Optional[str]:
    """Re-evaluate inventory status and maintain open/resolved alerts.

    Returns current inventory status string, or None if card missing.
    Does not commit — caller owns the transaction.
    """
    card = (
        db.query(models.Card)
        .filter(models.Card.id == card_id)
        .with_for_update()
        .first()
    )
    if card is None:
        return None

    stock = int(card.stock or 0)
    threshold = effective_threshold(card)
    status = inventory_status_for_stock(stock, threshold)

    if not alerts_enabled(card):
        # Still auto-resolve open alerts when alerts are disabled and stock recovered?
        # Spec: alerts when enabled. If disabled, resolve open alerts to avoid stale UI.
        _resolve_open_alerts(
            db,
            product_id=card.id,
            alert_types=[ALERT_TYPE_LOW_STOCK, ALERT_TYPE_OUT_OF_STOCK],
            actor_admin_user_id=actor_admin_user_id,
            reason="alerts_disabled_or_cleared",
        )
        return status

    meta = {"source": source} if source else None
    meta_json = None if meta is None else json.dumps(meta, ensure_ascii=False)

    if status == INVENTORY_STATUS_IN_STOCK:
        _resolve_open_alerts(
            db,
            product_id=card.id,
            alert_types=[ALERT_TYPE_LOW_STOCK, ALERT_TYPE_OUT_OF_STOCK],
            actor_admin_user_id=actor_admin_user_id,
            reason="stock_above_threshold",
        )
        return status

    if status == INVENTORY_STATUS_LOW_STOCK:
        # Out-of-stock no longer applies
        _resolve_open_alerts(
            db,
            product_id=card.id,
            alert_types=[ALERT_TYPE_OUT_OF_STOCK],
            actor_admin_user_id=actor_admin_user_id,
            reason="stock_recovered_from_zero",
        )
        existing = _open_alert(db, product_id=card.id, alert_type=ALERT_TYPE_LOW_STOCK)
        if existing is None:
            alert = models_inventory.InventoryAlert(
                product_id=card.id,
                alert_type=ALERT_TYPE_LOW_STOCK,
                stock_quantity=stock,
                threshold=threshold,
                status=ALERT_STATUS_OPEN,
                metadata_json=meta_json,
                created_by=actor_admin_user_id,
            )
            db.add(alert)
            db.flush()
            write_inventory_audit(
                db,
                action="inventory_alert_opened",
                actor_admin_user_id=actor_admin_user_id,
                product_id=card.id,
                alert_id=alert.id,
                after={
                    "alert_type": ALERT_TYPE_LOW_STOCK,
                    "stock": stock,
                    "threshold": threshold,
                },
                reason=source,
            )
        else:
            existing.stock_quantity = stock
            existing.threshold = threshold
        return status

    # out_of_stock
    existing_oos = _open_alert(db, product_id=card.id, alert_type=ALERT_TYPE_OUT_OF_STOCK)
    if existing_oos is None:
        alert = models_inventory.InventoryAlert(
            product_id=card.id,
            alert_type=ALERT_TYPE_OUT_OF_STOCK,
            stock_quantity=stock,
            threshold=threshold,
            status=ALERT_STATUS_OPEN,
            metadata_json=meta_json,
            created_by=actor_admin_user_id,
        )
        db.add(alert)
        db.flush()
        write_inventory_audit(
            db,
            action="inventory_alert_opened",
            actor_admin_user_id=actor_admin_user_id,
            product_id=card.id,
            alert_id=alert.id,
            after={
                "alert_type": ALERT_TYPE_OUT_OF_STOCK,
                "stock": stock,
                "threshold": threshold,
            },
            reason=source,
        )
    else:
        existing_oos.stock_quantity = stock
        existing_oos.threshold = threshold

    # Keep or open low_stock? Spec: stock 0 -> out_of_stock OPEN.
    # low_stock is for stock > 0 AND <= threshold. Resolve low_stock when OOS.
    _resolve_open_alerts(
        db,
        product_id=card.id,
        alert_types=[ALERT_TYPE_LOW_STOCK],
        actor_admin_user_id=actor_admin_user_id,
        reason="superseded_by_out_of_stock",
    )
    return status


def evaluate_cards_inventory(
    db: Session,
    card_ids: list[int],
    *,
    actor_admin_user_id: Optional[int] = None,
    source: Optional[str] = None,
) -> None:
    seen: set[int] = set()
    for card_id in card_ids:
        if card_id is None or card_id in seen:
            continue
        seen.add(int(card_id))
        evaluate_card_inventory(
            db,
            int(card_id),
            actor_admin_user_id=actor_admin_user_id,
            source=source,
        )


def manually_resolve_alert(
    db: Session,
    alert_id: int,
    *,
    actor_admin_user_id: Optional[int] = None,
    reason: Optional[str] = None,
) -> models_inventory.InventoryAlert:
    alert = (
        db.query(models_inventory.InventoryAlert)
        .filter(models_inventory.InventoryAlert.id == alert_id)
        .with_for_update()
        .first()
    )
    if alert is None:
        raise LookupError("alert_not_found")
    if alert.status == ALERT_STATUS_RESOLVED:
        return alert
    before = {"status": alert.status}
    alert.status = ALERT_STATUS_RESOLVED
    alert.resolved_at = datetime.utcnow()
    alert.resolved_by = actor_admin_user_id
    write_inventory_audit(
        db,
        action="inventory_alert_manually_resolved",
        actor_admin_user_id=actor_admin_user_id,
        product_id=alert.product_id,
        alert_id=alert.id,
        before=before,
        after={"status": ALERT_STATUS_RESOLVED},
        reason=reason or "manual_resolve",
    )
    # Note: if stock still below threshold, next evaluate can open a new alert.
    return alert


def count_open_alerts(db: Session, *, alert_type: Optional[str] = None) -> int:
    q = db.query(models_inventory.InventoryAlert).filter(
        models_inventory.InventoryAlert.status == ALERT_STATUS_OPEN
    )
    if alert_type:
        q = q.filter(models_inventory.InventoryAlert.alert_type == alert_type)
    return int(q.count() or 0)
