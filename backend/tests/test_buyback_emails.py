"""Buyback email notification tests."""

from __future__ import annotations

from unittest.mock import patch

from auth import hash_password
import models
import models_buyback
from services.email_delivery import SendResult
from services.buyback_emails import (
    notify_buyback_assessment_ready,
    notify_buyback_decision,
    notify_buyback_inbound_received,
    notify_buyback_package_shipped,
    notify_buyback_payout_completed,
    notify_buyback_request_submitted,
    notification_already_sent,
)


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


def _request(db, user: models.User, **kwargs) -> models_buyback.BuybackRequest:
    data = {
        "user_id": user.id,
        "request_number": "KBB-20260720-0099",
        "public_buyback_code": "KRX-BUY-20260720-000099",
        "inbound_mgmt_id": "KRX-PKG-20260720-000099",
        "status": models_buyback.BuybackRequestStatus.submitted.value,
        "estimated_total": 5000,
    }
    data.update(kwargs)
    request = models_buyback.BuybackRequest(**data)
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
    return request


@patch("services.buyback_emails.email_configured", return_value=True)
@patch("services.buyback_emails.send_templated_email")
def test_notify_buyback_request_submitted(mock_send, mock_configured, db):
    mock_send.return_value = SendResult(ok=True)
    user = _create_user(db)
    request = _request(db, user)

    notify_buyback_request_submitted(db, request, user)

    assert mock_send.call_count == 2
    subjects = [call.kwargs["fallback_subject"] for call in mock_send.call_args_list]
    assert any("買取申込を受け付けました" in s for s in subjects)
    assert any("新規買取申込" in s for s in subjects)

    deliveries = db.query(models_buyback.NotificationDelivery).all()
    assert len(deliveries) == 2
    assert all(d.status == "sent" for d in deliveries)


@patch("services.buyback_emails.email_configured", return_value=True)
@patch("services.buyback_emails.send_templated_email")
def test_notify_buyback_payout_completed(mock_send, mock_configured, db):
    mock_send.return_value = SendResult(ok=True)
    user = _create_user(db)
    request = _request(
        db,
        user,
        status=models_buyback.BuybackRequestStatus.paid.value,
        payout_total=4800,
    )

    ok, err = notify_buyback_payout_completed(db, request, user)
    assert ok is True
    assert err is None
    mock_send.assert_called_once()
    assert "振込が完了しました" in mock_send.call_args.kwargs["fallback_subject"]


@patch("services.buyback_emails.email_configured", return_value=True)
@patch("services.buyback_emails.send_templated_email")
def test_notify_inbound_received_and_idempotent(mock_send, mock_configured, db):
    mock_send.return_value = SendResult(ok=True)
    user = _create_user(db, email="recv@example.com")
    request = _request(
        db,
        user,
        status=models_buyback.BuybackRequestStatus.received.value,
    )

    ok, err = notify_buyback_inbound_received(db, request, user)
    assert ok and err is None
    assert mock_send.call_count == 1
    assert "受け取りました" in mock_send.call_args.kwargs["fallback_subject"]
    assert notification_already_sent(db, "buyback_inbound_received", str(request.id))

    ok2, _ = notify_buyback_inbound_received(db, request, user)
    assert ok2 is True
    assert mock_send.call_count == 1


@patch("services.buyback_emails.email_configured", return_value=True)
@patch("services.buyback_emails.send_templated_email")
def test_notify_assessment_and_decision(mock_send, mock_configured, db):
    mock_send.return_value = SendResult(ok=True)
    user = _create_user(db, email="assess@example.com")
    request = _request(
        db,
        user,
        status=models_buyback.BuybackRequestStatus.awaiting_customer.value,
        assessed_total=4200,
    )

    notify_buyback_assessment_ready(db, request, user)
    assert any("査定結果" in c.kwargs["fallback_subject"] for c in mock_send.call_args_list)

    request.status = models_buyback.BuybackRequestStatus.accepted.value
    db.commit()
    notify_buyback_decision(db, request, user)
    assert any("買取が成立" in c.kwargs["fallback_subject"] for c in mock_send.call_args_list)

    keys = {d.template_key for d in db.query(models_buyback.NotificationDelivery).all()}
    assert "buyback_assessment_ready" in keys
    assert "buyback_accepted" in keys


@patch("services.buyback_emails.email_configured", return_value=True)
@patch("services.buyback_emails.send_templated_email")
def test_notify_package_shipped(mock_send, mock_configured, db):
    mock_send.return_value = SendResult(ok=True)
    user = _create_user(db, email="ship@example.com")
    request = _request(
        db,
        user,
        status=models_buyback.BuybackRequestStatus.rejected.value,
    )
    package = models_buyback.BuybackShipmentPackage(
        request_id=request.id,
        package_code=f"{request.inbound_mgmt_id}-01",
        package_kind="return",
        box_index=1,
        total_boxes=1,
        destination_user_id=user.id,
        shipping_method="yamato",
        tracking_number="TRACK-123",
        status=models_buyback.BuybackShipmentPackageStatus.shipped.value,
    )
    db.add(package)
    db.commit()
    db.refresh(package)

    ok, err = notify_buyback_package_shipped(db, request, user, package)
    assert ok and err is None
    mock_send.assert_called_once()
    assert "発送しました" in mock_send.call_args.kwargs["fallback_subject"]
    assert "TRACK-123" in mock_send.call_args.kwargs["fallback_html"]

    notify_buyback_package_shipped(db, request, user, package)
    assert mock_send.call_count == 1
