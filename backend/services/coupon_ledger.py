"""Coupon reservation / confirm / release ledger."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

import models
import models_coupons
from services.coupon_calculator import (
    CartLine,
    is_within_validity,
    quote_coupon,
)


STATUS_RESERVED = "reserved"
STATUS_USED = "used"
STATUS_RELEASED = "released"


def get_coupon_by_code(db: Session, code: str) -> Optional[models_coupons.Coupon]:
    normalized = (code or "").strip().upper()
    if not normalized:
        return None
    return (
        db.query(models_coupons.Coupon)
        .filter(func.upper(models_coupons.Coupon.code) == normalized)
        .first()
    )


def count_redemptions(
    db: Session,
    *,
    coupon_id: int,
    user_id: Optional[int] = None,
    statuses: Optional[tuple[str, ...]] = None,
    exclude_order_id: Optional[int] = None,
) -> int:
    statuses = statuses or (STATUS_RESERVED, STATUS_USED)
    q = db.query(func.count(models_coupons.CouponRedemption.id)).filter(
        models_coupons.CouponRedemption.coupon_id == coupon_id,
        models_coupons.CouponRedemption.status.in_(list(statuses)),
    )
    if user_id is not None:
        q = q.filter(models_coupons.CouponRedemption.user_id == user_id)
    if exclude_order_id is not None:
        q = q.filter(models_coupons.CouponRedemption.order_id != exclude_order_id)
    return int(q.scalar() or 0)


def user_has_assignment(db: Session, *, coupon_id: int, user_id: int) -> bool:
    return (
        db.query(models_coupons.CouponAssignment.id)
        .filter(
            models_coupons.CouponAssignment.coupon_id == coupon_id,
            models_coupons.CouponAssignment.user_id == user_id,
        )
        .first()
        is not None
    )


def validate_coupon_for_user(
    db: Session,
    *,
    coupon: models_coupons.Coupon,
    user_id: int,
    items_subtotal: int,
    shipping_fee: int,
    lines: list[CartLine],
    exclude_order_id: Optional[int] = None,
) -> tuple[int, int, int]:
    """Return (discount_amount, shipping_discount, shipping_fee_after). Raises HTTPException."""
    if not coupon.is_active:
        raise HTTPException(status_code=400, detail="このクーポンは現在無効です")
    if not is_within_validity(coupon):
        raise HTTPException(status_code=400, detail="クーポンの有効期間外です")

    if coupon.audience == "assigned" and not user_has_assignment(
        db, coupon_id=coupon.id, user_id=user_id
    ):
        raise HTTPException(status_code=400, detail="このクーポンは配布対象外です")

    if int(items_subtotal) < int(coupon.min_subtotal_yen or 0):
        raise HTTPException(
            status_code=400,
            detail=f"最低購入金額（{int(coupon.min_subtotal_yen)}円）未満です",
        )

    quote = quote_coupon(
        coupon,
        lines=lines,
        items_subtotal=items_subtotal,
        shipping_fee=shipping_fee,
    )
    if coupon.coupon_type in ("fixed_amount", "percent") and quote.discount_amount <= 0:
        raise HTTPException(status_code=400, detail="対象商品がカートにありません")
    if coupon.coupon_type == "free_shipping" and quote.shipping_discount <= 0:
        raise HTTPException(status_code=400, detail="送料が発生していないため適用できません")

    total_uses = count_redemptions(
        db, coupon_id=coupon.id, exclude_order_id=exclude_order_id
    )
    if coupon.max_uses_total is not None and total_uses >= int(coupon.max_uses_total):
        raise HTTPException(status_code=400, detail="クーポンの利用上限に達しています")

    user_uses = count_redemptions(
        db, coupon_id=coupon.id, user_id=user_id, exclude_order_id=exclude_order_id
    )
    if user_uses >= int(coupon.max_uses_per_user or 1):
        raise HTTPException(status_code=400, detail="このクーポンの利用回数上限に達しています")

    return quote.discount_amount, quote.shipping_discount, quote.shipping_fee_after


def reserve_coupon_for_order(
    db: Session,
    *,
    coupon: models_coupons.Coupon,
    user_id: int,
    order_id: int,
    discount_amount: int,
    shipping_discount: int,
) -> models_coupons.CouponRedemption:
    key = f"reserve:order:{order_id}"
    existing = (
        db.query(models_coupons.CouponRedemption)
        .filter(models_coupons.CouponRedemption.order_id == order_id)
        .first()
    )
    if existing:
        if existing.status == STATUS_RELEASED:
            existing.coupon_id = coupon.id
            existing.user_id = user_id
            existing.discount_amount = discount_amount
            existing.shipping_discount = shipping_discount
            existing.status = STATUS_RESERVED
            existing.idempotency_key = key
            existing.updated_at = datetime.utcnow()
            db.flush()
            return existing
        return existing

    by_key = (
        db.query(models_coupons.CouponRedemption)
        .filter(models_coupons.CouponRedemption.idempotency_key == key)
        .first()
    )
    if by_key:
        return by_key

    row = models_coupons.CouponRedemption(
        coupon_id=coupon.id,
        user_id=user_id,
        order_id=order_id,
        discount_amount=discount_amount,
        shipping_discount=shipping_discount,
        status=STATUS_RESERVED,
        idempotency_key=key,
    )
    db.add(row)
    db.flush()
    return row


def confirm_coupon_for_order(db: Session, *, order_id: int) -> None:
    row = (
        db.query(models_coupons.CouponRedemption)
        .filter(models_coupons.CouponRedemption.order_id == order_id)
        .first()
    )
    if not row:
        return
    if row.status == STATUS_USED:
        return
    if row.status == STATUS_RELEASED:
        return
    row.status = STATUS_USED
    row.updated_at = datetime.utcnow()
    db.flush()


def release_coupon_for_order(db: Session, *, order_id: int) -> None:
    row = (
        db.query(models_coupons.CouponRedemption)
        .filter(models_coupons.CouponRedemption.order_id == order_id)
        .first()
    )
    if not row:
        return
    if row.status == STATUS_RELEASED:
        return
    # reserved -> released; used -> released (full cancel/refund restore)
    row.status = STATUS_RELEASED
    row.updated_at = datetime.utcnow()
    db.flush()
