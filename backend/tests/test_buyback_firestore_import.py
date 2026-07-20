"""Firestore buylist import tests (Phase 8)."""

from __future__ import annotations

import models_buyback
from services.buyback_firestore_import import import_firestore_buylist_export, validate_import_counts


def test_import_firestore_export_creates_products_and_prices(db):
    payload = {
        "items": [
            {
                "id": 101,
                "name": "テストカード",
                "category": "raw",
                "isPublished": True,
                "conditionPrices": [
                    {"conditionCode": "A", "conditionName": "極美品", "price": 1200, "isVisible": True},
                    {"conditionCode": "B", "conditionName": "美品", "price": 800, "isVisible": True},
                ],
            },
            {
                "id": 102,
                "name": "レガシー価格商品",
                "category": "box",
                "price": 5000,
            },
        ],
        "images": {"101": "data:image/png;base64,abc"},
    }

    result = import_firestore_buylist_export(db, payload)
    assert result.created == 2
    assert result.price_rows_upserted == 3
    assert not result.errors

    products = db.query(models_buyback.BuybackProduct).order_by(models_buyback.BuybackProduct.id).all()
    assert len(products) == 2
    assert products[0].firestore_item_id == "101"
    assert products[0].image_url == "data:image/png;base64,abc"

    prices = (
        db.query(models_buyback.BuybackProductPrice)
        .filter(models_buyback.BuybackProductPrice.product_id == products[0].id)
        .all()
    )
    assert len(prices) == 2

    stats = validate_import_counts(db, payload)
    assert stats["export_count"] == 2
    assert stats["db_count"] == 2
    assert stats["missing_in_db"] == 0


def test_import_is_idempotent(db):
    payload = {
        "items": [
            {
                "id": 201,
                "name": "初回",
                "category": "raw",
                "price": 100,
            }
        ],
        "images": {},
    }
    first = import_firestore_buylist_export(db, payload)
    assert first.created == 1

    payload["items"][0]["name"] = "更新後"
    payload["items"][0]["price"] = 200
    second = import_firestore_buylist_export(db, payload)
    assert second.updated == 1
    assert second.created == 0

    product = (
        db.query(models_buyback.BuybackProduct)
        .filter(models_buyback.BuybackProduct.firestore_item_id == "201")
        .one()
    )
    assert product.name == "更新後"
    price = (
        db.query(models_buyback.BuybackProductPrice)
        .filter(models_buyback.BuybackProductPrice.product_id == product.id)
        .one()
    )
    assert price.price_normal == 200
