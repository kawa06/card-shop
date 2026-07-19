"""Buyback request submission tests (Phase 5)."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi import HTTPException

from auth import hash_password
import models
import models_buyback
from services.buyback_cart import add_cart_item, get_or_create_cart
from services.buyback_request_number import assign_buyback_request_number
from services.buyback_requests import get_user_request, list_user_requests, submit_request_from_cart


def _create_user(db, email: str = "buyer@example.com") -> models.User:
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


def _seed_cart(db, user: models.User) -> None:
    add_cart_item(
        db,
        user_id=user.id,
        firestore_item_id="fs_req_001",
        product_name="申込テストカード",
        category="raw",
        condition_code="A",
        unit_price=1500,
        quantity=2,
    )


@patch("services.buyback_requests.notify_buyback_request_submitted")
def test_submit_request_from_cart(mock_notify, db):
    user = _create_user(db)
    _seed_cart(db, user)

    request = submit_request_from_cart(db, user=user, customer_note="テスト備考")

    assert request.request_number.startswith("KBB-")
    assert request.status == models_buyback.BuybackRequestStatus.submitted.value
    assert request.estimated_total == 3000
    assert request.customer_note == "テスト備考"
    assert len(request.items) == 1
    assert request.items[0].product_name_snapshot == "申込テストカード"
    mock_notify.assert_called_once()

    cart = get_or_create_cart(db, user.id)
    db.refresh(cart)
    assert not cart.items


def test_submit_empty_cart_fails(db):
    user = _create_user(db, email="empty@example.com")

    with pytest.raises(HTTPException) as exc:
        submit_request_from_cart(db, user=user)

    assert exc.value.status_code == 400


@patch("services.buyback_requests.notify_buyback_request_submitted")
def test_list_and_get_user_requests(mock_notify, db):
    user = _create_user(db, email="list@example.com")
    _seed_cart(db, user)
    created = submit_request_from_cart(db, user=user)

    summaries = list_user_requests(db, user_id=user.id)
    assert len(summaries) == 1
    assert summaries[0].request_number == created.request_number

    detail = get_user_request(db, user_id=user.id, request_id=created.id)
    assert detail.id == created.id
    assert len(detail.items) == 1


def test_assign_buyback_request_number_sequential(db):
    user = _create_user(db, email="num@example.com")
    req1 = models_buyback.BuybackRequest(
        user_id=user.id,
        status=models_buyback.BuybackRequestStatus.submitted.value,
    )
    req2 = models_buyback.BuybackRequest(
        user_id=user.id,
        status=models_buyback.BuybackRequestStatus.submitted.value,
    )
    db.add(req1)
    db.add(req2)
    db.flush()

    num1 = assign_buyback_request_number(db, req1)
    num2 = assign_buyback_request_number(db, req2)
    db.commit()

    assert num1.startswith("KBB-")
    assert num2.startswith("KBB-")
    assert num1 != num2
