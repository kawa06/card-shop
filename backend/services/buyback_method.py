"""Normalize buyback method (store vs mail) across DB/API/UI."""

from __future__ import annotations

STORE_ALIASES = frozenset(
    {
        "store",
        "STORE",
        "IN_STORE",
        "in_store",
        "店舗買取",
        "店舗",
    }
)
MAIL_ALIASES = frozenset(
    {
        "mail",
        "MAIL",
        "POSTAL",
        "postal",
        "SHIPPING",
        "shipping",
        "郵送買取",
        "郵送",
    }
)


def normalize_buyback_method(value: str | None) -> str:
    raw = (value or "mail").strip()
    if raw in STORE_ALIASES or raw.lower() == "store":
        return "store"
    if raw in MAIL_ALIASES or raw.lower() == "mail":
        return "mail"
    if raw.lower() in {"store", "mail"}:
        return raw.lower()
    return "mail"


def is_store_purchase(value: str | None) -> bool:
    return normalize_buyback_method(value) == "store"


def is_mail_purchase(value: str | None) -> bool:
    return normalize_buyback_method(value) == "mail"


def buyback_method_label(value: str | None) -> str:
    return "店舗買取" if is_store_purchase(value) else "郵送買取"
