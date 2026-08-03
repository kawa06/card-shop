"""Extensible audience targeting for announcement/campaign email broadcasts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any, Callable

from sqlalchemy import distinct, func
from sqlalchemy.orm import Session

import models


@dataclass(frozen=True)
class AudienceSegmentDef:
    segment_key: str
    label: str
    description: str
    requires_params: bool = False


AUDIENCE_SEGMENTS: dict[str, AudienceSegmentDef] = {
    "all_verified": AudienceSegmentDef("all_verified", "全ユーザー", "メール認証済みの全会員"),
    "kyc_verified": AudienceSegmentDef("kyc_verified", "本人確認済みのみ", "本人確認が承認済みの会員"),
    "minors": AudienceSegmentDef("minors", "未成年のみ", "18歳未満の会員"),
    "guardians": AudienceSegmentDef("guardians", "保護者", "保護者同意が登録されている会員"),
    "buyers_only": AudienceSegmentDef("buyers_only", "購入者のみ", "過去に購入履歴がある会員"),
    "buyback_users": AudienceSegmentDef("buyback_users", "買取利用者のみ", "買取申請履歴がある会員"),
    "point_holders": AudienceSegmentDef("point_holders", "ポイント保有者", "ポイント残高を保有する会員（将来拡張）"),
    "by_rank": AudienceSegmentDef("by_rank", "ランク別", "指定会員ランクの会員（将来拡張）", requires_params=True),
    "admins": AudienceSegmentDef("admins", "管理者", "管理者アカウント"),
    "test_users": AudienceSegmentDef("test_users", "テストユーザー", "テスト用メールアドレス"),
    "specific_users": AudienceSegmentDef("specific_users", "任意ユーザー", "ユーザーIDを指定", requires_params=True),
    "custom_emails": AudienceSegmentDef("custom_emails", "メールアドレス指定", "メールアドレスを直接指定", requires_params=True),
}

DEFAULT_AUDIENCE_KEY = "all_verified"


def list_audience_segments() -> list[dict[str, Any]]:
    return [
        {
            "segment_key": seg.segment_key,
            "label": seg.label,
            "description": seg.description,
            "requires_params": seg.requires_params,
        }
        for seg in AUDIENCE_SEGMENTS.values()
    ]


def _base_email_query(db: Session):
    return db.query(models.User).filter(
        models.User.email.isnot(None),
        models.User.email != "",
    )


def _verified_users(db: Session) -> list[models.User]:
    return (
        _base_email_query(db)
        .filter(models.User.is_verified.is_(True))
        .order_by(models.User.id)
        .all()
    )


def _age_years(birth_date: date, on: date | None = None) -> int:
    on = on or date.today()
    years = on.year - birth_date.year
    if (on.month, on.day) < (birth_date.month, birth_date.day):
        years -= 1
    return years


def _resolve_kyc_verified(db: Session) -> list[models.User]:
    try:
        import models_buyback

        approved_user_ids = (
            db.query(distinct(models_buyback.IdentityVerification.user_id))
            .filter(models_buyback.IdentityVerification.status == "approved")
            .subquery()
        )
        return (
            _base_email_query(db)
            .filter(
                models.User.is_verified.is_(True),
                models.User.id.in_(db.query(approved_user_ids.c.user_id)),
            )
            .order_by(models.User.id)
            .all()
        )
    except Exception:
        return []


def _resolve_minors(db: Session) -> list[models.User]:
    users = _verified_users(db)
    return [u for u in users if u.birth_date and _age_years(u.birth_date) < 18]


def _resolve_guardians(db: Session) -> list[models.User]:
    try:
        import models_buyback

        guardian_user_ids = (
            db.query(distinct(models_buyback.GuardianConsent.user_id))
            .filter(models_buyback.GuardianConsent.status == "signed")
            .subquery()
        )
        return (
            _base_email_query(db)
            .filter(
                models.User.is_verified.is_(True),
                models.User.id.in_(db.query(guardian_user_ids.c.user_id)),
            )
            .order_by(models.User.id)
            .all()
        )
    except Exception:
        return []


def _resolve_buyers(db: Session) -> list[models.User]:
    buyer_ids = db.query(distinct(models.Order.user_id)).filter(models.Order.user_id.isnot(None)).subquery()
    return (
        _base_email_query(db)
        .filter(
            models.User.is_verified.is_(True),
            models.User.id.in_(db.query(buyer_ids.c.user_id)),
        )
        .order_by(models.User.id)
        .all()
    )


def _resolve_buyback_users(db: Session) -> list[models.User]:
    try:
        import models_buyback

        buyback_ids = db.query(distinct(models_buyback.BuybackRequest.user_id)).subquery()
        return (
            _base_email_query(db)
            .filter(
                models.User.is_verified.is_(True),
                models.User.id.in_(db.query(buyback_ids.c.user_id)),
            )
            .order_by(models.User.id)
            .all()
        )
    except Exception:
        return []


def _resolve_point_holders(db: Session, params: dict[str, Any]) -> list[models.User]:
    # Placeholder until points ledger exists — extensible via params without code changes later.
    _ = params
    return []


def _resolve_by_rank(db: Session, params: dict[str, Any]) -> list[models.User]:
    # Placeholder until member rank exists.
    _ = params.get("rank_name")
    return []


def _resolve_admins(db: Session) -> list[models.User]:
    return (
        _base_email_query(db)
        .filter(models.User.is_admin.is_(True))
        .order_by(models.User.id)
        .all()
    )


def _resolve_test_users(db: Session) -> list[models.User]:
    return (
        _base_email_query(db)
        .filter(
            models.User.is_verified.is_(True),
            models.User.email.ilike("%+test%"),
        )
        .order_by(models.User.id)
        .all()
    )


def _resolve_specific_users(db: Session, params: dict[str, Any]) -> list[models.User]:
    raw_ids = params.get("user_ids") or params.get("userIds") or []
    if isinstance(raw_ids, str):
        raw_ids = [x.strip() for x in raw_ids.split(",") if x.strip()]
    ids = [int(x) for x in raw_ids if str(x).isdigit()]
    if not ids:
        return []
    return (
        _base_email_query(db)
        .filter(models.User.id.in_(ids))
        .order_by(models.User.id)
        .all()
    )


def _resolve_custom_emails(db: Session, params: dict[str, Any]) -> list[models.User]:
    raw = params.get("emails") or params.get("email_list") or []
    if isinstance(raw, str):
        raw = [x.strip() for x in raw.replace("\n", ",").split(",") if x.strip()]
    emails = [str(e).strip().lower() for e in raw if str(e).strip()]
    if not emails:
        return []
    found = (
        _base_email_query(db)
        .filter(func.lower(models.User.email).in_(emails))
        .order_by(models.User.id)
        .all()
    )
    found_emails = {u.email.lower() for u in found}
    # Synthetic users for addresses not in DB (send-only list entries).
    extras: list[models.User] = []
    for email in emails:
        if email not in found_emails:
            ghost = models.User(id=0, email=email, name=email.split("@")[0], password_hash="", is_verified=True)
            extras.append(ghost)
    return found + extras


_RESOLVERS: dict[str, Callable[..., list[models.User]]] = {
    "all_verified": lambda db, params: _verified_users(db),
    "kyc_verified": lambda db, params: _resolve_kyc_verified(db),
    "minors": lambda db, params: _resolve_minors(db),
    "guardians": lambda db, params: _resolve_guardians(db),
    "buyers_only": lambda db, params: _resolve_buyers(db),
    "buyback_users": lambda db, params: _resolve_buyback_users(db),
    "point_holders": _resolve_point_holders,
    "by_rank": _resolve_by_rank,
    "admins": lambda db, params: _resolve_admins(db),
    "test_users": lambda db, params: _resolve_test_users(db),
    "specific_users": _resolve_specific_users,
    "custom_emails": _resolve_custom_emails,
}


def parse_audience_params(raw: str | dict | None) -> dict[str, Any]:
    import json

    if isinstance(raw, dict):
        return raw
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, dict) else {}
    except json.JSONDecodeError:
        return {}


def resolve_audience(
    db: Session,
    segment_key: str,
    params: dict[str, Any] | None = None,
) -> tuple[list[models.User], str]:
    key = segment_key if segment_key in AUDIENCE_SEGMENTS else DEFAULT_AUDIENCE_KEY
    seg = AUDIENCE_SEGMENTS[key]
    resolver = _RESOLVERS.get(key, _RESOLVERS[DEFAULT_AUDIENCE_KEY])
    recipients = resolver(db, params or {})
    # Deduplicate by email
    seen: set[str] = set()
    unique: list[models.User] = []
    for user in recipients:
        email = (user.email or "").strip().lower()
        if not email or email in seen:
            continue
        seen.add(email)
        unique.append(user)
    return unique, seg.label
