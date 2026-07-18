import stripe
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from database import get_db
from auth import get_current_user
import models
import schemas
from services.order_checkout import (
    bank_transfer_payment_deadline,
    cancel_unpaid_order,
    clear_cart_for_order,
    create_order_from_cart,
    fulfill_order_inventory,
    get_user_cart_items,
    reserve_inventory_for_order,
    resolve_shipping_fee,
    validate_shipping_method,
)
from services.countries import is_domestic_japan
from services.stripe_service import (
    build_line_items,
    construct_webhook_event,
    create_checkout_session,
    retrieve_checkout_session,
    stripe_key_valid,
)

router = APIRouter(prefix="/api/payments", tags=["payments"])


def _session_value(session, key: str, default=None):
    if isinstance(session, dict):
        return session.get(key, default)
    return getattr(session, key, default)


def _metadata_value(session, key: str, default=None):
    metadata = _session_value(session, "metadata") or {}
    if isinstance(metadata, dict):
        return metadata.get(key, default)
    return getattr(metadata, key, default)


def _order_id_from_session(session) -> int | None:
    order_id = _metadata_value(session, "order_id") or _session_value(session, "client_reference_id")
    if not order_id:
        return None
    return int(order_id)


def _handle_bank_transfer_pending(db: Session, order: models.Order) -> models.Order:
    order.payment_method = "stripe_bank_transfer"
    order.payment_status = "awaiting_payment"
    if not order.stock_reserved:
        db.refresh(order)
        reserve_inventory_for_order(db, order)
        if not order.payment_deadline:
            order.payment_deadline = bank_transfer_payment_deadline()
        clear_cart_for_order(db, order)
    elif not order.payment_deadline:
        order.payment_deadline = bank_transfer_payment_deadline()
    db.commit()
    db.refresh(order)
    return order


@router.get("/stripe/config")
def stripe_public_config():
    valid = stripe_key_valid()
    return {
        "enabled": valid,
        "publishable_key": None,
        "bank_transfer_enabled": valid,
    }


@router.post("/stripe/create-checkout-session", response_model=schemas.StripeCheckoutSessionOut)
def create_stripe_checkout_session(
    payload: schemas.StripeCheckoutSessionCreate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    checkout_type = (payload.checkout_type or "card").lower()
    if checkout_type not in {"card", "bank_transfer"}:
        raise HTTPException(status_code=400, detail="不正な決済種別です")

    if checkout_type == "bank_transfer" and not is_domestic_japan(payload.country):
        raise HTTPException(status_code=400, detail="Stripe銀行振込は日本国内のみ利用できます")

    if not stripe_key_valid():
        raise HTTPException(
            status_code=503,
            detail="Stripe APIキーが無効です。Stripeダッシュボードで新しいSecret keyを発行し、RailwayのSTRIPE_SECRET_KEYを1行で設定してください。",
        )

    cart_items = get_user_cart_items(db, current_user.id)
    validate_shipping_method(cart_items, payload.shipping_method, payload.country)
    shipping_fee = resolve_shipping_fee(payload.shipping_method, payload.region, payload.country, db)

    payment_method = "stripe_bank_transfer" if checkout_type == "bank_transfer" else "stripe_card"

    is_bank_transfer = checkout_type == "bank_transfer"

    order = create_order_from_cart(
        db,
        user=current_user,
        cart_items=cart_items,
        postal_code=payload.postal_code,
        country=payload.country,
        region=payload.region,
        city=payload.city,
        address_line1=payload.address_line1,
        address_line2=payload.address_line2,
        shipping_address=payload.shipping_address,
        shipping_method=payload.shipping_method,
        shipping_fee=shipping_fee,
        payment_method=payment_method,
        payment_status="awaiting_payment",
        finalize=False,
        reserve_stock=is_bank_transfer,
        payment_deadline=bank_transfer_payment_deadline() if is_bank_transfer else None,
    )

    shipping_label = payload.shipping_method or "送料"
    line_items = build_line_items(cart_items, shipping_fee, shipping_label)
    try:
        session = create_checkout_session(
            order_id=order.id,
            customer_email=current_user.email,
            line_items=line_items,
            locale=payload.locale or "ja",
            checkout_type=checkout_type,
        )
    except stripe.error.AuthenticationError as exc:
        cancel_unpaid_order(db, order)
        raise HTTPException(
            status_code=503,
            detail="Stripe APIキーが無効です。Stripeダッシュボードで新しいSecret keyを発行し、RailwayのSTRIPE_SECRET_KEYを1行で設定してください。",
        ) from exc
    except stripe.error.StripeError as exc:
        cancel_unpaid_order(db, order)
        message = getattr(exc, "user_message", None) or str(exc)
        raise HTTPException(status_code=502, detail=f"Stripeエラー: {message}") from exc
    except Exception:
        cancel_unpaid_order(db, order)
        raise

    order.stripe_checkout_session_id = session.id
    db.commit()

    if not session.url:
        cancel_unpaid_order(db, order)
        raise HTTPException(status_code=502, detail="Stripe Checkout URLの生成に失敗しました")

    return {"checkout_url": session.url, "session_id": session.id, "order_id": order.id}


@router.get("/stripe/confirm", response_model=schemas.StripeCheckoutConfirmOut)
def confirm_stripe_checkout(
    session_id: str,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    session = retrieve_checkout_session(session_id)
    order_id = _order_id_from_session(session)
    if not order_id:
        raise HTTPException(status_code=400, detail="注文情報が見つかりません")

    order = db.query(models.Order).filter(
        models.Order.id == order_id,
        models.Order.user_id == current_user.id,
    ).first()
    if not order:
        raise HTTPException(status_code=404, detail="注文が見つかりません")

    if _session_value(session, "payment_status") == "paid":
        fulfilled = fulfill_order_inventory(db, order.id)
        return {
            "order": fulfilled,
            "payment_status": fulfilled.payment_status or "paid",
            "pending_bank_transfer": False,
        }

    checkout_type = _metadata_value(session, "checkout_type", "")
    if (
        checkout_type == "bank_transfer"
        and _session_value(session, "status") == "complete"
        and _session_value(session, "payment_status") == "unpaid"
    ):
        pending = _handle_bank_transfer_pending(db, order)
        return {
            "order": pending,
            "payment_status": pending.payment_status or "awaiting_payment",
            "pending_bank_transfer": True,
        }

    raise HTTPException(status_code=400, detail="決済が完了していません")


@router.post("/stripe/webhook", status_code=status.HTTP_200_OK)
async def stripe_webhook(request: Request, db: Session = Depends(get_db)):
    payload = await request.body()
    event = construct_webhook_event(payload, request.headers.get("stripe-signature"))
    event_type = event["type"]
    session = event["data"]["object"]

    if event_type == "checkout.session.completed":
        order_id = _order_id_from_session(session)
        if not order_id:
            return {"received": True}

        if _session_value(session, "payment_status") == "paid":
            fulfill_order_inventory(db, order_id)
        elif _session_value(session, "payment_status") == "unpaid":
            checkout_type = _metadata_value(session, "checkout_type")
            if checkout_type == "bank_transfer":
                order = db.query(models.Order).filter(models.Order.id == order_id).first()
                if order and order.payment_status != "paid":
                    _handle_bank_transfer_pending(db, order)

    elif event_type == "checkout.session.async_payment_succeeded":
        order_id = _order_id_from_session(session)
        if order_id:
            fulfill_order_inventory(db, order_id)

    elif event_type in {"checkout.session.async_payment_failed", "checkout.session.expired"}:
        order_id = _order_id_from_session(session)
        if order_id:
            order = db.query(models.Order).filter(models.Order.id == order_id).first()
            if order and order.payment_status != "paid":
                cancel_unpaid_order(db, order)

    return {"received": True}
