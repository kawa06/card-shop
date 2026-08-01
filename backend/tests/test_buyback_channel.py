"""Buyback channel settings, banners, and store reservation tests."""

from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import patch

import pytest
from fastapi import HTTPException

from auth import hash_password
import models
import models_buyback
import schemas_buyback
from services.buyback_cart import add_cart_item
from services.buyback_channel import (
    create_banner,
    get_or_create_channel_settings,
    list_active_banners,
    list_available_slots,
    normalize_product_promo_badge_fields,
    now_jst,
    resolve_active_product_promo_badge,
    to_naive_utc,
    update_banner,
    update_channel_settings,
    validate_store_visit_at,
    _banner_is_active,
)
from services.buyback_logistics_logs import write_buyback_audit
from services.buyback_requests import submit_request_from_cart
from services.sensitive_redaction import redact_audit_value
import json


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


def test_banner_update_with_timezone_aware_datetimes(db):
    now = datetime.utcnow()
    banner = create_banner(
        db,
        title="期間限定",
        description=None,
        target_channel="both",
        starts_at=now - timedelta(hours=1),
        ends_at=now + timedelta(hours=2),
        background_color="#111111",
        text_color="#ffffff",
        sort_order=0,
        is_visible=True,
    )
    db.commit()

    aware_start = datetime.fromisoformat("2026-08-01T00:00:00+00:00")
    aware_end = datetime.fromisoformat("2026-08-31T23:59:59+00:00")
    update_banner(
        db,
        banner,
        title="更新後",
        starts_at=aware_start,
        ends_at=aware_end,
    )

    before = schemas_buyback.BuybackPromoBannerOut(
        id=banner.id,
        title="before",
        description=None,
        target_channel="both",
        starts_at=now,
        ends_at=now + timedelta(days=1),
        background_color="#111111",
        text_color="#ffffff",
        sort_order=0,
        is_visible=True,
        is_active=False,
    )
    after = schemas_buyback.BuybackPromoBannerOut(
        id=banner.id,
        title=banner.title,
        description=banner.description,
        target_channel=banner.target_channel,
        starts_at=banner.starts_at,
        ends_at=banner.ends_at,
        background_color=banner.background_color,
        text_color=banner.text_color,
        sort_order=banner.sort_order,
        is_visible=banner.is_visible,
        is_active=_banner_is_active(banner, datetime.utcnow()),
    )
    details = {
        "before": before.model_dump(mode="json"),
        "after": after.model_dump(mode="json"),
    }
    json.dumps(redact_audit_value(details), ensure_ascii=False)

    assert banner.starts_at == to_naive_utc(aware_start)
    assert banner.ends_at == to_naive_utc(aware_end)
    assert _banner_is_active(banner, datetime.utcnow()) is True


def test_product_promo_badge_active_window(db):
    product = models_buyback.BuybackProduct(
        name="Promo Card",
        category="raw",
        is_active=True,
        sort_order=0,
        promo_badge_text="限定UP",
        promo_badge_bg="#ff0000",
        promo_badge_fg="#ffffff",
        promo_badge_starts_at=datetime.utcnow() - timedelta(hours=1),
        promo_badge_ends_at=datetime.utcnow() + timedelta(hours=1),
    )
    db.add(product)
    db.commit()

    active = resolve_active_product_promo_badge(product)
    assert active is not None
    assert active["text"] == "限定UP"

    product.promo_badge_ends_at = datetime.utcnow() - timedelta(minutes=1)
    assert resolve_active_product_promo_badge(product) is None


def test_normalize_product_promo_badge_clears_when_empty():
    assert normalize_product_promo_badge_fields(
        text="  ",
        bg="#111111",
        fg="#ffffff",
        starts_at=None,
        ends_at=None,
    ) == (None, None, None, None, None)


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
