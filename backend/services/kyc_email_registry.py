"""KYC / guardian consent email event registry — extensible without changing send code."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional

KycRecipientType = Literal["customer", "guardian", "admin"]


@dataclass(frozen=True)
class KycEmailEventDef:
    event_key: str
    default_template_key: str
    description: str
    recipient_type: KycRecipientType = "customer"
    auto_send_default: bool = True
    dedupe_reference_suffix: str = ""


# Legacy buyback KYC keys → canonical kyc_* keys
LEGACY_TEMPLATE_ALIASES: dict[str, str] = {
    "buyback_identity_approved": "kyc_identity_approved",
    "buyback_identity_rejected": "kyc_identity_rejected",
    "buyback_identity_resubmit_requested": "kyc_identity_resubmit_requested",
    "buyback_guardian_consent": "kyc_guardian_consent_requested",
}


KYC_EMAIL_EVENTS: dict[str, KycEmailEventDef] = {
    # Identity — customer
    "kyc_identity_received": KycEmailEventDef(
        "kyc_identity_received", "kyc_identity_received", "本人確認受付"
    ),
    "kyc_identity_upload_completed": KycEmailEventDef(
        "kyc_identity_upload_completed", "kyc_identity_upload_completed", "本人確認書類アップロード完了"
    ),
    "kyc_identity_review_started": KycEmailEventDef(
        "kyc_identity_review_started", "kyc_identity_review_started", "本人確認審査開始"
    ),
    "kyc_identity_approved": KycEmailEventDef(
        "kyc_identity_approved", "kyc_identity_approved", "本人確認承認"
    ),
    "kyc_identity_returned": KycEmailEventDef(
        "kyc_identity_returned", "kyc_identity_returned", "本人確認差し戻し"
    ),
    "kyc_identity_resubmit_requested": KycEmailEventDef(
        "kyc_identity_resubmit_requested", "kyc_identity_resubmit_requested", "本人確認再提出依頼"
    ),
    "kyc_identity_rejected": KycEmailEventDef(
        "kyc_identity_rejected", "kyc_identity_rejected", "本人確認却下"
    ),
    "kyc_identity_expiry_notice": KycEmailEventDef(
        "kyc_identity_expiry_notice", "kyc_identity_expiry_notice", "本人確認有効期限のお知らせ"
    ),
    # Guardian — guardian recipient
    "kyc_guardian_consent_requested": KycEmailEventDef(
        "kyc_guardian_consent_requested",
        "kyc_guardian_consent_requested",
        "保護者同意依頼",
        recipient_type="guardian",
    ),
    "kyc_guardian_consent_received": KycEmailEventDef(
        "kyc_guardian_consent_received", "kyc_guardian_consent_received", "保護者同意受付"
    ),
    "kyc_guardian_consent_completed": KycEmailEventDef(
        "kyc_guardian_consent_completed", "kyc_guardian_consent_completed", "保護者同意完了"
    ),
    "kyc_guardian_identity_received": KycEmailEventDef(
        "kyc_guardian_identity_received", "kyc_guardian_identity_received", "保護者本人確認受付"
    ),
    "kyc_guardian_identity_upload_completed": KycEmailEventDef(
        "kyc_guardian_identity_upload_completed",
        "kyc_guardian_identity_upload_completed",
        "保護者本人確認書類アップロード完了",
    ),
    "kyc_guardian_identity_review_started": KycEmailEventDef(
        "kyc_guardian_identity_review_started",
        "kyc_guardian_identity_review_started",
        "保護者本人確認審査開始",
    ),
    "kyc_guardian_identity_approved": KycEmailEventDef(
        "kyc_guardian_identity_approved", "kyc_guardian_identity_approved", "保護者本人確認承認"
    ),
    "kyc_guardian_identity_returned": KycEmailEventDef(
        "kyc_guardian_identity_returned", "kyc_guardian_identity_returned", "保護者本人確認差し戻し"
    ),
    "kyc_guardian_identity_resubmit_requested": KycEmailEventDef(
        "kyc_guardian_identity_resubmit_requested",
        "kyc_guardian_identity_resubmit_requested",
        "保護者本人確認再提出依頼",
    ),
    "kyc_guardian_identity_rejected": KycEmailEventDef(
        "kyc_guardian_identity_rejected", "kyc_guardian_identity_rejected", "保護者本人確認却下"
    ),
    "kyc_guardian_consent_expiry_notice": KycEmailEventDef(
        "kyc_guardian_consent_expiry_notice",
        "kyc_guardian_consent_expiry_notice",
        "保護者同意期限のお知らせ",
        recipient_type="guardian",
    ),
    # Other
    "kyc_auth_info_changed": KycEmailEventDef(
        "kyc_auth_info_changed", "kyc_auth_info_changed", "認証情報変更"
    ),
    "kyc_auth_revoked": KycEmailEventDef(
        "kyc_auth_revoked", "kyc_auth_revoked", "認証取消"
    ),
    "kyc_system_error": KycEmailEventDef(
        "kyc_system_error", "kyc_system_error", "システムエラー", auto_send_default=False
    ),
}


# Identity status → default event (admin may override template via registry)
IDENTITY_STATUS_TO_EVENT: dict[str, str] = {
    "pending": "kyc_identity_received",
    "approved": "kyc_identity_approved",
    "rejected": "kyc_identity_rejected",
    "resubmit_requested": "kyc_identity_resubmit_requested",
}


def normalize_template_key(template_key: str) -> str:
    return LEGACY_TEMPLATE_ALIASES.get(template_key, template_key)


def resolve_kyc_template_key(event_key: str) -> str:
    key = LEGACY_TEMPLATE_ALIASES.get(event_key, event_key)
    event = KYC_EMAIL_EVENTS.get(key)
    if event:
        return event.default_template_key
    return key


def get_kyc_email_event(event_key: str) -> Optional[KycEmailEventDef]:
    key = LEGACY_TEMPLATE_ALIASES.get(event_key, event_key)
    return KYC_EMAIL_EVENTS.get(key)


def all_auto_send_defaults() -> dict[str, bool]:
    return {ev.event_key: ev.auto_send_default for ev in KYC_EMAIL_EVENTS.values()}


def resolve_identity_status_event(
    *,
    from_status: str | None,
    to_status: str,
    action: str | None = None,
) -> str | None:
    """Map identity verification transitions to email events."""
    if action == "returned":
        return "kyc_identity_returned"
    if to_status == "pending" and from_status in {None, "not_submitted", "resubmit_requested", "rejected", "expired"}:
        return "kyc_identity_received"
    return IDENTITY_STATUS_TO_EVENT.get(to_status)
