from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from database import get_db
from auth import get_current_user
import models
import schemas

router = APIRouter(prefix="/api/orders", tags=["orders"])


@router.post("", response_model=schemas.OrderOut, status_code=status.HTTP_201_CREATED)
def create_order(
    payload: schemas.OrderCreate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    cart_items = (
        db.query(models.CartItem)
        .filter(models.CartItem.user_id == current_user.id)
        .all()
    )
    if not cart_items:
        raise HTTPException(status_code=400, detail="カートが空です")

    # Validate stock and calculate total
    total = 0.0
    for item in cart_items:
        card = item.card
        if not card.is_active:
            raise HTTPException(status_code=400, detail=f"カード「{card.name}」は現在販売されていません")
        if card.stock < item.quantity:
            raise HTTPException(status_code=400, detail=f"カード「{card.name}」の在庫が不足しています")
        total += card.price * item.quantity

    # Create order
    order = models.Order(
        user_id=current_user.id,
        total_amount=round(total, 2),
        postal_code=payload.postal_code,
        country=payload.country,
        region=payload.region,
        city=payload.city,
        address_line1=payload.address_line1,
        address_line2=payload.address_line2,
        shipping_address=payload.shipping_address,
        status=models.OrderStatus.pending,
    )
    db.add(order)
    db.flush()  # Get order.id

    # Create order items and decrease stock
    for item in cart_items:
        order_item = models.OrderItem(
            order_id=order.id,
            card_id=item.card_id,
            quantity=item.quantity,
            unit_price=item.card.price,
        )
        db.add(order_item)
        item.card.stock -= item.quantity

    # Clear cart
    for item in cart_items:
        db.delete(item)

    db.commit()
    db.refresh(order)
    return order


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
