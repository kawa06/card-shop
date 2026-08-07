"""Live auction bidding services (Phase 3-2)."""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

import models_live_auction
import schemas_live_auction
from services.live_auction_rate_limit import check_live_bid_rate_limit
from services.live_auctions import finish_auction, serialize_auction
from services.live_events import emit_live_event


def _utcnow() -> datetime:
    return datetime.utcnow()


def _log_bid(
    db: Session,
    *,
    auction_id: int,
    action: str,
    user_id: Optional[int] = None,
    bid_id: Optional[int] = None,
    amount: Optional[int] = None,
    detail: Optional[dict] = None,
) -> None:
    db.add(
        models_live_auction.LiveBidLog(
            auction_id=auction_id,
            bid_id=bid_id,
            user_id=user_id,
            action=action,
            amount=amount,
            detail_json=json.dumps(detail, ensure_ascii=False) if detail else None,
        )
    )


def _validate_bid_amount(auction: models_live_auction.LiveAuction, amount: int) -> None:
    if auction.bid_count == 0:
        min_amount = auction.start_price
    else:
        if auction.current_price is None:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Auction price state invalid")
        min_amount = auction.current_price + auction.min_bid_increment
    if amount < min_amount:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Bid must be at least {min_amount}",
        )
    if (amount - min_amount) % auction.min_bid_increment != 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Bid increment invalid")


def _maybe_extend(
    db: Session,
    auction: models_live_auction.LiveAuction,
    *,
    trigger_bid_id: int,
) -> bool:
    if not auction.auto_extend_enabled:
        return False
    if auction.extension_count >= auction.max_extensions:
        return False
    if auction.ends_at is None:
        return False
    remaining = (auction.ends_at - _utcnow()).total_seconds()
    if remaining > auction.trigger_remaining_seconds:
        return False
    previous = auction.ends_at
    auction.ends_at = auction.ends_at + timedelta(seconds=auction.extension_seconds)
    auction.extension_count += 1
    db.add(
        models_live_auction.LiveAuctionExtension(
            auction_id=auction.id,
            previous_ends_at=previous,
            new_ends_at=auction.ends_at,
            trigger_bid_id=trigger_bid_id,
            extension_number=auction.extension_count,
        )
    )
    _log_bid(
        db,
        auction_id=auction.id,
        action="auction.extended",
        bid_id=trigger_bid_id,
        detail={
            "previous_ends_at": previous.isoformat(),
            "new_ends_at": auction.ends_at.isoformat(),
            "extension_count": auction.extension_count,
        },
    )
    return True


def list_bids(
    db: Session,
    auction_id: int,
    *,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[models_live_auction.LiveBid], int]:
    query = db.query(models_live_auction.LiveBid).filter(
        models_live_auction.LiveBid.auction_id == auction_id
    )
    total = query.count()
    items = (
        query.order_by(models_live_auction.LiveBid.amount.desc(), models_live_auction.LiveBid.id.desc())
        .offset(offset)
        .limit(min(limit, 100))
        .all()
    )
    return items, total


def serialize_bid(bid: models_live_auction.LiveBid) -> schemas_live_auction.LiveBidOut:
    return schemas_live_auction.LiveBidOut.model_validate(bid)


def place_bid(
    db: Session,
    *,
    auction_id: int,
    user_id: int,
    payload: schemas_live_auction.LiveBidPlaceIn,
) -> schemas_live_auction.LiveBidPlaceOut:
    rate = check_live_bid_rate_limit(user_id, auction_id)
    if not rate.allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=rate.reason or "Rate limit exceeded",
            headers={"Retry-After": str(rate.retry_after_seconds)},
        )

    if payload.idempotency_key:
        existing = (
            db.query(models_live_auction.LiveBid)
            .filter(
                models_live_auction.LiveBid.auction_id == auction_id,
                models_live_auction.LiveBid.idempotency_key == payload.idempotency_key,
            )
            .first()
        )
        if existing is not None:
            auction = (
                db.query(models_live_auction.LiveAuction)
                .filter(models_live_auction.LiveAuction.id == auction_id)
                .first()
            )
            return schemas_live_auction.LiveBidPlaceOut(
                bid=serialize_bid(existing),
                auction=serialize_auction(db, auction),
                instant_buy=False,
                extended=False,
            )

    auction = (
        db.query(models_live_auction.LiveAuction)
        .filter(models_live_auction.LiveAuction.id == auction_id)
        .with_for_update()
        .first()
    )
    if auction is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Auction not found")
    if auction.status != "running":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Auction is not accepting bids")
    if auction.ends_at is not None and auction.ends_at <= _utcnow():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Auction has ended")

    amount = payload.amount
    _validate_bid_amount(auction, amount)

    previous_leader = (
        db.query(models_live_auction.LiveBid)
        .filter(
            models_live_auction.LiveBid.auction_id == auction.id,
            models_live_auction.LiveBid.status == "active",
        )
        .order_by(
            models_live_auction.LiveBid.amount.desc(),
            models_live_auction.LiveBid.id.desc(),
        )
        .first()
    )
    previous_leader_user_id = previous_leader.user_id if previous_leader else None

    if previous_leader is not None and previous_leader.user_id != user_id:
        previous_leader.status = "outbid"

    bid = models_live_auction.LiveBid(
        auction_id=auction.id,
        user_id=user_id,
        amount=amount,
        status="active",
        idempotency_key=payload.idempotency_key,
    )
    db.add(bid)
    db.flush()

    auction.current_price = amount
    auction.bid_count += 1
    distinct_bidders = (
        db.query(models_live_auction.LiveBid.user_id)
        .filter(models_live_auction.LiveBid.auction_id == auction.id)
        .distinct()
        .count()
    )
    auction.bidder_count = int(distinct_bidders)
    auction.updated_at = _utcnow()

    _log_bid(
        db,
        auction_id=auction.id,
        action="bid.created",
        user_id=user_id,
        bid_id=bid.id,
        amount=amount,
    )

    instant_buy = auction.buy_now_price is not None and amount >= auction.buy_now_price
    extended = False
    if instant_buy:
        auction.winner_user_id = user_id
        auction.winning_amount = amount
        bid.status = "won"
        auction.status = "finished"
        _log_bid(
            db,
            auction_id=auction.id,
            action="auction.instant_buy",
            user_id=user_id,
            bid_id=bid.id,
            amount=amount,
        )
    else:
        extended = _maybe_extend(db, auction, trigger_bid_id=bid.id)

    db.commit()
    db.refresh(auction)
    db.refresh(bid)

    emit_live_event(
        auction.stream_id,
        "bid.created",
        serialize_bid(bid).model_dump(mode="json"),
    )
    if previous_leader_user_id is not None and previous_leader_user_id != user_id:
        emit_live_event(
            auction.stream_id,
            "bid.outbid",
            {"auction_id": auction.id, "user_id": previous_leader_user_id, "amount": amount},
        )
    if extended:
        emit_live_event(
            auction.stream_id,
            "auction.extended",
            serialize_auction(db, auction).model_dump(mode="json"),
        )
    if instant_buy:
        emit_live_event(
            auction.stream_id,
            "auction.instant_buy",
            serialize_auction(db, auction).model_dump(mode="json"),
        )
        emit_live_event(
            auction.stream_id,
            "bid.winner",
            {"auction_id": auction.id, "user_id": user_id, "amount": amount},
        )
        emit_live_event(
            auction.stream_id,
            "auction.finished",
            serialize_auction(db, auction).model_dump(mode="json"),
        )

    return schemas_live_auction.LiveBidPlaceOut(
        bid=serialize_bid(bid),
        auction=serialize_auction(db, auction),
        instant_buy=instant_buy,
        extended=extended,
    )
