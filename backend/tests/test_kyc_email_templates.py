"""Tests for KYC / guardian consent email template platform."""

from unittest.mock import patch

from services.kyc_email_auto_send import get_auto_send_settings, should_auto_send, update_auto_send_settings
from services.kyc_email_registry import (
    LEGACY_TEMPLATE_ALIASES,
    KYC_EMAIL_EVENTS,
    normalize_template_key,
    resolve_kyc_template_key,
)
from services.kyc_email_templates_seed import seed_kyc_email_templates
from services.kyc_email_variables import build_kyc_sample_variables
from services.email_template_seed import seed_email_templates


def test_kyc_template_keys_and_legacy_aliases():
    assert resolve_kyc_template_key("buyback_identity_approved") == "kyc_identity_approved"
    assert normalize_template_key("buyback_guardian_consent") == "kyc_guardian_consent_requested"
    assert len(KYC_EMAIL_EVENTS) == 22


def test_seed_kyc_templates(db):
    seed_email_templates(db)
    count = seed_kyc_email_templates(db, force_upgrade=True)
    assert count >= 22

    from models_email import EmailTemplate

    tpl = db.query(EmailTemplate).filter(EmailTemplate.template_key == "kyc_identity_approved").first()
    assert tpl is not None
    assert tpl.category == "kyc"
    assert "{{kycInfoBlock}}" in tpl.html_body


def test_kyc_sample_variables_no_document_urls():
    sample = build_kyc_sample_variables("kyc_identity_approved")
    assert sample["authNo"] == "KYC-000001"
    assert sample["kycInfoBlock"]
    serialized = str(sample)
    assert "storage_key" not in serialized
    assert "kyc/" not in serialized


def test_kyc_auto_send_settings(db):
    defaults = get_auto_send_settings(db)
    assert defaults.get("kyc_identity_approved") is True
    assert defaults.get("kyc_system_error") is False
    updated = update_auto_send_settings(db, {"kyc_identity_approved": False})
    assert updated["kyc_identity_approved"] is False
    assert should_auto_send(db, "kyc_identity_approved") is False
    assert should_auto_send(db, "kyc_identity_approved", explicit=True) is True


def test_legacy_aliases_cover_old_keys():
    assert LEGACY_TEMPLATE_ALIASES["buyback_identity_rejected"] == "kyc_identity_rejected"


@patch("services.kyc_emails.email_configured", return_value=True)
@patch("services.kyc_emails.send_templated_email")
def test_send_kyc_event_respects_auto_send(mock_send, _mock_configured, db, test_user):
    from models_buyback import IdentityVerification, IdentityVerificationStatus
    from services.email_delivery import SendResult
    from services.kyc_emails import send_kyc_event_email

    mock_send.return_value = SendResult(ok=True)

    seed_kyc_email_templates(db, force_upgrade=True)
    update_auto_send_settings(db, {"kyc_identity_approved": False})
    db.commit()

    verification = IdentityVerification(
        user_id=test_user.id,
        status=IdentityVerificationStatus.approved.value,
    )
    db.add(verification)
    db.commit()
    db.refresh(verification)

    ok, err = send_kyc_event_email(
        db, "kyc_identity_approved", user=test_user, verification=verification
    )
    assert ok is True
    mock_send.assert_not_called()

    ok, err = send_kyc_event_email(
        db,
        "kyc_identity_approved",
        user=test_user,
        verification=verification,
        send_email=True,
        force=True,
    )
    assert ok is True
    mock_send.assert_called_once()
