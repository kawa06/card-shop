"""Best-effort redaction for security logs and audit payloads."""

from __future__ import annotations

import re
from typing import Any

REDACTED = "[redacted]"
OPAQUE_TOKEN_IN_TEXT = re.compile(r"(?<![A-Za-z0-9_-])[A-Za-z0-9_-]{43}(?![A-Za-z0-9_-])")
SENSITIVE_KEY_PARTS = (
    "authorization",
    "cookie",
    "password",
    "proxy_secret",
    "scan_token",
    "scanned_code",
    "secret",
    "token",
)


def redact_text(value: str | None) -> str | None:
    if value is None:
        return None
    return OPAQUE_TOKEN_IN_TEXT.sub(REDACTED, value)


def redact_audit_value(value: Any, *, key: str | None = None) -> Any:
    normalized_key = (key or "").lower()
    if any(part in normalized_key for part in SENSITIVE_KEY_PARTS):
        return REDACTED
    if isinstance(value, dict):
        return {
            item_key: redact_audit_value(item_value, key=str(item_key))
            for item_key, item_value in value.items()
        }
    if isinstance(value, list):
        return [redact_audit_value(item) for item in value]
    if isinstance(value, tuple):
        return [redact_audit_value(item) for item in value]
    if isinstance(value, str):
        return redact_text(value)
    return value
