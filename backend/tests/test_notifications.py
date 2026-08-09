"""Phase 3-6 user notifications tests."""

from __future__ import annotations

from unittest.mock import MagicMock

import models
import models_notifications
from auth import create_access_token
from services.notification_events import (
    notify_auction_won,
    notify_coupon_assigned,
    notify_live_offer_reviewed,
    notify_order_paid,
    notify_order_shipped,
    notify_buyback_status,
)
from services.notification_settings import get_or_create_settings, update_settings
from services.user_notifications import (
    create_user_notification,
    mark_all_read,
    mark_read,
    unread_count,
)
from tests.conftest import auth_headers, create_admin_user


def test_create_and_dedupe(db, test_user):
    a = create_user_notification(
        db,
        user_id=test_user.id,
        type="order_paid",
        title="paid",
        body="ok",
        dedupe_key="order_paid:1",
        category="order",
    )
    b = create_user_notification(
        db,
        user_id=test_user.id,
        type="order_paid",
        title="paid again",
        body="ok",
        dedupe_key="order_paid:1",
        category="order",
    )
    db.commit()
    assert a is not None and b is not None
    assert a.id == b.id
    assert unread_count(db, user_id=test_user.id) == 1


def test_list_mark_read_privacy(api_client, db, test_user):
    other = models.User(email="other-notif@test.com", name="Other", password_hash="x")
    db.add(other)
    db.commit()
    db.refresh(other)

    mine = create_user_notification(
        db,
        user_id=test_user.id,
        type="t",
        title="mine",
        body="b",
        dedupe_key="mine:1",
    )
    create_user_notification(
        db,
        user_id=other.id,
        type="t",
        title="theirs",
        body="b",
        dedupe_key="theirs:1",
    )
    db.commit()

    listed = api_client.get("/api/notifications", headers=auth_headers(test_user))
    assert listed.status_code == 200
    ids = [i["id"] for i in listed.json()["items"]]
    assert mine.id in ids
    assert all(i["title"] != "theirs" for i in listed.json()["items"])

    forbidden = api_client.post(
        f"/api/notifications/{mine.id + 9999}/read",
        headers=auth_headers(test_user),
    )
    assert forbidden.status_code == 404

    other_row = (
        db.query(models_notifications.UserNotification)
        .filter(models_notifications.UserNotification.user_id == other.id)
        .first()
    )
    steal = api_client.post(
        f"/api/notifications/{other_row.id}/read",
        headers=auth_headers(test_user),
    )
    assert steal.status_code == 404

    ok = api_client.post(f"/api/notifications/{mine.id}/read", headers=auth_headers(test_user))
    assert ok.status_code == 200
    assert ok.json()["is_read"] is True

    count = api_client.get("/api/notifications/unread-count", headers=auth_headers(test_user))
    assert count.status_code == 200
    assert count.json()["unread_count"] == 0


def test_mark_all_read(db, test_user):
    for i in range(3):
        create_user_notification(
            db,
            user_id=test_user.id,
            type="t",
            title=f"n{i}",
            body="b",
            dedupe_key=f"all:{i}",
        )
    db.commit()
    assert unread_count(db, user_id=test_user.id) == 3
    mark_all_read(db, user_id=test_user.id)
    db.commit()
    assert unread_count(db, user_id=test_user.id) == 0


def test_settings_block_in_app(db, test_user):
    update_settings(db, test_user.id, campaign_in_app=False)
    db.commit()
    row = create_user_notification(
        db,
        user_id=test_user.id,
        type="coupon_assigned",
        title="c",
        body="b",
        category="campaign",
        dedupe_key="blocked:1",
    )
    assert row is None


def test_email_failure_does_not_raise(db, test_user):
    def boom():
        raise RuntimeError("email down")

    row = create_user_notification(
        db,
        user_id=test_user.id,
        type="custom",
        title="t",
        body="b",
        category="campaign",
        dedupe_key="email-fail:1",
        send_email=True,
        email_sender=boom,
    )
    db.commit()
    assert row is not None
    assert row.email_status == "failed"


def test_event_helpers(db, test_user):
    order = models.Order(
        user_id=test_user.id,
        total_amount=1000,
        items_subtotal=1000,
        shipping_fee=0,
        payment_status="paid",
        status=models.OrderStatus.processing,
    )
    db.add(order)
    db.commit()
    db.refresh(order)
    notify_order_paid(db, order)
    notify_order_shipped(db, order)
    db.commit()
    assert unread_count(db, user_id=test_user.id) >= 2

    req = MagicMock(id=99, user_id=test_user.id)
    notify_buyback_status(db, req, status="assessed")
    offer = MagicMock(id=7, user_id=test_user.id, stream_id=1, status="accepted")
    notify_live_offer_reviewed(db, offer, status="accepted")
    auction = MagicMock(id=3, stream_id=1, current_price=5000, winning_amount=5000)
    notify_auction_won(db, auction, winner_user_id=test_user.id)
    coupon = MagicMock(id=1, code="SAVE", name="Save")
    notify_coupon_assigned(db, user_id=test_user.id, coupon=coupon, assignment_id=11)
    db.commit()
    assert unread_count(db, user_id=test_user.id) >= 5


def test_admin_broadcast_rbac(api_client, db, test_user):
    admin = create_admin_user(db, email="notif-admin@test.com", role_code="owner")
    token = create_access_token({"sub": str(admin.id)})
    ok = api_client.post(
        "/api/admin/user-notifications/broadcast",
        headers={"Authorization": f"Bearer {token}"},
        json={"title": "Hello", "body": "World", "user_id": test_user.id},
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["created"] >= 1

    viewer = create_admin_user(db, email="notif-viewer@test.com", role_code="support_manager")
    denied = api_client.post(
        "/api/admin/user-notifications/broadcast",
        headers={"Authorization": f"Bearer {create_access_token({'sub': str(viewer.id)})}"},
        json={"title": "Nope", "body": "x", "user_id": test_user.id},
    )
    assert denied.status_code == 403


def test_settings_api(api_client, test_user):
    get_res = api_client.get("/api/notifications/settings", headers=auth_headers(test_user))
    assert get_res.status_code == 200
    patch = api_client.patch(
        "/api/notifications/settings",
        headers=auth_headers(test_user),
        json={"auction_email": False, "email_enabled": False},
    )
    assert patch.status_code == 200
    assert patch.json()["auction_email"] is False
    assert patch.json()["email_enabled"] is False
