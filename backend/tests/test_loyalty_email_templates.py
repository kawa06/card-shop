"""Tests for point/coupon/rank email template platform."""

from unittest.mock import patch

from services.loyalty_email_auto_send import get_auto_send_settings, should_auto_send, update_auto_send_settings
from services.loyalty_email_registry import LEGACY_TEMPLATE_ALIASES, LOYALTY_EMAIL_EVENTS, normalize_template_key
from services.loyalty_email_templates_seed import seed_loyalty_email_templates
from services.loyalty_email_variables import build_loyalty_sample_variables
from services.email_template_seed import seed_email_templates


def test_loyalty_template_keys_and_legacy_aliases():
    assert normalize_template_key("coupon_issued") == "coupon_distributed"
    assert normalize_template_key("point_referral") == "point_granted"
    assert len(LOYALTY_EMAIL_EVENTS) == 25


def test_seed_loyalty_templates(db):
    seed_email_templates(db)
    count = seed_loyalty_email_templates(db, force_upgrade=True)
    assert count >= 25

    from models_email import EmailTemplate

    tpl = db.query(EmailTemplate).filter(EmailTemplate.template_key == "point_granted").first()
    assert tpl is not None
    assert tpl.category == "point"
    assert "{{loyaltyInfoBlock}}" in tpl.html_body

    rank_tpl = db.query(EmailTemplate).filter(EmailTemplate.template_key == "rank_up").first()
    assert rank_tpl is not None
    assert rank_tpl.category == "rank"


def test_loyalty_sample_variables():
    sample = build_loyalty_sample_variables("coupon_distributed")
    assert sample["couponName"]
    assert sample["currentPoints"]
    assert sample["loyaltyInfoBlock"]


def test_loyalty_auto_send_settings(db):
    defaults = get_auto_send_settings(db)
    assert defaults.get("point_granted") is True
    assert defaults.get("loyalty_system_error") is False
    updated = update_auto_send_settings(db, {"point_granted": False})
    assert updated["point_granted"] is False
    assert should_auto_send(db, "point_granted") is False
    assert should_auto_send(db, "point_granted", explicit=True) is True


def test_legacy_aliases_cover_old_keys():
    assert LEGACY_TEMPLATE_ALIASES["coupon_issued"] == "coupon_distributed"


@patch("services.loyalty_emails.email_configured", return_value=True)
@patch("services.loyalty_emails.send_templated_email")
def test_send_loyalty_event_respects_auto_send(mock_send, _mock_configured, db, test_user):
    from services.email_delivery import SendResult
    from services.loyalty_emails import send_loyalty_event_email
    from services.loyalty_email_variables import LoyaltyEmailSnapshot

    mock_send.return_value = SendResult(ok=True)

    seed_loyalty_email_templates(db, force_upgrade=True)
    update_auto_send_settings(db, {"point_granted": False})
    db.commit()

    snapshot = LoyaltyEmailSnapshot(granted_points="100 pt", current_points="500 pt")
    ok, err = send_loyalty_event_email(db, "point_granted", user=test_user, snapshot=snapshot)
    assert ok is True
    mock_send.assert_not_called()

    ok, err = send_loyalty_event_email(
        db, "point_granted", user=test_user, snapshot=snapshot, send_email=True, force=True
    )
    assert ok is True
    mock_send.assert_called_once()
