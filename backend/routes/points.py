"""User-facing points API."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

import models
import schemas_points
from auth import get_current_user
from database import get_db
from services.point_ledger import get_account_summary, get_expiring_soon_points
import models_points
from services.point_orders import preview_checkout_points

router = APIRouter(prefix="/api/points", tags=["points"])


@router.get("/balance", response_model=schemas_points.PointBalanceOut)
def get_my_balance(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    account = get_account_summary(db, current_user.id)
    expiring = get_expiring_soon_points(db, current_user.id)
    return schemas_points.PointBalanceOut(
        available_points=account.available_points,
        reserved_points=account.reserved_points,
        lifetime_earned=account.lifetime_earned,
        lifetime_used=account.lifetime_used,
        expiring_soon_points=expiring,
    )


@router.get("/history", response_model=schemas_points.PointHistoryOut)
def get_my_history(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = (
        db.query(models_points.PointTransaction)
        .filter(models_points.PointTransaction.user_id == current_user.id)
        .order_by(models_points.PointTransaction.created_at.desc())
    )
    total = query.count()
    items = query.offset(offset).limit(limit).all()
    return schemas_points.PointHistoryOut(items=items, total=total)


@router.post("/checkout-preview", response_model=schemas_points.PointCheckoutPreviewOut)
def checkout_preview(
    payload: schemas_points.PointCheckoutPreviewIn,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    result = preview_checkout_points(
        db,
        user_id=current_user.id,
        items_subtotal=payload.items_subtotal,
        shipping_fee=payload.shipping_fee,
        packaging_fee=payload.packaging_fee,
        discount_amount=payload.discount_amount,
        requested_points=payload.requested_points,
    )
    return schemas_points.PointCheckoutPreviewOut(**result)
