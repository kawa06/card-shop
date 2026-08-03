"""Buyback payout readiness (KYC + guardian + bank account)."""

from __future__ import annotations

from sqlalchemy.orm import Session

import models
import models_buyback
from services.buyback_age import age_profile_for_user, requires_guardian_consent_for_user
from services.buyback_guardian import get_latest_guardian_consent, guardian_documents_complete
from services.buyback_identity import get_or_create_identity
from services.buyback_payout_accounts import list_payout_accounts

IDENTITY_STATUS_LABELS = {
    "not_submitted": "未提出",
    "pending": "審査中",
    "approved": "承認済み",
    "rejected": "否認",
    "resubmit_requested": "再提出依頼",
    "expired": "期限切れ",
}

PAYOUT_TRANSFER_STATUS_LABELS = {
    "unpaid": "未振込",
    "scheduled": "振込予定",
    "completed": "振込済み",
}

GUARDIAN_STATUS_LABELS = {
    "pending": "同意待ち",
    "signed": "同意済み",
    "expired": "期限切れ",
    "revoked": "取り消し",
}


def get_compliance_status(
    db: Session,
    *,
    user_id: int,
    user: models.User | None = None,
    requires_guardian: bool | None = None,
) -> dict:
    if user is None:
        user = db.query(models.User).filter(models.User.id == user_id).first()
    needs_guardian = (
        requires_guardian_consent_for_user(user)
        if requires_guardian is None
        else bool(requires_guardian)
    )
    identity = get_or_create_identity(db, user_id)
    guardian = get_latest_guardian_consent(db, user_id)
    accounts = list_payout_accounts(db, user_id)
    default_account = next((a for a in accounts if a.is_default), None)

    identity_ready = identity.status == models_buyback.IdentityVerificationStatus.approved.value
    guardian_ready = True
    guardian_status = None
    guardian_status_label = None
    if needs_guardian:
        guardian_status = guardian.status if guardian else None
        guardian_status_label = (
            GUARDIAN_STATUS_LABELS.get(guardian_status, guardian_status)
            if guardian_status
            else "未申請"
        )
        guardian_ready = bool(
            guardian
            and guardian.status == models_buyback.GuardianConsentStatus.signed.value
            and guardian_documents_complete(guardian)
        )

    payout_ready = default_account is not None
    age, age_as_of = age_profile_for_user(user)

    return {
        "birth_date": user.birth_date.isoformat() if user and user.birth_date else None,
        "age": age,
        "age_as_of": age_as_of.isoformat() if age_as_of else None,
        "requires_guardian_consent": needs_guardian,
        "identity_status": identity.status,
        "identity_status_label": IDENTITY_STATUS_LABELS.get(identity.status, identity.status),
        "identity_ready": identity_ready,
        "has_identity_documents": bool(identity.storage_key_front),
        "guardian_status": guardian_status,
        "guardian_status_label": guardian_status_label,
        "guardian_ready": guardian_ready,
        "guardian_has_documents": guardian_documents_complete(guardian),
        "payout_account_count": len(accounts),
        "payout_account_ready": payout_ready,
        "ready_for_payout": identity_ready and guardian_ready and payout_ready,
    }
