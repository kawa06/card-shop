"""Public live auction routes (Phase 3-2)."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

import models
import schemas_live_auction
from auth import get_current_user
from database import get_db
from services.live_auctions import get_auction_or_404, list_auctions, serialize_auction
from services.live_bids import list_bids, place_bid, serialize_bid
from services.live_streams import get_stream_or_404

router = APIRouter(prefix="/api/live", tags=["live-auctions"])


@router.get("/streams/{stream_id}/auctions", response_model=schemas_live_auction.LiveAuctionListOut)
def public_list_auctions(
    stream_id: int,
    status: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=50),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    stream = get_stream_or_404(db, stream_id)
    if stream.visibility != "public":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Stream not found")
    items, total = list_auctions(db, stream_id=stream_id, status_filter=status, limit=limit, offset=offset)
    return schemas_live_auction.LiveAuctionListOut(
        items=[serialize_auction(db, a) for a in items],
        total=total,
    )


@router.get("/auctions/{auction_id}", response_model=schemas_live_auction.LiveAuctionOut)
def public_get_auction(auction_id: int, db: Session = Depends(get_db)):
    auction = get_auction_or_404(db, auction_id)
    stream = get_stream_or_404(db, auction.stream_id)
    if stream.visibility != "public":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Auction not found")
    return serialize_auction(db, auction)


@router.get("/auctions/{auction_id}/bids", response_model=schemas_live_auction.LiveBidListOut)
def public_list_bids(
    auction_id: int,
    limit: int = Query(20, ge=1, le=50),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    auction = get_auction_or_404(db, auction_id)
    stream = get_stream_or_404(db, auction.stream_id)
    if stream.visibility != "public":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Auction not found")
    items, total = list_bids(db, auction_id, limit=limit, offset=offset)
    return schemas_live_auction.LiveBidListOut(items=[serialize_bid(b) for b in items], total=total)


@router.post("/auctions/{auction_id}/bids", response_model=schemas_live_auction.LiveBidPlaceOut, status_code=201)
def public_place_bid(
    auction_id: int,
    payload: schemas_live_auction.LiveBidPlaceIn,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    auction = get_auction_or_404(db, auction_id)
    stream = get_stream_or_404(db, auction.stream_id)
    if stream.visibility != "public":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Auction not found")
    return place_bid(db, auction_id=auction_id, user_id=current_user.id, payload=payload)
