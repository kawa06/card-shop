"""User-facing coupons API."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session

import models
import models_coupons
import schemas_coupons
from auth import get_current_user
from database import get_db
from services.coupon_calculator import is_within_validity
from services.coupon_ledger import count_redemptions, user_has_assignment
from services.coupon_orders import preview_checkout_coupon

router = APIRouter(prefix="/api/coupons", tags=["coupons"])


def _remaining_uses(db: Session, coupon: models_coupons.Coupon, user_id: int) -> int:
    used = count_redemptions(db, coupon_id=coupon.id, user_id=user_id)
    return max(0, int(coupon.max_uses_per_user or 1) - used)


def _to_user_out(db: Session, coupon: models_coupons.Coupon, user_id: int, *, assigned: bool) -> schemas_coupons.UserCouponOut:
    return schemas_coupons.UserCouponOut(
        id=coupon.id,
        code=coupon.code,
        name=coupon.name,
        description=coupon.description,
        coupon_type=coupon.coupon_type,
        amount_yen=coupon.amount_yen,
        percent_off=coupon.percent_off,
        max_discount_yen=coupon.max_discount_yen,
        min_subtotal_yen=int(coupon.min_subtotal_yen or 0),
        starts_at=coupon.starts_at,
        ends_at=coupon.ends_at,
        assigned=assigned,
        remaining_uses_for_user=_remaining_uses(db, coupon, user_id),
    )


@router.get("/mine", response_model=schemas_coupons.UserCouponListOut)
def list_my_coupons(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    now = datetime.utcnow()
    assigned_ids = {
        row.coupon_id
        for row in db.query(models_coupons.CouponAssignment)
        .filter(models_coupons.CouponAssignment.user_id == current_user.id)
        .all()
    }
    q = db.query(models_coupons.Coupon).filter(models_coupons.Coupon.is_active.is_(True))
    conditions = [models_coupons.Coupon.audience == "public"]
    if assigned_ids:
        conditions.append(models_coupons.Coupon.id.in_(list(assigned_ids)))
    q = q.filter(or_(*conditions))
    items: list[schemas_coupons.UserCouponOut] = []
    for coupon in q.order_by(models_coupons.Coupon.id.desc()).all():
        if not is_within_validity(coupon, now=now):
            continue
        if coupon.audience == "assigned" and coupon.id not in assigned_ids:
            continue
        if _remaining_uses(db, coupon, current_user.id) <= 0:
            continue
        items.append(_to_user_out(db, coupon, current_user.id, assigned=coupon.id in assigned_ids))
    return schemas_coupons.UserCouponListOut(items=items, total=len(items))


@router.post("/checkout-preview", response_model=schemas_coupons.CouponCheckoutPreviewOut)
def checkout_preview(
    payload: schemas_coupons.CouponCheckoutPreviewIn,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    result = preview_checkout_coupon(
        db,
        user_id=current_user.id,
        coupon_code=payload.coupon_code,
        items_subtotal=payload.items_subtotal,
        shipping_fee=payload.shipping_fee,
        packaging_fee=payload.packaging_fee,
        cart_items=payload.cart_items,
    )
    return schemas_coupons.CouponCheckoutPreviewOut(**result)
