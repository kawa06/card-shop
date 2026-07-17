from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from database import get_db
from auth import get_current_user
import models
import schemas
from services.order_checkout import (
    cancel_unpaid_order,
    create_order_from_cart,
    fulfill_order_inventory,
    get_user_cart_items,
    resolve_shipping_fee,
    validate_shipping_method,
)
from services.stripe_service import (
    build_line_items,
    construct_webhook_event,
    create_checkout_session,
    retrieve_checkout_session,
    stripe_configured,
)

router = APIRouter(prefix="/api/payments", tags=["payments"])


@router.get("/stripe/config")
def stripe_public_config():
    return {
        "enabled": stripe_configured(),
        "publishable_key": None,
    }


@router.post("/stripe/create-checkout-session", response_model=schemas.StripeCheckoutSessionOut)
def create_stripe_checkout_session(
    payload: schemas.StripeCheckoutSessionCreate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    cart_items = get_user_cart_items(db, current_user.id)
    validate_shipping_method(cart_items, payload.shipping_method)
    shipping_fee = resolve_shipping_fee(payload.shipping_method, payload.region, payload.country, db)

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
        payment_method="stripe",
        payment_status="awaiting_payment",
        finalize=False,
    )

    shipping_label = payload.shipping_method or "送料"
    line_items = build_line_items(cart_items, shipping_fee, shipping_label)
    try:
        session = create_checkout_session(
            order_id=order.id,
            customer_email=current_user.email,
            line_items=line_items,
            locale=payload.locale or "ja",
        )
    except Exception:
        cancel_unpaid_order(db, order)
        raise

    order.stripe_checkout_session_id = session.id
    db.commit()

    if not session.url:
        cancel_unpaid_order(db, order)
        raise HTTPException(status_code=502, detail="Stripe Checkout URLの生成に失敗しました")

    return {"checkout_url": session.url, "session_id": session.id, "order_id": order.id}


@router.get("/stripe/confirm", response_model=schemas.OrderOut)
def confirm_stripe_checkout(
    session_id: str,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    session = retrieve_checkout_session(session_id)
    order_id = session.metadata.get("order_id") or session.client_reference_id
    if not order_id:
        raise HTTPException(status_code=400, detail="注文情報が見つかりません")

    order = db.query(models.Order).filter(
        models.Order.id == int(order_id),
        models.Order.user_id == current_user.id,
    ).first()
    if not order:
        raise HTTPException(status_code=404, detail="注文が見つかりません")

    if session.payment_status != "paid":
        raise HTTPException(status_code=400, detail="決済が完了していません")

    return fulfill_order_inventory(db, order.id)


@router.post("/stripe/webhook", status_code=status.HTTP_200_OK)
async def stripe_webhook(request: Request, db: Session = Depends(get_db)):
    payload = await request.body()
    event = construct_webhook_event(payload, request.headers.get("stripe-signature"))

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        if session.get("payment_status") != "paid":
            return {"received": True}

        order_id = session.get("metadata", {}).get("order_id") or session.get("client_reference_id")
        if order_id:
            fulfill_order_inventory(db, int(order_id))

    elif event["type"] == "checkout.session.expired":
        session = event["data"]["object"]
        order_id = session.get("metadata", {}).get("order_id") or session.get("client_reference_id")
        if order_id:
            order = db.query(models.Order).filter(models.Order.id == int(order_id)).first()
            if order and order.payment_status != "paid":
                cancel_unpaid_order(db, order)

    return {"received": True}
