"""Field-level encryption for payout bank account numbers."""

from __future__ import annotations

import base64
import hashlib
import logging

from cryptography.fernet import Fernet, InvalidToken

from config import settings

logger = logging.getLogger(__name__)

_DEV_FALLBACK_SECRET = "dev-only-buyback-payout-key-change-me"


def _fernet() -> Fernet:
    secret = (settings.BUYBACK_PAYOUT_ENCRYPTION_KEY or "").strip()
    if not secret:
        if settings.DEBUG:
            secret = _DEV_FALLBACK_SECRET
            logger.warning("BUYBACK_PAYOUT_ENCRYPTION_KEY not set; using DEBUG fallback")
        else:
            raise RuntimeError("BUYBACK_PAYOUT_ENCRYPTION_KEY is not configured")
    digest = hashlib.sha256(secret.encode("utf-8")).digest()
    key = base64.urlsafe_b64encode(digest)
    return Fernet(key)


def encrypt_account_number(raw: str) -> str:
    value = (raw or "").strip()
    if not value:
        raise ValueError("口座番号が空です")
    if not value.isdigit():
        raise ValueError("口座番号は数字のみで入力してください")
    if len(value) < 4 or len(value) > 14:
        raise ValueError("口座番号は4〜14桁で入力してください")
    return _fernet().encrypt(value.encode("utf-8")).decode("utf-8")


def decrypt_account_number(token: str) -> str:
    try:
        return _fernet().decrypt(token.encode("utf-8")).decode("utf-8")
    except InvalidToken as exc:
        raise ValueError("口座番号の復号に失敗しました") from exc


def mask_account_number(raw: str) -> str:
    digits = (raw or "").strip()
    if len(digits) <= 4:
        return "*" * len(digits)
    return "*" * (len(digits) - 4) + digits[-4:]
