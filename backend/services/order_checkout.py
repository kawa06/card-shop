"""Shared order creation and fulfillment logic."""

from __future__ import annotations

import json
from typing import Iterable

from fastapi import HTTPException
from sqlalchemy.orm import Session

import models
from services.shipping_rates import calculate_shipping_fee


def get_user_cart_items(db: Session, user_id: int) -> list[models.CartItem]:
    items = (
        db.query(models.CartItem)
        .filter(models.CartItem.user_id == user_id)
        .all()
    )
    if not items:
        raise HTTPException(status_code=400, detail="カートが空です")
    return items


def validate_shipping_method(cart_items: Iterable[models.CartItem], shipping_method: str | None) -> None:
    allowed_methods_set: set[str] | None = None
    for item in cart_items:
        card = item.card
        if not card.allowed_shipping_methods:
            continue
        raw = card.allowed_shipping_methods
        if raw in ("null", "[]", ""):
            continue
        try:
            methods = json.loads(raw)
            if isinstance(methods, list) and methods:
                methods_set = set(methods)
                allowed_methods_set = methods_set if allowed_methods_set is None else allowed_methods_set.intersection(methods_set)
        except Exception:
            pass

    if allowed_methods_set is None:
        return

    if not allowed_methods_set:
        raise HTTPException(
            status_code=400,
            detail="カート内の商品の組み合わせにより、利用可能な発送方法がありません。 / No available shipping methods for this combination of items.",
        )

    if shipping_method not in allowed_methods_set:
        raise HTTPException(
            status_code=400,
            detail=f"選択された発送方法（{shipping_method}）はこの注文では利用できません。 / The selected shipping method ({shipping_method}) is not available for this order.",
        )


def validate_cart_stock(cart_items: Iterable[models.CartItem]) -> float:
    subtotal = 0.0
    for item in cart_items:
        card = item.card
        if not card.is_active:
            raise HTTPException(status_code=400, detail=f"カード「{card.name}」は現在販売されていません")
        if card.stock < item.quantity:
            raise HTTPException(status_code=400, detail=f"カード「{card.name}」の在庫が不足しています")
        subtotal += card.price * item.quantity
    return subtotal


def create_order_from_cart(
    db: Session,
    *,
    user: models.User,
    cart_items: list[models.CartItem],
    postal_code: str | None,
    country: str | None,
    region: str | None,
    city: str | None,
    address_line1: str | None,
    address_line2: str | None,
    shipping_address: str | None,
    shipping_method: str | None,
    shipping_fee: int,
    payment_method: str | None,
    payment_status: str,
    stripe_checkout_session_id: str | None = None,
    finalize: bool,
) -> models.Order:
    subtotal = validate_cart_stock(cart_items)
    order = models.Order(
        user_id=user.id,
        total_amount=round(subtotal + shipping_fee, 2),
        postal_code=postal_code,
        country=country,
        region=region,
        city=city,
        address_line1=address_line1,
        address_line2=address_line2,
        shipping_address=shipping_address,
        shipping_method=shipping_method,
        shipping_fee=shipping_fee,
        payment_method=payment_method,
        payment_status=payment_status,
        stripe_checkout_session_id=stripe_checkout_session_id,
        status=models.OrderStatus.pending,
    )
    db.add(order)
    db.flush()

    for item in cart_items:
        db.add(
            models.OrderItem(
                order_id=order.id,
                card_id=item.card_id,
                quantity=item.quantity,
                unit_price=item.card.price,
            )
        )

    if finalize:
        apply_inventory_for_order(db, order)

    db.commit()
    db.refresh(order)
    return order


def apply_inventory_for_order(db: Session, order: models.Order) -> None:
    for order_item in order.items:
        card = db.query(models.Card).filter(models.Card.id == order_item.card_id).with_for_update().first()
        if not card:
            raise HTTPException(status_code=400, detail="カードが見つかりません")
        if card.stock < order_item.quantity:
            raise HTTPException(status_code=400, detail=f"カード「{card.name}」の在庫が不足しています")
        card.stock -= order_item.quantity

    for order_item in order.items:
        cart_item = (
            db.query(models.CartItem)
            .filter(
                models.CartItem.user_id == order.user_id,
                models.CartItem.card_id == order_item.card_id,
            )
            .first()
        )
        if cart_item:
            if cart_item.quantity <= order_item.quantity:
                db.delete(cart_item)
            else:
                cart_item.quantity -= order_item.quantity


def fulfill_order_inventory(
    db: Session,
    order_id: int,
) -> models.Order:
    order = db.query(models.Order).filter(models.Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="注文が見つかりません")

    if order.payment_status == "paid":
        return order

    apply_inventory_for_order(db, order)

    order.payment_status = "paid"
    order.status = models.OrderStatus.processing
    db.commit()
    db.refresh(order)
    return order


def cancel_unpaid_order(db: Session, order: models.Order) -> None:
    if order.payment_status == "paid":
        return
    db.query(models.OrderItem).filter(models.OrderItem.order_id == order.id).delete()
    db.delete(order)
    db.commit()


def resolve_shipping_fee(shipping_method: str | None, region: str | None, country: str | None, db: Session) -> int:
    if not shipping_method:
        return 0
    return calculate_shipping_fee(shipping_method, region, country, db=db)
