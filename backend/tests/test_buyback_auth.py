"""Buyback API skeleton tests."""

from __future__ import annotations


def test_buyback_health(api_client):
    res = api_client.get("/api/buyback/health")
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "ok"
    assert body["phase"] == "10"
    assert body["products_source"] == "postgresql+firestore_fallback"
    assert body["cutover_complete"] is False


def test_buyback_products_empty(api_client):
    res = api_client.get("/api/buyback/products")
    assert res.status_code == 200
    assert res.json() == []


def test_buyback_auth_sync_requires_token(api_client):
    res = api_client.post("/api/buyback/auth/sync")
    assert res.status_code == 401


def test_buyback_cart_requires_auth(api_client):
    res = api_client.get("/api/buyback/cart")
    assert res.status_code == 401
