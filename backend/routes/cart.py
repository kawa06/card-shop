from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from database import get_db
from auth import get_current_user
import models
import schemas

router = APIRouter(prefix="/cart", tags=["cart"])


@router.get("", response_model=list[schemas.CartItemOut])
def get_cart(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return (
        db.query(models.CartItem)
        .filter(models.CartItem.user_id == current_user.id)
        .all()
    )


@router.post("", response_model=schemas.CartItemOut, status_code=status.HTTP_201_CREATED)
def add_to_cart(
    payload: schemas.CartItemCreate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    card = db.query(models.Card).filter(
        models.Card.id == payload.card_id,
        models.Card.is_active == True,
    ).first()
    if not card:
        raise HTTPException(status_code=404, detail="カードが見つかりません")
    if card.stock < payload.quantity:
        raise HTTPException(status_code=400, detail="在庫が不足しています")

    existing = db.query(models.CartItem).filter(
        models.CartItem.user_id == current_user.id,
        models.CartItem.card_id == payload.card_id,
    ).first()

    if existing:
        new_qty = existing.quantity + payload.quantity
        if card.stock < new_qty:
            raise HTTPException(status_code=400, detail="在庫が不足しています")
        existing.quantity = new_qty
        db.commit()
        db.refresh(existing)
        return existing

    item = models.CartItem(
        user_id=current_user.id,
        card_id=payload.card_id,
        quantity=payload.quantity,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.put("/{item_id}", response_model=schemas.CartItemOut)
def update_cart_item(
    item_id: int,
    payload: schemas.CartItemUpdate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    item = db.query(models.CartItem).filter(
        models.CartItem.id == item_id,
        models.CartItem.user_id == current_user.id,
    ).first()
    if not item:
        raise HTTPException(status_code=404, detail="カートアイテムが見つかりません")

    if item.card.stock < payload.quantity:
        raise HTTPException(status_code=400, detail="在庫が不足しています")

    item.quantity = payload.quantity
    db.commit()
    db.refresh(item)
    return item


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_from_cart(
    item_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    item = db.query(models.CartItem).filter(
        models.CartItem.id == item_id,
        models.CartItem.user_id == current_user.id,
    ).first()
    if not item:
        raise HTTPException(status_code=404, detail="カートアイテムが見つかりません")
    db.delete(item)
    db.commit()
