"""Live offer domain services (Phase 3-3)."""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

import models
import models_live
import models_live_auction
import models_live_offer
import schemas_live_offer
from services.live_events import emit_live_event
from services.live_offer_rate_limit import check_live_offer_rate_limit
from services.live_streams import get_stream_or_404

ADMIN_ACTIONS = {
    "accept": "accepted",
    "reject": "rejected",
    "hold": "held",
}

ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    "pending": {"accepted", "rejected", "held", "cancelled", "expired"},
    "held": {"accepted", "rejected", "cancelled", "expired"},
    "accepted": set(),
    "rejected": set(),
    "expired": set(),
    "cancelled": set(),
}


def _utcnow() -> datetime:
    return datetime.utcnow()


def _shop_settings(db: Session, shop_id: int = 1) -> models_live_offer.LiveOfferSettings:
    row = (
        db.query(models_live_offer.LiveOfferSettings)
        .filter(models_live_offer.LiveOfferSettings.shop_id == shop_id)
        .first()
    )
    if row is None:
        row = models_live_offer.LiveOfferSettings(shop_id=shop_id)
        db.add(row)
        db.commit()
        db.refresh(row)
    return row


def _sender_name(db: Session, user_id: int) -> Optional[str]:
    user = db.query(models.User).filter(models.User.id == user_id).first()
    return user.name if user else None


def _serialize_product(
    db: Session, product: models_live.LiveProduct
) -> schemas_live_offer.LiveOfferProductOut:
    card = db.query(models.Card).filter(models.Card.id == product.card_id).first()
    return schemas_live_offer.LiveOfferProductOut(
        id=product.id,
        stream_id=product.stream_id,
        card_id=product.card_id,
        display_price=product.display_price,
        card_name=card.name if card else None,
        card_image_url=card.image_url if card else None,
    )


def serialize_offer(
    db: Session,
    offer: models_live_offer.LiveOffer,
    *,
    public: bool = False,
) -> schemas_live_offer.LiveOfferOut | schemas_live_offer.LiveOfferPublicOut:
    product = (
        db.query(models_live.LiveProduct)
        .filter(models_live.LiveProduct.id == offer.live_product_id)
        .first()
    )
    product_out = _serialize_product(db, product) if product else None
    sender = _sender_name(db, offer.user_id)
    if public:
        return schemas_live_offer.LiveOfferPublicOut(
            id=offer.id,
            amount=offer.amount,
            status=offer.status,
            sender_name=sender,
            live_product_id=offer.live_product_id,
            product=product_out,
            created_at=offer.created_at,
        )
    return schemas_live_offer.LiveOfferOut(
        id=offer.id,
        stream_id=offer.stream_id,
        live_product_id=offer.live_product_id,
        user_id=offer.user_id,
        amount=offer.amount,
        status=offer.status,
        review_note=offer.review_note,
        reviewed_at=offer.reviewed_at,
        reviewed_by_admin_id=offer.reviewed_by_admin_id,
        display_expires_at=offer.display_expires_at,
        purchase_expires_at=offer.purchase_expires_at,
        created_at=offer.created_at,
        updated_at=offer.updated_at,
        sender_name=sender,
        product=product_out,
    )


def _emit_offer(
    db: Session,
    offer: models_live_offer.LiveOffer,
    event_type: str,
    *,
    public: bool = True,
) -> None:
    payload = serialize_offer(db, offer, public=public).model_dump(mode="json")
    emit_live_event(offer.stream_id, event_type, payload)


def _audit_log(
    db: Session,
    *,
    stream_id: int,
    offer_id: int,
    action: str,
    before_status: Optional[str],
    after_status: Optional[str],
    admin_user_id: Optional[int] = None,
    detail: Optional[dict] = None,
) -> None:
    db.add(
        models_live_offer.LiveOfferAuditLog(
            stream_id=stream_id,
            offer_id=offer_id,
            action=action,
            admin_user_id=admin_user_id,
            before_status=before_status,
            after_status=after_status,
            detail_json=json.dumps(detail, ensure_ascii=False) if detail else None,
        )
    )


def _validate_amount(settings: models_live_offer.LiveOfferSettings, amount: int) -> None:
    if not isinstance(amount, int):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Amount must be an integer")
    if amount < 1:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Amount must be at least 1")
    if amount > settings.max_amount:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Amount must not exceed {settings.max_amount}",
        )


def _assert_no_auction_conflict(db: Session, live_product_id: int) -> None:
    conflict = (
        db.query(models_live_auction.LiveAuction)
        .filter(
            models_live_auction.LiveAuction.live_product_id == live_product_id,
            models_live_auction.LiveAuction.status.in_(("running", "paused")),
        )
        .first()
    )
    if conflict is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Offers are not allowed while an auction is active for this product",
        )


def _assert_offers_enabled(db: Session, stream: models_live.LiveStream, product: models_live.LiveProduct) -> None:
    stream_enabled = getattr(stream, "offers_enabled", True)
    product_enabled = getattr(product, "offers_enabled", True)
    if not stream_enabled or not product_enabled:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Offers are disabled")


def expire_stale_offers(db: Session, *, stream_id: Optional[int] = None) -> int:
    now = _utcnow()
    query = db.query(models_live_offer.LiveOffer).filter(
        models_live_offer.LiveOffer.status.in_(("pending", "held")),
        models_live_offer.LiveOffer.display_expires_at.isnot(None),
        models_live_offer.LiveOffer.display_expires_at <= now,
    )
    if stream_id is not None:
        query = query.filter(models_live_offer.LiveOffer.stream_id == stream_id)
    count = 0
    for offer in query.all():
        before = offer.status
        offer.status = "expired"
        offer.updated_at = now
        _audit_log(
            db,
            stream_id=offer.stream_id,
            offer_id=offer.id,
            action="offer.expired",
            before_status=before,
            after_status="expired",
        )
        count += 1
        _emit_offer(db, offer, "offer.expired")
    if count:
        db.commit()
    return count


def get_offer_or_404(db: Session, offer_id: int) -> models_live_offer.LiveOffer:
    offer = db.query(models_live_offer.LiveOffer).filter(models_live_offer.LiveOffer.id == offer_id).first()
    if offer is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Offer not found")
    return offer


def get_stream_offer_or_404(
    db: Session, stream_id: int, offer_id: int
) -> models_live_offer.LiveOffer:
    offer = get_offer_or_404(db, offer_id)
    if offer.stream_id != stream_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Offer not found")
    return offer


def list_offers(
    db: Session,
    *,
    stream_id: int,
    status_filter: Optional[str] = None,
    sort: str = "created_at",
    order: str = "desc",
    limit: int = 50,
    offset: int = 0,
    public: bool = False,
) -> tuple[list[models_live_offer.LiveOffer], int]:
    expire_stale_offers(db, stream_id=stream_id)
    query = db.query(models_live_offer.LiveOffer).filter(
        models_live_offer.LiveOffer.stream_id == stream_id
    )
    if status_filter:
        query = query.filter(models_live_offer.LiveOffer.status == status_filter)
    if public:
        query = query.filter(models_live_offer.LiveOffer.status.in_(("pending", "held", "accepted")))
    total = query.count()
    sort_col = (
        models_live_offer.LiveOffer.amount
        if sort == "amount"
        else models_live_offer.LiveOffer.created_at
    )
    if order == "asc":
        query = query.order_by(sort_col.asc(), models_live_offer.LiveOffer.id.asc())
    else:
        query = query.order_by(sort_col.desc(), models_live_offer.LiveOffer.id.desc())
    items = query.offset(offset).limit(min(limit, 100)).all()
    return items, total


def create_offer(
    db: Session,
    *,
    stream_id: int,
    user_id: int,
    payload: schemas_live_offer.LiveOfferCreateIn,
) -> models_live_offer.LiveOffer:
    stream = get_stream_or_404(db, stream_id)
    settings = _shop_settings(db, shop_id=stream.shop_id)
    _validate_amount(settings, payload.amount)

    rate = check_live_offer_rate_limit(
        user_id,
        stream_id,
        max_count=settings.rate_limit_count,
        window_seconds=settings.rate_limit_window_seconds,
    )
    if not rate.allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=rate.reason or "Rate limit exceeded",
            headers={"Retry-After": str(rate.retry_after_seconds)},
        )

    if payload.idempotency_key:
        existing = (
            db.query(models_live_offer.LiveOffer)
            .filter(
                models_live_offer.LiveOffer.stream_id == stream_id,
                models_live_offer.LiveOffer.user_id == user_id,
                models_live_offer.LiveOffer.idempotency_key == payload.idempotency_key,
            )
            .first()
        )
        if existing is not None:
            return existing

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

    _assert_offers_enabled(db, stream, product)
    _assert_no_auction_conflict(db, product.id)

    now = _utcnow()
    offer = models_live_offer.LiveOffer(
        stream_id=stream_id,
        live_product_id=product.id,
        user_id=user_id,
        amount=payload.amount,
        status="pending",
        idempotency_key=payload.idempotency_key,
        display_expires_at=now + timedelta(seconds=settings.display_ttl_seconds),
    )
    db.add(offer)
    db.flush()
    _audit_log(
        db,
        stream_id=stream_id,
        offer_id=offer.id,
        action="offer.created",
        before_status=None,
        after_status="pending",
        detail={"amount": payload.amount},
    )
    db.commit()
    db.refresh(offer)
    _emit_offer(db, offer, "offer.created")
    return offer


def cancel_offer(db: Session, offer: models_live_offer.LiveOffer, *, user_id: int) -> models_live_offer.LiveOffer:
    if offer.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your offer")
    if offer.status not in ("pending", "held"):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Offer cannot be cancelled")
    return _transition_offer(db, offer, "cancelled", action="offer.cancelled")


def _create_purchase_right(
    db: Session,
    offer: models_live_offer.LiveOffer,
    settings: models_live_offer.LiveOfferSettings,
) -> models_live_offer.LiveOfferPurchaseRight:
    product = (
        db.query(models_live.LiveProduct)
        .filter(models_live.LiveProduct.id == offer.live_product_id)
        .first()
    )
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Live product not found")
    now = _utcnow()
    expires_at = now + timedelta(seconds=settings.purchase_window_seconds)
    offer.purchase_expires_at = expires_at
    right = models_live_offer.LiveOfferPurchaseRight(
        offer_id=offer.id,
        user_id=offer.user_id,
        live_product_id=product.id,
        card_id=product.card_id,
        accepted_price=offer.amount,
        status="active",
        expires_at=expires_at,
    )
    db.add(right)
    return right


def _transition_offer(
    db: Session,
    offer: models_live_offer.LiveOffer,
    target_status: str,
    *,
    action: str,
    admin_user_id: Optional[int] = None,
    review_note: Optional[str] = None,
) -> models_live_offer.LiveOffer:
    before = offer.status
    allowed = ALLOWED_TRANSITIONS.get(before, set())
    if target_status not in allowed:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot transition offer from {before} to {target_status}",
        )
    offer.status = target_status
    offer.updated_at = _utcnow()
    if admin_user_id is not None:
        offer.reviewed_by_admin_id = admin_user_id
        offer.reviewed_at = _utcnow()
    if review_note is not None:
        offer.review_note = review_note
    if target_status == "accepted":
        settings = _shop_settings(db)
        _create_purchase_right(db, offer, settings)
    _audit_log(
        db,
        stream_id=offer.stream_id,
        offer_id=offer.id,
        action=action,
        before_status=before,
        after_status=target_status,
        admin_user_id=admin_user_id,
        detail={"review_note": review_note} if review_note else None,
    )
    db.commit()
    db.refresh(offer)
    _emit_offer(db, offer, action)
    try:
        from services.notification_events import notify_live_offer_reviewed

        notify_live_offer_reviewed(db, offer, status=target_status)
        db.commit()
    except Exception:
        pass
    return offer


def review_offer(
    db: Session,
    offer: models_live_offer.LiveOffer,
    *,
    action: str,
    admin_user_id: int,
    review_note: Optional[str] = None,
) -> models_live_offer.LiveOffer:
    if action not in ADMIN_ACTIONS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid review action")
    target = ADMIN_ACTIONS[action]
    if action == "accept":
        event = "offer.accepted"
    elif action == "reject":
        event = "offer.rejected"
    else:
        event = "offer.held"
    return _transition_offer(
        db,
        offer,
        target,
        action=event,
        admin_user_id=admin_user_id,
        review_note=review_note,
    )


def get_stream_offers_settings(
    db: Session, stream_id: int
) -> schemas_live_offer.LiveOfferSettingsOut:
    stream = get_stream_or_404(db, stream_id)
    settings = _shop_settings(db, shop_id=stream.shop_id)
    return schemas_live_offer.LiveOfferSettingsOut(
        shop_id=settings.shop_id,
        purchase_window_seconds=settings.purchase_window_seconds,
        display_ttl_seconds=settings.display_ttl_seconds,
        max_amount=settings.max_amount,
        rate_limit_count=settings.rate_limit_count,
        rate_limit_window_seconds=settings.rate_limit_window_seconds,
        offers_enabled=bool(getattr(stream, "offers_enabled", True)),
    )


def patch_stream_offers_settings(
    db: Session,
    stream_id: int,
    payload: schemas_live_offer.LiveOfferSettingsPatchIn,
) -> schemas_live_offer.LiveOfferSettingsOut:
    stream = get_stream_or_404(db, stream_id)
    settings = _shop_settings(db, shop_id=stream.shop_id)
    data = payload.model_dump(exclude_unset=True)
    if "offers_enabled" in data:
        stream.offers_enabled = data.pop("offers_enabled")
    for key, value in data.items():
        setattr(settings, key, value)
    settings.updated_at = _utcnow()
    db.commit()
    db.refresh(stream)
    db.refresh(settings)
    return get_stream_offers_settings(db, stream_id)


def patch_product_offers_enabled(
    db: Session,
    stream_id: int,
    product_id: int,
    *,
    offers_enabled: bool,
) -> models_live.LiveProduct:
    product = (
        db.query(models_live.LiveProduct)
        .filter(
            models_live.LiveProduct.id == product_id,
            models_live.LiveProduct.stream_id == stream_id,
        )
        .first()
    )
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Live product not found")
    product.offers_enabled = offers_enabled
    db.commit()
    db.refresh(product)
    return product
