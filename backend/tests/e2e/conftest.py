"""Playwright and production E2E fixtures (Phase 9)."""

from __future__ import annotations

import os

import httpx
import pytest

E2E_RUN = os.getenv("E2E_RUN", "").strip() in {"1", "true", "yes"}
E2E_RUN_PLAYWRIGHT = os.getenv("E2E_RUN_PLAYWRIGHT", "").strip() in {"1", "true", "yes"}

BUYLIST_URL = os.getenv("E2E_BUYLIST_URL", "https://card-vault-public.vercel.app").rstrip("/")
SHOP_URL = os.getenv("E2E_SHOP_URL", "https://frontend-one-topaz-20.vercel.app").rstrip("/")
BACKEND_URL = os.getenv(
    "E2E_BACKEND_URL",
    "https://backend-production-054e.up.railway.app",
).rstrip("/")


def pytest_configure(config):
    config.addinivalue_line("markers", "e2e: production smoke tests")
    config.addinivalue_line("markers", "playwright: browser E2E tests")


@pytest.fixture(scope="session")
def backend_url() -> str:
    return BACKEND_URL


@pytest.fixture(scope="session")
def buylist_url() -> str:
    return BUYLIST_URL


@pytest.fixture(scope="session")
def shop_url() -> str:
    return SHOP_URL


@pytest.fixture(scope="session")
def http_client() -> httpx.Client:
    with httpx.Client(timeout=30.0, follow_redirects=True) as client:
        yield client


def pytest_collection_modifyitems(config, items):
    skip_e2e = pytest.mark.skip(reason="Set E2E_RUN=1 to run production smoke tests")
    skip_playwright = pytest.mark.skip(
        reason="Set E2E_RUN_PLAYWRIGHT=1 to run Playwright browser tests"
    )
    for item in items:
        if "e2e" in item.keywords and not E2E_RUN:
            item.add_marker(skip_e2e)
        if "playwright" in item.keywords and not E2E_RUN_PLAYWRIGHT:
            item.add_marker(skip_playwright)
