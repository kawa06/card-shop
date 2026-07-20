"""Buyback request submission and listing (Phase 5)."""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session, joinedload

import models
import models_buyback
from services.buyback_emails import notify_buyback_request_submitted
from services.buyback_request_number import assign_buyback_request_number

logger = logging.getLogger(__name__)


def _audit_request(
    db: Session,
    *,
    action: str,
    user_id: int,
    request_id: int,
    details: dict,
) -> None:
    try:
        db.add(
            models_buyback.BuybackAuditLog(
                actor_user_id=user_id,
                action=action,
                entity_type="buyback_request",
                entity_id=str(request_id),
                details_json=json.dumps(details, ensure_ascii=False),
            )
        )
    except Exception as exc:
        logger.warning("Failed to write buyback request audit log: %s", exc)


def _load_user_cart_with_products(
    db: Session, user_id: int
) -> models_buyback.BuybackCart | None:
    return (
        db.query(models_buyback.BuybackCart)
        .filter(models_buyback.BuybackCart.user_id == user_id)
        .options(
            joinedload(models_buyback.BuybackCart.items).joinedload(
                models_buyback.BuybackCartItem.product
            )
        )
        .first()
    )


def submit_request_from_cart(
    db: Session,
    *,
    user: models.User,
    customer_note: Optional[str] = None,
    shipping_method: Optional[str] = None,
    rejected_item_handling: Optional[str] = None,
    agreed_prepaid_shipping: bool = False,
    agreed_cod_consequence: bool = False,
    agreed_condition_rejection: bool = False,
) -> models_buyback.BuybackRequest:
    if not agreed_prepaid_shipping:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="送料元払いでの発送に同意してください",
        )
    if not agreed_cod_consequence:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="着払い発送時の返送・返送料自己負担について確認してください",
        )
    if not agreed_condition_rejection:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="状態による買取不可の可能性について確認してください",
        )
    allowed_handling = {
        models_buyback.RejectedItemHandling.return_rejected_only.value,
        models_buyback.RejectedItemHandling.dispose_rejected.value,
        models_buyback.RejectedItemHandling.return_all_if_any_rejected.value,
    }
    if not rejected_item_handling or rejected_item_handling not in allowed_handling:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="買取不可商品の対応方法を選択してください",
        )

    cart = _load_user_cart_with_products(db, user.id)
    if not cart or not cart.items:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="カートが空のため申込できません",
        )

    now = datetime.utcnow()
    estimated_total = sum(
        item.unit_price_snapshot * item.quantity for item in cart.items
    )

    request = models_buyback.BuybackRequest(
        user_id=user.id,
        status=models_buyback.BuybackRequestStatus.submitted.value,
        shipping_method=(shipping_method or "").strip() or None,
        customer_note=(customer_note or "").strip() or None,
        estimated_total=estimated_total,
        rejected_item_handling=rejected_item_handling,
        agreed_prepaid_shipping=agreed_prepaid_shipping,
        agreed_cod_consequence=agreed_cod_consequence,
        agreed_condition_rejection=agreed_condition_rejection,
        submitted_at=now,
    )
    db.add(request)
    db.flush()

    assign_buyback_request_number(db, request)

    for cart_item in cart.items:
        product = cart_item.product
        product_name = product.name if product else "（商品名不明）"
        db.add(
            models_buyback.BuybackRequestItem(
                request_id=request.id,
                product_id=cart_item.product_id,
                product_name_snapshot=product_name,
                condition_code=cart_item.condition_code,
                quantity=cart_item.quantity,
                listed_unit_price=cart_item.unit_price_snapshot,
                line_status=models_buyback.BuybackItemLineStatus.pending.value,
            )
        )

    db.add(
        models_buyback.BuybackStatusHistory(
            request_id=request.id,
            from_status=None,
            to_status=models_buyback.BuybackRequestStatus.submitted.value,
            changed_by_user_id=user.id,
            note="カートから申込",
        )
    )

    _audit_request(
        db,
        action="request_submitted",
        user_id=user.id,
        request_id=request.id,
        details={
            "request_number": request.request_number,
            "item_count": len(cart.items),
            "estimated_total": estimated_total,
        },
    )

    for cart_item in list(cart.items):
        db.delete(cart_item)
    cart.updated_at = now

    db.commit()

    request = (
        db.query(models_buyback.BuybackRequest)
        .filter(models_buyback.BuybackRequest.id == request.id)
        .options(joinedload(models_buyback.BuybackRequest.items))
        .first()
    )
    if request:
        notify_buyback_request_submitted(db, request, user)

    return request


def list_user_requests(
    db: Session, *, user_id: int, limit: int = 50
) -> list[models_buyback.BuybackRequest]:
    return (
        db.query(models_buyback.BuybackRequest)
        .filter(models_buyback.BuybackRequest.user_id == user_id)
        .options(joinedload(models_buyback.BuybackRequest.items))
        .order_by(models_buyback.BuybackRequest.created_at.desc())
        .limit(limit)
        .all()
    )


def get_user_request(
    db: Session, *, user_id: int, request_id: int
) -> models_buyback.BuybackRequest:
    request = (
        db.query(models_buyback.BuybackRequest)
        .filter(
            models_buyback.BuybackRequest.id == request_id,
            models_buyback.BuybackRequest.user_id == user_id,
        )
        .options(joinedload(models_buyback.BuybackRequest.items))
        .first()
    )
    if not request:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="買取申込が見つかりません",
        )
    return request
