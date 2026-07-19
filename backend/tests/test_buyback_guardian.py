"""Guardian consent workflow tests."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from auth import hash_password
import models
import models_buyback
from services.buyback_guardian import (
    get_latest_guardian_consent,
    preview_guardian_consent_by_token,
    request_guardian_consent,
    sign_guardian_consent,
)


def _user(db) -> models.User:
    user = models.User(
        email="minor@example.com",
        name="Minor User",
        password_hash=hash_password("secret123"),
        is_verified=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@patch("services.buyback_guardian.notify_guardian_consent_requested")
def test_guardian_consent_request_and_sign(mock_notify, db):
    user = _user(db)
    consent, token = request_guardian_consent(
        db,
        user=user,
        guardian_name="保護者 太郎",
        guardian_email="guardian@example.com",
    )
    assert consent.status == models_buyback.GuardianConsentStatus.pending.value
    mock_notify.assert_called_once()

    preview = preview_guardian_consent_by_token(db, token=token)
    assert preview.guardian_name == "保護者 太郎"

    signed = sign_guardian_consent(db, token=token)
    assert signed.status == models_buyback.GuardianConsentStatus.signed.value
    assert signed.signed_at is not None

    latest = get_latest_guardian_consent(db, user.id)
    assert latest.status == models_buyback.GuardianConsentStatus.signed.value
