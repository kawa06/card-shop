from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from database import get_db
from auth import get_current_user
import models
import schemas
from services.order_checkout import (
    create_order_from_cart,
    get_user_cart_items,
    resolve_shipping_fee,
    validate_shipping_method,
)

router = APIRouter(prefix="/api/orders", tags=["orders"])


@router.post("", response_model=schemas.OrderOut, status_code=status.HTTP_201_CREATED)
def create_order(
    payload: schemas.OrderCreate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if payload.payment_method in ("credit_card", "konbini"):
        raise HTTPException(
            status_code=400,
            detail="カード決済・コンビニ決済はStripe Checkoutをご利用ください。",
        )

    cart_items = get_user_cart_items(db, current_user.id)
    validate_shipping_method(cart_items, payload.shipping_method)
    shipping_fee = resolve_shipping_fee(payload.shipping_method, payload.region, payload.country, db)

    return create_order_from_cart(
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
        payment_method=payload.payment_method,
        payment_status="pending",
        finalize=True,
    )


@router.get("", response_model=list[schemas.OrderOut])
def list_orders(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return (
        db.query(models.Order)
        .filter(models.Order.user_id == current_user.id)
        .order_by(models.Order.created_at.desc())
        .all()
    )


@router.get("/{order_id}", response_model=schemas.OrderOut)
def get_order(
    order_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    order = db.query(models.Order).filter(
        models.Order.id == order_id,
        models.Order.user_id == current_user.id,
    ).first()
    if not order:
        raise HTTPException(status_code=404, detail="注文が見つかりません")
    return order
