"""Tests for member/login/security email template platform."""

from unittest.mock import patch

from services.member_email_auto_send import get_auto_send_settings, should_auto_send, update_auto_send_settings
from services.member_email_registry import LEGACY_TEMPLATE_ALIASES, MEMBER_EMAIL_EVENTS, normalize_template_key
from services.member_email_templates_seed import seed_member_email_templates
from services.member_email_variables import build_member_sample_variables
from services.email_template_seed import seed_email_templates


def test_member_template_keys_and_legacy_aliases():
    assert normalize_template_key("member_login_notify") == "login_success"
    assert normalize_template_key("member_2fa_otp") == "security_2fa_otp_sent"
    assert len(MEMBER_EMAIL_EVENTS) == 28


def test_seed_member_templates(db):
    seed_email_templates(db)
    count = seed_member_email_templates(db, force_upgrade=True)
    assert count >= 28

    from models_email import EmailTemplate

    tpl = db.query(EmailTemplate).filter(EmailTemplate.template_key == "login_success").first()
    assert tpl is not None
    assert tpl.category == "login"
    assert "{{memberInfoBlock}}" in tpl.html_body


def test_member_sample_variables_no_secrets():
    sample = build_member_sample_variables("security_2fa_otp_sent")
    assert sample["verifyUrl"]
    serialized = str(sample)
    assert "otpCode" not in sample
    assert "123456" not in serialized
    assert "password" not in serialized.lower() or "resetUrl" in sample


def test_member_auto_send_settings(db):
    defaults = get_auto_send_settings(db)
    assert defaults.get("login_success") is True
    assert defaults.get("login_failed") is False
    updated = update_auto_send_settings(db, {"login_success": False})
    assert updated["login_success"] is False
    assert should_auto_send(db, "login_success") is False
    assert should_auto_send(db, "login_success", explicit=True) is True


def test_legacy_aliases_cover_old_keys():
    assert LEGACY_TEMPLATE_ALIASES["member_register"] == "member_register_completed"


@patch("services.member_emails.email_configured", return_value=True)
@patch("services.member_emails.send_templated_email")
def test_send_member_event_respects_auto_send(mock_send, _mock_configured, db, test_user):
    from services.email_delivery import SendResult
    from services.member_emails import send_member_event_email

    mock_send.return_value = SendResult(ok=True)

    seed_member_email_templates(db, force_upgrade=True)
    update_auto_send_settings(db, {"login_success": False})
    db.commit()

    ok, err = send_member_event_email(db, "login_success", user=test_user)
    assert ok is True
    mock_send.assert_not_called()

    ok, err = send_member_event_email(
        db, "login_success", user=test_user, send_email=True, force=True
    )
    assert ok is True
    mock_send.assert_called_once()
