"""Tests for inquiry attachment upload tokens."""

from services.inquiry_upload import (
    create_attachment_download_token,
    verify_attachment_download_token,
)


def test_attachment_download_token_roundtrip():
    token = create_attachment_download_token(42, user_id=7)
    payload = verify_attachment_download_token(token)
    assert payload["aid"] == 42
    assert payload["uid"] == 7
    assert payload["adm"] is False


def test_admin_attachment_download_token():
    token = create_attachment_download_token(99, is_admin=True)
    payload = verify_attachment_download_token(token)
    assert payload["aid"] == 99
    assert payload["adm"] is True
