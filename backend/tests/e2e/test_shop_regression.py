"""Card shop regression smoke (Phase 9).

Run with:
  E2E_RUN_PLAYWRIGHT=1 pytest tests/e2e/test_shop_regression.py -q
"""

from __future__ import annotations

import pytest


pytestmark = pytest.mark.playwright


def test_shop_home_loads(page, shop_url):
    page.goto(shop_url, wait_until="domcontentloaded")
    assert page.title()
    body = page.locator("body").inner_text()
    assert body.strip() != ""


def test_shop_cards_page(page, shop_url):
    page.goto(f"{shop_url}/cards", wait_until="domcontentloaded")
    assert page.url.endswith("/cards") or "/cards" in page.url
