"""Buyback email notification tests."""

from __future__ import annotations

from unittest.mock import patch

from auth import hash_password
import models
import models_buyback
from services.buyback_emails import notify_buyback_request_submitted


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


@patch("services.buyback_emails.email_configured", return_value=True)
@patch("services.buyback_emails._send_html_email", return_value=(True, None))
def test_notify_buyback_request_submitted(mock_send, mock_configured, db):
    user = _create_user(db)
    request = models_buyback.BuybackRequest(
        user_id=user.id,
        request_number="KBB-20260719-0001",
        status=models_buyback.BuybackRequestStatus.submitted.value,
        estimated_total=5000,
    )
    db.add(request)
    db.flush()
    db.add(
        models_buyback.BuybackRequestItem(
            request_id=request.id,
            product_name_snapshot="テストカード",
            condition_code="A",
            quantity=1,
            listed_unit_price=5000,
        )
    )
    db.commit()
    db.refresh(request)

    notify_buyback_request_submitted(db, request, user)

    assert mock_send.call_count == 2
    subjects = [call.kwargs["subject"] for call in mock_send.call_args_list]
    assert any("買取申込を受け付けました" in s for s in subjects)
    assert any("新規買取申込" in s for s in subjects)

    deliveries = db.query(models_buyback.NotificationDelivery).all()
    assert len(deliveries) == 2
    assert all(d.status == "sent" for d in deliveries)
