"""Buyback cart helpers (Phase 4)."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

import models_buyback


MAX_CART_QUANTITY = 999


def get_or_create_cart(db: Session, user_id: int) -> models_buyback.BuybackCart:
    cart = (
        db.query(models_buyback.BuybackCart)
        .filter(models_buyback.BuybackCart.user_id == user_id)
        .first()
    )
    if cart:
        return cart
    cart = models_buyback.BuybackCart(user_id=user_id)
    db.add(cart)
    db.commit()
    db.refresh(cart)
    return cart


def ensure_product_from_firestore(
    db: Session,
    *,
    firestore_item_id: str,
    name: str,
    category: str,
    condition_code: str,
    unit_price: int,
    image_url: Optional[str] = None,
) -> models_buyback.BuybackProduct:
    firestore_item_id = firestore_item_id.strip()
    if not firestore_item_id:
        raise HTTPException(status_code=400, detail="商品IDが不正です")

    product = (
        db.query(models_buyback.BuybackProduct)
        .filter(models_buyback.BuybackProduct.firestore_item_id == firestore_item_id)
        .first()
    )
    if not product:
        product = models_buyback.BuybackProduct(
            firestore_item_id=firestore_item_id,
            name=name.strip() or firestore_item_id,
            category=category.strip() or "raw",
            image_url=image_url,
            is_active=True,
        )
        db.add(product)
        db.flush()
    else:
        if name.strip():
            product.name = name.strip()
        if category.strip():
            product.category = category.strip()
        if image_url:
            product.image_url = image_url
        product.updated_at = datetime.utcnow()

    price_row = (
        db.query(models_buyback.BuybackProductPrice)
        .filter(
            models_buyback.BuybackProductPrice.product_id == product.id,
            models_buyback.BuybackProductPrice.condition_code == condition_code,
        )
        .first()
    )
    if price_row:
        price_row.price_normal = unit_price
    else:
        db.add(
            models_buyback.BuybackProductPrice(
                product_id=product.id,
                condition_code=condition_code,
                price_normal=unit_price,
            )
        )

    db.flush()
    return product


def add_cart_item(
    db: Session,
    *,
    user_id: int,
    firestore_item_id: str,
    product_name: str,
    category: str,
    condition_code: str,
    unit_price: int,
    quantity: int,
    image_url: Optional[str] = None,
) -> models_buyback.BuybackCartItem:
    if quantity < 1 or quantity > MAX_CART_QUANTITY:
        raise HTTPException(status_code=400, detail=f"数量は1〜{MAX_CART_QUANTITY}で指定してください")
    if unit_price < 0:
        raise HTTPException(status_code=400, detail="価格が不正です")

    product = ensure_product_from_firestore(
        db,
        firestore_item_id=firestore_item_id,
        name=product_name,
        category=category,
        condition_code=condition_code,
        unit_price=unit_price,
        image_url=image_url,
    )
    cart = get_or_create_cart(db, user_id)

    existing = (
        db.query(models_buyback.BuybackCartItem)
        .filter(
            models_buyback.BuybackCartItem.cart_id == cart.id,
            models_buyback.BuybackCartItem.product_id == product.id,
            models_buyback.BuybackCartItem.condition_code == condition_code,
        )
        .first()
    )
    if existing:
        new_qty = existing.quantity + quantity
        if new_qty > MAX_CART_QUANTITY:
            raise HTTPException(status_code=400, detail=f"数量は最大{MAX_CART_QUANTITY}枚までです")
        existing.quantity = new_qty
        existing.unit_price_snapshot = unit_price
        cart.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(existing)
        return existing

    item = models_buyback.BuybackCartItem(
        cart_id=cart.id,
        product_id=product.id,
        condition_code=condition_code,
        quantity=quantity,
        unit_price_snapshot=unit_price,
    )
    db.add(item)
    cart.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(item)
    return item


def update_cart_item_quantity(
    db: Session,
    *,
    user_id: int,
    item_id: int,
    quantity: int,
) -> models_buyback.BuybackCartItem:
    if quantity < 1 or quantity > MAX_CART_QUANTITY:
        raise HTTPException(status_code=400, detail=f"数量は1〜{MAX_CART_QUANTITY}で指定してください")

    item = (
        db.query(models_buyback.BuybackCartItem)
        .join(models_buyback.BuybackCart)
        .filter(
            models_buyback.BuybackCartItem.id == item_id,
            models_buyback.BuybackCart.user_id == user_id,
        )
        .first()
    )
    if not item:
        raise HTTPException(status_code=404, detail="カート内の商品が見つかりません")

    item.quantity = quantity
    item.cart.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(item)
    return item


def remove_cart_item(db: Session, *, user_id: int, item_id: int) -> None:
    item = (
        db.query(models_buyback.BuybackCartItem)
        .join(models_buyback.BuybackCart)
        .filter(
            models_buyback.BuybackCartItem.id == item_id,
            models_buyback.BuybackCart.user_id == user_id,
        )
        .first()
    )
    if not item:
        raise HTTPException(status_code=404, detail="カート内の商品が見つかりません")
    cart = item.cart
    db.delete(item)
    cart.updated_at = datetime.utcnow()
    db.commit()


def clear_cart(db: Session, *, user_id: int) -> None:
    cart = (
        db.query(models_buyback.BuybackCart)
        .filter(models_buyback.BuybackCart.user_id == user_id)
        .first()
    )
    if not cart:
        return
    db.query(models_buyback.BuybackCartItem).filter(
        models_buyback.BuybackCartItem.cart_id == cart.id
    ).delete(synchronize_session=False)
    cart.updated_at = datetime.utcnow()
    db.commit()
