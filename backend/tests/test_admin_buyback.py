"""Admin buyback (Phase 7) tests."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi import HTTPException

from auth import hash_password
import models
import models_buyback
from config import settings
from services.buyback_admin import (
    approve_identity,
    complete_request_payout,
    reject_identity,
    update_request_status,
)
from services.buyback_payout_accounts import create_payout_account
from services.buyback_identity import submit_identity_verification, upload_identity_document


@pytest.fixture(autouse=True)
def buyback_dev_settings(monkeypatch):
    monkeypatch.setattr(settings, "DEBUG", True)
    monkeypatch.setattr(settings, "BUYBACK_PAYOUT_ENCRYPTION_KEY", "test-key-for-buyback-payout-32b")


def _admin(db) -> models.User:
    user = models.User(
        email="admin@example.com",
        name="Admin",
        password_hash=hash_password("secret123"),
        is_admin=True,
        is_verified=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _customer(db) -> models.User:
    user = models.User(
        email="customer@example.com",
        name="Customer",
        password_hash=hash_password("secret123"),
        is_verified=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _pending_identity(db, user: models.User) -> models_buyback.IdentityVerification:
    upload_identity_document(
        db,
        user_id=user.id,
        side="front",
        content_type="image/jpeg",
        data=b"\xff\xd8\xffjpeg",
    )
    upload_identity_document(
        db,
        user_id=user.id,
        side="back",
        content_type="image/png",
        data=b"\x89PNG\r\npng",
    )
    return submit_identity_verification(db, user_id=user.id, document_type="drivers_license")


def test_approve_identity(db):
    admin = _admin(db)
    customer = _customer(db)
    identity = _pending_identity(db, customer)

    approved = approve_identity(db, verification_id=identity.id, admin_user=admin)
    assert approved.status == models_buyback.IdentityVerificationStatus.approved.value
    assert approved.reviewed_by_user_id == admin.id
    assert approved.rejection_reason is None


def test_reject_identity_requires_reason(db):
    admin = _admin(db)
    customer = _customer(db)
    identity = _pending_identity(db, customer)

    with pytest.raises(Exception):
        reject_identity(
            db,
            verification_id=identity.id,
            admin_user=admin,
            rejection_reason="",
        )


def test_reject_identity(db):
    admin = _admin(db)
    customer = _customer(db)
    identity = _pending_identity(db, customer)

    rejected = reject_identity(
        db,
        verification_id=identity.id,
        admin_user=admin,
        rejection_reason="画像が不鮮明です",
    )
    assert rejected.status == models_buyback.IdentityVerificationStatus.rejected.value
    assert rejected.rejection_reason == "画像が不鮮明です"


def test_update_request_status_cannot_bypass_barcode_receive(db):
    admin = _admin(db)
    customer = _customer(db)
    request = models_buyback.BuybackRequest(
        user_id=customer.id,
        request_number="KBB-20260720-0001",
        status=models_buyback.BuybackRequestStatus.submitted.value,
        estimated_total=1000,
    )
    db.add(request)
    db.commit()
    db.refresh(request)

    with pytest.raises(HTTPException) as exc_info:
        update_request_status(
            db,
            request_id=request.id,
            admin_user=admin,
            new_status=models_buyback.BuybackRequestStatus.received.value,
            admin_note="着荷確認",
        )
    assert "無効なバーコードです" in str(exc_info.value)
    db.refresh(request)
    assert request.status == models_buyback.BuybackRequestStatus.submitted.value
    assert request.admin_note is None
    assert len(request.status_history) == 0


def _payout_pending_request(db, customer: models.User) -> models_buyback.BuybackRequest:
    create_payout_account(
        db,
        user_id=customer.id,
        bank_name="テスト銀行",
        branch_name="本店",
        account_type="ordinary",
        account_number="1234567",
        account_holder="テスト タロウ",
        set_default=True,
    )
    request = models_buyback.BuybackRequest(
        user_id=customer.id,
        request_number="KBB-20260720-0099",
        status=models_buyback.BuybackRequestStatus.payout_pending.value,
        estimated_total=5000,
        assessed_total=4800,
        payout_total=4800,
    )
    db.add(request)
    db.commit()
    db.refresh(request)
    return request


@patch("services.buyback_admin.notify_buyback_payout_completed", return_value=(True, None))
def test_complete_request_payout(mock_notify, db):
    admin = _admin(db)
    customer = _customer(db)
    request = _payout_pending_request(db, customer)

    updated = complete_request_payout(
        db,
        request_id=request.id,
        admin_user=admin,
        send_email=True,
    )
    assert updated.status == models_buyback.BuybackRequestStatus.paid.value
    assert updated.payout_total == 4800
    assert updated.paid_at is not None
    mock_notify.assert_called_once()


def test_complete_request_payout_requires_account(db):
    admin = _admin(db)
    customer = _customer(db)
    request = models_buyback.BuybackRequest(
        user_id=customer.id,
        request_number="KBB-20260720-0100",
        status=models_buyback.BuybackRequestStatus.payout_pending.value,
        payout_total=1000,
    )
    db.add(request)
    db.commit()
    db.refresh(request)

    with pytest.raises(Exception):
        complete_request_payout(
            db,
            request_id=request.id,
            admin_user=admin,
        )
