"""Tests for customer assessment response confirmation."""

from __future__ import annotations

import json
from unittest.mock import patch

from auth import hash_password
import models
import models_buyback
from fastapi import HTTPException
from services.buyback_admin import update_request_items
from services.buyback_assessment_response import submit_assessment_response
from services.buyback_cart import add_cart_item
from services.buyback_requests import get_user_request, submit_request_from_cart


def _create_admin(db) -> models.User:
    user = models.User(
        email="admin-assess@example.com",
        name="Admin",
        password_hash=hash_password("secret123"),
        is_admin=True,
        is_verified=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _create_user(db, *, email: str = "buyer-assess@example.com") -> models.User:
    user = models.User(
        email=email,
        name="Buyer",
        password_hash=hash_password("secret123"),
        is_verified=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _awaiting_customer_request(db, *, quantity: int = 1, assessment_lines=None):
    admin = _create_admin(db)
    user = _create_user(db)
    add_cart_item(
        db,
        user_id=user.id,
        firestore_item_id="fs_assess_001",
        product_name="ストームエメラルダ",
        category="raw",
        condition_code="A",
        unit_price=1000,
        quantity=quantity,
    )
    request = submit_request_from_cart(
        db,
        user=user,
        rejected_item_handling="return_rejected_only",
        agreed_prepaid_shipping=True,
        agreed_cod_consequence=True,
        agreed_condition_rejection=True,
    )
    item_id = request.items[0].id
    update_payload = {
        "id": item_id,
        "line_status": "buyable",
    }
    if assessment_lines is not None:
        update_payload["assessment_lines"] = assessment_lines
    else:
        update_payload["assessed_unit_price"] = 100
    update_request_items(
        db,
        request_id=request.id,
        admin_user=admin,
        item_updates=[update_payload],
    )
    request.status = models_buyback.BuybackRequestStatus.awaiting_customer.value
    request.assessed_total = 100 * quantity if assessment_lines is None else sum(
        row["quantity"] * row["unit_price"] for row in assessment_lines
    )
    db.commit()
    db.refresh(request)
    return user, request


@patch("services.buyback_assessment_response.notify_buyback_status_changed")
def test_submit_all_accept(mock_notify, db):
    user, request = _awaiting_customer_request(db, quantity=2)
    item = request.items[0]
    result = submit_assessment_response(
        db,
        user=user,
        request_id=request.id,
        decisions=[
            {
                "item_id": item.id,
                "unit_decisions": [
                    {"line_index": 0, "unit_index": 0, "accepted": True},
                    {"line_index": 0, "unit_index": 1, "accepted": True},
                ],
            }
        ],
    )
    assert result.status == models_buyback.BuybackRequestStatus.accepted.value
    assert result.payout_total == 200
    assert result.customer_confirmed_at is not None
    assert result.customer_confirmed_by_user_id == user.id
    assert item.customer_decision == "accepted"


@patch("services.buyback_assessment_response.notify_buyback_status_changed")
def test_submit_partial_reject(mock_notify, db):
    user, request = _awaiting_customer_request(
        db,
        quantity=2,
        assessment_lines=[
            {"quantity": 1, "unit_price": 100},
            {"quantity": 1, "unit_price": 80},
        ],
    )
    item = request.items[0]
    result = submit_assessment_response(
        db,
        user=user,
        request_id=request.id,
        decisions=[
            {
                "item_id": item.id,
                "unit_decisions": [
                    {"line_index": 0, "unit_index": 0, "accepted": True},
                    {"line_index": 1, "unit_index": 0, "accepted": False},
                ],
            }
        ],
    )
    assert result.status == models_buyback.BuybackRequestStatus.accepted.value
    assert result.payout_total == 100
    assert item.customer_decision == "partial"
    lines = json.loads(item.customer_decision_lines_json)
    assert len(lines) == 2
    assert item.is_return_target is True


@patch("services.buyback_assessment_response.notify_buyback_status_changed")
def test_submit_all_reject(mock_notify, db):
    user, request = _awaiting_customer_request(db)
    item = request.items[0]
    result = submit_assessment_response(
        db,
        user=user,
        request_id=request.id,
        decisions=[
            {
                "item_id": item.id,
                "unit_decisions": [{"line_index": 0, "unit_index": 0, "accepted": False}],
            }
        ],
    )
    assert result.status == models_buyback.BuybackRequestStatus.rejected.value
    assert result.payout_total == 0
    assert item.customer_decision == "rejected"


@patch("services.buyback_assessment_response.notify_buyback_status_changed")
def test_submit_missing_selection(mock_notify, db):
    user, request = _awaiting_customer_request(db, quantity=2)
    item = request.items[0]
    try:
        submit_assessment_response(
            db,
            user=user,
            request_id=request.id,
            decisions=[
                {
                    "item_id": item.id,
                    "unit_decisions": [{"line_index": 0, "unit_index": 0, "accepted": True}],
                }
            ],
        )
    except HTTPException as exc:
        assert exc.status_code == 400
        assert "すべての枚数" in str(exc.detail)
    else:
        raise AssertionError("expected HTTPException")


@patch("services.buyback_assessment_response.notify_buyback_status_changed")
def test_submit_missing_item(mock_notify, db):
    user, request = _awaiting_customer_request(db)
    try:
        submit_assessment_response(
            db,
            user=user,
            request_id=request.id,
            decisions=[],
        )
    except HTTPException as exc:
        assert exc.status_code == 422 or exc.status_code == 400
    else:
        raise AssertionError("expected HTTPException")


@patch("services.buyback_assessment_response.notify_buyback_status_changed")
def test_submit_already_confirmed(mock_notify, db):
    user, request = _awaiting_customer_request(db)
    item = request.items[0]
    submit_assessment_response(
        db,
        user=user,
        request_id=request.id,
        decisions=[
            {
                "item_id": item.id,
                "unit_decisions": [{"line_index": 0, "unit_index": 0, "accepted": True}],
            }
        ],
    )
    try:
        submit_assessment_response(
            db,
            user=user,
            request_id=request.id,
            decisions=[
                {
                    "item_id": item.id,
                    "unit_decisions": [{"line_index": 0, "unit_index": 0, "accepted": True}],
                }
            ],
        )
    except HTTPException as exc:
        assert exc.status_code == 400
    else:
        raise AssertionError("expected HTTPException")


def test_other_user_cannot_confirm(db):
    owner, request = _awaiting_customer_request(db)
    other = _create_user(db, email="other@example.com")
    item = request.items[0]
    try:
        submit_assessment_response(
            db,
            user=other,
            request_id=request.id,
            decisions=[
                {
                    "item_id": item.id,
                    "unit_decisions": [{"line_index": 0, "unit_index": 0, "accepted": True}],
                }
            ],
        )
    except HTTPException as exc:
        assert exc.status_code == 404
    else:
        raise AssertionError("expected HTTPException")


def test_get_user_request_ownership(db):
    owner, request = _awaiting_customer_request(db)
    other = _create_user(db, email="other2@example.com")
    loaded = get_user_request(db, user_id=owner.id, request_id=request.id)
    assert loaded.id == request.id
    try:
        get_user_request(db, user_id=other.id, request_id=request.id)
    except HTTPException as exc:
        assert exc.status_code == 404
    else:
        raise AssertionError("expected HTTPException")
