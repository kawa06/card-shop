"""Production smoke tests (Phase 9).

Run with: E2E_RUN=1 pytest tests/e2e/test_production_smoke.py -q
"""

from __future__ import annotations

import pytest


pytestmark = pytest.mark.e2e


def test_buyback_health(http_client, backend_url):
    res = http_client.get(f"{backend_url}/api/buyback/health")
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "ok"
    assert body["phase"] == "9"
    assert body["products_source"] == "postgresql"


def test_buyback_products_migrated(http_client, backend_url):
    res = http_client.get(f"{backend_url}/api/buyback/products")
    assert res.status_code == 200
    products = res.json()
    assert len(products) >= 1
    assert all(p.get("firestore_item_id") for p in products)


def test_shop_homepage(http_client, shop_url):
    res = http_client.get(shop_url)
    assert res.status_code == 200
    assert "KRX" in res.text or "krx" in res.text.lower()


def test_buylist_homepage(http_client, buylist_url):
    res = http_client.get(buylist_url)
    assert res.status_code == 200
    assert "買取" in res.text
