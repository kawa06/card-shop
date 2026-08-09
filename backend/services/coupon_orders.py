"""Order/checkout integration for coupons."""

from __future__ import annotations

from typing import Optional, Sequence

from fastapi import HTTPException
from sqlalchemy.orm import Session, joinedload

import models
from services.coupon_calculator import CartLine, lines_from_payload, quote_coupon
from services.coupon_ledger import (
    confirm_coupon_for_order,
    get_coupon_by_code,
    release_coupon_for_order,
    reserve_coupon_for_order,
    validate_coupon_for_user,
)
from services.point_calculator import calculate_order_total_yen


def cart_lines_from_order(db: Session, order: models.Order) -> list[CartLine]:
    items = (
        db.query(models.OrderItem)
        .options(joinedload(models.OrderItem.card))
        .filter(models.OrderItem.order_id == order.id)
        .all()
    )
    lines: list[CartLine] = []
    for item in items:
        category_id = None
        if item.card is not None:
            category_id = item.card.category_id
        lines.append(
            CartLine(
                card_id=int(item.card_id),
                quantity=int(item.quantity),
                unit_price=int(round(float(item.unit_price or 0))),
                category_id=int(category_id) if category_id is not None else None,
            )
        )
    return lines


def preview_checkout_coupon(
    db: Session,
    *,
    user_id: int,
    coupon_code: str,
    items_subtotal: int,
    shipping_fee: int = 0,
    packaging_fee: int = 0,
    cart_items: Optional[Sequence[dict]] = None,
) -> dict:
    coupon = get_coupon_by_code(db, coupon_code)
    if not coupon:
        return {
            "valid": False,
            "coupon_code": (coupon_code or "").strip().upper() or None,
            "discount_amount": 0,
            "shipping_fee_after": int(shipping_fee),
            "shipping_discount": 0,
            "total_yen_before_points": calculate_order_total_yen(
                items_subtotal=items_subtotal,
                shipping_fee=shipping_fee,
                packaging_fee=packaging_fee,
            ),
            "message": "クーポンコードが見つかりません",
        }

    lines = lines_from_payload(cart_items)
    try:
        discount, shipping_discount, shipping_after = validate_coupon_for_user(
            db,
            coupon=coupon,
            user_id=user_id,
            items_subtotal=items_subtotal,
            shipping_fee=shipping_fee,
            lines=lines,
        )
    except HTTPException as exc:
        return {
            "valid": False,
            "coupon_code": coupon.code,
            "coupon_name": coupon.name,
            "coupon_type": coupon.coupon_type,
            "discount_amount": 0,
            "shipping_fee_after": int(shipping_fee),
            "shipping_discount": 0,
            "total_yen_before_points": calculate_order_total_yen(
                items_subtotal=items_subtotal,
                shipping_fee=shipping_fee,
                packaging_fee=packaging_fee,
            ),
            "message": str(exc.detail),
        }

    total = calculate_order_total_yen(
        items_subtotal=items_subtotal,
        shipping_fee=shipping_after,
        packaging_fee=packaging_fee,
        discount_amount=discount,
    )
    return {
        "valid": True,
        "coupon_code": coupon.code,
        "coupon_name": coupon.name,
        "coupon_type": coupon.coupon_type,
        "discount_amount": discount,
        "shipping_fee_after": shipping_after,
        "shipping_discount": shipping_discount,
        "total_yen_before_points": total,
        "message": None,
    }


def apply_coupon_on_order_created(
    db: Session,
    order: models.Order,
    *,
    coupon_code: Optional[str],
) -> int:
    """Apply coupon after order exists. Returns discount_amount. Mutates order."""
    code = (coupon_code or "").strip()
    if not code:
        return 0

    coupon = get_coupon_by_code(db, code)
    if not coupon:
        raise HTTPException(status_code=400, detail="クーポンコードが見つかりません")

    lines = cart_lines_from_order(db, order)
    discount, shipping_discount, shipping_after = validate_coupon_for_user(
        db,
        coupon=coupon,
        user_id=order.user_id,
        items_subtotal=int(order.items_subtotal or 0),
        shipping_fee=int(order.shipping_fee or 0),
        lines=lines,
        exclude_order_id=order.id,
    )

    reserve_coupon_for_order(
        db,
        coupon=coupon,
        user_id=order.user_id,
        order_id=order.id,
        discount_amount=discount,
        shipping_discount=shipping_discount,
    )

    order.coupon_code = coupon.code
    order.coupon_name = coupon.name
    order.discount_amount = int(discount)
    if shipping_discount > 0:
        order.shipping_fee = int(shipping_after)

    order.total_amount = calculate_order_total_yen(
        items_subtotal=int(order.items_subtotal or 0),
        shipping_fee=int(order.shipping_fee or 0),
        packaging_fee=int(order.packaging_fee or 0),
        payment_fee=int(order.payment_fee or 0),
        discount_amount=int(order.discount_amount or 0),
        points_used=int(order.points_used or 0),
    )
    return discount


def on_order_paid_coupon(db: Session, order: models.Order) -> None:
    confirm_coupon_for_order(db, order_id=order.id)


def on_coupon_order_cancelled(db: Session, order: models.Order) -> None:
    release_coupon_for_order(db, order_id=order.id)
