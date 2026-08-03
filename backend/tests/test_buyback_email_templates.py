"""Tests for buyback email template platform."""

from unittest.mock import patch

from services.buyback_email_auto_send import get_auto_send_settings, should_auto_send, update_auto_send_settings
from services.buyback_email_registry import resolve_status_change_event, resolve_buyback_template_key
from services.buyback_email_templates_seed import seed_buyback_email_templates
from services.buyback_email_variables import build_buyback_sample_variables
from services.email_template_seed import seed_email_templates


def test_buyback_template_keys_and_legacy_aliases():
    assert resolve_buyback_template_key("buyback_package_shipped") == "buyback_return_shipped"
    assert resolve_buyback_template_key("buyback_assessing", "store") == "buyback_store_assessing_start"


def test_status_change_event_respects_method():
    assert resolve_status_change_event(to_status="awaiting_shipment", buyback_method="mail") == "buyback_awaiting_shipment"
    assert resolve_status_change_event(to_status="awaiting_visit", buyback_method="store") == "buyback_store_reservation"


def test_seed_buyback_templates(db):
    seed_email_templates(db)
    count = seed_buyback_email_templates(db, force_upgrade=True)
    assert count >= 30

    from models_email import EmailTemplate

    tpl = db.query(EmailTemplate).filter(EmailTemplate.template_key == "buyback_request_submitted").first()
    assert tpl is not None
    assert tpl.category == "buyback"
    assert "{{buybackInfoBlock}}" in tpl.html_body


def test_buyback_sample_variables():
    sample = build_buyback_sample_variables("buyback_assessment_ready")
    assert sample["buyNo"] == "BB-20260801-001"
    assert sample["buybackInfoBlock"]


def test_auto_send_settings(db):
    defaults = get_auto_send_settings(db)
    assert defaults.get("buyback_request_submitted") is True
    updated = update_auto_send_settings(db, {"buyback_request_submitted": False})
    assert updated["buyback_request_submitted"] is False
    assert should_auto_send(db, "buyback_request_submitted") is False
    assert should_auto_send(db, "buyback_request_submitted", explicit=True) is True


@patch("services.buyback_emails.email_configured", return_value=True)
@patch("services.buyback_emails.send_templated_email")
def test_send_buyback_event_email_respects_auto_send(mock_send, _mock_configured, db, test_user):
    from models_buyback import BuybackRequest, BuybackRequestStatus
    from services.buyback_emails import send_buyback_event_email
    from services.email_delivery import SendResult

    mock_send.return_value = SendResult(ok=True)

    seed_buyback_email_templates(db, force_upgrade=True)
    update_auto_send_settings(db, {"buyback_inbound_received": False})
    db.commit()

    request = BuybackRequest(
        user_id=test_user.id,
        status=BuybackRequestStatus.received.value,
        buyback_method="mail",
        request_number="BB-TEST-001",
    )
    db.add(request)
    db.commit()
    db.refresh(request)

    ok, err = send_buyback_event_email(db, request, test_user, "buyback_inbound_received")
    assert ok is True
    mock_send.assert_not_called()

    ok, err = send_buyback_event_email(
        db, request, test_user, "buyback_inbound_received", send_email=True, force=True
    )
    assert ok is True
    mock_send.assert_called_once()
