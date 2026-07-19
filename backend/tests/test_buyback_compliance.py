"""Buyback compliance status tests."""

from __future__ import annotations

import pytest

from auth import hash_password
import models
import models_buyback
from config import settings
from services.buyback_compliance import get_compliance_status
from services.buyback_payout_accounts import create_payout_account


@pytest.fixture(autouse=True)
def buyback_dev_settings(monkeypatch):
    monkeypatch.setattr(settings, "DEBUG", True)
    monkeypatch.setattr(settings, "BUYBACK_PAYOUT_ENCRYPTION_KEY", "test-key-for-buyback-payout-32b")


def _user(db) -> models.User:
    user = models.User(
        email="compliance@example.com",
        name="Compliance User",
        password_hash=hash_password("secret123"),
        is_verified=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def test_compliance_not_ready_by_default(db):
    user = _user(db)
    status = get_compliance_status(db, user_id=user.id, requires_guardian=False)
    assert status["identity_ready"] is False
    assert status["payout_account_ready"] is False
    assert status["ready_for_payout"] is False


def test_compliance_ready_when_all_complete(db):
    user = _user(db)
    identity = models_buyback.IdentityVerification(
        user_id=user.id,
        status=models_buyback.IdentityVerificationStatus.approved.value,
        storage_key_front="kyc/1/1/front.jpg",
    )
    db.add(identity)
    db.commit()

    create_payout_account(
        db,
        user_id=user.id,
        bank_name="テスト銀行",
        branch_name="本店",
        account_type="ordinary",
        account_number="1234567",
        account_holder="テスト",
    )

    status = get_compliance_status(db, user_id=user.id, requires_guardian=False)
    assert status["identity_ready"] is True
    assert status["payout_account_ready"] is True
    assert status["ready_for_payout"] is True
