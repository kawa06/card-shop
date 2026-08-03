"""Guardian consent workflow for minor buyback sellers."""

from __future__ import annotations

import hashlib
import logging
import secrets
from datetime import datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

import models
import models_buyback
from config import settings
from services.buyback_emails import notify_guardian_consent_requested
from services.buyback_identity import ALLOWED_DOCUMENT_TYPES
from services.buyback_kyc_storage import delete_kyc_object, upload_guardian_document

logger = logging.getLogger(__name__)

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


def guardian_documents_complete(consent: models_buyback.GuardianConsent | None) -> bool:
    if not consent or not consent.storage_key_front:
        return False
    doc_type = (consent.document_type or "").strip()
    if doc_type == "my_number_card":
        return True
    return bool(consent.storage_key_back)


def _ensure_editable_consent(
    db: Session,
    user_id: int,
    *,
    guardian_name: str | None = None,
    guardian_email: str | None = None,
) -> models_buyback.GuardianConsent:
    latest = get_latest_guardian_consent(db, user_id)
    if latest and latest.status == models_buyback.GuardianConsentStatus.signed.value:
        raise HTTPException(status_code=400, detail="保護者同意は既に完了しています")
    if latest and latest.status == models_buyback.GuardianConsentStatus.pending.value:
        if guardian_name:
            latest.guardian_name = guardian_name.strip()
        if guardian_email:
            latest.guardian_email = guardian_email.strip().lower()
        db.commit()
        db.refresh(latest)
        return latest
    if latest and latest.status == models_buyback.GuardianConsentStatus.expired.value:
        latest.status = models_buyback.GuardianConsentStatus.pending.value
        latest.consent_token_hash = None
        latest.expires_at = None
        latest.signed_at = None
        latest.storage_key_front = None
        latest.storage_key_back = None
        if guardian_name:
            latest.guardian_name = guardian_name.strip()
        if guardian_email:
            latest.guardian_email = guardian_email.strip().lower()
        db.commit()
        db.refresh(latest)
        return latest

    consent = models_buyback.GuardianConsent(
        user_id=user_id,
        guardian_name=(guardian_name or "").strip() or None,
        guardian_email=(guardian_email or "").strip().lower() or None,
        status=models_buyback.GuardianConsentStatus.pending.value,
    )
    db.add(consent)
    db.commit()
    db.refresh(consent)
    return consent


def upload_guardian_consent_document(
    db: Session,
    *,
    user_id: int,
    side: str,
    content_type: str | None,
    data: bytes,
) -> models_buyback.GuardianConsent:
    if side not in ("front", "back"):
        raise HTTPException(status_code=400, detail="side は front または back を指定してください")

    consent = _ensure_editable_consent(db, user_id)
    if consent.status == models_buyback.GuardianConsentStatus.signed.value:
        raise HTTPException(status_code=400, detail="同意済みのため書類を更新できません")

    side_label = "表面" if side == "front" else "裏面"
    previous_key = consent.storage_key_front if side == "front" else consent.storage_key_back

    try:
        key = upload_guardian_document(
            user_id=user_id,
            consent_id=consent.id,
            side=side,
            content_type=content_type,
            data=data,
        )
    except ValueError as exc:
        logger.warning(
            "guardian_upload_rejected user_id=%s consent_id=%s side=%s size=%s mime=%s",
            user_id,
            consent.id,
            side,
            len(data or b""),
            (content_type or "")[:64],
        )
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        logger.error(
            "guardian_upload_failed user_id=%s consent_id=%s side=%s size=%s mime=%s",
            user_id,
            consent.id,
            side,
            len(data or b""),
            (content_type or "")[:64],
        )
        raise HTTPException(
            status_code=503,
            detail=f"保護者本人確認書類の{side_label}をアップロードできませんでした。時間をおいて再度お試しください。",
        ) from exc
    except Exception as exc:
        logger.error(
            "guardian_upload_failed user_id=%s consent_id=%s side=%s err=%s",
            user_id,
            consent.id,
            side,
            type(exc).__name__,
        )
        raise HTTPException(
            status_code=500,
            detail=f"保護者本人確認書類の{side_label}をアップロードできませんでした。時間をおいて再度お試しください。",
        ) from exc

    if side == "front":
        consent.storage_key_front = key
    else:
        consent.storage_key_back = key
    db.commit()
    db.refresh(consent)

    if previous_key and previous_key != key:
        delete_kyc_object(previous_key)

    return consent


def set_guardian_document_type(
    db: Session,
    *,
    user_id: int,
    document_type: str,
) -> models_buyback.GuardianConsent:
    doc_type = (document_type or "").strip()
    if doc_type not in ALLOWED_DOCUMENT_TYPES:
        raise HTTPException(status_code=400, detail="保護者本人確認書類の種類が不正です")

    consent = _ensure_editable_consent(db, user_id)
    if consent.status == models_buyback.GuardianConsentStatus.signed.value:
        raise HTTPException(status_code=400, detail="同意済みのため書類種別を更新できません")

    consent.document_type = doc_type
    if doc_type == "my_number_card":
        consent.storage_key_back = None
    db.commit()
    db.refresh(consent)
    return consent


def request_guardian_consent(
    db: Session,
    *,
    user: models.User,
    guardian_name: str,
    guardian_email: str,
    resend: bool = False,
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

    consent = _ensure_editable_consent(
        db, user.id, guardian_name=name, guardian_email=email
    )
    if not guardian_documents_complete(consent):
        raise HTTPException(
            status_code=400,
            detail="保護者の本人確認書類をアップロードしてから依頼してください",
        )

    now = datetime.utcnow()
    if (
        not resend
        and consent.consent_token_hash
        and consent.expires_at
        and consent.expires_at > now
    ):
        raise HTTPException(
            status_code=409,
            detail="同意依頼メールは既に送信済みです。「再送」から再度送信できます。",
        )

    raw_token = secrets.token_urlsafe(CONSENT_TOKEN_BYTES)
    expires_at = datetime.utcnow() + timedelta(days=settings.BUYBACK_GUARDIAN_CONSENT_EXPIRE_DAYS)
    consent.consent_token_hash = _hash_token(raw_token)
    consent.expires_at = expires_at
    db.commit()
    db.refresh(consent)
    email_ok, email_err, error_code, user_message = notify_guardian_consent_requested(
        db, consent, user, raw_token
    )
    if not email_ok:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "message": user_message
                or "保護者へのメール送信に失敗しました。メールアドレスを確認して再度お試しください。",
                "error_code": error_code or "mail_send_failed",
                "technical_detail": email_err,
            },
        )
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
    if not guardian_documents_complete(consent):
        raise HTTPException(status_code=400, detail="保護者の本人確認書類が未登録です")

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
