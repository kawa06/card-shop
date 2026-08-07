"""Admin live auction routes (Phase 3-2)."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

import schemas_live_auction
from auth import get_current_admin_context
from database import get_db
from services.admin_auth import AdminAccessError, AdminContext, require_permission
from services.live_auctions import (
    cancel_auction,
    create_auction,
    force_end_auction,
    finish_auction,
    get_stream_auction_or_404,
    list_auctions,
    pause_auction,
    resume_auction,
    serialize_auction,
    start_auction,
    update_auction,
)
from services.live_bids import list_bids, serialize_bid
from services.live_streams import get_stream_or_404

router = APIRouter(prefix="/api/admin/live", tags=["admin-live-auctions"])


def _handle_admin_error(exc: AdminAccessError) -> None:
    raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc


@router.get("/streams/{stream_id}/auctions", response_model=schemas_live_auction.LiveAuctionListOut)
def admin_list_auctions(
    stream_id: int,
    status: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    ctx: AdminContext = Depends(get_current_admin_context),
    db: Session = Depends(get_db),
):
    try:
        require_permission(ctx, "auction.read")
    except AdminAccessError as exc:
        _handle_admin_error(exc)
    get_stream_or_404(db, stream_id)
    items, total = list_auctions(db, stream_id=stream_id, status_filter=status, limit=limit, offset=offset)
    return schemas_live_auction.LiveAuctionListOut(
        items=[serialize_auction(db, a) for a in items],
        total=total,
    )


@router.post("/streams/{stream_id}/auctions", response_model=schemas_live_auction.LiveAuctionOut, status_code=201)
def admin_create_auction(
    stream_id: int,
    payload: schemas_live_auction.LiveAuctionCreateIn,
    ctx: AdminContext = Depends(get_current_admin_context),
    db: Session = Depends(get_db),
):
    try:
        require_permission(ctx, "auction.write")
    except AdminAccessError as exc:
        _handle_admin_error(exc)
    auction = create_auction(db, stream_id=stream_id, payload=payload, admin_user_id=ctx.admin_user.id)
    return serialize_auction(db, auction)


@router.get("/streams/{stream_id}/auctions/{auction_id}", response_model=schemas_live_auction.LiveAuctionOut)
def admin_get_auction(
    stream_id: int,
    auction_id: int,
    ctx: AdminContext = Depends(get_current_admin_context),
    db: Session = Depends(get_db),
):
    try:
        require_permission(ctx, "auction.read")
    except AdminAccessError as exc:
        _handle_admin_error(exc)
    auction = get_stream_auction_or_404(db, stream_id, auction_id)
    return serialize_auction(db, auction)


@router.patch("/streams/{stream_id}/auctions/{auction_id}", response_model=schemas_live_auction.LiveAuctionOut)
def admin_update_auction(
    stream_id: int,
    auction_id: int,
    payload: schemas_live_auction.LiveAuctionUpdateIn,
    ctx: AdminContext = Depends(get_current_admin_context),
    db: Session = Depends(get_db),
):
    try:
        require_permission(ctx, "auction.write")
    except AdminAccessError as exc:
        _handle_admin_error(exc)
    auction = get_stream_auction_or_404(db, stream_id, auction_id)
    auction = update_auction(db, auction, payload)
    return serialize_auction(db, auction)


@router.post("/streams/{stream_id}/auctions/{auction_id}/start", response_model=schemas_live_auction.LiveAuctionOut)
def admin_start_auction(
    stream_id: int,
    auction_id: int,
    payload: schemas_live_auction.LiveAuctionStartIn | None = None,
    ctx: AdminContext = Depends(get_current_admin_context),
    db: Session = Depends(get_db),
):
    try:
        require_permission(ctx, "auction.manage")
    except AdminAccessError as exc:
        _handle_admin_error(exc)
    auction = get_stream_auction_or_404(db, stream_id, auction_id)
    auction = start_auction(db, auction, payload)
    return serialize_auction(db, auction)


@router.post("/streams/{stream_id}/auctions/{auction_id}/pause", response_model=schemas_live_auction.LiveAuctionOut)
def admin_pause_auction(
    stream_id: int,
    auction_id: int,
    ctx: AdminContext = Depends(get_current_admin_context),
    db: Session = Depends(get_db),
):
    try:
        require_permission(ctx, "auction.manage")
    except AdminAccessError as exc:
        _handle_admin_error(exc)
    auction = get_stream_auction_or_404(db, stream_id, auction_id)
    auction = pause_auction(db, auction)
    return serialize_auction(db, auction)


@router.post("/streams/{stream_id}/auctions/{auction_id}/resume", response_model=schemas_live_auction.LiveAuctionOut)
def admin_resume_auction(
    stream_id: int,
    auction_id: int,
    ctx: AdminContext = Depends(get_current_admin_context),
    db: Session = Depends(get_db),
):
    try:
        require_permission(ctx, "auction.manage")
    except AdminAccessError as exc:
        _handle_admin_error(exc)
    auction = get_stream_auction_or_404(db, stream_id, auction_id)
    auction = resume_auction(db, auction)
    return serialize_auction(db, auction)


@router.post("/streams/{stream_id}/auctions/{auction_id}/finish", response_model=schemas_live_auction.LiveAuctionOut)
def admin_finish_auction(
    stream_id: int,
    auction_id: int,
    ctx: AdminContext = Depends(get_current_admin_context),
    db: Session = Depends(get_db),
):
    try:
        require_permission(ctx, "auction.manage")
    except AdminAccessError as exc:
        _handle_admin_error(exc)
    auction = get_stream_auction_or_404(db, stream_id, auction_id)
    auction = finish_auction(db, auction)
    return serialize_auction(db, auction)


@router.post("/streams/{stream_id}/auctions/{auction_id}/cancel", response_model=schemas_live_auction.LiveAuctionOut)
def admin_cancel_auction(
    stream_id: int,
    auction_id: int,
    ctx: AdminContext = Depends(get_current_admin_context),
    db: Session = Depends(get_db),
):
    try:
        require_permission(ctx, "auction.manage")
    except AdminAccessError as exc:
        _handle_admin_error(exc)
    auction = get_stream_auction_or_404(db, stream_id, auction_id)
    auction = cancel_auction(db, auction)
    return serialize_auction(db, auction)


@router.post("/streams/{stream_id}/auctions/{auction_id}/force-end", response_model=schemas_live_auction.LiveAuctionOut)
def admin_force_end_auction(
    stream_id: int,
    auction_id: int,
    ctx: AdminContext = Depends(get_current_admin_context),
    db: Session = Depends(get_db),
):
    try:
        require_permission(ctx, "auction.manage")
    except AdminAccessError as exc:
        _handle_admin_error(exc)
    auction = get_stream_auction_or_404(db, stream_id, auction_id)
    auction = force_end_auction(db, auction)
    return serialize_auction(db, auction)


@router.get(
    "/streams/{stream_id}/auctions/{auction_id}/bids",
    response_model=schemas_live_auction.LiveBidListOut,
)
def admin_list_bids(
    stream_id: int,
    auction_id: int,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    ctx: AdminContext = Depends(get_current_admin_context),
    db: Session = Depends(get_db),
):
    try:
        require_permission(ctx, "auction.read")
    except AdminAccessError as exc:
        _handle_admin_error(exc)
    get_stream_auction_or_404(db, stream_id, auction_id)
    items, total = list_bids(db, auction_id, limit=limit, offset=offset)
    return schemas_live_auction.LiveBidListOut(items=[serialize_bid(b) for b in items], total=total)
