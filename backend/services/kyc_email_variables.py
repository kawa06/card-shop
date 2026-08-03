"""Build KYC / guardian consent email template variables (privacy-safe — no document URLs or PII)."""

from __future__ import annotations

import html
from datetime import datetime
from typing import Any, Optional

import models
import models_buyback
from config import settings
from services.email_delivery import get_brand_settings
from services.email_order_layout import (
    build_buttons_block,
    build_contact_block,
    build_kyc_info_block,
    build_notes_block,
    build_signature_block,
    build_text_body,
)
from services.kyc_email_registry import get_kyc_email_event, normalize_template_key

KYC_INFO_FIELD_DEFS: dict[str, tuple[str, str]] = {
    "authNo": ("認証番号", "authNo"),
    "receivedAt": ("受付日時", "receivedAt"),
    "submittedAt": ("申請日時", "submittedAt"),
    "reviewStartedAt": ("審査開始日時", "reviewStartedAt"),
    "approvedAt": ("承認日時", "approvedAt"),
    "expiresAt": ("有効期限", "expiresAt"),
    "resubmitDeadline": ("再提出期限", "resubmitDeadline"),
    "consentExpiresAt": ("同意期限", "consentExpiresAt"),
    "statusLabel": ("ステータス", "statusLabel"),
    "verificationType": ("認証種別", "verificationType"),
}

KYC_EVENT_VISIBLE_FIELDS: dict[str, list[str]] = {
    "kyc_identity_received": ["authNo", "receivedAt", "statusLabel", "verificationType"],
    "kyc_identity_upload_completed": ["authNo", "submittedAt", "statusLabel"],
    "kyc_identity_review_started": ["authNo", "reviewStartedAt", "statusLabel"],
    "kyc_identity_approved": ["authNo", "approvedAt", "statusLabel"],
    "kyc_identity_returned": ["authNo", "resubmitDeadline", "statusLabel"],
    "kyc_identity_resubmit_requested": ["authNo", "resubmitDeadline", "statusLabel"],
    "kyc_identity_rejected": ["authNo", "statusLabel"],
    "kyc_identity_expiry_notice": ["authNo", "expiresAt", "statusLabel"],
    "kyc_guardian_consent_requested": ["authNo", "consentExpiresAt", "verificationType"],
    "kyc_guardian_consent_received": ["authNo", "receivedAt", "statusLabel"],
    "kyc_guardian_consent_completed": ["authNo", "approvedAt", "statusLabel"],
    "kyc_guardian_identity_received": ["authNo", "receivedAt", "statusLabel"],
    "kyc_guardian_identity_upload_completed": ["authNo", "submittedAt", "statusLabel"],
    "kyc_guardian_identity_review_started": ["authNo", "reviewStartedAt", "statusLabel"],
    "kyc_guardian_identity_approved": ["authNo", "approvedAt", "statusLabel"],
    "kyc_guardian_identity_returned": ["authNo", "resubmitDeadline", "statusLabel"],
    "kyc_guardian_identity_resubmit_requested": ["authNo", "resubmitDeadline", "statusLabel"],
    "kyc_guardian_identity_rejected": ["authNo", "statusLabel"],
    "kyc_guardian_consent_expiry_notice": ["authNo", "consentExpiresAt"],
    "kyc_auth_info_changed": ["authNo", "statusLabel"],
    "kyc_auth_revoked": ["authNo", "statusLabel"],
    "kyc_system_error": ["authNo"],
}

IDENTITY_STATUS_LABELS: dict[str, str] = {
    "not_submitted": "未提出",
    "pending": "審査中",
    "approved": "承認済み",
    "rejected": "却下",
    "resubmit_requested": "再提出依頼",
    "expired": "期限切れ",
}

GUARDIAN_STATUS_LABELS: dict[str, str] = {
    "pending": "同意待ち",
    "signed": "同意完了",
    "expired": "期限切れ",
    "revoked": "取消",
}

RAW_KYC_VARIABLE_KEYS = frozenset({
    "kycInfoBlock",
    "buttonsBlock",
    "notesBlock",
    "contactBlock",
    "signatureBlock",
    "content",
    "returnReason",
    "rejectionReason",
    "resubmitReason",
    "差し戻し理由",
    "却下理由",
})


def _format_jst(dt: datetime | None) -> str:
    if not dt:
        return ""
    return dt.strftime("%Y/%m/%d %H:%M")


def _auth_no(*, prefix: str, entity_id: int) -> str:
    return f"{prefix}-{entity_id:06d}"


def _mask_email(email: str) -> str:
    """Mask email for display in non-recipient contexts."""
    parts = (email or "").split("@")
    if len(parts) != 2:
        return "****"
    local, domain = parts
    if len(local) <= 2:
        masked_local = local[0] + "*"
    else:
        masked_local = local[0] + "*" * (len(local) - 2) + local[-1]
    return f"{masked_local}@{domain}"


def _settings_url() -> str:
    return f"{settings.BUYLIST_URL.rstrip('/')}/settings.html"


def _consent_url(raw_token: str) -> str:
    return f"{settings.BUYLIST_URL.rstrip('/')}/guardian-consent.html?token={raw_token}"


def _placeholder_copy() -> tuple[str, str, str, str]:
    return (
        "（本文タイトル）",
        "（本文説明を入力してください）",
        "（注意事項を入力してください）",
        "（お問い合わせ案内を入力してください）",
    )


def _default_kyc_buttons(event_key: str, ctx: dict[str, str]) -> list[dict[str, str]]:
    settings_url = ctx.get("settingsUrl") or ctx.get("認証URL") or ""
    consent_url = ctx.get("consentUrl") or ctx.get("認証URL") or ""
    contact_url = ctx.get("contactUrl") or ""

    if event_key == "kyc_guardian_consent_requested" and consent_url:
        return [{"text": "（ボタンラベル）", "url": consent_url}]
    if event_key in {
        "kyc_identity_received",
        "kyc_identity_upload_completed",
        "kyc_identity_review_started",
        "kyc_identity_approved",
        "kyc_identity_returned",
        "kyc_identity_resubmit_requested",
        "kyc_identity_rejected",
        "kyc_identity_expiry_notice",
        "kyc_guardian_consent_received",
        "kyc_guardian_consent_completed",
        "kyc_guardian_identity_received",
        "kyc_guardian_identity_upload_completed",
        "kyc_auth_info_changed",
        "kyc_auth_revoked",
    } and settings_url:
        return [{"text": "（ボタンラベル）", "url": settings_url}]
    if contact_url:
        return [{"text": "（ボタンラベル）", "url": contact_url}]
    return []


def _build_kyc_info_block_for_event(event_key: str, ctx: dict[str, str]) -> str:
    field_keys = KYC_EVENT_VISIBLE_FIELDS.get(event_key, list(KYC_INFO_FIELD_DEFS.keys()))
    rows: list[tuple[str, str]] = []
    for fk in field_keys:
        if fk not in KYC_INFO_FIELD_DEFS:
            continue
        label, var_key = KYC_INFO_FIELD_DEFS[fk]
        value = ctx.get(var_key, "")
        if value:
            rows.append((label, html.escape(str(value))))
    return build_kyc_info_block(rows)


def build_identity_email_variables(
    db,
    user: models.User,
    verification: models_buyback.IdentityVerification,
    event_key: str,
    *,
    reason: str | None = None,
    consent_url: str | None = None,
    body_title: Optional[str] = None,
    body_description: Optional[str] = None,
    notes_html: Optional[str] = None,
    contact_html: Optional[str] = None,
    buttons: Optional[list[dict[str, str]]] = None,
    brand_color: str = "#ca8a04",
) -> dict[str, Any]:
    event_key = normalize_template_key(event_key)
    name = user.name or "お客"
    p_title, p_desc, p_notes, p_contact = _placeholder_copy()
    title = body_title or p_title
    desc = body_description or p_desc
    notes = notes_html if notes_html is not None else p_notes
    contact = contact_html if contact_html is not None else p_contact

    brand = get_brand_settings(db)
    signature_html = getattr(brand, "email_signature_html", None) or ""
    contact_url = brand.contact_url or settings.FRONTEND_URL or ""
    settings_url = _settings_url()
    auth_no = _auth_no(prefix="KYC", entity_id=verification.id)

    ctx = {
        "authNo": auth_no,
        "認証番号": auth_no,
        "receivedAt": _format_jst(verification.submitted_at),
        "受付日時": _format_jst(verification.submitted_at),
        "submittedAt": _format_jst(verification.submitted_at),
        "申請日時": _format_jst(verification.submitted_at),
        "reviewStartedAt": _format_jst(verification.submitted_at),
        "審査開始日時": _format_jst(verification.submitted_at),
        "approvedAt": _format_jst(verification.reviewed_at),
        "承認日時": _format_jst(verification.reviewed_at),
        "expiresAt": _format_jst(verification.expires_at),
        "有効期限": _format_jst(verification.expires_at),
        "resubmitDeadline": _format_jst(verification.expires_at),
        "再提出期限": _format_jst(verification.expires_at),
        "statusLabel": IDENTITY_STATUS_LABELS.get(verification.status or "", verification.status or ""),
        "ステータス": IDENTITY_STATUS_LABELS.get(verification.status or "", verification.status or ""),
        "verificationType": "本人確認",
        "認証種別": "本人確認",
        "settingsUrl": settings_url,
        "認証URL": consent_url or settings_url,
        "consentUrl": consent_url or "",
        "contactUrl": contact_url,
        "お問い合わせURL": contact_url,
    }

    safe_reason = html.escape(reason or "") if reason else ""
    kyc_info = _build_kyc_info_block_for_event(event_key, ctx)
    btn_list = buttons if buttons is not None else _default_kyc_buttons(event_key, {**ctx, "contactUrl": contact_url})

    variables: dict[str, Any] = {
        "name": name,
        "ユーザー名": name,
        "email": _mask_email(user.email or ""),
        "bodyTitle": title,
        "bodyDescription": desc,
        "kycInfoBlock": kyc_info,
        "buttonsBlock": build_buttons_block(btn_list, brand_color=brand_color or brand.brand_color or "#ca8a04"),
        "notesBlock": build_notes_block(notes),
        "contactBlock": build_contact_block(contact),
        "signatureBlock": build_signature_block(signature_html),
        "shopName": settings.SITE_NAME or "KRX TCG",
        "returnReason": safe_reason,
        "rejectionReason": safe_reason,
        "resubmitReason": safe_reason,
        "差し戻し理由": safe_reason,
        "却下理由": safe_reason,
        **ctx,
    }

    summary_lines = [f"認証番号: {auth_no}"]
    for fk in KYC_EVENT_VISIBLE_FIELDS.get(event_key, []):
        if fk in KYC_INFO_FIELD_DEFS:
            label, var_key = KYC_INFO_FIELD_DEFS[fk]
            val = ctx.get(var_key, "")
            if val:
                summary_lines.append(f"{label}: {val}")

    variables["_text_body"] = build_text_body(
        name=name,
        body_title=title,
        body_description=desc,
        order_summary_lines=summary_lines,
        notes=notes.replace("<br>", "\n").replace("<br/>", "\n") if notes else "",
        contact=contact.replace("<br>", "\n").replace("<br/>", "\n") if contact else "",
        buttons=btn_list,
    )
    return variables


def build_guardian_email_variables(
    db,
    consent: models_buyback.GuardianConsent,
    user: models.User,
    event_key: str,
    *,
    raw_token: str | None = None,
    recipient_name: str | None = None,
    reason: str | None = None,
    body_title: Optional[str] = None,
    body_description: Optional[str] = None,
    notes_html: Optional[str] = None,
    contact_html: Optional[str] = None,
    buttons: Optional[list[dict[str, str]]] = None,
    brand_color: str = "#ca8a04",
) -> dict[str, Any]:
    event_key = normalize_template_key(event_key)
    # Privacy: use recipient display name only; minor referred to generically in guardian emails
    if event_key == "kyc_guardian_consent_requested":
        name = recipient_name or "保護者"
    else:
        name = recipient_name or user.name or "お客"
    p_title, p_desc, p_notes, p_contact = _placeholder_copy()
    title = body_title or p_title
    desc = body_description or p_desc
    notes = notes_html if notes_html is not None else p_notes
    contact = contact_html if contact_html is not None else p_contact

    brand = get_brand_settings(db)
    signature_html = getattr(brand, "email_signature_html", None) or ""
    contact_url = brand.contact_url or settings.FRONTEND_URL or ""
    settings_url = _settings_url()
    consent_url = _consent_url(raw_token) if raw_token else ""
    auth_no = _auth_no(prefix="GC", entity_id=consent.id)

    ctx = {
        "authNo": auth_no,
        "認証番号": auth_no,
        "receivedAt": _format_jst(consent.created_at),
        "受付日時": _format_jst(consent.created_at),
        "submittedAt": _format_jst(consent.created_at),
        "申請日時": _format_jst(consent.created_at),
        "reviewStartedAt": _format_jst(consent.created_at),
        "審査開始日時": _format_jst(consent.created_at),
        "approvedAt": _format_jst(consent.signed_at),
        "承認日時": _format_jst(consent.signed_at),
        "consentExpiresAt": _format_jst(consent.expires_at),
        "同意期限": _format_jst(consent.expires_at),
        "expiresAt": _format_jst(consent.expires_at),
        "有効期限": _format_jst(consent.expires_at),
        "statusLabel": GUARDIAN_STATUS_LABELS.get(consent.status or "", consent.status or ""),
        "ステータス": GUARDIAN_STATUS_LABELS.get(consent.status or "", consent.status or ""),
        "verificationType": "保護者同意",
        "認証種別": "保護者同意",
        "settingsUrl": settings_url,
        "consentUrl": consent_url,
        "認証URL": consent_url or settings_url,
        "contactUrl": contact_url,
        "お問い合わせURL": contact_url,
        "guardianName": "保護者",
        "保護者氏名": "保護者",
        "minorName": "お子様",
    }

    safe_reason = html.escape(reason or "") if reason else ""
    kyc_info = _build_kyc_info_block_for_event(event_key, ctx)
    btn_list = buttons if buttons is not None else _default_kyc_buttons(event_key, {**ctx, "contactUrl": contact_url})

    variables: dict[str, Any] = {
        "name": name,
        "ユーザー名": name,
        "email": _mask_email(consent.guardian_email or user.email or ""),
        "bodyTitle": title,
        "bodyDescription": desc,
        "kycInfoBlock": kyc_info,
        "buttonsBlock": build_buttons_block(btn_list, brand_color=brand_color or brand.brand_color or "#ca8a04"),
        "notesBlock": build_notes_block(notes),
        "contactBlock": build_contact_block(contact),
        "signatureBlock": build_signature_block(signature_html),
        "shopName": settings.SITE_NAME or "KRX TCG",
        "returnReason": safe_reason,
        "rejectionReason": safe_reason,
        "resubmitReason": safe_reason,
        "差し戻し理由": safe_reason,
        "却下理由": safe_reason,
        **ctx,
    }

    summary_lines = [f"認証番号: {auth_no}"]
    for fk in KYC_EVENT_VISIBLE_FIELDS.get(event_key, []):
        if fk in KYC_INFO_FIELD_DEFS:
            label, var_key = KYC_INFO_FIELD_DEFS[fk]
            val = ctx.get(var_key, "")
            if val:
                summary_lines.append(f"{label}: {val}")

    variables["_text_body"] = build_text_body(
        name=name,
        body_title=title,
        body_description=desc,
        order_summary_lines=summary_lines,
        notes=notes.replace("<br>", "\n").replace("<br/>", "\n") if notes else "",
        contact=contact.replace("<br>", "\n").replace("<br/>", "\n") if contact else "",
        buttons=btn_list,
    )
    return variables


def build_kyc_sample_variables(template_key: str) -> dict[str, Any]:
    """Sample data for admin preview/test-send — no real PII."""
    template_key = normalize_template_key(template_key)
    event = get_kyc_email_event(template_key)
    event_key = event.event_key if event else template_key

    sample_ctx = {
        "authNo": "KYC-000001",
        "認証番号": "KYC-000001",
        "receivedAt": "2026/08/03 10:00",
        "受付日時": "2026/08/03 10:00",
        "submittedAt": "2026/08/03 10:15",
        "申請日時": "2026/08/03 10:15",
        "reviewStartedAt": "2026/08/03 11:00",
        "審査開始日時": "2026/08/03 11:00",
        "approvedAt": "2026/08/03 14:30",
        "承認日時": "2026/08/03 14:30",
        "expiresAt": "2026/09/03 23:59",
        "有効期限": "2026/09/03 23:59",
        "resubmitDeadline": "2026/08/10 23:59",
        "再提出期限": "2026/08/10 23:59",
        "consentExpiresAt": "2026/08/10 23:59",
        "同意期限": "2026/08/10 23:59",
        "statusLabel": "審査中",
        "ステータス": "審査中",
        "verificationType": "本人確認",
        "認証種別": "本人確認",
        "settingsUrl": f"{settings.BUYLIST_URL.rstrip('/')}/settings.html",
        "consentUrl": f"{settings.BUYLIST_URL.rstrip('/')}/guardian-consent.html?token=sample-token",
        "認証URL": f"{settings.BUYLIST_URL.rstrip('/')}/settings.html",
        "contactUrl": settings.FRONTEND_URL or "https://example.com/contact",
        "お問い合わせURL": settings.FRONTEND_URL or "https://example.com/contact",
        "guardianName": "保護者",
        "保護者氏名": "保護者",
        "minorName": "お子様",
        "returnReason": "（差し戻し理由）",
        "rejectionReason": "（却下理由）",
        "resubmitReason": "（再提出理由）",
        "差し戻し理由": "（差し戻し理由）",
        "却下理由": "（却下理由）",
    }

    kyc_info = _build_kyc_info_block_for_event(event_key, sample_ctx)
    buttons = _default_kyc_buttons(event_key, sample_ctx)
    brand_color = "#ca8a04"

    is_guardian_recipient = event and event.recipient_type == "guardian"
    display_name = "保護者" if is_guardian_recipient else "山田 太郎"

    variables: dict[str, Any] = {
        "name": display_name,
        "ユーザー名": display_name,
        "email": "s***e@example.com",
        "bodyTitle": "（本文タイトル）",
        "bodyDescription": "（本文説明を入力してください）",
        "kycInfoBlock": kyc_info,
        "buttonsBlock": build_buttons_block(buttons, brand_color=brand_color),
        "notesBlock": build_notes_block("（注意事項を入力してください）"),
        "contactBlock": build_contact_block("（お問い合わせ案内を入力してください）"),
        "signatureBlock": build_signature_block("（署名）"),
        "shopName": settings.SITE_NAME or "KRX TCG",
        **sample_ctx,
    }
    return variables


def kyc_variables_for_template(template_key: str) -> list[str]:
    template_key = normalize_template_key(template_key)
    base = [
        "name", "authNo", "bodyTitle", "bodyDescription",
        "kycInfoBlock", "buttonsBlock", "notesBlock", "contactBlock", "signatureBlock",
        "receivedAt", "submittedAt", "reviewStartedAt", "approvedAt",
        "expiresAt", "resubmitDeadline", "consentExpiresAt",
        "statusLabel", "verificationType", "settingsUrl", "consentUrl", "contactUrl",
        "guardianName", "minorName",
        "returnReason", "rejectionReason", "resubmitReason",
    ]
    if get_kyc_email_event(template_key):
        return base
    return base
