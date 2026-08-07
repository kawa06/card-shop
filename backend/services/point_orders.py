"""Order/checkout integration for points."""

from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy.orm import Session

import models
from services.point_calculator import (
    calculate_earn_base_yen,
    calculate_earn_points,
    calculate_max_usable_points,
    calculate_order_total_yen,
    points_to_yen,
)
from services.point_ledger import (
    confirm_points_for_order,
    earn_points_for_order,
    release_points_for_order,
    restore_used_points_for_order,
    reserve_points_for_order,
    reverse_earned_points_for_order,
)
from services.point_settings import get_point_settings


def validate_points_to_use(
    db: Session,
    *,
    user_id: int,
    points_to_use: int,
    items_subtotal: int,
    shipping_fee: int = 0,
    packaging_fee: int = 0,
    discount_amount: int = 0,
) -> int:
    """Validate and return the actually applicable points (integer)."""
    if points_to_use == 0:
        return 0
    if points_to_use < 0:
        raise HTTPException(status_code=400, detail="利用ポイントは0以上である必要があります")
    if isinstance(points_to_use, float) and not points_to_use.is_integer():
        raise HTTPException(status_code=400, detail="利用ポイントは整数である必要があります")
    points_to_use = int(points_to_use)

    settings = get_point_settings(db)
    if not settings.enabled:
        raise HTTPException(status_code=400, detail="ポイント機能は現在無効です")

    from services.point_ledger import get_account_summary

    account = get_account_summary(db, user_id)
    max_usable = calculate_max_usable_points(
        available_points=account.available_points,
        items_subtotal=items_subtotal,
        shipping_fee=shipping_fee,
        packaging_fee=packaging_fee,
        discount_amount=discount_amount,
        settings=settings,
    )
    if points_to_use > max_usable:
        raise HTTPException(
            status_code=400,
            detail=f"利用可能ポイントの上限（{max_usable}pt）を超えています",
        )
    if points_to_use > account.available_points:
        raise HTTPException(status_code=400, detail="ポイント残高が不足しています")
    return points_to_use


def preview_checkout_points(
    db: Session,
    *,
    user_id: int,
    items_subtotal: int,
    shipping_fee: int = 0,
    packaging_fee: int = 0,
    discount_amount: int = 0,
    requested_points: int = 0,
) -> dict:
    settings = get_point_settings(db)
    from services.point_ledger import get_account_summary

    account = get_account_summary(db, user_id)
    max_usable = 0
    if settings.enabled:
        max_usable = calculate_max_usable_points(
            available_points=account.available_points,
            items_subtotal=items_subtotal,
            shipping_fee=shipping_fee,
            packaging_fee=packaging_fee,
            discount_amount=discount_amount,
            settings=settings,
        )

    applied = 0
    if settings.enabled and requested_points > 0:
        try:
            applied = validate_points_to_use(
                db,
                user_id=user_id,
                points_to_use=requested_points,
                items_subtotal=items_subtotal,
                shipping_fee=shipping_fee,
                packaging_fee=packaging_fee,
                discount_amount=discount_amount,
            )
        except HTTPException:
            applied = 0

    total_yen = calculate_order_total_yen(
        items_subtotal=items_subtotal,
        shipping_fee=shipping_fee,
        packaging_fee=packaging_fee,
        discount_amount=discount_amount,
        points_used=applied,
    )
    earn_base = calculate_earn_base_yen(
        items_subtotal=items_subtotal,
        discount_amount=discount_amount,
        points_used=applied,
    )
    estimated_earn = calculate_earn_points(earn_base, settings.earn_rate_percent) if settings.enabled else 0

    return {
        "enabled": settings.enabled,
        "available_points": account.available_points,
        "reserved_points": account.reserved_points,
        "max_usable_points": max_usable,
        "requested_points": requested_points,
        "applied_points": applied,
        "total_yen": total_yen,
        "estimated_earn_points": estimated_earn,
    }


def apply_points_on_order_created(
    db: Session,
    order: models.Order,
    *,
    points_to_use: int,
) -> int:
    """Reserve points after order row exists. Returns applied points."""
    if points_to_use <= 0:
        order.points_used = 0
        order.points_reserved = 0
        return 0

    applied = validate_points_to_use(
        db,
        user_id=order.user_id,
        points_to_use=points_to_use,
        items_subtotal=int(order.items_subtotal or 0),
        shipping_fee=int(order.shipping_fee or 0),
        packaging_fee=int(order.packaging_fee or 0),
        discount_amount=int(order.discount_amount or 0),
    )
    reserve_points_for_order(
        db,
        user_id=order.user_id,
        order_id=order.id,
        amount=applied,
    )
    order.points_used = applied
    order.points_reserved = applied
    order.total_amount = calculate_order_total_yen(
        items_subtotal=int(order.items_subtotal or 0),
        shipping_fee=int(order.shipping_fee or 0),
        packaging_fee=int(order.packaging_fee or 0),
        payment_fee=int(order.payment_fee or 0),
        discount_amount=int(order.discount_amount or 0),
        points_used=applied,
    )
    order.points_earn_status = "pending"
    return applied


def on_order_paid(db: Session, order: models.Order) -> None:
    """Confirm point use and grant earn on payment success (idempotent)."""
    settings = get_point_settings(db)
    points_used = int(order.points_used or 0)

    if points_used > 0:
        confirm_points_for_order(db, user_id=order.user_id, order_id=order.id)

    if not settings.enabled:
        return
    if order.points_earn_status == "earned":
        return

    earn_base = calculate_earn_base_yen(
        items_subtotal=int(order.items_subtotal or 0),
        discount_amount=int(order.discount_amount or 0),
        points_used=points_used,
    )
    earn_amount = calculate_earn_points(earn_base, settings.earn_rate_percent)
    if earn_amount > 0:
        tx = earn_points_for_order(
            db,
            user_id=order.user_id,
            order_id=order.id,
            amount=earn_amount,
            expiration_days=settings.expiration_days,
        )
        if tx:
            order.points_earned = earn_amount
            order.points_earn_status = "earned"
    else:
        order.points_earn_status = "none"


def on_order_cancelled_or_failed(db: Session, order: models.Order) -> None:
    """Release reservation and reverse earn on cancel/fail (idempotent)."""
    points_used = int(order.points_used or 0)
    if points_used > 0:
        release_points_for_order(db, user_id=order.user_id, order_id=order.id)

    if order.points_earn_status == "earned" and int(order.points_earned or 0) > 0:
        reverse_earned_points_for_order(
            db,
            user_id=order.user_id,
            order_id=order.id,
            earn_amount=int(order.points_earned),
        )
        order.points_earn_status = "reversed"
    elif order.points_earn_status == "pending":
        order.points_earn_status = "none"


def on_order_cancelled_after_paid(db: Session, order: models.Order) -> None:
    """Restore used points and reverse earned points after paid order cancel."""
    points_used = int(order.points_used or 0)
    if points_used > 0:
        restore_used_points_for_order(
            db,
            user_id=order.user_id,
            order_id=order.id,
            amount=points_used,
        )

    if int(order.points_earned or 0) > 0 and order.points_earn_status == "earned":
        reverse_earned_points_for_order(
            db,
            user_id=order.user_id,
            order_id=order.id,
            earn_amount=int(order.points_earned),
        )
        order.points_earn_status = "reversed"


def order_points_display(order: models.Order) -> dict:
    earn_base = calculate_earn_base_yen(
        items_subtotal=int(order.items_subtotal or 0),
        discount_amount=int(order.discount_amount or 0),
        points_used=int(order.points_used or 0),
    )
    return {
        "points_used": int(order.points_used or 0),
        "points_earned": int(order.points_earned or 0),
        "points_earn_status": order.points_earn_status or "none",
        "points_discount_yen": points_to_yen(int(order.points_used or 0)),
        "earn_base_yen": earn_base,
    }
