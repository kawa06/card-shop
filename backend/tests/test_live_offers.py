"""Tests for Phase 3-3 live offers."""

from __future__ import annotations

from datetime import datetime, timedelta

import models
import models_live
import models_live_auction  # noqa: F401
import models_live_offer  # noqa: F401
import pytest
import schemas_live
import schemas_live_auction
import schemas_live_offer
from fastapi import HTTPException
from pydantic import ValidationError
from services.live_auctions import create_auction, start_auction
from services.live_offer_purchase import (
    create_order_from_offer,
    get_purchase_right_or_404,
    verify_purchase_right_owner,
)
from services.live_offer_rate_limit import reset_live_offer_rate_limits
from services.live_offers import (
    cancel_offer,
    create_offer,
    expire_stale_offers,
    review_offer,
)
from services.live_streams import add_product, create_stream, start_stream
from tests.conftest import admin_headers, auth_headers, create_admin_user


@pytest.fixture(autouse=True)
def _reset_offer_rate_limits():
    reset_live_offer_rate_limits()
    yield
    reset_live_offer_rate_limits()


def _card(db, *, stock: int = 3) -> models.Card:
    card = models.Card(name="Offer Card", price=2000, stock=stock)
    db.add(card)
    db.commit()
    db.refresh(card)
    return card


def _stream_with_product(db):
    admin = create_admin_user(db, email="offer-admin@test.com", role_code="sales_manager")
    from services.admin_auth import get_admin_user_for_user

    admin_user = get_admin_user_for_user(db, admin)
    stream = create_stream(
        db,
        payload=schemas_live.LiveStreamCreateIn(title="Offer Live", visibility="public"),
        admin_user_id=admin_user.id,
    )
    start_stream(db, stream)
    card = _card(db)
    product = add_product(db, stream, schemas_live.LiveProductCreateIn(card_id=card.id))
    return stream, product, admin, card


def _create_offer(db, stream, product, user, amount: int = 1500, **kwargs):
    return create_offer(
        db,
        stream_id=stream.id,
        user_id=user.id,
        payload=schemas_live_offer.LiveOfferCreateIn(
            live_product_id=product.id,
            amount=amount,
            **kwargs,
        ),
    )


def test_create_offer(db, test_user):
    stream, product, _admin, _card = _stream_with_product(db)
    offer = _create_offer(db, stream, product, test_user)
    assert offer.status == "pending"
    assert offer.amount == 1500
    assert offer.display_expires_at is not None


def test_create_offer_unauth(api_client, db):
    stream, product, _admin, _card = _stream_with_product(db)
    resp = api_client.post(
        f"/api/live/streams/{stream.id}/offers",
        json={"live_product_id": product.id, "amount": 1500},
    )
    assert resp.status_code == 401


def test_invalid_amount_zero():
    with pytest.raises(ValidationError):
        schemas_live_offer.LiveOfferCreateIn(live_product_id=1, amount=0)


def test_invalid_amount_over_max(db, test_user):
    stream, product, _admin, _card = _stream_with_product(db)
    settings = models_live_offer.LiveOfferSettings(shop_id=1, max_amount=5000)
    db.add(settings)
    db.commit()
    with pytest.raises(HTTPException) as exc:
        _create_offer(db, stream, product, test_user, amount=9999)
    assert exc.value.status_code == 400


def test_rate_limit(db, test_user, monkeypatch):
    stream, product, _admin, _card = _stream_with_product(db)
    monkeypatch.setattr(
        'services.live_offers.check_live_offer_rate_limit',
        lambda user_id, stream_id, *, max_count, window_seconds: __import__(
            'services.live_offer_rate_limit', fromlist=['check_live_offer_rate_limit']
        ).check_live_offer_rate_limit(user_id, stream_id, max_count=2, window_seconds=60),
    )
    _create_offer(db, stream, product, test_user, amount=1000)
    _create_offer(db, stream, product, test_user, amount=1100)
    with pytest.raises(HTTPException) as exc:
        _create_offer(db, stream, product, test_user, amount=1200)
    assert exc.value.status_code == 429


def test_idempotency(db, test_user):
    stream, product, _admin, _card = _stream_with_product(db)
    first = _create_offer(
        db,
        stream,
        product,
        test_user,
        amount=1500,
        idempotency_key="idem-1",
    )
    second = _create_offer(
        db,
        stream,
        product,
        test_user,
        amount=1500,
        idempotency_key="idem-1",
    )
    assert first.id == second.id


def test_accept_offer(db, test_user):
    stream, product, _admin, _card = _stream_with_product(db)
    offer = _create_offer(db, stream, product, test_user)
    accepted = review_offer(db, offer, action="accept", admin_user_id=1)
    assert accepted.status == "accepted"
    assert accepted.purchase_expires_at is not None
    right = get_purchase_right_or_404(db, offer.id)
    assert right.accepted_price == 1500


def test_reject_offer(db, test_user):
    stream, product, _admin, _card = _stream_with_product(db)
    offer = _create_offer(db, stream, product, test_user)
    rejected = review_offer(db, offer, action="reject", admin_user_id=1, review_note="too low")
    assert rejected.status == "rejected"
    assert rejected.review_note == "too low"


def test_hold_offer(db, test_user):
    stream, product, _admin, _card = _stream_with_product(db)
    offer = _create_offer(db, stream, product, test_user)
    held = review_offer(db, offer, action="hold", admin_user_id=1)
    assert held.status == "held"


def test_invalid_transition(db, test_user):
    stream, product, _admin, _card = _stream_with_product(db)
    offer = _create_offer(db, stream, product, test_user)
    review_offer(db, offer, action="reject", admin_user_id=1)
    with pytest.raises(HTTPException) as exc:
        review_offer(db, offer, action="accept", admin_user_id=1)
    assert exc.value.status_code == 409


def test_admin_offer_rbac_read_denied(api_client, db):
    stream, product, _admin, _card = _stream_with_product(db)
    create_admin_user(db, email="viewer-offer@test.com", role_code="viewer")
    denied = api_client.get(
        f"/api/admin/live/streams/{stream.id}/offers",
        headers=admin_headers("viewer-offer@test.com"),
    )
    assert denied.status_code == 403


def test_admin_offer_rbac_review_allowed(api_client, db, test_user):
    stream, product, _admin, _card = _stream_with_product(db)
    offer = _create_offer(db, stream, product, test_user)
    create_admin_user(db, email="sales-offer@test.com", role_code="sales_manager")
    resp = api_client.post(
        f"/api/admin/live/streams/{stream.id}/offers/{offer.id}/accept",
        headers=admin_headers("sales-offer@test.com"),
        json={},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "accepted"


def test_support_manager_cannot_review(api_client, db, test_user):
    stream, product, _admin, _card = _stream_with_product(db)
    offer = _create_offer(db, stream, product, test_user)
    create_admin_user(db, email="support-offer@test.com", role_code="support_manager")
    denied = api_client.post(
        f"/api/admin/live/streams/{stream.id}/offers/{offer.id}/accept",
        headers=admin_headers("support-offer@test.com"),
        json={},
    )
    assert denied.status_code == 403


def test_purchase_right_owner_check(db, test_user):
    stream, product, _admin, _card = _stream_with_product(db)
    other = models.User(email="other@example.com", password_hash="x", name="Other")
    db.add(other)
    db.commit()
    db.refresh(other)
    offer = _create_offer(db, stream, product, test_user)
    review_offer(db, offer, action="accept", admin_user_id=1)
    right = get_purchase_right_or_404(db, offer.id)
    with pytest.raises(HTTPException) as exc:
        verify_purchase_right_owner(right, other.id)
    assert exc.value.status_code == 403


def test_purchase_right_expiry(db, test_user):
    stream, product, _admin, _card = _stream_with_product(db)
    offer = _create_offer(db, stream, product, test_user)
    review_offer(db, offer, action="accept", admin_user_id=1)
    right = get_purchase_right_or_404(db, offer.id)
    right.expires_at = datetime.utcnow() - timedelta(seconds=1)
    db.commit()
    with pytest.raises(HTTPException) as exc:
        create_order_from_offer(
            db,
            offer_id=offer.id,
            user_id=test_user.id,
            payload=schemas_live_offer.LiveOfferPurchaseIn(),
        )
    assert exc.value.status_code == 409


def test_double_purchase_idempotent(db, test_user):
    stream, product, _admin, _card = _stream_with_product(db)
    offer = _create_offer(db, stream, product, test_user)
    review_offer(db, offer, action="accept", admin_user_id=1)
    first = create_order_from_offer(
        db,
        offer_id=offer.id,
        user_id=test_user.id,
        payload=schemas_live_offer.LiveOfferPurchaseIn(shipping_address="Test"),
    )
    second = create_order_from_offer(
        db,
        offer_id=offer.id,
        user_id=test_user.id,
        payload=schemas_live_offer.LiveOfferPurchaseIn(shipping_address="Test"),
    )
    assert first.order_id == second.order_id


def test_stock_conflict(db, test_user):
    stream, product, _admin, card = _stream_with_product(db)
    card.stock = 0
    db.commit()
    offer = _create_offer(db, stream, product, test_user)
    review_offer(db, offer, action="accept", admin_user_id=1)
    with pytest.raises(HTTPException) as exc:
        create_order_from_offer(
            db,
            offer_id=offer.id,
            user_id=test_user.id,
            payload=schemas_live_offer.LiveOfferPurchaseIn(),
        )
    assert exc.value.status_code == 409


def test_auction_conflict(db, test_user):
    stream, product, _admin, _card = _stream_with_product(db)
    auction = create_auction(
        db,
        stream_id=stream.id,
        payload=schemas_live_auction.LiveAuctionCreateIn(
            live_product_id=product.id,
            start_price=1000,
            min_bid_increment=100,
        ),
        admin_user_id=1,
    )
    start_auction(db, auction)
    with pytest.raises(HTTPException) as exc:
        _create_offer(db, stream, product, test_user)
    assert exc.value.status_code == 409


def test_live_offer_sse_hub_event():
    import asyncio

    from services.live_events import emit_live_event, live_event_hub

    async def run() -> None:
        gen = live_event_hub.stream(99, "public")
        first = await gen.__anext__()
        assert "connected" in first
        emit_live_event(99, "offer.created", {"id": 1, "amount": 1500, "status": "pending"})
        msg = await gen.__anext__()
        assert "offer.created" in msg
        await gen.aclose()

    asyncio.run(run())
    assert live_event_hub.global_connections == 0


def test_audit_log(db, test_user):
    stream, product, _admin, _card = _stream_with_product(db)
    offer = _create_offer(db, stream, product, test_user)
    logs = (
        db.query(models_live_offer.LiveOfferAuditLog)
        .filter(models_live_offer.LiveOfferAuditLog.offer_id == offer.id)
        .all()
    )
    assert any(log.action == "offer.created" for log in logs)
    review_offer(db, offer, action="accept", admin_user_id=1)
    logs = (
        db.query(models_live_offer.LiveOfferAuditLog)
        .filter(models_live_offer.LiveOfferAuditLog.offer_id == offer.id)
        .all()
    )
    assert any(log.after_status == "accepted" for log in logs)


def test_cancel_offer(db, test_user):
    stream, product, _admin, _card = _stream_with_product(db)
    offer = _create_offer(db, stream, product, test_user)
    cancelled = cancel_offer(db, offer, user_id=test_user.id)
    assert cancelled.status == "cancelled"


def test_public_list_sanitized(api_client, db, test_user):
    stream, product, _admin, _card = _stream_with_product(db)
    _create_offer(db, stream, product, test_user)
    resp = api_client.get(f"/api/live/streams/{stream.id}/offers")
    assert resp.status_code == 200
    item = resp.json()["items"][0]
    assert "sender_name" in item
    assert "user_id" not in item
    assert "email" not in str(item)


def test_offer_expiry(db, test_user):
    stream, product, _admin, _card = _stream_with_product(db)
    offer = _create_offer(db, stream, product, test_user)
    offer.display_expires_at = datetime.utcnow() - timedelta(seconds=1)
    db.commit()
    count = expire_stale_offers(db, stream_id=stream.id)
    assert count >= 1
    db.refresh(offer)
    assert offer.status == "expired"


def test_offers_disabled_on_stream(db, test_user):
    stream, product, _admin, _card = _stream_with_product(db)
    stream.offers_enabled = False
    db.commit()
    with pytest.raises(HTTPException) as exc:
        _create_offer(db, stream, product, test_user)
    assert exc.value.status_code == 409


def test_purchase_via_api(api_client, db, test_user):
    stream, product, _admin, _card = _stream_with_product(db)
    offer = _create_offer(db, stream, product, test_user)
    review_offer(db, offer, action="accept", admin_user_id=1)
    resp = api_client.post(
        f"/api/live/offers/{offer.id}/purchase",
        headers=auth_headers(test_user),
        json={"shipping_address": "Hyogo Test"},
    )
    assert resp.status_code == 201
    assert resp.json()["order_id"] > 0
