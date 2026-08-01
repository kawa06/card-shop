"""Buyback channel settings, banners, and store reservation tests."""

from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import patch

import pytest
from fastapi import HTTPException

from auth import hash_password
import models
import models_buyback
from services.buyback_cart import add_cart_item
from services.buyback_channel import (
    create_banner,
    get_or_create_channel_settings,
    list_active_banners,
    list_available_slots,
    now_jst,
    update_channel_settings,
    validate_store_visit_at,
)
from services.buyback_requests import submit_request_from_cart


def _create_user(db, email: str = "channel@example.com") -> models.User:
    user = models.User(
        email=email,
        name="Channel Buyer",
        password_hash=hash_password("secret123"),
        is_verified=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _seed_cart(db, user: models.User) -> None:
    add_cart_item(
        db,
        user_id=user.id,
        firestore_item_id="fs_channel_001",
        product_name="チャネルテスト",
        category="raw",
        condition_code="A",
        unit_price=1000,
        quantity=1,
    )


def _future_slot(db) -> datetime:
    target = now_jst().date() + timedelta(days=1)
    while True:
        slots = list_available_slots(db, target_date=target)
        if slots:
            return slots[0]
        target += timedelta(days=1)
        if (target - now_jst().date()).days > 14:
            raise RuntimeError("no slot found")


def test_channel_settings_defaults(db):
    settings = get_or_create_channel_settings(db)
    assert settings.store_enabled is True
    assert settings.mail_enabled is True
    assert settings.slot_interval_minutes == 30


def test_update_channel_settings_store_only(db):
    settings = update_channel_settings(db, store_enabled=True, mail_enabled=False)
    assert settings.store_enabled is True
    assert settings.mail_enabled is False


def test_cannot_disable_both_channels(db):
    with pytest.raises(HTTPException):
        update_channel_settings(db, store_enabled=False, mail_enabled=False)


def test_banner_active_window(db):
    now = datetime.utcnow()
    banner = create_banner(
        db,
        title="店舗限定",
        description="10%UP",
        target_channel="store",
        starts_at=now - timedelta(hours=1),
        ends_at=now + timedelta(hours=2),
        background_color="#111111",
        text_color="#ffffff",
        sort_order=1,
        is_visible=True,
    )
    db.commit()
    active = list_active_banners(db)
    assert any(b.id == banner.id for b in active)

    banner.ends_at = now - timedelta(minutes=1)
    db.commit()
    active_after = list_active_banners(db)
    assert not any(b.id == banner.id for b in active_after)


def test_past_slot_not_bookable(db):
    past = datetime.utcnow() - timedelta(hours=2)
    with pytest.raises(HTTPException) as exc:
        validate_store_visit_at(db, past)
    assert exc.value.status_code == 400


@patch("services.buyback_requests.notify_buyback_request_submitted")
def test_submit_store_request_creates_reservation(mock_notify, db):
    user = _create_user(db)
    _seed_cart(db, user)
    slot = _future_slot(db)

    request = submit_request_from_cart(
        db,
        user=user,
        rejected_item_handling="return_rejected_only",
        agreed_condition_rejection=True,
        buyback_method="store",
        store_visit_at=slot,
    )

    assert request.buyback_method == "store"
    assert request.store_visit_at == slot
    assert request.inbound_mgmt_id is None
    reservation = (
        db.query(models_buyback.BuybackStoreReservation)
        .filter(models_buyback.BuybackStoreReservation.request_id == request.id)
        .first()
    )
    assert reservation is not None
    assert reservation.visit_at == slot
    mock_notify.assert_called_once()


@patch("services.buyback_requests.notify_buyback_request_submitted")
def test_double_booking_rejected(mock_notify, db):
    user1 = _create_user(db, "u1@example.com")
    user2 = _create_user(db, "u2@example.com")
    slot = _future_slot(db)

    _seed_cart(db, user1)
    submit_request_from_cart(
        db,
        user=user1,
        rejected_item_handling="return_rejected_only",
        agreed_condition_rejection=True,
        buyback_method="store",
        store_visit_at=slot,
    )

    _seed_cart(db, user2)
    with pytest.raises(HTTPException) as exc:
        submit_request_from_cart(
            db,
            user=user2,
            rejected_item_handling="return_rejected_only",
            agreed_condition_rejection=True,
            buyback_method="store",
            store_visit_at=slot,
        )
    assert exc.value.status_code == 409
