"""Identity verification (KYC) for buyback."""

from __future__ import annotations

import logging
from datetime import datetime

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

import models
import models_buyback
from services.buyback_kyc_storage import delete_kyc_object, upload_kyc_document

logger = logging.getLogger(__name__)

ALLOWED_DOCUMENT_TYPES = {
    "drivers_license",
    "my_number_card",
    "passport",
    "residence_card",
}

EDITABLE_STATUSES = {
    models_buyback.IdentityVerificationStatus.not_submitted.value,
    models_buyback.IdentityVerificationStatus.rejected.value,
    models_buyback.IdentityVerificationStatus.resubmit_requested.value,
}

_SIDE_LABELS = {"front": "表面", "back": "裏面"}


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

    side_label = _SIDE_LABELS.get(side, side)
    previous_key = identity.storage_key_front if side == "front" else identity.storage_key_back

    try:
        key = upload_kyc_document(
            user_id=user_id,
            verification_id=identity.id,
            side=side,
            content_type=content_type,
            data=data,
        )
    except ValueError as exc:
        logger.warning(
            "identity_upload_rejected user_id=%s verification_id=%s side=%s size=%s mime=%s",
            user_id,
            identity.id,
            side,
            len(data or b""),
            (content_type or "")[:64],
        )
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        logger.error(
            "identity_upload_failed user_id=%s verification_id=%s side=%s size=%s mime=%s",
            user_id,
            identity.id,
            side,
            len(data or b""),
            (content_type or "")[:64],
        )
        raise HTTPException(
            status_code=503,
            detail=f"本人確認書類の{side_label}をアップロードできませんでした。時間をおいて再度お試しください。",
        ) from exc

    if side == "front":
        identity.storage_key_front = key
    else:
        identity.storage_key_back = key
    identity.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(identity)

    if previous_key and previous_key != key:
        delete_kyc_object(previous_key)

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

    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="ユーザーが見つかりません")
    if not user.birth_date:
        raise HTTPException(status_code=400, detail="生年月日を登録してから本人確認を提出してください")
    legal_name = (user.family_name or "") + (user.given_name or "")
    if not legal_name.strip() and not (user.name or "").strip():
        raise HTTPException(status_code=400, detail="氏名を登録してから本人確認を提出してください")
    if not user.postal_code or not user.region or not user.city or not user.address_line1:
        raise HTTPException(status_code=400, detail="住所を登録してから本人確認を提出してください")

    from services.buyback_identity_compare import snapshot_identity_profile

    now = datetime.utcnow()
    snapshot_identity_profile(identity, user)
    identity.document_type = doc_type
    identity.status = models_buyback.IdentityVerificationStatus.pending.value
    identity.submitted_at = now
    identity.updated_at = now
    identity.rejection_reason = None
    db.commit()
    db.refresh(identity)
    return identity
