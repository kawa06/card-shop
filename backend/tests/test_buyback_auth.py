"""Buyback API skeleton tests."""

from __future__ import annotations

from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def test_buyback_health():
    res = client.get("/api/buyback/health")
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "ok"
    assert body["phase"] == "6"


def test_buyback_products_empty(db):
    res = client.get("/api/buyback/products")
    assert res.status_code == 200
    assert res.json() == []


def test_buyback_auth_sync_requires_token():
    res = client.post("/api/buyback/auth/sync")
    assert res.status_code == 401


def test_buyback_cart_requires_auth():
    res = client.get("/api/buyback/cart")
    assert res.status_code == 401
