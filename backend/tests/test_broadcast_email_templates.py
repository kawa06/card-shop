"""Tests for announcement/campaign broadcast email template platform."""

from services.broadcast_audience_registry import DEFAULT_AUDIENCE_KEY, resolve_audience
from services.broadcast_email_registry import BROADCAST_EMAIL_EVENTS, LEGACY_TEMPLATE_ALIASES, normalize_template_key
from services.broadcast_email_templates_seed import seed_broadcast_email_templates
from services.broadcast_email_variables import build_broadcast_sample_variables
from services.email_template_seed import seed_email_templates


def test_broadcast_template_keys_and_legacy_aliases():
    assert normalize_template_key("announcement_broadcast") == "broadcast_notice_important"
    assert normalize_template_key("maintenance_notice") == "broadcast_maintenance_scheduled"
    assert len(BROADCAST_EMAIL_EVENTS) == 17


def test_seed_broadcast_templates(db):
    seed_email_templates(db)
    count = seed_broadcast_email_templates(db, force_upgrade=True)
    assert count >= 17

    from models_email import EmailTemplate

    tpl = db.query(EmailTemplate).filter(EmailTemplate.template_key == "broadcast_notice_important").first()
    assert tpl is not None
    assert tpl.category == "notice"
    assert "{{broadcastInfoBlock}}" in tpl.html_body
    assert "{{imageBlock}}" in tpl.html_body


def test_broadcast_sample_variables():
    sample = build_broadcast_sample_variables("broadcast_promo_start")
    assert sample["noticeTitle"]
    assert sample["imageBlock"]
    assert sample["broadcastInfoBlock"]


def test_resolve_all_verified_audience(db, test_user):
    test_user.is_verified = True
    db.commit()
    recipients, label = resolve_audience(db, DEFAULT_AUDIENCE_KEY, {})
    assert label
    assert any(u.email == test_user.email for u in recipients)


def test_legacy_aliases_cover_old_keys():
    assert LEGACY_TEMPLATE_ALIASES["incident_resolved"] == "broadcast_incident_recovered"
