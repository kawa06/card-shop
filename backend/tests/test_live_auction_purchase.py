"""Tests for Phase 3-4 live auction purchase flow."""

from __future__ import annotations

import models
import models_live_auction  # noqa: F401
import pytest
import schemas_live_auction
from fastapi import HTTPException
from services.live_auction_purchase import create_order_from_auction, get_purchase_right_or_404
from services.live_auctions import create_auction, finish_auction, start_auction
from services.live_bids import place_bid
from services.point_ledger import admin_grant_points, get_or_create_account
from tests.conftest import create_admin_user
from tests.test_live_auctions import _stream_with_product


def test_finish_auction_creates_purchase_right(db, test_user):
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
    finish_auction(db, auction)
    right = get_purchase_right_or_404(db, auction.id)
    assert right.user_id == test_user.id
    assert right.winning_price == 1000
    assert right.status == "active"


def test_auction_purchase_with_points(db, test_user):
    admin = create_admin_user(db, email="auction-points@test.com", role_code="admin")
    admin_grant_points(
        db,
        user_id=test_user.id,
        amount=500,
        reason="auction test",
        admin_user_id=admin.id,
        idempotency_key="auction-grant",
    )
    db.commit()

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
    finish_auction(db, auction)

    result = create_order_from_auction(
        db,
        auction_id=auction.id,
        user_id=test_user.id,
        payload=schemas_live_auction.LiveAuctionPurchaseIn(
            shipping_address="Auction points test",
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


def test_auction_purchase_wrong_user_forbidden(db, test_user):
    stream, product, _admin = _stream_with_product(db)
    other = models.User(email="other-bidder@test.com", password_hash="x", name="Other")
    db.add(other)
    db.commit()
    db.refresh(other)

    auction = create_auction(
        db,
        stream_id=stream.id,
        payload=schemas_live_auction.LiveAuctionCreateIn(
            live_product_id=product.id,
            start_price=1000,
        ),
        admin_user_id=1,
    )
    start_auction(db, auction)
    place_bid(
        db,
        auction_id=auction.id,
        user_id=other.id,
        payload=schemas_live_auction.LiveBidPlaceIn(amount=1000),
    )
    finish_auction(db, auction)

    with pytest.raises(HTTPException) as exc:
        create_order_from_auction(
            db,
            auction_id=auction.id,
            user_id=test_user.id,
            payload=schemas_live_auction.LiveAuctionPurchaseIn(shipping_address="x"),
        )
    assert exc.value.status_code == 403
