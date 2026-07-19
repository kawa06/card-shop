"""Buyback payout encryption and account tests."""

from __future__ import annotations

import pytest

from auth import hash_password
import models
from config import settings
from services.buyback_payout_accounts import (
    create_payout_account,
    delete_payout_account,
    list_payout_accounts_masked,
    set_default_payout_account,
)
from services.buyback_payout_crypto import decrypt_account_number, encrypt_account_number, mask_account_number


@pytest.fixture(autouse=True)
def buyback_dev_settings(monkeypatch):
    monkeypatch.setattr(settings, "DEBUG", True)
    monkeypatch.setattr(settings, "BUYBACK_PAYOUT_ENCRYPTION_KEY", "test-key-for-buyback-payout-32b")


def _user(db, email="payout@example.com") -> models.User:
    user = models.User(
        email=email,
        name="Payout User",
        password_hash=hash_password("secret123"),
        is_verified=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def test_encrypt_decrypt_roundtrip():
    token = encrypt_account_number("1234567")
    assert decrypt_account_number(token) == "1234567"
    assert mask_account_number("1234567") == "***4567"


def test_create_and_list_payout_account(db):
    user = _user(db)
    created = create_payout_account(
        db,
        user_id=user.id,
        bank_name="テスト銀行",
        branch_name="本店",
        account_type="ordinary",
        account_number="1234567",
        account_holder="テスト タロウ",
    )
    assert created["account_number_masked"].endswith("4567")
    assert created["is_default"] is True

    rows = list_payout_accounts_masked(db, user.id)
    assert len(rows) == 1
    assert rows[0]["bank_name"] == "テスト銀行"


def test_set_default_and_delete_payout_account(db):
    user = _user(db, email="payout2@example.com")
    first = create_payout_account(
        db,
        user_id=user.id,
        bank_name="A銀行",
        branch_name=None,
        account_type="ordinary",
        account_number="1111111",
        account_holder="A",
    )
    second = create_payout_account(
        db,
        user_id=user.id,
        bank_name="B銀行",
        branch_name=None,
        account_type="checking",
        account_number="2222222",
        account_holder="B",
        set_default=True,
    )
    assert second["is_default"] is True

    updated = set_default_payout_account(db, user_id=user.id, account_id=first["id"])
    assert updated["is_default"] is True

    delete_payout_account(db, user_id=user.id, account_id=first["id"])
    remaining = list_payout_accounts_masked(db, user.id)
    assert len(remaining) == 1
    assert remaining[0]["is_default"] is True
