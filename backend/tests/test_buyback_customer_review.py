"""Tests for customer review eligibility and legacy item status compatibility."""

from __future__ import annotations

import json

import models_buyback
from services.buyback_customer_review import can_review_appraisal, sync_item_line_statuses_from_assessment
from services.buyback_item_labels import is_customer_choosable_item


def _make_request(db, user, *, status: str, buyback_method: str = "mail"):
    req = models_buyback.BuybackRequest(
        user_id=user.id,
        status=status,
        buyback_method=buyback_method,
        request_number="T-001",
        estimated_total=1000,
        assessed_total=1000,
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


def test_can_review_with_pending_line_and_assessment_data(db, test_user):
    req = _make_request(db, test_user, status="assessed")
    assert can_review_appraisal(req, user_id=test_user.id) is True
    item = req.items[0]
    assert is_customer_choosable_item(item, req) is True


def test_sync_item_line_statuses_from_assessment(db, test_user):
    req = _make_request(db, test_user, status="assessed")
    item = req.items[0]
    assert item.line_status == "pending"
    sync_item_line_statuses_from_assessment(req)
    assert item.line_status == models_buyback.BuybackItemLineStatus.reduced.value
