"""Buyback payout readiness (KYC + guardian + bank account)."""

from __future__ import annotations

from sqlalchemy.orm import Session

import models_buyback
from services.buyback_guardian import get_latest_guardian_consent
from services.buyback_identity import get_or_create_identity
from services.buyback_payout_accounts import list_payout_accounts

IDENTITY_STATUS_LABELS = {
    "not_submitted": "未提出",
    "pending": "審査中",
    "approved": "承認済み",
    "rejected": "差戻し",
    "expired": "期限切れ",
}

GUARDIAN_STATUS_LABELS = {
    "pending": "同意待ち",
    "signed": "同意済み",
    "expired": "期限切れ",
    "revoked": "取り消し",
}


def get_compliance_status(db: Session, *, user_id: int, requires_guardian: bool = False) -> dict:
    identity = get_or_create_identity(db, user_id)
    guardian = get_latest_guardian_consent(db, user_id)
    accounts = list_payout_accounts(db, user_id)
    default_account = next((a for a in accounts if a.is_default), None)

    identity_ready = identity.status == models_buyback.IdentityVerificationStatus.approved.value
    guardian_ready = True
    guardian_status = None
    guardian_status_label = None
    if requires_guardian:
        guardian_status = guardian.status if guardian else None
        guardian_status_label = (
            GUARDIAN_STATUS_LABELS.get(guardian_status, guardian_status)
            if guardian_status
            else "未申請"
        )
        guardian_ready = bool(
            guardian and guardian.status == models_buyback.GuardianConsentStatus.signed.value
        )

    payout_ready = default_account is not None

    return {
        "identity_status": identity.status,
        "identity_status_label": IDENTITY_STATUS_LABELS.get(identity.status, identity.status),
        "identity_ready": identity_ready,
        "has_identity_documents": bool(identity.storage_key_front),
        "requires_guardian_consent": requires_guardian,
        "guardian_status": guardian_status,
        "guardian_status_label": guardian_status_label,
        "guardian_ready": guardian_ready,
        "payout_account_count": len(accounts),
        "payout_account_ready": payout_ready,
        "ready_for_payout": identity_ready and guardian_ready and payout_ready,
    }
