"""Guardian consent workflow tests."""

from __future__ import annotations

from datetime import date
from io import BytesIO
from unittest.mock import patch

import pytest
from fastapi import HTTPException

from auth import hash_password
import models
import models_buyback
from config import settings
from services.buyback_guardian import (
    get_latest_guardian_consent,
    preview_guardian_consent_by_token,
    request_guardian_consent,
    set_guardian_document_type,
    sign_guardian_consent,
    upload_guardian_consent_document,
)
from tests.conftest import auth_headers


def _minor(db) -> models.User:
    user = models.User(
        email="minor@example.com",
        name="Minor User",
        password_hash=hash_password("secret123"),
        is_verified=True,
        birth_date=date(2012, 1, 1),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _user(db) -> models.User:
    return _minor(db)


@patch("services.buyback_guardian.guardian_documents_complete", return_value=True)
@patch("services.buyback_guardian.notify_guardian_consent_requested", return_value=(True, None, None, None))
def test_guardian_consent_request_and_sign(mock_notify, mock_docs, db):
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


def test_guardian_document_upload_requires_document_type(db):
    user = _minor(db)
    front = b"\xff\xd8\xff" + b"fakejpeg"

    with pytest.raises(HTTPException) as exc:
        upload_guardian_consent_document(
            db,
            user_id=user.id,
            side="front",
            content_type="image/jpeg",
            data=front,
        )
    assert exc.value.status_code == 400
    assert "種類を選択" in str(exc.value.detail)


def test_guardian_document_upload_success(db):
    user = _minor(db)
    set_guardian_document_type(db, user_id=user.id, document_type="drivers_license")
    front = b"\xff\xd8\xff" + b"fakejpeg"
    back = b"\x89PNG\r\n" + b"fakepng"

    uploaded_front = upload_guardian_consent_document(
        db,
        user_id=user.id,
        side="front",
        content_type="image/jpeg",
        data=front,
    )
    assert uploaded_front.storage_key_front

    uploaded_back = upload_guardian_consent_document(
        db,
        user_id=user.id,
        side="back",
        content_type="image/png",
        data=back,
    )
    assert uploaded_back.storage_key_back


def test_guardian_document_upload_api(api_client, db):
    user = _minor(db)
    headers = auth_headers(user)
    jpeg = b"\xff\xd8\xff\xe0" + b"0" * 200

    doc_type_res = api_client.post(
        "/api/buyback/guardian-consent/document-type",
        json={"document_type": "drivers_license"},
        headers=headers,
    )
    assert doc_type_res.status_code == 200

    files = {"file": ("test.jpg", BytesIO(jpeg), "image/jpeg")}
    upload_res = api_client.post(
        "/api/buyback/guardian-consent/documents?side=front",
        files=files,
        headers=headers,
    )
    assert upload_res.status_code == 200
    body = upload_res.json()
    assert body["has_front"] is True
    assert body["document_type"] == "drivers_license"
