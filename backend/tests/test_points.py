"""Phase 3-4 points system tests."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from fastapi import HTTPException

import models
import models_points
from auth import create_access_token
from services.point_calculator import calculate_earn_points, calculate_max_usable_points
from services.point_ledger import (
    admin_deduct_points,
    admin_grant_points,
    confirm_points_for_order,
    earn_points_for_order,
    expire_due_points,
    get_or_create_account,
    release_points_for_order,
    reserve_points_for_order,
    reverse_earned_points_for_order,
)
from services.point_orders import (
    apply_points_on_order_created,
    on_order_cancelled_or_failed,
    on_order_paid,
    validate_points_to_use,
)
from services.point_settings import get_point_settings
from tests.conftest import auth_headers, create_admin_user


def _order(db, user, *, subtotal=2000, total=2000):
    order = models.Order(
        user_id=user.id,
        total_amount=float(total),
        items_subtotal=subtotal,
        shipping_fee=0,
        discount_amount=0,
        payment_method="stripe_card",
        payment_status="pending",
        status=models.OrderStatus.pending,
    )
    db.add(order)
    db.commit()
    db.refresh(order)
    return order


def test_account_creation(db, test_user):
    account = get_or_create_account(db, test_user.id)
    assert account.available_points == 0
    assert account.reserved_points == 0


def test_admin_grant_and_earn(db, test_user):
    admin = create_admin_user(db, email="points-admin@test.com", role_code="admin")
    tx = admin_grant_points(
        db,
        user_id=test_user.id,
        amount=1000,
        reason="campaign",
        admin_user_id=admin.id,
        idempotency_key="grant-1",
    )
    db.commit()
    account = get_or_create_account(db, test_user.id)
    assert account.available_points == 1000
    assert tx.amount == 1000

    order = _order(db, test_user)
    earn = earn_points_for_order(
        db,
        user_id=test_user.id,
        order_id=order.id,
        amount=19,
        expiration_days=180,
        idempotency_key=f"earn:order:{order.id}",
    )
    db.commit()
    account = get_or_create_account(db, test_user.id)
    assert account.available_points == 1019
    assert earn is not None

    again = earn_points_for_order(
        db,
        user_id=test_user.id,
        order_id=order.id,
        amount=19,
        expiration_days=180,
        idempotency_key=f"earn:order:{order.id}",
    )
    assert again.id == earn.id


def test_double_grant_idempotency(db, test_user):
    admin = create_admin_user(db, email="points-admin2@test.com", role_code="admin")
    first = admin_grant_points(
        db,
        user_id=test_user.id,
        amount=500,
        reason="test",
        admin_user_id=admin.id,
        idempotency_key="dup-grant",
    )
    second = admin_grant_points(
        db,
        user_id=test_user.id,
        amount=500,
        reason="test",
        admin_user_id=admin.id,
        idempotency_key="dup-grant",
    )
    db.commit()
    assert first.id == second.id
    account = get_or_create_account(db, test_user.id)
    assert account.available_points == 500


def test_reserve_use_and_insufficient(db, test_user):
    admin = create_admin_user(db, email="points-admin3@test.com", role_code="admin")
    admin_grant_points(
        db,
        user_id=test_user.id,
        amount=1000,
        reason="seed",
        admin_user_id=admin.id,
        idempotency_key="seed-1000",
    )
    db.commit()

    order = _order(db, test_user, total=1500)
    reserve_points_for_order(db, user_id=test_user.id, order_id=order.id, amount=600)
    db.commit()
    account = get_or_create_account(db, test_user.id)
    assert account.available_points == 400
    assert account.reserved_points == 600

    confirm_points_for_order(db, user_id=test_user.id, order_id=order.id)
    db.commit()
    account = get_or_create_account(db, test_user.id)
    assert account.reserved_points == 0
    assert account.lifetime_used == 600

    order2 = _order(db, test_user, total=500)
    with pytest.raises(HTTPException) as exc:
        reserve_points_for_order(db, user_id=test_user.id, order_id=order2.id, amount=500)
    assert exc.value.status_code == 400


def test_validate_rejects_negative_and_over_balance(db, test_user):
    with pytest.raises(HTTPException):
        validate_points_to_use(
            db,
            user_id=test_user.id,
            points_to_use=-1,
            items_subtotal=1000,
        )
    admin = create_admin_user(db, email="points-admin4@test.com", role_code="admin")
    admin_grant_points(
        db,
        user_id=test_user.id,
        amount=100,
        reason="small",
        admin_user_id=admin.id,
        idempotency_key="small-grant",
    )
    db.commit()
    with pytest.raises(HTTPException):
        validate_points_to_use(
            db,
            user_id=test_user.id,
            points_to_use=200,
            items_subtotal=5000,
        )


def test_release_on_payment_failure(db, test_user):
    admin = create_admin_user(db, email="points-admin5@test.com", role_code="admin")
    admin_grant_points(
        db,
        user_id=test_user.id,
        amount=800,
        reason="seed",
        admin_user_id=admin.id,
        idempotency_key="seed-800",
    )
    db.commit()
    order = _order(db, test_user)
    reserve_points_for_order(db, user_id=test_user.id, order_id=order.id, amount=800)
    db.commit()
    release_points_for_order(db, user_id=test_user.id, order_id=order.id)
    db.commit()
    account = get_or_create_account(db, test_user.id)
    assert account.available_points == 800
    assert account.reserved_points == 0


def test_cancel_restore_flow(db, test_user):
    admin = create_admin_user(db, email="points-admin6@test.com", role_code="admin")
    admin_grant_points(
        db,
        user_id=test_user.id,
        amount=500,
        reason="seed",
        admin_user_id=admin.id,
        idempotency_key="seed-500",
    )
    db.commit()
    order = _order(db, test_user)
    apply_points_on_order_created(db, order, points_to_use=300)
    db.commit()

    on_order_cancelled_or_failed(db, order)
    db.commit()
    account = get_or_create_account(db, test_user.id)
    assert account.available_points == 500
    assert account.reserved_points == 0


def test_admin_deduct_rejects_over_balance(db, test_user):
    admin = create_admin_user(db, email="points-admin7@test.com", role_code="admin")
    admin_grant_points(
        db,
        user_id=test_user.id,
        amount=200,
        reason="seed",
        admin_user_id=admin.id,
        idempotency_key="seed-200",
    )
    db.commit()
    with pytest.raises(HTTPException):
        admin_deduct_points(
            db,
            user_id=test_user.id,
            amount=500,
            reason="too much",
            admin_user_id=admin.id,
            idempotency_key="deduct-fail",
        )


def test_expiration(db, test_user):
    admin = create_admin_user(db, email="points-admin8@test.com", role_code="admin")
    admin_grant_points(
        db,
        user_id=test_user.id,
        amount=300,
        reason="expire test",
        admin_user_id=admin.id,
        idempotency_key="expire-grant",
        expiration_days=1,
    )
    db.commit()
    lot = (
        db.query(models_points.PointExpirationLot)
        .filter(models_points.PointExpirationLot.user_id == test_user.id)
        .first()
    )
    lot.expires_at = datetime.utcnow() - timedelta(hours=1)
    db.commit()
    expired = expire_due_points(db, user_id=test_user.id)
    db.commit()
    assert expired == 300
    account = get_or_create_account(db, test_user.id)
    assert account.available_points == 0


def test_calculate_earn_floor():
    assert calculate_earn_points(1980, 1) == 19


def test_sequential_double_reserve_fails(db, test_user):
    admin = create_admin_user(db, email="points-admin9@test.com", role_code="admin")
    admin_grant_points(
        db,
        user_id=test_user.id,
        amount=1000,
        reason="seed",
        admin_user_id=admin.id,
        idempotency_key="seed-concurrent",
    )
    db.commit()
    order_a = _order(db, test_user, total=1000)
    order_b = _order(db, test_user, total=1000)

    reserve_points_for_order(db, user_id=test_user.id, order_id=order_a.id, amount=1000)
    db.commit()
    with pytest.raises(HTTPException):
        reserve_points_for_order(db, user_id=test_user.id, order_id=order_b.id, amount=1000)


def test_points_api_balance(api_client, test_user):
    resp = api_client.get("/api/points/balance", headers=auth_headers(test_user))
    assert resp.status_code == 200
    assert "available_points" in resp.json()


def test_admin_grant_rbac(api_client, db, test_user):
    admin = create_admin_user(db, email="points-owner@test.com", role_code="owner")
    token = create_access_token({"sub": str(admin.id)})
    resp = api_client.post(
        "/api/admin/points/grant",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "user_id": test_user.id,
            "amount": 1000,
            "reason": "E2E seed",
            "idempotency_key": "api-grant-1",
        },
    )
    assert resp.status_code == 200

    viewer = create_admin_user(db, email="viewer@test.com", role_code="support_manager")
    viewer_token = create_access_token({"sub": str(viewer.id)})
    denied = api_client.post(
        "/api/admin/points/grant",
        headers={"Authorization": f"Bearer {viewer_token}"},
        json={
            "user_id": test_user.id,
            "amount": 100,
            "reason": "should fail",
        },
    )
    assert denied.status_code == 403


def test_reverse_earn_partial_when_spent(db, test_user):
    admin = create_admin_user(db, email="points-admin10@test.com", role_code="admin")
    order = _order(db, test_user, subtotal=5000)
    earn_points_for_order(
        db,
        user_id=test_user.id,
        order_id=order.id,
        amount=50,
        expiration_days=None,
    )
    db.commit()
    order2 = _order(db, test_user)
    reserve_points_for_order(db, user_id=test_user.id, order_id=order2.id, amount=50)
    confirm_points_for_order(db, user_id=test_user.id, order_id=order2.id)
    db.commit()

    reverse_earned_points_for_order(
        db,
        user_id=test_user.id,
        order_id=order.id,
        earn_amount=50,
    )
    db.commit()
    account = get_or_create_account(db, test_user.id)
    assert account.available_points >= 0

def test_live_offer_order_with_points(db, test_user):
    """Phase 3-4: offer purchase applies points without changing accepted price."""
    from tests.test_live_offers import _create_offer, _stream_with_product, review_offer
    import schemas_live_offer
    from services.live_offer_purchase import create_order_from_offer
    from services.point_ledger import get_or_create_account

    admin = create_admin_user(db, email="points-live@test.com", role_code="admin")
    admin_grant_points(
        db,
        user_id=test_user.id,
        amount=500,
        reason="live offer test",
        admin_user_id=admin.id,
        idempotency_key="live-offer-grant",
    )
    db.commit()

    stream, product, _admin, _card = _stream_with_product(db)
    offer = _create_offer(db, stream, product, test_user, amount=1000)
    review_offer(db, offer, action="accept", admin_user_id=admin.id)

    result = create_order_from_offer(
        db,
        offer_id=offer.id,
        user_id=test_user.id,
        payload=schemas_live_offer.LiveOfferPurchaseIn(
            shipping_address="Points test",
            points_to_use=300,
        ),
    )
    order = db.query(models.Order).filter(models.Order.id == result.order_id).first()
    db.refresh(order)
    assert order.items_subtotal == 1000
    assert order.points_used == 300
    assert int(round(order.total_amount)) == 700

    account = get_or_create_account(db, test_user.id)
    assert account.reserved_points == 300

