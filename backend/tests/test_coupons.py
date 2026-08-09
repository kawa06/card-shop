"""Phase 3-5 coupons system tests."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from fastapi import HTTPException

import models
import models_coupons
from auth import create_access_token
from services.coupon_calculator import CartLine, quote_coupon
from services.coupon_ledger import (
    confirm_coupon_for_order,
    count_redemptions,
    validate_coupon_for_user,
)
from services.coupon_orders import (
    apply_coupon_on_order_created,
    on_coupon_order_cancelled,
    on_order_paid_coupon,
)
from services.point_ledger import admin_grant_points, get_or_create_account
from services.point_orders import apply_points_on_order_created, on_order_cancelled_or_failed
from tests.conftest import auth_headers, create_admin_user


def _coupon(
    db,
    *,
    code="SAVE500",
    name="Save 500",
    coupon_type="fixed_amount",
    audience="public",
    amount_yen=500,
    percent_off=None,
    max_discount_yen=None,
    min_subtotal_yen=0,
    max_uses_total=None,
    max_uses_per_user=1,
    starts_at=None,
    ends_at=None,
    card_ids_json=None,
    category_ids_json=None,
    is_active=True,
):
    row = models_coupons.Coupon(
        code=code,
        name=name,
        coupon_type=coupon_type,
        audience=audience,
        amount_yen=amount_yen,
        percent_off=percent_off,
        max_discount_yen=max_discount_yen,
        min_subtotal_yen=min_subtotal_yen,
        max_uses_total=max_uses_total,
        max_uses_per_user=max_uses_per_user,
        starts_at=starts_at,
        ends_at=ends_at,
        card_ids_json=card_ids_json,
        category_ids_json=category_ids_json,
        is_active=is_active,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def _card(db, *, price=2000.0, category_id=None):
    card = models.Card(
        name="Coupon Test Card",
        price=price,
        stock=20,
        condition="a",
        is_active=True,
        category_id=category_id,
    )
    db.add(card)
    db.commit()
    db.refresh(card)
    return card


def _order_with_item(db, user, card, *, shipping_fee=650, quantity=1):
    subtotal = int(round(float(card.price))) * quantity
    order = models.Order(
        user_id=user.id,
        total_amount=float(subtotal + shipping_fee),
        items_subtotal=subtotal,
        shipping_fee=shipping_fee,
        packaging_fee=0,
        discount_amount=0,
        payment_method="stripe_card",
        payment_status="pending",
        status=models.OrderStatus.pending,
    )
    db.add(order)
    db.flush()
    db.add(
        models.OrderItem(
            order_id=order.id,
            card_id=card.id,
            quantity=quantity,
            unit_price=card.price,
        )
    )
    db.commit()
    db.refresh(order)
    return order


def test_quote_fixed_percent_free_shipping():
    fixed = models_coupons.Coupon(code="F", name="F", coupon_type="fixed_amount", amount_yen=500)
    percent = models_coupons.Coupon(
        code="P", name="P", coupon_type="percent", percent_off=10, max_discount_yen=300
    )
    ship = models_coupons.Coupon(code="S", name="S", coupon_type="free_shipping")
    lines = [CartLine(card_id=1, quantity=1, unit_price=2000)]

    qf = quote_coupon(fixed, lines=lines, items_subtotal=2000, shipping_fee=650)
    assert qf.discount_amount == 500
    assert qf.shipping_fee_after == 650

    qp = quote_coupon(percent, lines=lines, items_subtotal=2000, shipping_fee=650)
    assert qp.discount_amount == 200  # floor 10% = 200, under cap 300
    assert qp.shipping_fee_after == 650

    qs = quote_coupon(ship, lines=lines, items_subtotal=2000, shipping_fee=650)
    assert qs.discount_amount == 0
    assert qs.shipping_discount == 650
    assert qs.shipping_fee_after == 0


def test_targeting_card_and_category(db):
    cat = models.Category(name="Cat", slug="cat-coupon")
    db.add(cat)
    db.commit()
    db.refresh(cat)
    card_a = _card(db, price=1000, category_id=cat.id)
    card_b = _card(db, price=3000, category_id=None)

    by_card = _coupon(
        db,
        code="CARDONLY",
        amount_yen=9999,
        card_ids_json=f"[{card_a.id}]",
    )
    lines = [
        CartLine(card_id=card_a.id, quantity=1, unit_price=1000, category_id=cat.id),
        CartLine(card_id=card_b.id, quantity=1, unit_price=3000),
    ]
    q = quote_coupon(by_card, lines=lines, items_subtotal=4000, shipping_fee=0)
    assert q.eligible_subtotal == 1000
    assert q.discount_amount == 1000

    by_cat = _coupon(
        db,
        code="CATONLY",
        coupon_type="percent",
        amount_yen=None,
        percent_off=50,
        category_ids_json=f"[{cat.id}]",
    )
    q2 = quote_coupon(by_cat, lines=lines, items_subtotal=4000, shipping_fee=0)
    assert q2.eligible_subtotal == 1000
    assert q2.discount_amount == 500


def test_min_subtotal_and_expired(db, test_user):
    coupon = _coupon(db, code="MIN1000", min_subtotal_yen=1000, amount_yen=100)
    with pytest.raises(HTTPException) as exc:
        validate_coupon_for_user(
            db,
            coupon=coupon,
            user_id=test_user.id,
            items_subtotal=500,
            shipping_fee=0,
            lines=[CartLine(card_id=1, quantity=1, unit_price=500)],
        )
    assert exc.value.status_code == 400

    expired = _coupon(
        db,
        code="EXPIRED",
        ends_at=datetime.utcnow() - timedelta(days=1),
    )
    with pytest.raises(HTTPException):
        validate_coupon_for_user(
            db,
            coupon=expired,
            user_id=test_user.id,
            items_subtotal=2000,
            shipping_fee=0,
            lines=[CartLine(card_id=1, quantity=1, unit_price=2000)],
        )


def test_max_uses_per_user(db, test_user):
    coupon = _coupon(db, code="ONCE", max_uses_per_user=1, amount_yen=100)
    card = _card(db)
    order1 = _order_with_item(db, test_user, card)
    apply_coupon_on_order_created(db, order1, coupon_code="ONCE")
    confirm_coupon_for_order(db, order_id=order1.id)
    db.commit()

    order2 = _order_with_item(db, test_user, card)
    with pytest.raises(HTTPException):
        apply_coupon_on_order_created(db, order2, coupon_code="ONCE")


def test_reserve_confirm_release_idempotent(db, test_user):
    coupon = _coupon(db, code="LIFE", amount_yen=300)
    card = _card(db)
    order = _order_with_item(db, test_user, card)
    apply_coupon_on_order_created(db, order, coupon_code="LIFE")
    db.commit()
    db.refresh(order)
    assert order.discount_amount == 300
    assert order.coupon_code == "LIFE"
    assert count_redemptions(db, coupon_id=coupon.id) == 1

    apply_coupon_on_order_created(db, order, coupon_code="LIFE")
    db.commit()
    assert count_redemptions(db, coupon_id=coupon.id) == 1

    on_order_paid_coupon(db, order)
    db.commit()
    row = (
        db.query(models_coupons.CouponRedemption)
        .filter(models_coupons.CouponRedemption.order_id == order.id)
        .one()
    )
    assert row.status == "used"

    on_coupon_order_cancelled(db, order)
    db.commit()
    db.refresh(row)
    assert row.status == "released"
    assert count_redemptions(db, coupon_id=coupon.id) == 0


def test_free_shipping_on_order(db, test_user):
    _coupon(db, code="FREESHIP", coupon_type="free_shipping", amount_yen=None)
    card = _card(db)
    order = _order_with_item(db, test_user, card, shipping_fee=800)
    apply_coupon_on_order_created(db, order, coupon_code="FREESHIP")
    db.commit()
    db.refresh(order)
    assert order.shipping_fee == 0
    assert order.discount_amount == 0
    assert order.coupon_code == "FREESHIP"


def test_coupon_then_points_stack(db, test_user):
    admin = create_admin_user(db, email="cpn-pts-admin@test.com", role_code="admin")
    admin_grant_points(
        db,
        user_id=test_user.id,
        amount=2000,
        reason="seed",
        admin_user_id=admin.id,
        idempotency_key="cpn-pts-seed",
    )
    db.commit()
    _coupon(db, code="STACK500", amount_yen=500)
    card = _card(db, price=2000)
    order = _order_with_item(db, test_user, card, shipping_fee=0)
    apply_coupon_on_order_created(db, order, coupon_code="STACK500")
    db.commit()
    db.refresh(order)
    assert order.discount_amount == 500

    apply_points_on_order_created(db, order, points_to_use=300)
    db.commit()
    db.refresh(order)
    assert order.points_used == 300
    assert int(order.total_amount) == 2000 - 500 - 300

    on_order_cancelled_or_failed(db, order)
    on_coupon_order_cancelled(db, order)
    db.commit()
    account = get_or_create_account(db, test_user.id)
    assert account.available_points == 2000
    row = (
        db.query(models_coupons.CouponRedemption)
        .filter(models_coupons.CouponRedemption.order_id == order.id)
        .one()
    )
    assert row.status == "released"


def test_assigned_audience(db, test_user):
    admin = create_admin_user(db, email="cpn-assign-admin@test.com", role_code="admin")
    coupon = _coupon(db, code="PRIVATE", audience="assigned", amount_yen=200)
    card = _card(db)
    order = _order_with_item(db, test_user, card)
    with pytest.raises(HTTPException):
        apply_coupon_on_order_created(db, order, coupon_code="PRIVATE")

    db.add(
        models_coupons.CouponAssignment(
            coupon_id=coupon.id,
            user_id=test_user.id,
            assigned_by=admin.id,
        )
    )
    db.commit()
    apply_coupon_on_order_created(db, order, coupon_code="PRIVATE")
    db.commit()
    db.refresh(order)
    assert order.discount_amount == 200


def test_admin_create_and_user_preview_api(api_client, db, test_user):
    admin = create_admin_user(db, email="cpn-api-admin@test.com", role_code="owner")
    token = create_access_token({"sub": str(admin.id)})
    created = api_client.post(
        "/api/admin/coupons",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "code": "api500",
            "name": "API Fixed",
            "coupon_type": "fixed_amount",
            "amount_yen": 500,
            "audience": "public",
        },
    )
    assert created.status_code == 201, created.text
    assert created.json()["code"] == "API500"

    preview = api_client.post(
        "/api/coupons/checkout-preview",
        headers=auth_headers(test_user),
        json={
            "coupon_code": "API500",
            "items_subtotal": 2000,
            "shipping_fee": 650,
            "cart_items": [{"card_id": 1, "quantity": 1, "unit_price": 2000}],
        },
    )
    assert preview.status_code == 200
    body = preview.json()
    assert body["valid"] is True
    assert body["discount_amount"] == 500

    csv_res = api_client.get(
        "/api/admin/coupons/export.csv",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert csv_res.status_code == 200
    assert "API500" in csv_res.text


def test_assign_appears_in_mine(api_client, db, test_user):
    admin = create_admin_user(db, email="cpn-mine-admin@test.com", role_code="owner")
    token = create_access_token({"sub": str(admin.id)})
    created = api_client.post(
        "/api/admin/coupons",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "code": "MINE1",
            "name": "Mine Coupon",
            "coupon_type": "percent",
            "percent_off": 10,
            "audience": "assigned",
        },
    )
    assert created.status_code == 201
    coupon_id = created.json()["id"]
    assigned = api_client.post(
        f"/api/admin/coupons/{coupon_id}/assign",
        headers={"Authorization": f"Bearer {token}"},
        json={"user_id": test_user.id},
    )
    assert assigned.status_code == 200, assigned.text

    mine = api_client.get("/api/coupons/mine", headers=auth_headers(test_user))
    assert mine.status_code == 200
    payload = mine.json()
    items = payload if isinstance(payload, list) else payload.get("items", [])
    codes = [c["code"] for c in items]
    assert "MINE1" in codes
