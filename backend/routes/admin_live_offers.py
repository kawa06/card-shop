"""Admin live offer routes (Phase 3-3)."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

import schemas_live_offer
from auth import get_current_admin_context
from database import get_db
from services.admin_auth import AdminAccessError, AdminContext, require_permission
from services.live_offers import (
    get_stream_offer_or_404,
    get_stream_offers_settings,
    list_offers,
    patch_product_offers_enabled,
    patch_stream_offers_settings,
    review_offer,
    serialize_offer,
)

router = APIRouter(prefix="/api/admin/live", tags=["admin-live-offers"])


def _handle_admin_error(exc: AdminAccessError) -> None:
    raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc


@router.get("/streams/{stream_id}/offers/settings", response_model=schemas_live_offer.LiveOfferSettingsOut)
def admin_get_offers_settings(
    stream_id: int,
    ctx: AdminContext = Depends(get_current_admin_context),
    db: Session = Depends(get_db),
):
    try:
        require_permission(ctx, "offer.manage")
    except AdminAccessError as exc:
        _handle_admin_error(exc)
    return get_stream_offers_settings(db, stream_id)


@router.patch("/streams/{stream_id}/offers/settings", response_model=schemas_live_offer.LiveOfferSettingsOut)
def admin_patch_offers_settings(
    stream_id: int,
    payload: schemas_live_offer.LiveOfferSettingsPatchIn,
    ctx: AdminContext = Depends(get_current_admin_context),
    db: Session = Depends(get_db),
):
    try:
        require_permission(ctx, "offer.manage")
    except AdminAccessError as exc:
        _handle_admin_error(exc)
    return patch_stream_offers_settings(db, stream_id, payload)


@router.patch("/streams/{stream_id}/products/{product_id}/offers")
def admin_patch_product_offers_enabled(
    stream_id: int,
    product_id: int,
    payload: schemas_live_offer.LiveOfferProductOffersEnabledPatchIn,
    ctx: AdminContext = Depends(get_current_admin_context),
    db: Session = Depends(get_db),
):
    try:
        require_permission(ctx, "offer.manage")
    except AdminAccessError as exc:
        _handle_admin_error(exc)
    product = patch_product_offers_enabled(
        db, stream_id, product_id, offers_enabled=payload.offers_enabled
    )
    return {"id": product.id, "offers_enabled": bool(getattr(product, "offers_enabled", True))}


@router.get("/streams/{stream_id}/offers", response_model=schemas_live_offer.LiveOfferListOut)
def admin_list_offers(
    stream_id: int,
    status: Optional[str] = Query(None),
    sort: str = Query("created_at"),
    order: str = Query("desc"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    ctx: AdminContext = Depends(get_current_admin_context),
    db: Session = Depends(get_db),
):
    try:
        require_permission(ctx, "offer.read")
    except AdminAccessError as exc:
        _handle_admin_error(exc)
    items, total = list_offers(
        db,
        stream_id=stream_id,
        status_filter=status,
        sort=sort,
        order=order,
        limit=limit,
        offset=offset,
    )
    return schemas_live_offer.LiveOfferListOut(
        items=[serialize_offer(db, o) for o in items],
        total=total,
    )


@router.get("/streams/{stream_id}/offers/{offer_id}", response_model=schemas_live_offer.LiveOfferOut)
def admin_get_offer(
    stream_id: int,
    offer_id: int,
    ctx: AdminContext = Depends(get_current_admin_context),
    db: Session = Depends(get_db),
):
    try:
        require_permission(ctx, "offer.read")
    except AdminAccessError as exc:
        _handle_admin_error(exc)
    offer = get_stream_offer_or_404(db, stream_id, offer_id)
    return serialize_offer(db, offer)


@router.post("/streams/{stream_id}/offers/{offer_id}/accept", response_model=schemas_live_offer.LiveOfferOut)
def admin_accept_offer(
    stream_id: int,
    offer_id: int,
    payload: schemas_live_offer.LiveOfferReviewIn | None = None,
    ctx: AdminContext = Depends(get_current_admin_context),
    db: Session = Depends(get_db),
):
    try:
        require_permission(ctx, "offer.review")
    except AdminAccessError as exc:
        _handle_admin_error(exc)
    offer = get_stream_offer_or_404(db, stream_id, offer_id)
    offer = review_offer(
        db,
        offer,
        action="accept",
        admin_user_id=ctx.admin_user.id,
        review_note=payload.review_note if payload else None,
    )
    return serialize_offer(db, offer)


@router.post("/streams/{stream_id}/offers/{offer_id}/reject", response_model=schemas_live_offer.LiveOfferOut)
def admin_reject_offer(
    stream_id: int,
    offer_id: int,
    payload: schemas_live_offer.LiveOfferReviewIn | None = None,
    ctx: AdminContext = Depends(get_current_admin_context),
    db: Session = Depends(get_db),
):
    try:
        require_permission(ctx, "offer.review")
    except AdminAccessError as exc:
        _handle_admin_error(exc)
    offer = get_stream_offer_or_404(db, stream_id, offer_id)
    offer = review_offer(
        db,
        offer,
        action="reject",
        admin_user_id=ctx.admin_user.id,
        review_note=payload.review_note if payload else None,
    )
    return serialize_offer(db, offer)


@router.post("/streams/{stream_id}/offers/{offer_id}/hold", response_model=schemas_live_offer.LiveOfferOut)
def admin_hold_offer(
    stream_id: int,
    offer_id: int,
    payload: schemas_live_offer.LiveOfferReviewIn | None = None,
    ctx: AdminContext = Depends(get_current_admin_context),
    db: Session = Depends(get_db),
):
    try:
        require_permission(ctx, "offer.review")
    except AdminAccessError as exc:
        _handle_admin_error(exc)
    offer = get_stream_offer_or_404(db, stream_id, offer_id)
    offer = review_offer(
        db,
        offer,
        action="hold",
        admin_user_id=ctx.admin_user.id,
        review_note=payload.review_note if payload else None,
    )
    return serialize_offer(db, offer)
