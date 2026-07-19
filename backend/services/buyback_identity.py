"""Identity verification (KYC) for buyback."""

from __future__ import annotations

from datetime import datetime

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

import models_buyback
from services.buyback_kyc_storage import upload_kyc_document

ALLOWED_DOCUMENT_TYPES = {
    "drivers_license",
    "my_number_card",
    "passport",
    "residence_card",
}

EDITABLE_STATUSES = {
    models_buyback.IdentityVerificationStatus.not_submitted.value,
    models_buyback.IdentityVerificationStatus.rejected.value,
}


def get_or_create_identity(db: Session, user_id: int) -> models_buyback.IdentityVerification:
    row = (
        db.query(models_buyback.IdentityVerification)
        .filter(models_buyback.IdentityVerification.user_id == user_id)
        .order_by(models_buyback.IdentityVerification.id.desc())
        .first()
    )
    if row:
        return row
    row = models_buyback.IdentityVerification(
        user_id=user_id,
        status=models_buyback.IdentityVerificationStatus.not_submitted.value,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def upload_identity_document(
    db: Session,
    *,
    user_id: int,
    side: str,
    content_type: str | None,
    data: bytes,
) -> models_buyback.IdentityVerification:
    if side not in ("front", "back"):
        raise HTTPException(status_code=400, detail="side は front または back を指定してください")

    identity = get_or_create_identity(db, user_id)
    if identity.status not in EDITABLE_STATUSES:
        raise HTTPException(
            status_code=400,
            detail="現在の本人確認ステータスでは書類を更新できません",
        )

    try:
        key = upload_kyc_document(
            user_id=user_id,
            verification_id=identity.id,
            side=side,
            content_type=content_type,
            data=data,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    if side == "front":
        identity.storage_key_front = key
    else:
        identity.storage_key_back = key
    identity.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(identity)
    return identity


def submit_identity_verification(
    db: Session,
    *,
    user_id: int,
    document_type: str,
) -> models_buyback.IdentityVerification:
    doc_type = (document_type or "").strip()
    if doc_type not in ALLOWED_DOCUMENT_TYPES:
        raise HTTPException(status_code=400, detail="本人確認書類の種類が不正です")

    identity = get_or_create_identity(db, user_id)
    if identity.status not in EDITABLE_STATUSES:
        raise HTTPException(
            status_code=400,
            detail="現在の本人確認ステータスでは再提出できません",
        )
    if not identity.storage_key_front:
        raise HTTPException(status_code=400, detail="本人確認書類（表面）をアップロードしてください")
    if doc_type != "my_number_card" and not identity.storage_key_back:
        raise HTTPException(status_code=400, detail="本人確認書類（裏面）をアップロードしてください")

    now = datetime.utcnow()
    identity.document_type = doc_type
    identity.status = models_buyback.IdentityVerificationStatus.pending.value
    identity.submitted_at = now
    identity.updated_at = now
    identity.rejection_reason = None
    db.commit()
    db.refresh(identity)
    return identity
