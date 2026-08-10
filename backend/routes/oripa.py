"""Phase 3-9/3-10 public / customer Oripa API (content-secret)."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

import models
import models_oripa
import schemas_oripa_public
from auth import get_current_user
from config import settings
from database import get_db
from services.oripa_admin import OripaError, raise_http
from services.oripa_assignment import list_purchase_entry_numbers
from services.oripa_constants import (
    ENTRY_ASSIGNMENT_ASSIGNED,
    ENTRY_ASSIGNMENT_AVAILABLE,
    ORIPA_PURCHASE_COMPLETED,
    ORIPA_PURCHASE_PENDING,
    ORIPA_STATUS_ON_SALE,
    format_entry_number,
)
from services.oripa_payment import (
    build_oripa_stripe_line_items,
    reserve_oripa_entries_for_payment,
)
from services.order_checkout import fulfill_order_inventory
from services.stripe_service import (
    adjust_line_items_to_total,
    create_checkout_session,
    stripe_key_valid,
)

router = APIRouter(prefix="/api", tags=["oripa"])

FORBIDDEN_CUSTOMER_FIELDS = {
    "linked_product_id",
    "linked_product_name",
    "linked_inventory_id",
    "prize_tier",
    "rarity",
    "cost",
    "market_price",
    "win",
    "lose",
    "当たり",
    "ハズレ",
}


def _remaining(db: Session, oripa_id: int) -> int:
    return int(
        db.query(func.count(models_oripa.OripaEntry.id))
        .filter(
            models_oripa.OripaEntry.oripa_id == oripa_id,
            models_oripa.OripaEntry.assignment_status == ENTRY_ASSIGNMENT_AVAILABLE,
        )
        .scalar()
        or 0
    )


def _public_oripa(db: Session, row: models_oripa.Oripa) -> schemas_oripa_public.OripaPublicOut:
    return schemas_oripa_public.OripaPublicOut(
        id=row.id,
        title=row.title,
        description=row.description,
        price_per_entry=float(row.price_per_entry),
        total_entries=int(row.total_entries),
        remaining_entries=_remaining(db, row.id),
        status=row.status,
        sale_start_at=row.sale_start_at,
        sale_end_at=row.sale_end_at,
        max_entries_per_purchase=int(row.max_entries_per_purchase),
    )


@router.get("/oripas", response_model=schemas_oripa_public.OripaPublicListOut)
def list_public_oripas(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    query = db.query(models_oripa.Oripa).filter(models_oripa.Oripa.status == ORIPA_STATUS_ON_SALE)
    total = query.count()
    rows = query.order_by(models_oripa.Oripa.id.desc()).offset(offset).limit(limit).all()
    return schemas_oripa_public.OripaPublicListOut(
        total=total,
        items=[_public_oripa(db, r) for r in rows],
    )


@router.get("/oripas/{oripa_id}", response_model=schemas_oripa_public.OripaPublicOut)
def get_public_oripa(oripa_id: int, db: Session = Depends(get_db)):
    row = db.query(models_oripa.Oripa).filter(models_oripa.Oripa.id == oripa_id).first()
    if row is None or row.status in {"draft", "scheduled"}:
        raise HTTPException(status_code=404, detail="オリパが見つかりません")
    return _public_oripa(db, row)


@router.post("/oripas/{oripa_id}/purchase", response_model=schemas_oripa_public.OripaPurchaseResultOut)
def purchase_oripa(
    oripa_id: int,
    payload: schemas_oripa_public.OripaPurchaseIn,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    """Reserve oripa slots and start Stripe Checkout (numbers revealed only after paid)."""
    try:
        purchase = reserve_oripa_entries_for_payment(
            db,
            oripa_id=oripa_id,
            user_id=user.id,
            quantity=payload.quantity,
            idempotency_key=payload.idempotency_key,
        )
        order = db.query(models.Order).filter(models.Order.id == purchase.order_id).first()
        if order is None:
            raise OripaError("注文の作成に失敗しました", status_code=500)

        # Idempotent resume: already completed
        if purchase.status == ORIPA_PURCHASE_COMPLETED:
            db.commit()
            nums = list_purchase_entry_numbers(db, purchase.id)
            return schemas_oripa_public.OripaPurchaseResultOut(
                purchase_id=purchase.id,
                oripa_id=oripa_id,
                quantity=purchase.quantity,
                entry_labels=[format_entry_number(n) for n in nums],
                status=purchase.status,
                order_id=order.id,
                payment_status=order.payment_status,
            )

        # Apply coupon / points like normal checkout (optional)
        from services.coupon_orders import apply_coupon_on_order_created
        from services.point_orders import apply_points_on_order_created

        coupon_code = (payload.coupon_code or "").strip() or None
        if coupon_code and int(order.discount_amount or 0) == 0:
            apply_coupon_on_order_created(db, order, coupon_code=coupon_code)
            db.flush()
            db.refresh(order)

        points_requested = int(payload.points_to_use or 0)
        if points_requested > 0 and int(order.points_used or 0) == 0:
            apply_points_on_order_created(db, order, points_to_use=points_requested)
            db.flush()
            db.refresh(order)
            # Keep purchase.total_amount in sync for audits
            purchase.total_amount = float(order.total_amount)

        oripa = db.query(models_oripa.Oripa).filter(models_oripa.Oripa.id == oripa_id).first()
        assert oripa is not None

        # Zero-yen (points/coupon fully covered): fulfill without Stripe
        if int(round(order.total_amount or 0)) <= 0:
            fulfilled = fulfill_order_inventory(db, order.id)
            db.refresh(purchase)
            nums = list_purchase_entry_numbers(db, purchase.id)
            success_url = f"{settings.FRONTEND_URL.rstrip('/')}/checkout/success?session_id=points-only-{fulfilled.id}"
            return schemas_oripa_public.OripaPurchaseResultOut(
                purchase_id=purchase.id,
                oripa_id=oripa_id,
                quantity=purchase.quantity,
                entry_labels=[format_entry_number(n) for n in nums],
                status=ORIPA_PURCHASE_COMPLETED,
                order_id=fulfilled.id,
                checkout_url=success_url,
                session_id=f"points-only-{fulfilled.id}",
                payment_status=fulfilled.payment_status,
            )

        if not stripe_key_valid():
            # Local/dev only: allow end-to-end without Stripe keys.
            # Production has DEBUG=false and must use real Checkout.
            if bool(getattr(settings, "DEBUG", False)):
                fulfilled = fulfill_order_inventory(db, order.id)
                db.refresh(purchase)
                nums = list_purchase_entry_numbers(db, purchase.id)
                return schemas_oripa_public.OripaPurchaseResultOut(
                    purchase_id=purchase.id,
                    oripa_id=oripa_id,
                    quantity=purchase.quantity,
                    entry_labels=[format_entry_number(n) for n in nums],
                    status=ORIPA_PURCHASE_COMPLETED,
                    order_id=fulfilled.id,
                    payment_status=fulfilled.payment_status,
                )
            from services.order_checkout import cancel_unpaid_order

            cancel_unpaid_order(db, order)
            raise HTTPException(
                status_code=503,
                detail="Stripe APIキーが無効です。管理者にお問い合わせください。",
            )

        # Resume existing session URL if present
        if purchase.stripe_checkout_session_id and order.stripe_checkout_session_id:
            from services.stripe_service import retrieve_checkout_session

            try:
                session = retrieve_checkout_session(order.stripe_checkout_session_id)
                if getattr(session, "url", None) and getattr(session, "status", None) != "expired":
                    db.commit()
                    return schemas_oripa_public.OripaPurchaseResultOut(
                        purchase_id=purchase.id,
                        oripa_id=oripa_id,
                        quantity=purchase.quantity,
                        entry_labels=[],
                        status=ORIPA_PURCHASE_PENDING,
                        order_id=order.id,
                        checkout_url=session.url,
                        session_id=session.id,
                        payment_status=order.payment_status,
                    )
            except Exception:
                pass

        line_items = build_oripa_stripe_line_items(purchase, oripa)
        if int(order.points_used or 0) > 0 or int(order.discount_amount or 0) > 0:
            line_items = adjust_line_items_to_total(line_items, int(round(order.total_amount)))

        try:
            session = create_checkout_session(
                order_id=order.id,
                customer_email=user.email,
                line_items=line_items,
                locale="ja",
                checkout_type="card",
                extra_metadata={
                    "oripa_id": str(oripa_id),
                    "oripa_purchase_id": str(purchase.id),
                    "checkout_kind": "oripa",
                },
            )
        except Exception:
            from services.order_checkout import cancel_unpaid_order

            cancel_unpaid_order(db, order)
            raise

        order.stripe_checkout_session_id = session.id
        purchase.stripe_checkout_session_id = session.id
        db.commit()

        if not session.url:
            from services.order_checkout import cancel_unpaid_order

            cancel_unpaid_order(db, order)
            raise HTTPException(status_code=502, detail="Stripe Checkout URLの生成に失敗しました")

        return schemas_oripa_public.OripaPurchaseResultOut(
            purchase_id=purchase.id,
            oripa_id=oripa_id,
            quantity=purchase.quantity,
            entry_labels=[],  # secrecy until paid
            status=ORIPA_PURCHASE_PENDING,
            order_id=order.id,
            checkout_url=session.url,
            session_id=session.id,
            payment_status=order.payment_status,
        )
    except OripaError as exc:
        db.rollback()
        raise_http(exc)


@router.get("/me/oripa-purchases/{purchase_id}", response_model=schemas_oripa_public.OripaPurchaseResultOut)
def get_my_oripa_purchase(
    purchase_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    """Poll purchase status after redirect (numbers only when completed)."""
    purchase = (
        db.query(models_oripa.OripaPurchase)
        .filter(
            models_oripa.OripaPurchase.id == purchase_id,
            models_oripa.OripaPurchase.user_id == user.id,
        )
        .first()
    )
    if purchase is None:
        raise HTTPException(status_code=404, detail="購入が見つかりません")
    order = None
    if purchase.order_id:
        order = db.query(models.Order).filter(models.Order.id == purchase.order_id).first()
    labels: list[str] = []
    if purchase.status == ORIPA_PURCHASE_COMPLETED:
        labels = [format_entry_number(n) for n in list_purchase_entry_numbers(db, purchase.id)]
    return schemas_oripa_public.OripaPurchaseResultOut(
        purchase_id=purchase.id,
        oripa_id=purchase.oripa_id,
        quantity=purchase.quantity,
        entry_labels=labels,
        status=purchase.status,
        order_id=purchase.order_id,
        session_id=purchase.stripe_checkout_session_id,
        payment_status=order.payment_status if order else None,
    )


@router.get("/me/oripa-entries", response_model=schemas_oripa_public.OripaHeldListOut)
def my_oripa_entries(
    shipment_status: Optional[str] = Query("held"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    query = db.query(models_oripa.OripaEntry).filter(
        models_oripa.OripaEntry.assigned_user_id == user.id,
        models_oripa.OripaEntry.assignment_status == ENTRY_ASSIGNMENT_ASSIGNED,
    )
    if shipment_status:
        query = query.filter(models_oripa.OripaEntry.shipment_status == shipment_status)
    total = query.count()
    rows = (
        query.order_by(models_oripa.OripaEntry.assigned_at.desc(), models_oripa.OripaEntry.id.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    items: list[schemas_oripa_public.OripaEntryPublicOut] = []
    for row in rows:
        oripa = db.query(models_oripa.Oripa).filter(models_oripa.Oripa.id == row.oripa_id).first()
        items.append(
            schemas_oripa_public.OripaEntryPublicOut(
                id=row.id,
                oripa_id=row.oripa_id,
                oripa_title=oripa.title if oripa else None,
                entry_label=format_entry_number(row.entry_number),
                assignment_status=row.assignment_status,
                shipment_status=row.shipment_status,
                assigned_at=row.assigned_at,
                purchase_id=row.assigned_purchase_id,
            )
        )
    return schemas_oripa_public.OripaHeldListOut(total=total, items=items)
