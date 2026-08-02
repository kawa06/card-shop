"""Guardian consent workflow for minor buyback sellers."""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

import models
import models_buyback
from config import settings
from services.buyback_emails import notify_guardian_consent_requested

CONSENT_TOKEN_BYTES = 32


def _hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def get_latest_guardian_consent(
    db: Session, user_id: int
) -> models_buyback.GuardianConsent | None:
    return (
        db.query(models_buyback.GuardianConsent)
        .filter(models_buyback.GuardianConsent.user_id == user_id)
        .order_by(models_buyback.GuardianConsent.id.desc())
        .first()
    )


def request_guardian_consent(
    db: Session,
    *,
    user: models.User,
    guardian_name: str,
    guardian_email: str,
) -> tuple[models_buyback.GuardianConsent, str]:
    name = (guardian_name or "").strip()
    email = (guardian_email or "").strip().lower()
    if not name:
        raise HTTPException(status_code=400, detail="保護者氏名を入力してください")
    if not email or "@" not in email:
        raise HTTPException(status_code=400, detail="保護者メールアドレスが不正です")

    latest = get_latest_guardian_consent(db, user.id)
    if latest and latest.status == models_buyback.GuardianConsentStatus.signed.value:
        raise HTTPException(status_code=400, detail="保護者同意は既に完了しています")

    raw_token = secrets.token_urlsafe(CONSENT_TOKEN_BYTES)
    expires_at = datetime.utcnow() + timedelta(days=settings.BUYBACK_GUARDIAN_CONSENT_EXPIRE_DAYS)

    consent = models_buyback.GuardianConsent(
        user_id=user.id,
        guardian_name=name,
        guardian_email=email,
        consent_token_hash=_hash_token(raw_token),
        status=models_buyback.GuardianConsentStatus.pending.value,
        expires_at=expires_at,
    )
    db.add(consent)
    db.commit()
    db.refresh(consent)

    notify_guardian_consent_requested(db, consent, user, raw_token)
    return consent, raw_token


def sign_guardian_consent(db: Session, *, token: str) -> models_buyback.GuardianConsent:
    raw = (token or "").strip()
    if not raw:
        raise HTTPException(status_code=400, detail="同意トークンが必要です")

    token_hash = _hash_token(raw)
    consent = (
        db.query(models_buyback.GuardianConsent)
        .filter(models_buyback.GuardianConsent.consent_token_hash == token_hash)
        .first()
    )
    if not consent:
        raise HTTPException(status_code=404, detail="同意リンクが無効です")
    if consent.status == models_buyback.GuardianConsentStatus.signed.value:
        return consent
    if consent.expires_at and consent.expires_at < datetime.utcnow():
        consent.status = models_buyback.GuardianConsentStatus.expired.value
        db.commit()
        raise HTTPException(status_code=410, detail="同意リンクの有効期限が切れています")

    consent.status = models_buyback.GuardianConsentStatus.signed.value
    consent.signed_at = datetime.utcnow()
    consent.consent_token_hash = None
    db.commit()
    db.refresh(consent)
    return consent


def preview_guardian_consent_by_token(
    db: Session, *, token: str
) -> models_buyback.GuardianConsent:
    raw = (token or "").strip()
    if not raw:
        raise HTTPException(status_code=400, detail="同意トークンが必要です")
    consent = (
        db.query(models_buyback.GuardianConsent)
        .filter(models_buyback.GuardianConsent.consent_token_hash == _hash_token(raw))
        .first()
    )
    if not consent:
        raise HTTPException(status_code=404, detail="同意リンクが無効です")
    if consent.expires_at and consent.expires_at < datetime.utcnow():
        raise HTTPException(status_code=410, detail="同意リンクの有効期限が切れています")
    return consent
