"""Tests for buyback item assessment admin operations."""

from __future__ import annotations

from unittest.mock import patch

from auth import hash_password
import models
import models_buyback
from services.buyback_admin import update_request_items
from services.buyback_cart import add_cart_item
from services.buyback_requests import submit_request_from_cart


def _create_admin(db) -> models.User:
    user = models.User(
        email="admin@example.com",
        name="Admin",
        password_hash=hash_password("secret123"),
        is_admin=True,
        is_verified=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _create_user(db) -> models.User:
    user = models.User(
        email="buyer@example.com",
        name="Buyer",
        password_hash=hash_password("secret123"),
        is_verified=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@patch("services.buyback_requests.notify_buyback_request_submitted")
def test_update_request_items_rejected_with_reason(mock_notify, db):
    admin = _create_admin(db)
    user = _create_user(db)
    add_cart_item(
        db,
        user_id=user.id,
        firestore_item_id="fs_001",
        product_name="査定テストカード",
        category="raw",
        condition_code="A",
        unit_price=1000,
        quantity=1,
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

    updated = update_request_items(
        db,
        request_id=request.id,
        admin_user=admin,
        item_updates=[
            {
                "id": item_id,
                "line_status": "rejected",
                "rejection_reason_code": "major_damage",
            }
        ],
    )

    item = updated.items[0]
    assert item.line_status == "rejected"
    assert item.rejection_reason_code == "major_damage"
    assert item.is_return_target is True
    assert updated.assessed_total == 0


@patch("services.buyback_requests.notify_buyback_request_submitted")
def test_update_request_items_reduced_price(mock_notify, db):
    admin = _create_admin(db)
    user = _create_user(db)
    add_cart_item(
        db,
        user_id=user.id,
        firestore_item_id="fs_002",
        product_name="減額テストカード",
        category="raw",
        condition_code="A",
        unit_price=2000,
        quantity=1,
    )
    request = submit_request_from_cart(
        db,
        user=user,
        rejected_item_handling="dispose_rejected",
        agreed_prepaid_shipping=True,
        agreed_cod_consequence=True,
        agreed_condition_rejection=True,
    )
    item_id = request.items[0].id

    updated = update_request_items(
        db,
        request_id=request.id,
        admin_user=admin,
        item_updates=[
            {
                "id": item_id,
                "line_status": "reduced",
                "assessed_unit_price": 1500,
            }
        ],
    )

    assert updated.assessed_total == 1500
    assert updated.items[0].line_status == "reduced"


@patch("services.buyback_requests.notify_buyback_request_submitted")
def test_update_request_items_assessment_lines(mock_notify, db):
    admin = _create_admin(db)
    user = _create_user(db)
    add_cart_item(
        db,
        user_id=user.id,
        firestore_item_id="fs_003",
        product_name="複数枚テストカード",
        category="raw",
        condition_code="A",
        unit_price=1000,
        quantity=5,
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

    updated = update_request_items(
        db,
        request_id=request.id,
        admin_user=admin,
        item_updates=[
            {
                "id": item_id,
                "line_status": "buyable",
                "assessment_lines": [
                    {"quantity": 3, "unit_price": 1000},
                    {"quantity": 2, "unit_price": 800},
                ],
            }
        ],
    )

    assert updated.assessed_total == 4600


@patch("services.buyback_requests.notify_buyback_request_submitted")
def test_update_request_items_condition_and_comment(mock_notify, db):
    admin = _create_admin(db)
    user = _create_user(db)
    add_cart_item(
        db,
        user_id=user.id,
        firestore_item_id="fs_004",
        product_name="状態変更テスト",
        category="raw",
        condition_code="A",
        unit_price=1000,
        quantity=1,
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

    updated = update_request_items(
        db,
        request_id=request.id,
        admin_user=admin,
        item_updates=[
            {
                "id": item_id,
                "line_status": "buyable",
                "condition_code": "B",
                "assessment_comment": "軽微な角スレあり",
            }
        ],
    )

    item = updated.items[0]
    assert item.condition_code == "B"
    assert item.assessment_comment == "軽微な角スレあり"

    from services.buyback_admin import list_request_assessment_logs

    logs = list_request_assessment_logs(db, request_id=request.id)
    assert any(log["action"] == "request_items_updated" for log in logs)
    item = updated.items[0]
    assert item.assessed_unit_price == 920
    assert item.assessment_lines_json is not None
