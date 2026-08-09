"""Phase 3-9 public / customer Oripa API (content-secret)."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

import models
import models_oripa
import schemas_oripa_public
from auth import get_current_user
from database import get_db
from services.oripa_assignment import assign_oripa_entries, list_purchase_entry_numbers
from services.oripa_admin import OripaError, raise_http
from services.oripa_constants import (
    ENTRY_ASSIGNMENT_ASSIGNED,
    ENTRY_ASSIGNMENT_AVAILABLE,
    ENTRY_SHIPMENT_HELD,
    ORIPA_STATUS_ON_SALE,
    format_entry_number,
)

router = APIRouter(prefix="/api", tags=["oripa"])

# Fields that must never appear in customer JSON (defense-in-depth documentation).
FORBIDDEN_CUSTOMER_FIELDS = {
    "linked_product_id",
    "linked_product_name",
    "linked_inventory_id",
    "prize_tier",
    "rarity",
    "cost",
    "market_price",
    "win",
    "lose",
    "当たり",
    "ハズレ",
}


def _remaining(db: Session, oripa_id: int) -> int:
    return int(
        db.query(func.count(models_oripa.OripaEntry.id))
        .filter(
            models_oripa.OripaEntry.oripa_id == oripa_id,
            models_oripa.OripaEntry.assignment_status == ENTRY_ASSIGNMENT_AVAILABLE,
        )
        .scalar()
        or 0
    )


def _public_oripa(db: Session, row: models_oripa.Oripa) -> schemas_oripa_public.OripaPublicOut:
    return schemas_oripa_public.OripaPublicOut(
        id=row.id,
        title=row.title,
        description=row.description,
        price_per_entry=float(row.price_per_entry),
        total_entries=int(row.total_entries),
        remaining_entries=_remaining(db, row.id),
        status=row.status,
        sale_start_at=row.sale_start_at,
        sale_end_at=row.sale_end_at,
        max_entries_per_purchase=int(row.max_entries_per_purchase),
    )


@router.get("/oripas", response_model=schemas_oripa_public.OripaPublicListOut)
def list_public_oripas(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    query = db.query(models_oripa.Oripa).filter(models_oripa.Oripa.status == ORIPA_STATUS_ON_SALE)
    total = query.count()
    rows = query.order_by(models_oripa.Oripa.id.desc()).offset(offset).limit(limit).all()
    return schemas_oripa_public.OripaPublicListOut(
        total=total,
        items=[_public_oripa(db, r) for r in rows],
    )


@router.get("/oripas/{oripa_id}", response_model=schemas_oripa_public.OripaPublicOut)
def get_public_oripa(oripa_id: int, db: Session = Depends(get_db)):
    row = db.query(models_oripa.Oripa).filter(models_oripa.Oripa.id == oripa_id).first()
    if row is None or row.status not in {ORIPA_STATUS_ON_SALE, "sold_out", "ended"}:
        # Hide drafts from public
        if row is None or row.status == "draft" or row.status == "scheduled":
            raise HTTPException(status_code=404, detail="オリパが見つかりません")
    return _public_oripa(db, row)


@router.post("/oripas/{oripa_id}/purchase", response_model=schemas_oripa_public.OripaPurchaseResultOut)
def purchase_oripa(
    oripa_id: int,
    payload: schemas_oripa_public.OripaPurchaseIn,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    """Purchase entries and assign numbers.

    Step 4: assignment runs in this request after auth.
    Stripe checkout integration is layered in later shipping/payment steps;
    idempotency_key must be used by clients / webhooks to avoid double assign.
    """
    try:
        purchase = assign_oripa_entries(
            db,
            oripa_id=oripa_id,
            user_id=user.id,
            quantity=payload.quantity,
            idempotency_key=payload.idempotency_key,
        )
        db.commit()
        nums = list_purchase_entry_numbers(db, purchase.id)
        return schemas_oripa_public.OripaPurchaseResultOut(
            purchase_id=purchase.id,
            oripa_id=oripa_id,
            quantity=purchase.quantity,
            entry_labels=[format_entry_number(n) for n in nums],
            status=purchase.status,
        )
    except OripaError as exc:
        db.rollback()
        raise_http(exc)


@router.get("/me/oripa-entries", response_model=schemas_oripa_public.OripaHeldListOut)
def my_oripa_entries(
    shipment_status: Optional[str] = Query("held"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    query = db.query(models_oripa.OripaEntry).filter(
        models_oripa.OripaEntry.assigned_user_id == user.id,
        models_oripa.OripaEntry.assignment_status == ENTRY_ASSIGNMENT_ASSIGNED,
    )
    if shipment_status:
        query = query.filter(models_oripa.OripaEntry.shipment_status == shipment_status)
    total = query.count()
    rows = (
        query.order_by(models_oripa.OripaEntry.assigned_at.desc(), models_oripa.OripaEntry.id.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    items: list[schemas_oripa_public.OripaEntryPublicOut] = []
    for row in rows:
        oripa = db.query(models_oripa.Oripa).filter(models_oripa.Oripa.id == row.oripa_id).first()
        items.append(
            schemas_oripa_public.OripaEntryPublicOut(
                id=row.id,
                oripa_id=row.oripa_id,
                oripa_title=oripa.title if oripa else None,
                entry_label=format_entry_number(row.entry_number),
                assignment_status=row.assignment_status,
                shipment_status=row.shipment_status,
                assigned_at=row.assigned_at,
                purchase_id=row.assigned_purchase_id,
            )
        )
    return schemas_oripa_public.OripaHeldListOut(total=total, items=items)
