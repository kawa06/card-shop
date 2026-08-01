"""Stripe bank transfer checkout and webhook behavior tests."""

from __future__ import annotations

from datetime import datetime, timedelta

import models
from routes.payments import _handle_bank_transfer_pending
from services.order_checkout import (
    BANK_TRANSFER_METHODS,
    cancel_unpaid_order,
    expire_overdue_bank_transfer_orders,
    fulfill_order_inventory,
    reserve_inventory_for_order,
)
from services.order_emails import send_bank_transfer_pending_email, send_purchase_confirmation_email
from services.stripe_events import claim_stripe_event


def _create_card(db, *, stock: int = 10, price: float = 1000.0) -> models.Card:
    card = models.Card(
        name="テストカード",
        price=price,
        stock=stock,
        condition="a",
        is_active=True,
    )
    db.add(card)
    db.commit()
    db.refresh(card)
    return card


def _create_bank_transfer_order(db, test_user, *, stock_reserved: bool = False) -> models.Order:
    card = _create_card(db)
    order = models.Order(
        user_id=test_user.id,
        total_amount=card.price,
        status=models.OrderStatus.pending,
        payment_status="awaiting_payment",
        payment_method="stripe_bank_transfer",
        payment_deadline=datetime.utcnow() + timedelta(hours=48),
        stock_reserved=stock_reserved,
        shipping_method="click_post",
        shipping_address="兵庫県テスト市",
    )
    db.add(order)
    db.flush()
    db.add(
        models.OrderItem(
            order_id=order.id,
            card_id=card.id,
            quantity=1,
            unit_price=card.price,
        )
    )
    db.commit()
    db.refresh(order)
    return order


def test_bank_transfer_pending_handler_sets_status(db, test_user):
    order = _create_bank_transfer_order(db, test_user)
    updated = _handle_bank_transfer_pending(db, order)

    assert updated.payment_status == "awaiting_payment"
    assert updated.payment_method == "stripe_bank_transfer"
    assert updated.stock_reserved is True
    assert updated.payment_deadline is not None


def test_fulfill_order_marks_paid_and_assigns_order_number(db, test_user, monkeypatch):
    order = _create_bank_transfer_order(db, test_user, stock_reserved=True)
    reserve_inventory_for_order(db, order)
    db.refresh(order)
    card = db.query(models.Card).first()
    initial_stock = card.stock

    emails: list[int] = []

    def _fake_email(db_session, order_obj):
        emails.append(order_obj.id)

    monkeypatch.setattr(
        "services.order_checkout.try_auto_purchase_email_after_payment",
        _fake_email,
    )

    fulfilled = fulfill_order_inventory(db, order.id, stripe_payment_intent_id="pi_test")
    db.refresh(fulfilled)
    db.refresh(card)

    assert fulfilled.payment_status == "paid"
    assert fulfilled.order_number is not None
    assert fulfilled.stripe_payment_intent_id == "pi_test"
    assert card.stock == initial_stock
    assert emails == [order.id]


def test_fulfill_paid_order_is_idempotent(db, test_user, monkeypatch):
    order = _create_bank_transfer_order(db, test_user, stock_reserved=True)
    reserve_inventory_for_order(db, order)

    call_count = {"n": 0}

    def _fake_email(db_session, order_obj):
        call_count["n"] += 1

    monkeypatch.setattr(
        "services.order_checkout.try_auto_purchase_email_after_payment",
        _fake_email,
    )

    first = fulfill_order_inventory(db, order.id)
    second = fulfill_order_inventory(db, order.id)

    assert first.payment_status == "paid"
    assert second.payment_status == "paid"
    assert call_count["n"] == 1


def test_cancel_unpaid_order_releases_stock(db, test_user):
    order = _create_bank_transfer_order(db, test_user)
    reserve_inventory_for_order(db, order)
    db.refresh(order)
    card = db.query(models.Card).first()
    assert card.stock == 9

    cancel_unpaid_order(db, order, as_expired=True)
    db.refresh(order)
    db.refresh(card)

    assert order.payment_status == "expired"
    assert order.status == models.OrderStatus.cancelled
    assert order.shipping_status == "cancelled"
    assert order.stock_reserved is False
    assert card.stock == 10


def test_expire_overdue_bank_transfer_orders(db, test_user):
    order = _create_bank_transfer_order(db, test_user)
    reserve_inventory_for_order(db, order)
    order.payment_deadline = datetime.utcnow() - timedelta(hours=1)
    db.commit()

    count = expire_overdue_bank_transfer_orders(db)
    db.refresh(order)

    assert count == 1
    assert order.payment_status == "expired"


def test_claim_stripe_event_prevents_duplicate_processing(db):
    assert claim_stripe_event(db, "evt_dup_1", event_type="checkout.session.completed", order_id=99) is True
    db.commit()
    assert claim_stripe_event(db, "evt_dup_1", event_type="checkout.session.completed", order_id=99) is False


def test_bank_transfer_pending_email_mock(db, test_user, monkeypatch):
    order = _create_bank_transfer_order(db, test_user, stock_reserved=True)

    monkeypatch.setattr(
        "services.order_emails.email_configured",
        lambda: False,
    )
    monkeypatch.setattr("services.order_emails.settings.DEBUG", True)

    ok, err = send_bank_transfer_pending_email(db, order.id)
    db.refresh(order)

    assert ok is True
    assert err is None
    assert order.email_send_status == "bank_transfer_pending_ok"


def test_bank_transfer_cancel_email_mock(db, test_user, monkeypatch):
    order = _create_bank_transfer_order(db, test_user, stock_reserved=True)

    monkeypatch.setattr("services.order_emails.email_configured", lambda: False)
    monkeypatch.setattr("services.order_emails.settings.DEBUG", True)

    cancel_unpaid_order(db, order, as_expired=True)
    db.refresh(order)

    assert order.payment_status == "expired"
    assert order.email_send_status == "bank_transfer_expired_ok"


def test_purchase_email_includes_payment_method(db, test_user, paid_order, monkeypatch):
    paid_order.payment_method = "stripe_bank_transfer"
    db.commit()

    captured: dict[str, str] = {}

    def _fake_send(*, to: str, subject: str, html: str):
        captured["html"] = html
        return True, None

    monkeypatch.setattr("services.order_emails._send_html_email", _fake_send)
    monkeypatch.setattr("services.order_emails.email_configured", lambda: True)

    ok, err = send_purchase_confirmation_email(db, paid_order.id, force=True)
    assert ok is True
    assert "銀行振込（Stripe）" in captured["html"]


def test_bank_transfer_methods_constant():
    assert "stripe_bank_transfer" in BANK_TRANSFER_METHODS
