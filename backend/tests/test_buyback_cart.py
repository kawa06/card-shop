"""Buyback cart service tests."""

from __future__ import annotations

from auth import hash_password
import models
from services.buyback_cart import (
    add_cart_item,
    clear_cart,
    get_or_create_cart,
    remove_cart_item,
    update_cart_item_quantity,
)


def _create_user(db, email: str = "buyer@example.com") -> models.User:
    user = models.User(
        email=email,
        name="Buyer",
        password_hash=hash_password("secret123"),
        is_verified=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def test_add_and_get_buyback_cart(db):
    user = _create_user(db)
    item = add_cart_item(
        db,
        user_id=user.id,
        firestore_item_id="fs_item_001",
        product_name="テストカード",
        category="raw",
        condition_code="A",
        unit_price=1000,
        quantity=2,
    )
    assert item.quantity == 2
    cart = get_or_create_cart(db, user.id)
    db.refresh(cart)
    assert len(cart.items) == 1
    assert cart.items[0].unit_price_snapshot * cart.items[0].quantity == 2000


def test_merge_same_cart_line(db):
    user = _create_user(db, email="merge@example.com")
    payload = dict(
        user_id=user.id,
        firestore_item_id="fs_item_merge",
        product_name="マージテスト",
        category="box",
        condition_code="B",
        unit_price=500,
        quantity=1,
    )
    add_cart_item(db, **payload)
    add_cart_item(db, **payload)
    cart = get_or_create_cart(db, user.id)
    db.refresh(cart)
    assert len(cart.items) == 1
    assert cart.items[0].quantity == 2


def test_update_and_delete_cart_item(db):
    user = _create_user(db, email="edit@example.com")
    item = add_cart_item(
        db,
        user_id=user.id,
        firestore_item_id="fs_edit",
        product_name="編集テスト",
        category="psa",
        condition_code="A",
        unit_price=3000,
        quantity=1,
    )
    updated = update_cart_item_quantity(
        db, user_id=user.id, item_id=item.id, quantity=3
    )
    assert updated.quantity == 3
    remove_cart_item(db, user_id=user.id, item_id=item.id)
    cart = get_or_create_cart(db, user.id)
    db.refresh(cart)
    assert cart.items == [] or len(cart.items) == 0


def test_clear_cart(db):
    user = _create_user(db, email="clear@example.com")
    add_cart_item(
        db,
        user_id=user.id,
        firestore_item_id="fs_clear",
        product_name="クリアテスト",
        category="raw",
        condition_code="A",
        unit_price=100,
        quantity=1,
    )
    clear_cart(db, user_id=user.id)
    cart = get_or_create_cart(db, user.id)
    db.refresh(cart)
    assert not cart.items
