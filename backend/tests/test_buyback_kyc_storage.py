"""KYC storage backend selection and error handling tests."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from config import settings
import services.buyback_kyc_storage as storage


@pytest.fixture(autouse=True)
def reset_debug(monkeypatch):
    monkeypatch.setattr(settings, "DEBUG", False)


def test_storage_prefers_s3_over_api(monkeypatch):
    monkeypatch.setattr(settings, "R2_ACCOUNT_ID", "acct")
    monkeypatch.setattr(settings, "R2_BUCKET_NAME", "bucket")
    monkeypatch.setattr(settings, "R2_API_TOKEN", "token")
    monkeypatch.setattr(settings, "R2_ACCESS_KEY_ID", "a" * 36)
    monkeypatch.setattr(settings, "R2_SECRET_ACCESS_KEY", "s" * 32)

    with patch.object(storage, "_upload_r2_s3") as s3_upload, patch.object(
        storage, "_upload_cf_api"
    ) as api_upload:
        storage._store_object(key="kyc/1/2/front/x.jpg", data=b"x", content_type="image/jpeg")

    s3_upload.assert_called_once()
    api_upload.assert_not_called()


def test_storage_falls_back_to_api_when_s3_fails(monkeypatch):
    monkeypatch.setattr(settings, "R2_ACCOUNT_ID", "acct")
    monkeypatch.setattr(settings, "R2_BUCKET_NAME", "bucket")
    monkeypatch.setattr(settings, "R2_API_TOKEN", "token")
    monkeypatch.setattr(settings, "R2_ACCESS_KEY_ID", "a" * 36)
    monkeypatch.setattr(settings, "R2_SECRET_ACCESS_KEY", "s" * 32)

    with patch.object(
        storage,
        "_upload_r2_s3",
        side_effect=RuntimeError(storage.KYC_STORAGE_USER_MESSAGE),
    ) as s3_upload, patch.object(storage, "_upload_cf_api") as api_upload:
        storage._store_object(key="kyc/guardian/1/2/front/x.jpg", data=b"x", content_type="image/jpeg")

    s3_upload.assert_called_once()
    api_upload.assert_called_once()


def test_unconfigured_storage_raises_user_message(monkeypatch):
    monkeypatch.setattr(settings, "R2_ACCOUNT_ID", None)
    monkeypatch.setattr(settings, "R2_BUCKET_NAME", None)
    monkeypatch.setattr(settings, "R2_API_TOKEN", None)
    monkeypatch.setattr(settings, "R2_ACCESS_KEY_ID", None)
    monkeypatch.setattr(settings, "R2_SECRET_ACCESS_KEY", None)

    with pytest.raises(RuntimeError, match="画像保存サーバーへ接続できませんでした"):
        storage.upload_guardian_document(
            user_id=1,
            consent_id=2,
            side="front",
            content_type="image/jpeg",
            data=b"\xff\xd8\xffjpeg",
        )
