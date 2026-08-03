"""Buylist shop settings API tests."""

from __future__ import annotations

from conftest import auth_headers, create_admin_user


def test_public_shop_settings_create_on_read(api_client, db):
    response = api_client.get("/api/buyback/shop")
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == "main"
    assert body["name"]
    assert body["slug"]
    assert body["show_notice"] is True


def test_admin_shop_settings_upsert(api_client, db):
    admin = create_admin_user(db, email="shop-admin@test.com", role_code="buyback_manager")
    headers = auth_headers(admin)

    get_resp = api_client.get("/api/admin/buyback/shop/settings", headers=headers)
    assert get_resp.status_code == 200

    put_resp = api_client.put(
        "/api/admin/buyback/shop/settings",
        headers=headers,
        json={
            "notice_text": "テスト注意書き",
            "show_notice": False,
            "name": "KRX TCG",
            "slug": "card-vault",
        },
    )
    assert put_resp.status_code == 200
    updated = put_resp.json()
    assert updated["notice_text"] == "テスト注意書き"
    assert updated["show_notice"] is False

    public = api_client.get("/api/buyback/shop")
    assert public.status_code == 200
    assert public.json()["notice_text"] == "テスト注意書き"
    assert public.json()["show_notice"] is False
