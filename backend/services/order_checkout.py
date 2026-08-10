"""Shared order creation and fulfillment logic."""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Iterable

from fastapi import HTTPException
from sqlalchemy.orm import Session, joinedload

import models
from config import settings
from services.shipping_rates import calculate_shipping_fee, calculate_shipping_quote
from services.countries import is_domestic_japan, INTERNATIONAL_METHOD_CODES
from services.shipping_display import normalize_method_code
from services.order_number import assign_order_number
from services.order_emails import try_auto_purchase_email_after_payment, try_auto_bank_transfer_cancelled_email

BANK_TRANSFER_METHODS = {"stripe_bank_transfer", "bank_transfer"}
TERMINAL_PAYMENT_STATUSES = {"paid", "cancelled", "expired"}


def get_user_cart_items(db: Session, user_id: int) -> list[models.CartItem]:
    items = (
        db.query(models.CartItem)
        .filter(models.CartItem.user_id == user_id)
        .all()
    )
    if not items:
        raise HTTPException(status_code=400, detail="カートが空です")
    return items


def validate_shipping_method(
    cart_items: Iterable[models.CartItem],
    shipping_method: str | None,
    country: str | None = None,
) -> None:
    shipping_method = normalize_method_code(shipping_method)
    if shipping_method in INTERNATIONAL_METHOD_CODES and not is_domestic_japan(country):
        return

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
                methods_set = {
                    normalize_method_code(m) or m
                    for m in methods
                    if isinstance(m, str) and m
                }
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


def _deduct_stock_locked(db: Session, order: models.Order) -> None:
    """Decrement stock with row-level locks to prevent overselling."""
    for order_item in order.items:
        if order_item.card_id is None:
            continue
        card = (
            db.query(models.Card)
            .filter(models.Card.id == order_item.card_id)
            .with_for_update()
            .first()
        )
        if not card:
            raise HTTPException(status_code=400, detail="カードが見つかりません")
        if card.stock < order_item.quantity:
            raise HTTPException(
                status_code=400,
                detail=f"カード「{card.name}」の在庫が不足しています（取り置き競合）",
            )
        card.stock -= order_item.quantity
    from services.inventory_alerts import evaluate_cards_inventory

    evaluate_cards_inventory(
        db,
        [int(oi.card_id) for oi in order.items if oi.card_id],
        source="order_stock_deduct",
    )


def reserve_inventory_for_order(db: Session, order: models.Order) -> None:
    """Hold stock for a bank-transfer order (deduct from available inventory)."""
    if order.stock_reserved:
        return
    _deduct_stock_locked(db, order)
    order.stock_reserved = True
    db.flush()


def release_inventory_for_order(db: Session, order: models.Order) -> None:
    """Restore stock when a reserved bank-transfer order is cancelled or expires."""
    if not order.stock_reserved:
        return
    order_items = (
        db.query(models.OrderItem)
        .filter(models.OrderItem.order_id == order.id)
        .all()
    )
    for order_item in order_items:
        if order_item.card_id is None:
            continue
        card = (
            db.query(models.Card)
            .filter(models.Card.id == order_item.card_id)
            .with_for_update()
            .first()
        )
        if card:
            card.stock += order_item.quantity
    order.stock_reserved = False
    from services.inventory_alerts import evaluate_cards_inventory

    evaluate_cards_inventory(
        db,
        [int(oi.card_id) for oi in order_items if oi.card_id],
        source="order_stock_release",
    )


def bank_transfer_payment_deadline() -> datetime:
    hours = settings.BANK_TRANSFER_PAYMENT_DEADLINE_HOURS
    return datetime.utcnow() + timedelta(hours=hours)


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
    packaging_fee: int = 0,
    payment_fee: int = 0,
    discount_amount: int = 0,
    items_subtotal: int | None = None,
    tax_rate_snapshot: int | None = None,
    payment_method: str | None,
    payment_status: str,
    stripe_checkout_session_id: str | None = None,
    finalize: bool,
    reserve_stock: bool = False,
    payment_deadline: datetime | None = None,
) -> models.Order:
    validate_cart_stock(cart_items)
    subtotal = int(round(items_subtotal if items_subtotal is not None else sum(item.card.price * item.quantity for item in cart_items)))
    shipping_total = int(shipping_fee) + int(packaging_fee)
    order_total = subtotal + shipping_total + int(payment_fee) - int(discount_amount)

    order = models.Order(
        user_id=user.id,
        total_amount=round(order_total, 2),
        items_subtotal=subtotal,
        tax_rate_snapshot=tax_rate_snapshot,
        postal_code=postal_code,
        country=country,
        region=region,
        city=city,
        address_line1=address_line1,
        address_line2=address_line2,
        shipping_address=shipping_address,
        shipping_method=shipping_method,
        shipping_fee=int(shipping_fee),
        packaging_fee=int(packaging_fee),
        payment_fee=int(payment_fee),
        discount_amount=int(discount_amount),
        payment_method=payment_method,
        payment_status=payment_status,
        stripe_checkout_session_id=stripe_checkout_session_id,
        status=models.OrderStatus.pending,
        payment_deadline=payment_deadline,
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
                product_name=item.card.name,
            )
        )

    db.flush()
    db.refresh(order)

    if reserve_stock:
        reserve_inventory_for_order(db, order)
        clear_cart_for_order(db, order)
    elif finalize:
        apply_inventory_for_order(db, order)

    db.commit()
    db.refresh(order)
    return order


def apply_inventory_for_order(db: Session, order: models.Order) -> None:
    if order.stock_reserved:
        return
    _deduct_stock_locked(db, order)
    clear_cart_for_order(db, order)


def fulfill_order_inventory(
    db: Session,
    order_id: int,
    *,
    stripe_payment_intent_id: str | None = None,
    stripe_event_id: str | None = None,
) -> models.Order:
    order = (
        db.query(models.Order)
        .options(
            joinedload(models.Order.items).joinedload(models.OrderItem.card),
            joinedload(models.Order.user),
        )
        .filter(models.Order.id == order_id)
        .first()
    )
    if not order:
        raise HTTPException(status_code=404, detail="注文が見つかりません")

    if order.payment_status == "paid":
        return order

    if order.payment_status in TERMINAL_PAYMENT_STATUSES - {"paid"}:
        raise HTTPException(status_code=400, detail="この注文は入金待ちではありません")

    if not order.stock_reserved:
        apply_inventory_for_order(db, order)
    else:
        order.stock_reserved = False

    order.payment_status = "paid"
    order.status = models.OrderStatus.processing
    order.shipping_status = "preparing"
    order.paid_at = datetime.utcnow()
    if stripe_payment_intent_id:
        order.stripe_payment_intent_id = stripe_payment_intent_id
    if stripe_event_id:
        order.stripe_event_id = stripe_event_id

    assign_order_number(db, order)
    from services.point_orders import on_order_paid
    from services.oripa_payment import confirm_oripa_purchase_for_order

    on_order_paid(db, order)
    confirm_oripa_purchase_for_order(db, order)
    db.commit()
    db.refresh(order)

    try_auto_purchase_email_after_payment(db, order)
    db.refresh(order)
    try:
        from services.notification_events import notify_order_paid

        notify_order_paid(db, order)
        db.commit()
    except Exception:
        pass
    return order


def clear_cart_for_order(db: Session, order: models.Order) -> None:
    for order_item in order.items:
        if order_item.card_id is None:
            continue
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


def cancel_unpaid_order(
    db: Session,
    order: models.Order,
    *,
    as_expired: bool = False,
) -> None:
    """Cancel an unpaid order, releasing reserved stock when applicable."""
    if order.payment_status == "paid":
        return
    if order.payment_status in TERMINAL_PAYMENT_STATUSES - {"paid"}:
        return

    release_inventory_for_order(db, order)
    from services.point_orders import on_order_cancelled_or_failed
    from services.coupon_orders import on_coupon_order_cancelled
    from services.oripa_payment import release_oripa_reservations_for_order

    release_oripa_reservations_for_order(
        db,
        order,
        reason="expired" if as_expired else "cancelled",
        as_expired=as_expired,
    )
    on_order_cancelled_or_failed(db, order)
    on_coupon_order_cancelled(db, order)
    order.payment_status = "expired" if as_expired else "cancelled"
    order.status = models.OrderStatus.cancelled
    order.shipping_status = "cancelled"
    db.commit()
    db.refresh(order)
    if order.payment_method in BANK_TRANSFER_METHODS:
        try_auto_bank_transfer_cancelled_email(db, order, as_expired=as_expired)


def expire_overdue_bank_transfer_orders(db: Session) -> int:
    """Auto-cancel bank transfer orders past payment_deadline. Returns count expired."""
    now = datetime.utcnow()
    orders = (
        db.query(models.Order)
        .filter(
            models.Order.payment_status == "awaiting_payment",
            models.Order.payment_deadline.isnot(None),
            models.Order.payment_deadline < now,
        )
        .all()
    )
    count = 0
    for order in orders:
        if order.payment_status != "awaiting_payment":
            continue
        cancel_unpaid_order(db, order, as_expired=True)
        count += 1
    return count


def extend_payment_deadline(
    db: Session,
    order: models.Order,
    *,
    hours: int | None = None,
    new_deadline: datetime | None = None,
) -> models.Order:
    if order.payment_status != "awaiting_payment":
        raise HTTPException(status_code=400, detail="入金待ちの注文のみ期限延長できます")

    if new_deadline:
        order.payment_deadline = new_deadline
    elif hours is not None:
        base = order.payment_deadline or datetime.utcnow()
        order.payment_deadline = base + timedelta(hours=hours)
    else:
        raise HTTPException(status_code=400, detail="延長時間または新しい期限を指定してください")

    db.commit()
    db.refresh(order)
    return order


def resolve_shipping_quote(
    shipping_method: str | None,
    region: str | None,
    country: str | None,
    db: Session,
) -> dict:
    if not shipping_method:
        return {"fee_jpy": 0, "base_shipping_fee_jpy": 0, "packaging_fee_jpy": 0}
    shipping_method = normalize_method_code(shipping_method) or shipping_method
    return calculate_shipping_quote(shipping_method, region, country, db=db)


def resolve_shipping_fee(shipping_method: str | None, region: str | None, country: str | None, db: Session) -> int:
    return int(resolve_shipping_quote(shipping_method, region, country, db)["fee_jpy"])
