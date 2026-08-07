"""Public live offer routes (Phase 3-3)."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

import models
import schemas_live_offer
from auth import get_current_user
from database import get_db
from services.live_offer_purchase import (
    create_order_from_offer,
    get_purchase_right_or_404,
    serialize_purchase_right,
    verify_purchase_right_owner,
)
from services.live_offers import (
    cancel_offer,
    create_offer,
    get_offer_or_404,
    get_stream_offer_or_404,
    list_offers,
    serialize_offer,
)
from services.live_streams import get_stream_or_404

router = APIRouter(prefix="/api/live", tags=["live-offers"])


@router.get("/streams/{stream_id}/offers", response_model=schemas_live_offer.LiveOfferPublicListOut)
def public_list_offers(
    stream_id: int,
    limit: int = Query(20, ge=1, le=50),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    stream = get_stream_or_404(db, stream_id)
    if stream.visibility != "public":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Stream not found")
    items, total = list_offers(db, stream_id=stream_id, limit=limit, offset=offset, public=True)
    return schemas_live_offer.LiveOfferPublicListOut(
        items=[serialize_offer(db, o, public=True) for o in items],
        total=total,
    )


@router.get("/streams/{stream_id}/offers/mine", response_model=schemas_live_offer.LiveOfferListOut)
def my_offers(
    stream_id: int,
    status: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    stream = get_stream_or_404(db, stream_id)
    if stream.visibility != "public":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Stream not found")
    items, total = list_offers(db, stream_id=stream_id, status_filter=status, limit=limit, offset=offset)
    mine = [o for o in items if o.user_id == current_user.id]
    return schemas_live_offer.LiveOfferListOut(
        items=[serialize_offer(db, o) for o in mine],
        total=len(mine),
    )


@router.post("/streams/{stream_id}/offers", response_model=schemas_live_offer.LiveOfferOut, status_code=201)
def public_create_offer(
    stream_id: int,
    payload: schemas_live_offer.LiveOfferCreateIn,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    stream = get_stream_or_404(db, stream_id)
    if stream.visibility != "public":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Stream not found")
    offer = create_offer(db, stream_id=stream_id, user_id=current_user.id, payload=payload)
    return serialize_offer(db, offer)


@router.post("/streams/{stream_id}/offers/{offer_id}/cancel", response_model=schemas_live_offer.LiveOfferOut)
def public_cancel_offer(
    stream_id: int,
    offer_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    stream = get_stream_or_404(db, stream_id)
    if stream.visibility != "public":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Stream not found")
    offer = get_stream_offer_or_404(db, stream_id, offer_id)
    offer = cancel_offer(db, offer, user_id=current_user.id)
    return serialize_offer(db, offer)


@router.get("/offers/{offer_id}/purchase-right", response_model=schemas_live_offer.LiveOfferPurchaseRightOut)
def get_my_purchase_right(
    offer_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    offer = get_offer_or_404(db, offer_id)
    stream = get_stream_or_404(db, offer.stream_id)
    if stream.visibility != "public":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Offer not found")
    right = get_purchase_right_or_404(db, offer_id)
    verify_purchase_right_owner(right, current_user.id)
    return serialize_purchase_right(right)


@router.post("/offers/{offer_id}/purchase", response_model=schemas_live_offer.LiveOfferPurchaseOut, status_code=201)
def purchase_from_offer(
    offer_id: int,
    payload: schemas_live_offer.LiveOfferPurchaseIn | None = None,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    offer = get_offer_or_404(db, offer_id)
    stream = get_stream_or_404(db, offer.stream_id)
    if stream.visibility != "public":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Offer not found")
    return create_order_from_offer(
        db,
        offer_id=offer_id,
        user_id=current_user.id,
        payload=payload or schemas_live_offer.LiveOfferPurchaseIn(),
    )
