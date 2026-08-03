"""Buyback request submission and listing (Phase 5)."""

from __future__ import annotations

import json
import logging
from datetime import date, datetime
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session, joinedload

import models
import models_buyback
from services.buyback_emails import notify_buyback_request_submitted
from services.buyback_inbound import provision_request_logistics
from services.buyback_request_number import assign_buyback_request_number
from services.buyback_channel import (
    create_store_reservation,
    validate_buyback_method,
    validate_store_visit_at,
)
from services.buyback_public_ids import assign_public_buyback_code, assign_public_member_id

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
    except Exception:
        logger.warning("Failed to write buyback request audit log")


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
    customer_planned_ship_date: Optional[date] = None,
    rejected_item_handling: Optional[str] = None,
    agreed_prepaid_shipping: bool = False,
    agreed_cod_consequence: bool = False,
    agreed_condition_rejection: bool = False,
    buyback_method: Optional[str] = None,
    store_visit_at: Optional[datetime] = None,
) -> models_buyback.BuybackRequest:
    method = validate_buyback_method(db, buyback_method)
    if method == "mail":
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
    else:
        if not agreed_condition_rejection:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="状態による買取不可の可能性について確認してください",
            )
        if not store_visit_at:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="来店日時を選択してください",
            )
        store_visit_at = validate_store_visit_at(db, store_visit_at)
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
    declared_item_count = sum(item.quantity for item in cart.items)

    planned_ship_date = customer_planned_ship_date

    initial_status = (
        models_buyback.BuybackRequestStatus.awaiting_visit.value
        if method == "store"
        else models_buyback.BuybackRequestStatus.awaiting_shipment.value
    )

    request = models_buyback.BuybackRequest(
        user_id=user.id,
        status=initial_status,
        buyback_method=method,
        store_visit_at=store_visit_at if method == "store" else None,
        shipping_method=(shipping_method or "").strip() or None if method == "mail" else None,
        customer_note=(customer_note or "").strip() or None,
        customer_planned_ship_date=planned_ship_date if method == "mail" else None,
        estimated_total=estimated_total,
        rejected_item_handling=rejected_item_handling,
        agreed_prepaid_shipping=agreed_prepaid_shipping if method == "mail" else False,
        agreed_cod_consequence=agreed_cod_consequence if method == "mail" else False,
        agreed_condition_rejection=agreed_condition_rejection,
        submitted_at=now,
    )
    db.add(request)
    db.flush()

    assign_buyback_request_number(db, request)
    inbound = None
    barcode = None
    reservation = None
    if method == "mail":
        inbound, barcode = provision_request_logistics(
            db,
            request=request,
            user=user,
            declared_item_count=declared_item_count,
        )
    else:
        assign_public_buyback_code(db, request)
        assign_public_member_id(db, user)
        reservation = create_store_reservation(
            db,
            request_id=request.id,
            user_id=user.id,
            visit_at=store_visit_at,
        )

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
            to_status=initial_status,
            changed_by_user_id=user.id,
            note="カートから申込",
        )
    )

    audit_details = {
            "request_number": request.request_number,
            "public_buyback_code": request.public_buyback_code,
            "buyback_method": method,
            "item_count": len(cart.items),
            "estimated_total": estimated_total,
        }
    if method == "mail" and inbound and barcode:
        audit_details.update(
            {
                "inbound_mgmt_id": request.inbound_mgmt_id,
                "inbound_shipment_id": inbound.id,
                "application_barcode_id": barcode.id,
            }
        )
    if method == "store" and reservation:
        audit_details["store_visit_at"] = reservation.visit_at.isoformat()
        audit_details["reservation_id"] = reservation.id

    _audit_request(
        db,
        action="request_submitted",
        user_id=user.id,
        request_id=request.id,
        details=audit_details,
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
            detail="買取申請が見つかりません",
        )
    return request
