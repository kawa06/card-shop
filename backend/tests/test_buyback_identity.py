"""Buyback identity (KYC) tests."""

from __future__ import annotations

from datetime import date

import pytest
from fastapi import HTTPException

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


def _identity(db, user_id: int, *, status: str, submitted_at=None) -> models_buyback.IdentityVerification:
    row = models_buyback.IdentityVerification(
        user_id=user_id,
        status=status,
        submitted_at=submitted_at,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


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


def test_pending_without_submitted_at_is_repaired_for_first_upload(db):
    user = _user(db)
    broken = _identity(
        db,
        user.id,
        status=models_buyback.IdentityVerificationStatus.pending.value,
        submitted_at=None,
    )
    front = b"\xff\xd8\xff" + b"fakejpeg"

    row = upload_identity_document(
        db, user_id=user.id, side="front", content_type="image/jpeg", data=front
    )

    assert row.id == broken.id
    assert row.status == models_buyback.IdentityVerificationStatus.not_submitted.value
    assert row.storage_key_front


@pytest.mark.parametrize(
    ("status", "expected_fragment"),
    [
        (models_buyback.IdentityVerificationStatus.pending.value, "現在審査中"),
        (models_buyback.IdentityVerificationStatus.approved.value, "承認済み"),
    ],
)
def test_upload_blocked_with_clear_message(db, status, expected_fragment):
    user = _user(db)
    from datetime import datetime

    _identity(db, user.id, status=status, submitted_at=datetime.utcnow())
    with pytest.raises(HTTPException) as exc:
        upload_identity_document(
            db,
            user_id=user.id,
            side="front",
            content_type="image/jpeg",
            data=b"\xff\xd8\xffjpeg",
        )
    assert exc.value.status_code == 400
    assert expected_fragment in str(exc.value.detail)


def test_resubmit_requested_allows_upload(db):
    user = _user(db)
    row = _identity(
        db,
        user.id,
        status=models_buyback.IdentityVerificationStatus.resubmit_requested.value,
    )
    uploaded = upload_identity_document(
        db,
        user_id=user.id,
        side="front",
        content_type="image/jpeg",
        data=b"\xff\xd8\xffjpeg",
    )
    assert uploaded.id == row.id
    assert uploaded.storage_key_front


def test_expired_allows_upload(db):
    user = _user(db)
    _identity(
        db,
        user.id,
        status=models_buyback.IdentityVerificationStatus.expired.value,
    )
    uploaded = upload_identity_document(
        db,
        user_id=user.id,
        side="front",
        content_type="image/jpeg",
        data=b"\xff\xd8\xffjpeg",
    )
    assert uploaded.storage_key_front


def test_pending_blocks_submit_with_clear_message(db):
    user = _user(db)
    from datetime import datetime

    identity = _identity(
        db,
        user.id,
        status=models_buyback.IdentityVerificationStatus.pending.value,
        submitted_at=datetime.utcnow(),
    )
    identity.storage_key_front = "kyc/test/front.jpg"
    identity.storage_key_back = "kyc/test/back.jpg"
    db.commit()

    with pytest.raises(HTTPException) as exc:
        submit_identity_verification(
            db, user_id=user.id, document_type="drivers_license"
        )
    assert exc.value.status_code == 400
    assert "現在審査中" in str(exc.value.detail)
