"""Admin buyback catalog CRUD tests."""

from __future__ import annotations

import pytest

import models_buyback
from conftest import auth_headers, create_admin_user


def _catalog_payload(**overrides):
    payload = {
        "name": "ピカチュウ",
        "category": "raw",
        "card_number": "025/165",
        "rarity": "RR",
        "pack_name": "151",
        "image_url": "https://cdn.example.test/pika.jpg",
        "notes": "テスト",
        "is_active": True,
        "sort_order": 10,
        "prices": [
            {
                "condition_code": "default",
                "price_normal": 1000,
                "price_high": 1200,
                "purchase_limit": 3,
                "tier_overflow_price": 800,
            }
        ],
    }
    payload.update(overrides)
    return payload


def test_create_catalog_product_minimal(api_client, db):
    admin = create_admin_user(db, email="catalog-admin@test.com", role_code="buyback_manager")
    response = api_client.post(
        "/api/admin/buyback/catalog/products",
        headers=auth_headers(admin),
        json=_catalog_payload(
            card_number=None,
            rarity=None,
            pack_name=None,
            image_url=None,
            notes=None,
            prices=[{"condition_code": "default", "price_normal": 0}],
        ),
    )
    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "ピカチュウ"
    assert body["prices"][0]["price_normal"] == 0


def test_create_catalog_product_full(api_client, db):
    admin = create_admin_user(db, email="catalog-full@test.com", role_code="admin")
    response = api_client.post(
        "/api/admin/buyback/catalog/products",
        headers=auth_headers(admin),
        json=_catalog_payload(),
    )
    assert response.status_code == 201
    body = response.json()
    assert body["card_number"] == "025/165"
    assert body["pack_name"] == "151"
    assert body["prices"][0]["price_high"] == 1200


def test_reject_negative_and_string_prices(api_client, db):
    admin = create_admin_user(db, email="catalog-invalid@test.com", role_code="admin")
    negative = api_client.post(
        "/api/admin/buyback/catalog/products",
        headers=auth_headers(admin),
        json=_catalog_payload(prices=[{"condition_code": "default", "price_normal": -1}]),
    )
    assert negative.status_code == 422

    string_price = api_client.post(
        "/api/admin/buyback/catalog/products",
        headers=auth_headers(admin),
        json=_catalog_payload(prices=[{"condition_code": "default", "price_normal": "100"}]),
    )
    assert string_price.status_code == 422


def test_duplicate_card_number_and_pack(api_client, db):
    admin = create_admin_user(db, email="catalog-dup@test.com", role_code="buyback_manager")
    headers = auth_headers(admin)
    first = api_client.post(
        "/api/admin/buyback/catalog/products",
        headers=headers,
        json=_catalog_payload(name="A"),
    )
    assert first.status_code == 201

    duplicate = api_client.post(
        "/api/admin/buyback/catalog/products",
        headers=headers,
        json=_catalog_payload(name="B"),
    )
    assert duplicate.status_code == 409
    assert "既に登録" in duplicate.json()["detail"]


def test_viewer_can_read_but_cannot_write(api_client, db):
    admin = create_admin_user(db, email="catalog-viewer@test.com", role_code="viewer")
    headers = auth_headers(admin)
    denied = api_client.post(
        "/api/admin/buyback/catalog/products",
        headers=headers,
        json=_catalog_payload(),
    )
    assert denied.status_code == 403

    listed = api_client.get(
        "/api/admin/buyback/catalog/products",
        headers=headers,
    )
    assert listed.status_code == 200


@pytest.mark.parametrize("role_code", ["viewer", "appraiser"])
def test_write_roles_rejected(api_client, db, role_code):
    admin = create_admin_user(db, email=f"{role_code}-catalog@test.com", role_code=role_code)
    response = api_client.post(
        "/api/admin/buyback/catalog/products",
        headers=auth_headers(admin),
        json=_catalog_payload(),
    )
    assert response.status_code == 403


def test_update_and_soft_delete(api_client, db):
    admin = create_admin_user(db, email="catalog-edit@test.com", role_code="buyback_manager")
    headers = auth_headers(admin)
    created = api_client.post(
        "/api/admin/buyback/catalog/products",
        headers=headers,
        json=_catalog_payload(),
    ).json()

    updated = api_client.put(
        f"/api/admin/buyback/catalog/products/{created['id']}",
        headers=headers,
        json=_catalog_payload(name="更新後", prices=[{"condition_code": "default", "price_normal": 500}]),
    )
    assert updated.status_code == 200
    assert updated.json()["name"] == "更新後"
    assert updated.json()["prices"][0]["price_normal"] == 500

    deleted = api_client.delete(
        f"/api/admin/buyback/catalog/products/{created['id']}",
        headers=headers,
    )
    assert deleted.status_code == 204

    row = db.query(models_buyback.BuybackProduct).filter_by(id=created["id"]).first()
    assert row is not None
    assert row.is_active is False

    hidden = api_client.get("/api/admin/buyback/catalog/products", headers=headers)
    assert all(item["id"] != created["id"] for item in hidden.json())

    visible = api_client.get(
        "/api/admin/buyback/catalog/products?include_inactive=true",
        headers=headers,
    )
    assert any(item["id"] == created["id"] for item in visible.json())


def test_list_reflects_created_product(api_client, db):
    admin = create_admin_user(db, email="catalog-list@test.com", role_code="admin")
    headers = auth_headers(admin)
    created = api_client.post(
        "/api/admin/buyback/catalog/products",
        headers=headers,
        json=_catalog_payload(name="一覧確認"),
    ).json()

    listed = api_client.get("/api/admin/buyback/catalog/products", headers=headers)
    assert listed.status_code == 200
    assert any(item["id"] == created["id"] for item in listed.json())
