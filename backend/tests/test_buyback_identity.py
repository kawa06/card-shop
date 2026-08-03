"""Buyback identity (KYC) tests."""

from __future__ import annotations

from datetime import date

import pytest

from auth import hash_password
import models
import models_buyback
from config import settings
from services.buyback_identity import (
    get_or_create_identity,
    submit_identity_verification,
    upload_identity_document,
)


@pytest.fixture(autouse=True)
def buyback_dev_settings(monkeypatch):
    monkeypatch.setattr(settings, "DEBUG", True)


def _user(db) -> models.User:
    user = models.User(
        email="kyc@example.com",
        name="KYC User",
        family_name="山田",
        given_name="太郎",
        password_hash=hash_password("secret123"),
        is_verified=True,
        birth_date=date(1990, 1, 1),
        postal_code="1000001",
        region="東京都",
        city="千代田区",
        address_line1="1-1",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def test_upload_and_submit_identity(db):
    user = _user(db)
    front = b"\xff\xd8\xff" + b"fakejpeg"
    back = b"\x89PNG\r\n" + b"fakepng"

    upload_identity_document(
        db, user_id=user.id, side="front", content_type="image/jpeg", data=front
    )
    upload_identity_document(
        db, user_id=user.id, side="back", content_type="image/png", data=back
    )

    row = submit_identity_verification(
        db, user_id=user.id, document_type="drivers_license"
    )
    assert row.status == models_buyback.IdentityVerificationStatus.pending.value
    assert row.storage_key_front
    assert row.storage_key_back


def test_my_number_card_requires_front_only(db):
    user = _user(db)
    upload_identity_document(
        db,
        user_id=user.id,
        side="front",
        content_type="image/jpeg",
        data=b"\xff\xd8\xffjpeg",
    )
    row = submit_identity_verification(
        db, user_id=user.id, document_type="my_number_card"
    )
    assert row.status == models_buyback.IdentityVerificationStatus.pending.value


def test_get_or_create_identity_is_idempotent(db):
    user = _user(db)
    first = get_or_create_identity(db, user.id)
    second = get_or_create_identity(db, user.id)
    assert first.id == second.id
