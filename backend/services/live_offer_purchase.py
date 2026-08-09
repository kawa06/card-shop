"""Live offer purchase-right and order creation (Phase 3-3)."""

from __future__ import annotations

from datetime import datetime

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

import models
import models_live_offer
import schemas_live_offer
from services.live_events import emit_live_event
from services.live_offers import serialize_offer
from services.order_number import assign_order_number


def _utcnow() -> datetime:
    return datetime.utcnow()


def get_purchase_right_or_404(
    db: Session, offer_id: int
) -> models_live_offer.LiveOfferPurchaseRight:
    right = (
        db.query(models_live_offer.LiveOfferPurchaseRight)
        .filter(models_live_offer.LiveOfferPurchaseRight.offer_id == offer_id)
        .first()
    )
    if right is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Purchase right not found")
    return right


def verify_purchase_right_owner(
    right: models_live_offer.LiveOfferPurchaseRight, user_id: int
) -> None:
    if right.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your purchase right")


def serialize_purchase_right(
    right: models_live_offer.LiveOfferPurchaseRight,
) -> schemas_live_offer.LiveOfferPurchaseRightOut:
    return schemas_live_offer.LiveOfferPurchaseRightOut.model_validate(right)


def create_order_from_offer(
    db: Session,
    *,
    offer_id: int,
    user_id: int,
    payload: schemas_live_offer.LiveOfferPurchaseIn,
) -> schemas_live_offer.LiveOfferPurchaseOut:
    offer = (
        db.query(models_live_offer.LiveOffer)
        .filter(models_live_offer.LiveOffer.id == offer_id)
        .with_for_update()
        .first()
    )
    if offer is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Offer not found")
    if offer.status != "accepted":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Offer is not accepted")

    right = (
        db.query(models_live_offer.LiveOfferPurchaseRight)
        .filter(models_live_offer.LiveOfferPurchaseRight.offer_id == offer_id)
        .with_for_update()
        .first()
    )
    if right is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Purchase right not found")
    verify_purchase_right_owner(right, user_id)

    if right.order_id is not None:
        db.refresh(right)
        return schemas_live_offer.LiveOfferPurchaseOut(
            order_id=right.order_id,
            purchase_right=serialize_purchase_right(right),
        )

    if right.status != "active":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Purchase right is not active")
    if right.expires_at <= _utcnow():
        right.status = "expired"
        db.commit()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Purchase right has expired")

    card = (
        db.query(models.Card)
        .filter(models.Card.id == right.card_id)
        .with_for_update()
        .first()
    )
    if card is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Card not found")
    if not card.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Card is not available")
    if card.stock < 1:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Insufficient stock")

    card.stock -= 1
    from services.inventory_alerts import evaluate_card_inventory

    evaluate_card_inventory(db, card.id, source="live_offer_purchase")
    unit_price = float(right.accepted_price)
    order = models.Order(
        user_id=user_id,
        total_amount=unit_price,
        items_subtotal=int(right.accepted_price),
        shipping_address=payload.shipping_address,
        shipping_method=payload.shipping_method or "click_post",
        shipping_fee=0,
        postal_code=payload.postal_code,
        country=payload.country,
        region=payload.region,
        city=payload.city,
        address_line1=payload.address_line1,
        address_line2=payload.address_line2,
        payment_method="live_offer",
        payment_status="pending",
        status=models.OrderStatus.pending,
        stock_reserved=True,
    )
    db.add(order)
    db.flush()
    db.add(
        models.OrderItem(
            order_id=order.id,
            card_id=card.id,
            quantity=1,
            unit_price=unit_price,
            product_name=card.name,
        )
    )
    assign_order_number(db, order)

    points_requested = int(payload.points_to_use or 0)
    if points_requested > 0:
        from services.point_orders import apply_points_on_order_created

        apply_points_on_order_created(db, order, points_to_use=points_requested)

    right.status = "used"
    right.order_id = order.id
    db.commit()
    db.refresh(order)
    db.refresh(right)

    if int(round(order.total_amount or 0)) <= 0:
        from services.order_checkout import fulfill_order_inventory

        fulfill_order_inventory(db, order.id)
        db.refresh(order)

    emit_live_event(
        offer.stream_id,
        "offer.purchase_completed",
        {
            "offer_id": offer.id,
            "order_id": order.id,
            "amount": right.accepted_price,
            "sender_name": serialize_offer(db, offer, public=True).sender_name,
        },
    )
    return schemas_live_offer.LiveOfferPurchaseOut(
        order_id=order.id,
        purchase_right=serialize_purchase_right(right),
    )


def expire_purchase_rights(db: Session) -> int:
    now = _utcnow()
    count = 0
    rights = (
        db.query(models_live_offer.LiveOfferPurchaseRight)
        .filter(
            models_live_offer.LiveOfferPurchaseRight.status == "active",
            models_live_offer.LiveOfferPurchaseRight.expires_at <= now,
        )
        .all()
    )
    for right in rights:
        right.status = "expired"
        offer = (
            db.query(models_live_offer.LiveOffer)
            .filter(models_live_offer.LiveOffer.id == right.offer_id)
            .first()
        )
        if offer and offer.status == "accepted":
            offer.status = "expired"
            offer.updated_at = now
        count += 1
    if count:
        db.commit()
    return count
