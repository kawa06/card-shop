"""Tests for unified email delivery."""

from __future__ import annotations

from unittest.mock import patch

import models_email
from services.email_delivery import render_template_string, send_templated_email
from services.email_template_seed import seed_email_templates


def test_render_template_string_escapes_html(db):
    out = render_template_string("Hello {{name}}", {"name": "<script>"})
    assert "<script>" not in out
    assert "&lt;script&gt;" in out


def test_send_templated_email_uses_fallback_when_template_inactive(db):
    seed_email_templates(db)
    tpl = (
        db.query(models_email.EmailTemplate)
        .filter(models_email.EmailTemplate.template_key == "order_payment_confirmed")
        .first()
    )
    tpl.is_active = False
    db.commit()

    with patch("services.email_delivery._send_resend", return_value=(True, None, "msg-1")):
        result = send_templated_email(
            db,
            template_key="order_payment_confirmed",
            to_email="buyer@example.com",
            variables={"name": "Tester"},
            fallback_subject="Fallback subject",
            fallback_html="<p>Fallback body</p>",
        )

    assert result.ok is True
    assert result.used_template is False
    log = db.query(models_email.EmailSendLog).order_by(models_email.EmailSendLog.id.desc()).first()
    assert log is not None
    assert log.status == "sent"
    assert log.recipient == "buyer@example.com"


def test_send_templated_email_logs_failure(db):
    seed_email_templates(db)
    with patch("services.email_delivery._send_resend", return_value=(False, "network error", None)):
        result = send_templated_email(
            db,
            template_key="member_login_notify",
            to_email="user@example.com",
            variables={"name": "User"},
            fallback_subject="Login",
            fallback_html="<p>Login notify</p>",
        )

    assert result.ok is False
    log = db.query(models_email.EmailSendLog).order_by(models_email.EmailSendLog.id.desc()).first()
    assert log.status == "failed"
    assert "network error" in (log.error_message or "")
