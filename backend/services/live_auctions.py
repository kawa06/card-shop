"""Live auction domain services (Phase 3-2)."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

import models
import models_live
import models_live_auction
import schemas_live_auction
from services.live_events import emit_live_event
from services.live_streams import get_stream_or_404


def _utcnow() -> datetime:
    return datetime.utcnow()


def _shop_settings(db: Session, shop_id: int = 1) -> models_live_auction.LiveAuctionSettings:
    row = (
        db.query(models_live_auction.LiveAuctionSettings)
        .filter(models_live_auction.LiveAuctionSettings.shop_id == shop_id)
        .first()
    )
    if row is None:
        row = models_live_auction.LiveAuctionSettings(shop_id=shop_id)
        db.add(row)
        db.commit()
        db.refresh(row)
    return row


def _serialize_product(db: Session, product: models_live.LiveProduct) -> schemas_live_auction.LiveAuctionProductOut:
    card = db.query(models.Card).filter(models.Card.id == product.card_id).first()
    return schemas_live_auction.LiveAuctionProductOut(
        id=product.id,
        stream_id=product.stream_id,
        card_id=product.card_id,
        display_price=product.display_price,
        card_name=card.name if card else None,
        card_image_url=card.image_url if card else None,
    )


def serialize_auction(db: Session, auction: models_live_auction.LiveAuction) -> schemas_live_auction.LiveAuctionOut:
    product = (
        db.query(models_live.LiveProduct)
        .filter(models_live.LiveProduct.id == auction.live_product_id)
        .first()
    )
    return schemas_live_auction.LiveAuctionOut(
        id=auction.id,
        stream_id=auction.stream_id,
        live_product_id=auction.live_product_id,
        status=auction.status,
        start_price=auction.start_price,
        current_price=auction.current_price,
        min_bid_increment=auction.min_bid_increment,
        buy_now_price=auction.buy_now_price,
        scheduled_start_at=auction.scheduled_start_at,
        scheduled_end_at=auction.scheduled_end_at,
        ends_at=auction.ends_at,
        extension_seconds=auction.extension_seconds,
        auto_extend_enabled=auction.auto_extend_enabled,
        max_extensions=auction.max_extensions,
        extension_count=auction.extension_count,
        trigger_remaining_seconds=auction.trigger_remaining_seconds,
        winner_user_id=auction.winner_user_id,
        winning_amount=auction.winning_amount,
        bid_count=auction.bid_count,
        bidder_count=auction.bidder_count,
        created_at=auction.created_at,
        updated_at=auction.updated_at,
        product=_serialize_product(db, product) if product else None,
    )


def _emit_auction(db: Session, auction: models_live_auction.LiveAuction, event_type: str) -> None:
    emit_live_event(
        auction.stream_id,
        event_type,
        serialize_auction(db, auction).model_dump(mode="json"),
    )


def get_auction_or_404(db: Session, auction_id: int) -> models_live_auction.LiveAuction:
    auction = (
        db.query(models_live_auction.LiveAuction)
        .filter(models_live_auction.LiveAuction.id == auction_id)
        .first()
    )
    if auction is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Auction not found")
    return auction


def get_stream_auction_or_404(
    db: Session, stream_id: int, auction_id: int
) -> models_live_auction.LiveAuction:
    auction = get_auction_or_404(db, auction_id)
    if auction.stream_id != stream_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Auction not found")
    return auction


def list_auctions(
    db: Session,
    *,
    stream_id: int,
    status_filter: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[models_live_auction.LiveAuction], int]:
    query = db.query(models_live_auction.LiveAuction).filter(
        models_live_auction.LiveAuction.stream_id == stream_id
    )
    if status_filter:
        query = query.filter(models_live_auction.LiveAuction.status == status_filter)
    total = query.count()
    items = (
        query.order_by(models_live_auction.LiveAuction.id.desc())
        .offset(offset)
        .limit(min(limit, 100))
        .all()
    )
    return items, total


def create_auction(
    db: Session,
    *,
    stream_id: int,
    payload: schemas_live_auction.LiveAuctionCreateIn,
    admin_user_id: int,
) -> models_live_auction.LiveAuction:
    get_stream_or_404(db, stream_id)
    product = (
        db.query(models_live.LiveProduct)
        .filter(
            models_live.LiveProduct.id == payload.live_product_id,
            models_live.LiveProduct.stream_id == stream_id,
        )
        .first()
    )
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Live product not found")
    settings = _shop_settings(db)
    auction = models_live_auction.LiveAuction(
        stream_id=stream_id,
        live_product_id=payload.live_product_id,
        status="waiting" if payload.scheduled_start_at else "draft",
        start_price=payload.start_price,
        min_bid_increment=payload.min_bid_increment or settings.default_min_bid_increment,
        buy_now_price=payload.buy_now_price,
        scheduled_start_at=payload.scheduled_start_at,
        scheduled_end_at=payload.scheduled_end_at,
        extension_seconds=payload.extension_seconds or settings.default_extension_seconds,
        auto_extend_enabled=(
            settings.default_auto_extend_enabled
            if payload.auto_extend_enabled is None
            else payload.auto_extend_enabled
        ),
        max_extensions=payload.max_extensions if payload.max_extensions is not None else settings.default_max_extensions,
        trigger_remaining_seconds=(
            payload.trigger_remaining_seconds or settings.default_trigger_remaining_seconds
        ),
        created_by_admin_id=admin_user_id,
    )
    if payload.duration_seconds:
        auction.ends_at = _utcnow() + timedelta(seconds=payload.duration_seconds)
    db.add(auction)
    db.commit()
    db.refresh(auction)
    _emit_auction(db, auction, "auction.created")
    return auction


def update_auction(
    db: Session,
    auction: models_live_auction.LiveAuction,
    payload: schemas_live_auction.LiveAuctionUpdateIn,
) -> models_live_auction.LiveAuction:
    if auction.status not in ("draft", "waiting"):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Auction cannot be updated")
    data = payload.model_dump(exclude_unset=True)
    for key, value in data.items():
        setattr(auction, key, value)
    auction.updated_at = _utcnow()
    db.commit()
    db.refresh(auction)
    _emit_auction(db, auction, "auction.updated")
    return auction


def start_auction(
    db: Session,
    auction: models_live_auction.LiveAuction,
    payload: Optional[schemas_live_auction.LiveAuctionStartIn] = None,
) -> models_live_auction.LiveAuction:
    if auction.status not in ("draft", "waiting", "paused"):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Auction cannot be started")
    duration = payload.duration_seconds if payload and payload.duration_seconds else None
    auction.status = "running"
    if auction.ends_at is None:
        if auction.scheduled_end_at:
            auction.ends_at = auction.scheduled_end_at
        elif duration:
            auction.ends_at = _utcnow() + timedelta(seconds=duration)
        else:
            auction.ends_at = _utcnow() + timedelta(minutes=5)
    auction.updated_at = _utcnow()
    db.commit()
    db.refresh(auction)
    _emit_auction(db, auction, "auction.started")
    return auction


def pause_auction(db: Session, auction: models_live_auction.LiveAuction) -> models_live_auction.LiveAuction:
    if auction.status != "running":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Only running auctions can be paused")
    auction.status = "paused"
    auction.updated_at = _utcnow()
    db.commit()
    db.refresh(auction)
    _emit_auction(db, auction, "auction.paused")
    return auction


def resume_auction(db: Session, auction: models_live_auction.LiveAuction) -> models_live_auction.LiveAuction:
    if auction.status != "paused":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Only paused auctions can be resumed")
    auction.status = "running"
    auction.updated_at = _utcnow()
    db.commit()
    db.refresh(auction)
    _emit_auction(db, auction, "auction.resumed")
    return auction


def _apply_winner_from_bids(db: Session, auction: models_live_auction.LiveAuction) -> None:
    winning_bid = (
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
    if winning_bid is None:
        auction.winner_user_id = None
        auction.winning_amount = None
        return
    auction.winner_user_id = winning_bid.user_id
    auction.winning_amount = winning_bid.amount
    winning_bid.status = "won"
    (
        db.query(models_live_auction.LiveBid)
        .filter(
            models_live_auction.LiveBid.auction_id == auction.id,
            models_live_auction.LiveBid.id != winning_bid.id,
            models_live_auction.LiveBid.status == "active",
        )
        .update({models_live_auction.LiveBid.status: "outbid"}, synchronize_session=False)
    )


def finish_auction(db: Session, auction: models_live_auction.LiveAuction) -> models_live_auction.LiveAuction:
    if auction.status in ("finished", "cancelled"):
        return auction
    if auction.status not in ("running", "paused"):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Auction cannot be finished")
    _apply_winner_from_bids(db, auction)
    auction.status = "finished"
    auction.updated_at = _utcnow()
    db.commit()
    db.refresh(auction)
    if auction.winner_user_id is not None:
        emit_live_event(
            auction.stream_id,
            "bid.winner",
            {
                "auction_id": auction.id,
                "user_id": auction.winner_user_id,
                "amount": auction.winning_amount,
            },
        )
    _emit_auction(db, auction, "auction.finished")
    return auction


def cancel_auction(db: Session, auction: models_live_auction.LiveAuction) -> models_live_auction.LiveAuction:
    if auction.status == "finished":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Finished auctions cannot be cancelled")
    auction.status = "cancelled"
    auction.updated_at = _utcnow()
    db.commit()
    db.refresh(auction)
    _emit_auction(db, auction, "auction.cancelled")
    return auction


def force_end_auction(db: Session, auction: models_live_auction.LiveAuction) -> models_live_auction.LiveAuction:
    return finish_auction(db, auction)
