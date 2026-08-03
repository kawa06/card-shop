"""Tests for inquiry email template platform."""

from unittest.mock import patch

from services.inquiry_email_auto_send import get_auto_send_settings, should_auto_send, update_auto_send_settings
from services.inquiry_email_registry import INQUIRY_EMAIL_EVENTS, LEGACY_TEMPLATE_ALIASES, normalize_template_key
from services.inquiry_email_templates_seed import seed_inquiry_email_templates
from services.inquiry_email_variables import build_inquiry_sample_variables
from services.email_template_seed import seed_email_templates


def test_inquiry_template_keys_and_legacy_aliases():
    assert normalize_template_key("inquiry_reply") == "inquiry_admin_reply"
    assert len(INQUIRY_EMAIL_EVENTS) == 11


def test_seed_inquiry_templates(db):
    seed_email_templates(db)
    count = seed_inquiry_email_templates(db, force_upgrade=True)
    assert count >= 11

    from models_email import EmailTemplate

    tpl = db.query(EmailTemplate).filter(EmailTemplate.template_key == "inquiry_received").first()
    assert tpl is not None
    assert tpl.category == "inquiry"
    assert "{{inquiryInfoBlock}}" in tpl.html_body


def test_inquiry_sample_variables_no_urls_in_attachments():
    sample = build_inquiry_sample_variables("inquiry_attachment_received")
    serialized = str(sample)
    assert "http" not in sample.get("attachmentBlock", "").lower() or "sample-image" in serialized
    assert "storage" not in serialized.lower()
    assert sample.get("inquiryNo")


def test_inquiry_auto_send_settings(db):
    defaults = get_auto_send_settings(db)
    assert defaults.get("inquiry_received") is True
    assert defaults.get("inquiry_system_error") is False
    updated = update_auto_send_settings(db, {"inquiry_received": False})
    assert updated["inquiry_received"] is False
    assert should_auto_send(db, "inquiry_received") is False
    assert should_auto_send(db, "inquiry_received", explicit=True) is True


def test_legacy_aliases_cover_old_keys():
    assert LEGACY_TEMPLATE_ALIASES["inquiry_reply"] == "inquiry_admin_reply"


@patch("services.inquiry_emails.email_configured", return_value=True)
@patch("services.inquiry_emails.send_templated_email")
def test_send_inquiry_event_respects_auto_send(mock_send, _mock_configured, db, test_user):
    import models

    from services.email_delivery import SendResult
    from services.inquiry_emails import send_inquiry_event_email

    mock_send.return_value = SendResult(ok=True)

    seed_inquiry_email_templates(db, force_upgrade=True)
    update_auto_send_settings(db, {"inquiry_received": False})
    db.commit()

    inquiry = models.Inquiry(
        inquiry_number="INQ-TEST-001",
        shop_id=1,
        user_id=test_user.id,
        reply_email=test_user.email,
        category="other",
        subject="test",
        status="waiting_admin",
    )
    db.add(inquiry)
    db.commit()
    db.refresh(inquiry)

    ok, err = send_inquiry_event_email(db, "inquiry_received", inquiry=inquiry, user=test_user)
    assert ok is True
    mock_send.assert_not_called()

    ok, err = send_inquiry_event_email(
        db, "inquiry_received", inquiry=inquiry, user=test_user, send_email=True, force=True
    )
    assert ok is True
    mock_send.assert_called_once()
