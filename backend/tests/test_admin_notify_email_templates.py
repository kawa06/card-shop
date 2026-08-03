"""Tests for admin notification email template platform."""

from unittest.mock import patch

from services.admin_notify_email_registry import ADMIN_NOTIFY_EMAIL_EVENTS, normalize_template_key
from services.admin_notify_email_templates_seed import seed_admin_notify_email_templates
from services.admin_notify_email_variables import build_admin_notify_sample_variables
from services.admin_notify_settings import (
    get_auto_send_settings,
    get_channel_settings,
    should_auto_send_email,
    update_auto_send_settings,
    update_channel_settings,
)
from services.email_template_seed import seed_email_templates


def test_admin_notify_template_count():
    assert len(ADMIN_NOTIFY_EMAIL_EVENTS) == 57


def test_legacy_buyback_admin_alias():
    assert normalize_template_key("buyback_request_admin_alert") == "admin_notify_buyback_request_new"


def test_seed_admin_notify_templates(db):
    seed_email_templates(db)
    count = seed_admin_notify_email_templates(db, force_upgrade=True)
    assert count >= 57

    from models_email import EmailTemplate

    tpl = db.query(EmailTemplate).filter(EmailTemplate.template_key == "admin_notify_order_received").first()
    assert tpl is not None
    assert tpl.category == "order"
    assert "{{adminNotifyInfoBlock}}" in tpl.html_body


def test_admin_notify_sample_no_sensitive_data():
    sample = build_admin_notify_sample_variables("admin_notify_kyc_submitted")
    serialized = str(sample).lower()
    assert "account_number" not in serialized
    assert "storage_path" not in serialized
    assert "document_url" not in serialized


def test_admin_notify_settings(db):
    defaults = get_auto_send_settings(db)
    assert defaults.get("admin_notify_order_received") is True
    channels = get_channel_settings(db)
    assert channels.get("admin_notify_security_admin_login") == "in_app"
    updated = update_auto_send_settings(db, {"admin_notify_order_received": False})
    assert updated["admin_notify_order_received"] is False
    assert should_auto_send_email(db, "admin_notify_order_received") is False
    ch = update_channel_settings(db, {"admin_notify_order_received": "email"})
    assert ch["admin_notify_order_received"] == "email"


@patch("services.admin_notify_emails.email_configured", return_value=True)
@patch("services.admin_notify_emails.send_templated_email")
def test_send_admin_notify_respects_auto_send(mock_send, _mock_configured, db):
    from services.email_delivery import SendResult
    from services.admin_notify_emails import send_admin_notify_event

    mock_send.return_value = SendResult(ok=True)

    seed_admin_notify_email_templates(db, force_upgrade=True)
    update_auto_send_settings(db, {"admin_notify_order_received": False})
    db.commit()

    ok, err, success, failed = send_admin_notify_event(db, "admin_notify_order_received", send_email=None)
    assert ok is True
    mock_send.assert_not_called()

    ok, err, success, failed = send_admin_notify_event(
        db, "admin_notify_order_received", force=True, send_email=True
    )
    assert ok is True
    assert mock_send.called
