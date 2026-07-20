"""Buylist browser E2E (Phase 9).

Run with:
  E2E_RUN_PLAYWRIGHT=1 pytest tests/e2e/test_buylist_browser.py -q
"""

from __future__ import annotations

import pytest


pytestmark = pytest.mark.playwright


def test_buylist_renders_products(page, buylist_url):
    page.goto(buylist_url, wait_until="networkidle")
    page.wait_for_selector(".item-card", timeout=30000)
    cards = page.locator(".item-card")
    assert cards.count() >= 1
    assert page.locator(".hero__title").inner_text() == "買取価格表"


def test_buylist_search_filters(page, buylist_url):
    page.goto(buylist_url, wait_until="networkidle")
    page.wait_for_selector(".item-card", timeout=30000)
    initial_count = page.locator(".item-card").count()
    assert initial_count >= 1

    page.fill("#searchInput", "zzzznotfound99999")
    page.wait_for_timeout(500)
    assert page.locator(".item-card").count() == 0

    page.fill("#searchInput", "")
    page.wait_for_timeout(500)
    assert page.locator(".item-card").count() >= 1
