"""Profile comparison helpers for identity verification review."""

from __future__ import annotations

from datetime import date
from typing import Literal

import models
import models_buyback
from services.user_profile import format_address, legal_full_name, legal_name_kana

MatchStatus = Literal["match", "partial", "mismatch", "unverified"]

MATCH_LABELS = {
    "match": "一致",
    "partial": "一部不一致",
    "mismatch": "不一致",
    "unverified": "要目視確認",
}


def _normalize_text(value: str | None) -> str:
    if not value:
        return ""
    return " ".join(str(value).strip().split())


def _normalize_date(value: date | str | None) -> str:
    if not value:
        return ""
    if isinstance(value, date):
        return value.isoformat()
    return str(value).strip()


def _field_status(registered: str, submitted: str) -> MatchStatus:
    reg = _normalize_text(registered)
    sub = _normalize_text(submitted)
    if not reg or not sub:
        return "unverified"
    if reg == sub:
        return "match"
    if reg in sub or sub in reg:
        return "partial"
    return "mismatch"


def _overall_status(statuses: list[MatchStatus]) -> MatchStatus:
    if not statuses or all(s == "unverified" for s in statuses):
        return "unverified"
    if all(s == "match" for s in statuses if s != "unverified"):
        if any(s == "unverified" for s in statuses):
            return "partial"
        return "match"
    if any(s == "mismatch" for s in statuses):
        return "mismatch"
    return "partial"


def build_profile_comparison(
    user: models.User | None,
    identity: models_buyback.IdentityVerification,
) -> dict:
    registered_name = legal_full_name(user)
    registered_kana = legal_name_kana(user)
    registered_birth = _normalize_date(user.birth_date if user else None)
    registered_address = user_address_from_user(user)

    submitted_name = identity.submitted_full_name or ""
    submitted_kana = identity.submitted_name_kana or ""
    submitted_birth = _normalize_date(identity.submitted_birth_date)
    submitted_address = format_address(
        postal_code=identity.submitted_postal_code,
        prefecture=identity.submitted_prefecture,
        city=identity.submitted_city,
        address_line1=identity.submitted_address_line1,
        address_line2=identity.submitted_address_line2,
    )

    has_snapshot = bool(submitted_name or submitted_birth or submitted_address)

    name_status = (
        _field_status(registered_name, submitted_name)
        if has_snapshot
        else ("unverified" if registered_name else "mismatch")
    )
    kana_status = (
        _field_status(registered_kana, submitted_kana)
        if submitted_kana
        else "unverified"
    )
    birth_status = (
        _field_status(registered_birth, submitted_birth)
        if has_snapshot
        else ("unverified" if registered_birth else "mismatch")
    )
    address_status = (
        _field_status(registered_address, submitted_address)
        if has_snapshot
        else ("unverified" if registered_address else "mismatch")
    )

    overall = _overall_status([name_status, birth_status, address_status])

    return {
        "overall_status": overall,
        "overall_label": MATCH_LABELS[overall],
        "fields": [
            {
                "key": "name",
                "label": "氏名",
                "registered": registered_name or "—",
                "submitted": submitted_name or "—",
                "status": name_status,
                "status_label": MATCH_LABELS[name_status],
            },
            {
                "key": "name_kana",
                "label": "フリガナ",
                "registered": registered_kana or "—",
                "submitted": submitted_kana or "—",
                "status": kana_status,
                "status_label": MATCH_LABELS[kana_status],
            },
            {
                "key": "birth_date",
                "label": "生年月日",
                "registered": registered_birth or "—",
                "submitted": submitted_birth or "—",
                "status": birth_status,
                "status_label": MATCH_LABELS[birth_status],
            },
            {
                "key": "address",
                "label": "住所",
                "registered": registered_address or "—",
                "submitted": submitted_address or "—",
                "status": address_status,
                "status_label": MATCH_LABELS[address_status],
            },
        ],
        "document_note": (
            "提出時の登録情報と現在の登録情報を自動照合しています。"
            "本人確認書類との一致は画像を目視で確認してください。"
        ),
    }


def user_address_from_user(user: models.User | None) -> str:
    if not user:
        return ""
    return format_address(
        postal_code=user.postal_code,
        prefecture=user.region,
        city=user.city,
        address_line1=user.address_line1,
        address_line2=user.address_line2,
    )


def snapshot_identity_profile(
    identity: models_buyback.IdentityVerification,
    user: models.User,
) -> None:
    identity.submitted_full_name = legal_full_name(user) or None
    identity.submitted_name_kana = legal_name_kana(user) or None
    identity.submitted_birth_date = user.birth_date
    identity.submitted_postal_code = user.postal_code
    identity.submitted_prefecture = user.region
    identity.submitted_city = user.city
    identity.submitted_address_line1 = user.address_line1
    identity.submitted_address_line2 = user.address_line2
