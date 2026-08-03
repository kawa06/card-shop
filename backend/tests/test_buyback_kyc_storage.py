"""KYC upload validation tests."""

from __future__ import annotations

import pytest

from services.buyback_kyc_storage import _validate_upload


def test_validate_upload_accepts_jpeg_magic_bytes_without_content_type():
    data = b"\xff\xd8\xff\xe0" + b"0" * 100
    assert _validate_upload(None, data) == ".jpg"


def test_validate_upload_rejects_empty_file():
    with pytest.raises(ValueError, match="空"):
        _validate_upload("image/jpeg", b"")


def test_validate_upload_rejects_oversized_file():
    data = b"\xff\xd8\xff\xe0" + b"0" * (10 * 1024 * 1024)
    with pytest.raises(ValueError, match="10MB"):
        _validate_upload("image/jpeg", data)


def test_normalize_access_key_strips_dashes():
    from services.buyback_kyc_storage import _normalize_access_key_id

    uuid_key = "70827082-bae0-3f52-6b6f-b2514949fecb"
    assert len(_normalize_access_key_id(uuid_key)) == 32


def test_validate_upload_rejects_unknown_format():
    with pytest.raises(ValueError, match="対応していない"):
        _validate_upload("text/plain", b"not-an-image" * 10)
