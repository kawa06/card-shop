"""Phase 3-9 Oripa admin service (CRUD, entry generation, linking, audit)."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

import models
import models_oripa
from services.oripa_constants import (
    ENTRY_ASSIGNMENT_AVAILABLE,
    ENTRY_SHIPMENT_HELD,
    ORIPA_STATUS_DRAFT,
    ORIPA_STATUS_TRANSITIONS,
    ORIPA_STATUSES,
    format_entry_number,
)


class OripaError(Exception):
    def __init__(self, detail: str, status_code: int = 400):
        self.detail = detail
        self.status_code = status_code
        super().__init__(detail)


def raise_http(exc: OripaError):
    from fastapi import HTTPException

    raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc


def write_oripa_audit(
    db: Session,
    *,
    action: str,
    actor_admin_user_id: Optional[int] = None,
    oripa_id: Optional[int] = None,
    entry_id: Optional[int] = None,
    before: Any = None,
    after: Any = None,
    reason: Optional[str] = None,
) -> None:
    db.add(
        models_oripa.OripaAuditLog(
            actor_admin_user_id=actor_admin_user_id,
            action=action,
            oripa_id=oripa_id,
            entry_id=entry_id,
            before_json=None if before is None else json.dumps(before, ensure_ascii=False, default=str),
            after_json=None if after is None else json.dumps(after, ensure_ascii=False, default=str),
            reason=reason,
        )
    )


def _counts(db: Session, oripa_id: int) -> dict[str, int]:
    available = (
        db.query(func.count(models_oripa.OripaEntry.id))
        .filter(
            models_oripa.OripaEntry.oripa_id == oripa_id,
            models_oripa.OripaEntry.assignment_status == ENTRY_ASSIGNMENT_AVAILABLE,
        )
        .scalar()
        or 0
    )
    assigned = (
        db.query(func.count(models_oripa.OripaEntry.id))
        .filter(
            models_oripa.OripaEntry.oripa_id == oripa_id,
            models_oripa.OripaEntry.assignment_status != ENTRY_ASSIGNMENT_AVAILABLE,
        )
        .scalar()
        or 0
    )
    linked = (
        db.query(func.count(models_oripa.OripaEntry.id))
        .filter(
            models_oripa.OripaEntry.oripa_id == oripa_id,
            models_oripa.OripaEntry.linked_product_id.isnot(None),
        )
        .scalar()
        or 0
    )
    return {
        "available_entries": int(available),
        "assigned_entries": int(assigned),
        "linked_entries": int(linked),
    }


def oripa_to_out(db: Session, row: models_oripa.Oripa) -> dict:
    c = _counts(db, row.id)
    return {
        "id": row.id,
        "title": row.title,
        "description": row.description,
        "price_per_entry": float(row.price_per_entry),
        "total_entries": int(row.total_entries),
        "status": row.status,
        "sale_start_at": row.sale_start_at,
        "sale_end_at": row.sale_end_at,
        "max_entries_per_purchase": int(row.max_entries_per_purchase),
        "created_at": row.created_at,
        "updated_at": row.updated_at,
        "created_by": row.created_by,
        **c,
    }


def entry_to_admin_out(db: Session, row: models_oripa.OripaEntry) -> dict:
    name = None
    if row.linked_product_id:
        card = db.query(models.Card).filter(models.Card.id == row.linked_product_id).first()
        name = card.name if card else None
    return {
        "id": row.id,
        "oripa_id": row.oripa_id,
        "entry_number": int(row.entry_number),
        "entry_label": format_entry_number(row.entry_number),
        "linked_product_id": row.linked_product_id,
        "linked_product_name": name,
        "assignment_status": row.assignment_status,
        "assigned_user_id": row.assigned_user_id,
        "assigned_order_id": row.assigned_order_id,
        "assigned_purchase_id": row.assigned_purchase_id,
        "assigned_at": row.assigned_at,
        "shipment_status": row.shipment_status,
        "shipment_id": row.shipment_id,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }


def create_oripa(
    db: Session,
    *,
    title: str,
    description: Optional[str],
    price_per_entry: float,
    total_entries: int,
    status: str = ORIPA_STATUS_DRAFT,
    sale_start_at: Optional[datetime] = None,
    sale_end_at: Optional[datetime] = None,
    max_entries_per_purchase: int = 10,
    actor_admin_user_id: Optional[int] = None,
) -> models_oripa.Oripa:
    if status not in ORIPA_STATUSES:
        raise OripaError(f"不正な status: {status}")
    if sale_start_at and sale_end_at and sale_end_at < sale_start_at:
        raise OripaError("sale_end_at は sale_start_at 以降である必要があります")

    row = models_oripa.Oripa(
        title=title.strip(),
        description=description,
        price_per_entry=float(price_per_entry),
        total_entries=int(total_entries),
        status=status,
        sale_start_at=sale_start_at,
        sale_end_at=sale_end_at,
        max_entries_per_purchase=int(max_entries_per_purchase),
        created_by=actor_admin_user_id,
    )
    db.add(row)
    db.flush()
    write_oripa_audit(
        db,
        action="oripa_created",
        actor_admin_user_id=actor_admin_user_id,
        oripa_id=row.id,
        after=oripa_to_out(db, row),
    )
    return row


def update_oripa(
    db: Session,
    oripa_id: int,
    *,
    actor_admin_user_id: Optional[int] = None,
    **fields: Any,
) -> models_oripa.Oripa:
    row = db.query(models_oripa.Oripa).filter(models_oripa.Oripa.id == oripa_id).first()
    if row is None:
        raise OripaError("オリパが見つかりません", status_code=404)

    before = oripa_to_out(db, row)
    data = {k: v for k, v in fields.items() if v is not None}

    if "status" in data:
        new_status = data["status"]
        if new_status not in ORIPA_STATUSES:
            raise OripaError(f"不正な status: {new_status}")
        if new_status != row.status:
            allowed = ORIPA_STATUS_TRANSITIONS.get(row.status, set())
            if new_status not in allowed:
                raise OripaError(f"不正な状態遷移です: {row.status} -> {new_status}")

    if "title" in data:
        row.title = str(data["title"]).strip()
    if "description" in data:
        row.description = data["description"]
    if "price_per_entry" in data:
        row.price_per_entry = float(data["price_per_entry"])
    if "status" in data:
        row.status = data["status"]
    if "sale_start_at" in data:
        row.sale_start_at = data["sale_start_at"]
    if "sale_end_at" in data:
        row.sale_end_at = data["sale_end_at"]
    if "max_entries_per_purchase" in data:
        row.max_entries_per_purchase = int(data["max_entries_per_purchase"])

    if row.sale_start_at and row.sale_end_at and row.sale_end_at < row.sale_start_at:
        raise OripaError("sale_end_at は sale_start_at 以降である必要があります")

    row.updated_at = datetime.utcnow()
    write_oripa_audit(
        db,
        action="oripa_updated",
        actor_admin_user_id=actor_admin_user_id,
        oripa_id=row.id,
        before=before,
        after=oripa_to_out(db, row),
    )
    return row


def delete_oripa(
    db: Session,
    oripa_id: int,
    *,
    actor_admin_user_id: Optional[int] = None,
) -> None:
    row = db.query(models_oripa.Oripa).filter(models_oripa.Oripa.id == oripa_id).first()
    if row is None:
        raise OripaError("オリパが見つかりません", status_code=404)
    assigned = (
        db.query(func.count(models_oripa.OripaEntry.id))
        .filter(
            models_oripa.OripaEntry.oripa_id == oripa_id,
            models_oripa.OripaEntry.assignment_status != ENTRY_ASSIGNMENT_AVAILABLE,
        )
        .scalar()
        or 0
    )
    if assigned:
        raise OripaError("割当済み番号があるオリパは削除できません")
    before = oripa_to_out(db, row)
    db.query(models_oripa.OripaEntry).filter(models_oripa.OripaEntry.oripa_id == oripa_id).delete()
    db.delete(row)
    write_oripa_audit(
        db,
        action="oripa_deleted",
        actor_admin_user_id=actor_admin_user_id,
        oripa_id=oripa_id,
        before=before,
    )


def generate_entries(
    db: Session,
    oripa_id: int,
    *,
    actor_admin_user_id: Optional[int] = None,
    force: bool = False,
) -> int:
    row = db.query(models_oripa.Oripa).filter(models_oripa.Oripa.id == oripa_id).first()
    if row is None:
        raise OripaError("オリパが見つかりません", status_code=404)

    existing = (
        db.query(func.count(models_oripa.OripaEntry.id))
        .filter(models_oripa.OripaEntry.oripa_id == oripa_id)
        .scalar()
        or 0
    )
    if existing and not force:
        raise OripaError("番号は既に生成済みです。再生成する場合は force=true を指定してください")
    if existing and force:
        assigned = (
            db.query(func.count(models_oripa.OripaEntry.id))
            .filter(
                models_oripa.OripaEntry.oripa_id == oripa_id,
                models_oripa.OripaEntry.assignment_status != ENTRY_ASSIGNMENT_AVAILABLE,
            )
            .scalar()
            or 0
        )
        if assigned:
            raise OripaError("割当済み番号があるため再生成できません")
        db.query(models_oripa.OripaEntry).filter(models_oripa.OripaEntry.oripa_id == oripa_id).delete()

    for n in range(1, int(row.total_entries) + 1):
        db.add(
            models_oripa.OripaEntry(
                oripa_id=oripa_id,
                entry_number=n,
                assignment_status=ENTRY_ASSIGNMENT_AVAILABLE,
                shipment_status=ENTRY_SHIPMENT_HELD,
            )
        )
    db.flush()
    write_oripa_audit(
        db,
        action="oripa_entries_generated",
        actor_admin_user_id=actor_admin_user_id,
        oripa_id=oripa_id,
        after={"total_entries": int(row.total_entries)},
    )
    return int(row.total_entries)


def link_entry_product(
    db: Session,
    entry_id: int,
    linked_product_id: Optional[int],
    *,
    actor_admin_user_id: Optional[int] = None,
) -> models_oripa.OripaEntry:
    entry = db.query(models_oripa.OripaEntry).filter(models_oripa.OripaEntry.id == entry_id).first()
    if entry is None:
        raise OripaError("番号が見つかりません", status_code=404)
    if linked_product_id is not None:
        card = db.query(models.Card).filter(models.Card.id == linked_product_id).first()
        if card is None:
            raise OripaError("商品が見つかりません", status_code=404)
    before = {"linked_product_id": entry.linked_product_id}
    entry.linked_product_id = linked_product_id
    entry.updated_at = datetime.utcnow()
    write_oripa_audit(
        db,
        action="oripa_entry_linked",
        actor_admin_user_id=actor_admin_user_id,
        oripa_id=entry.oripa_id,
        entry_id=entry.id,
        before=before,
        after={"linked_product_id": linked_product_id},
    )
    return entry


def bulk_link_products(
    db: Session,
    oripa_id: int,
    *,
    start_number: int,
    product_ids: list[int],
    actor_admin_user_id: Optional[int] = None,
) -> int:
    oripa = db.query(models_oripa.Oripa).filter(models_oripa.Oripa.id == oripa_id).first()
    if oripa is None:
        raise OripaError("オリパが見つかりません", status_code=404)
    count = 0
    for i, pid in enumerate(product_ids):
        num = start_number + i
        entry = (
            db.query(models_oripa.OripaEntry)
            .filter(
                models_oripa.OripaEntry.oripa_id == oripa_id,
                models_oripa.OripaEntry.entry_number == num,
            )
            .first()
        )
        if entry is None:
            raise OripaError(f"番号 {format_entry_number(num)} が見つかりません", status_code=404)
        link_entry_product(
            db,
            entry.id,
            pid,
            actor_admin_user_id=actor_admin_user_id,
        )
        count += 1
    return count
