"""Tests for buyback admin dashboard stats, list filter, and status sync."""

from __future__ import annotations

import json

import models_buyback
from services.buyback_admin import list_admin_requests, request_stats, update_request_status
from services.buyback_item_labels import compute_assessed_total, item_assessed_subtotal
from tests.conftest import create_admin_user


def _make_request(db, user, *, status: str, buyback_method: str = "mail", request_number: str = "T-001"):
    req = models_buyback.BuybackRequest(
        user_id=user.id,
        status=status,
        buyback_method=buyback_method,
        request_number=request_number,
        estimated_total=1000,
    )
    db.add(req)
    db.flush()
    item = models_buyback.BuybackRequestItem(
        request_id=req.id,
        product_name_snapshot="Test Card",
        condition_code="default",
        quantity=2,
        listed_unit_price=500,
        line_status=models_buyback.BuybackItemLineStatus.pending.value,
        assessment_lines_json=json.dumps(
            [{"quantity": 2, "unit_price": 400}],
            ensure_ascii=False,
        ),
    )
    db.add(item)
    db.commit()
    db.refresh(req)
    return req


def test_item_assessed_subtotal_uses_lines_when_pending(db, test_user):
    req = _make_request(db, test_user, status="assessed")
    item = req.items[0]
    assert item.line_status == "pending"
    assert item_assessed_subtotal(item, req) == 800
    assert compute_assessed_total(req.items, req) == 800


def test_update_request_status_syncs_items_and_total(db, test_user):
    admin = create_admin_user(db)
    req = _make_request(db, test_user, status="assessed")
    update_request_status(
        db,
        request_id=req.id,
        admin_user=admin,
        new_status=models_buyback.BuybackRequestStatus.awaiting_customer.value,
    )
    db.refresh(req)
    item = req.items[0]
    assert item.line_status == models_buyback.BuybackItemLineStatus.reduced.value
    assert req.assessed_total == 800


def test_list_admin_requests_filters_by_buyback_method(db, test_user):
    _make_request(db, test_user, status="submitted", buyback_method="mail", request_number="M-001")
    _make_request(db, test_user, status="submitted", buyback_method="store", request_number="S-001")

    mail_rows = list_admin_requests(db, buyback_method="mail", limit=50)
    store_rows = list_admin_requests(db, buyback_method="store", limit=50)

    assert all(r.buyback_method != "store" or r.request_number == "S-001" for r in mail_rows)
    assert any(r.request_number == "M-001" for r in mail_rows)
    assert not any(r.request_number == "S-001" for r in mail_rows)
    assert any(r.request_number == "S-001" for r in store_rows)
    assert not any(r.request_number == "M-001" for r in store_rows)


def test_request_stats_channel_breakdown(db, test_user):
    _make_request(db, test_user, status="assessing", buyback_method="mail", request_number="M-002")
    _make_request(db, test_user, status="awaiting_visit", buyback_method="store", request_number="S-002")

    stats = request_stats(db)
    assert stats["mail"]["assessing_count"] >= 1
    assert stats["store"]["awaiting_visit_count"] >= 1
