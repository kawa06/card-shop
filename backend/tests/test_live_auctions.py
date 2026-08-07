"""Tests for Phase 3-2 live auctions."""

from __future__ import annotations

from datetime import datetime, timedelta

import models
import models_live
import models_live_auction  # noqa: F401
import pytest
import schemas_live
import schemas_live_auction
from fastapi import HTTPException
from services.live_auctions import create_auction, finish_auction, serialize_auction, start_auction
from services.live_bids import place_bid
from services.live_streams import add_product, create_stream, start_stream
from tests.conftest import admin_headers, auth_headers, create_admin_user


def _card(db) -> models.Card:
    card = models.Card(name="Auction Card", price=2000, stock=3)
    db.add(card)
    db.commit()
    db.refresh(card)
    return card


def _stream_with_product(db):
    admin = create_admin_user(db, email="auction-admin@test.com", role_code="sales_manager")
    from services.admin_auth import get_admin_user_for_user

    admin_user = get_admin_user_for_user(db, admin)
    stream = create_stream(
        db,
        payload=schemas_live.LiveStreamCreateIn(title="Auction Live", visibility="public"),
        admin_user_id=admin_user.id,
    )
    start_stream(db, stream)
    card = _card(db)
    product = add_product(db, stream, schemas_live.LiveProductCreateIn(card_id=card.id))
    return stream, product, admin


def test_create_and_start_auction(db):
    stream, product, _admin = _stream_with_product(db)
    auction = create_auction(
        db,
        stream_id=stream.id,
        payload=schemas_live_auction.LiveAuctionCreateIn(
            live_product_id=product.id,
            start_price=1000,
            min_bid_increment=100,
            buy_now_price=5000,
            duration_seconds=120,
        ),
        admin_user_id=1,
    )
    assert auction.status == "draft"
    started = start_auction(db, auction)
    assert started.status == "running"
    assert started.ends_at is not None


def test_bid_validation_and_increment(db, test_user):
    stream, product, _admin = _stream_with_product(db)
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
        place_bid(
            db,
            auction_id=auction.id,
            user_id=test_user.id,
            payload=schemas_live_auction.LiveBidPlaceIn(amount=1050),
        )
    assert exc.value.status_code == 400
    result = place_bid(
        db,
        auction_id=auction.id,
        user_id=test_user.id,
        payload=schemas_live_auction.LiveBidPlaceIn(amount=1100),
    )
    assert result.bid.amount == 1100
    assert result.auction.current_price == 1100


def test_snipe_extension(db, test_user):
    stream, product, _admin = _stream_with_product(db)
    auction = create_auction(
        db,
        stream_id=stream.id,
        payload=schemas_live_auction.LiveAuctionCreateIn(
            live_product_id=product.id,
            start_price=1000,
            min_bid_increment=100,
            trigger_remaining_seconds=30,
            extension_seconds=45,
        ),
        admin_user_id=1,
    )
    start_auction(db, auction)
    auction.ends_at = datetime.utcnow() + timedelta(seconds=10)
    db.commit()
    previous = auction.ends_at
    result = place_bid(
        db,
        auction_id=auction.id,
        user_id=test_user.id,
        payload=schemas_live_auction.LiveBidPlaceIn(amount=1000),
    )
    assert result.extended is True
    assert result.auction.ends_at > previous
    assert result.auction.extension_count == 1


def test_instant_buy(db, test_user):
    stream, product, _admin = _stream_with_product(db)
    auction = create_auction(
        db,
        stream_id=stream.id,
        payload=schemas_live_auction.LiveAuctionCreateIn(
            live_product_id=product.id,
            start_price=1000,
            min_bid_increment=100,
            buy_now_price=3000,
        ),
        admin_user_id=1,
    )
    start_auction(db, auction)
    result = place_bid(
        db,
        auction_id=auction.id,
        user_id=test_user.id,
        payload=schemas_live_auction.LiveBidPlaceIn(amount=3000),
    )
    assert result.instant_buy is True
    assert result.auction.status == "finished"
    assert result.auction.winner_user_id == test_user.id


def test_finish_auction(db, test_user):
    stream, product, _admin = _stream_with_product(db)
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
    place_bid(
        db,
        auction_id=auction.id,
        user_id=test_user.id,
        payload=schemas_live_auction.LiveBidPlaceIn(amount=1000),
    )
    finished = finish_auction(db, auction)
    assert finished.status == "finished"
    assert finished.winner_user_id == test_user.id


def test_admin_auction_rbac(api_client, db):
    stream, product, _admin = _stream_with_product(db)
    create_admin_user(db, email="viewer@test.com", role_code="viewer")
    denied = api_client.get(
        f"/api/admin/live/streams/{stream.id}/auctions",
        headers=admin_headers("viewer@test.com"),
    )
    assert denied.status_code == 403

    create_admin_user(db, email="sales@test.com", role_code="sales_manager")
    created = api_client.post(
        f"/api/admin/live/streams/{stream.id}/auctions",
        headers=admin_headers("sales@test.com"),
        json={
            "live_product_id": product.id,
            "start_price": 1000,
            "min_bid_increment": 100,
        },
    )
    assert created.status_code == 201
    auction_id = created.json()["id"]
    started = api_client.post(
        f"/api/admin/live/streams/{stream.id}/auctions/{auction_id}/start",
        headers=admin_headers("sales@test.com"),
        json={"duration_seconds": 60},
    )
    assert started.status_code == 200
    assert started.json()["status"] == "running"


def test_public_bid_requires_auth(api_client, db, test_user):
    stream, product, _admin = _stream_with_product(db)
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
    denied = api_client.post(f"/api/live/auctions/{auction.id}/bids", json={"amount": 1000})
    assert denied.status_code == 401
    ok = api_client.post(
        f"/api/live/auctions/{auction.id}/bids",
        headers=auth_headers(test_user),
        json={"amount": 1000},
    )
    assert ok.status_code == 201


def test_live_auction_sse_hub_event():
    import asyncio

    from services.live_events import emit_live_event, live_event_hub

    async def run() -> None:
        gen = live_event_hub.stream(42, "public")
        first = await gen.__anext__()
        assert "connected" in first
        emit_live_event(42, "bid.created", {"auction_id": 1, "amount": 1200})
        msg = await gen.__anext__()
        assert "bid.created" in msg
        await gen.aclose()

    asyncio.run(run())
    assert live_event_hub.global_connections == 0
