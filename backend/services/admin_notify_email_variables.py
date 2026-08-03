"""Build admin notification email variables — minimal PII, no KYC/bank secrets."""

from __future__ import annotations

import html
import re
from datetime import datetime
from typing import Any, Optional

from config import settings
from services.email_delivery import get_brand_settings
from services.email_order_layout import (
    build_admin_notify_info_block,
    build_buttons_block,
    build_contact_block,
    build_notes_block,
    build_signature_block,
    build_text_body,
)
from services.admin_notify_email_registry import get_admin_notify_email_event, normalize_template_key

ADMIN_NOTIFY_INFO_FIELD_DEFS: dict[str, tuple[str, str]] = {
    "orderNo": ("注文番号", "orderNo"),
    "buybackNo": ("買取番号", "buybackNo"),
    "inquiryNo": ("お問い合わせ番号", "inquiryNo"),
    "userName": ("ユーザー名", "userName"),
    "adminName": ("管理者名", "adminName"),
    "eventAt": ("日時", "eventAt"),
    "productName": ("商品名", "productName"),
    "orderAmount": ("注文金額", "orderAmount"),
    "assessmentAmount": ("査定金額", "assessmentAmount"),
    "carrier": ("配送会社", "carrier"),
    "trackingNo": ("送り状番号", "trackingNo"),
    "assignee": ("担当者", "assignee"),
    "serverName": ("サーバー", "serverName"),
    "systemName": ("システム名", "systemName"),
    "ipAddress": ("IPアドレス", "ipAddress"),
}

ADMIN_NOTIFY_EVENT_VISIBLE_FIELDS: dict[str, list[str]] = {
    "admin_notify_order_received": ["orderNo", "userName", "orderAmount", "eventAt"],
    "admin_notify_order_cancelled": ["orderNo", "userName", "eventAt"],
    "admin_notify_order_refund_requested": ["orderNo", "userName", "orderAmount", "eventAt"],
    "admin_notify_order_refund_completed": ["orderNo", "userName", "orderAmount", "eventAt"],
    "admin_notify_order_payment_failed": ["orderNo", "userName", "eventAt"],
    "admin_notify_order_payment_error": ["orderNo", "userName", "eventAt"],
    "admin_notify_order_unpaid": ["orderNo", "userName", "orderAt"],
    "admin_notify_order_payment_expired": ["orderNo", "userName", "eventAt"],
    "admin_notify_shipping_pending": ["orderNo", "eventAt"],
    "admin_notify_shipping_completed": ["orderNo", "carrier", "trackingNo", "eventAt"],
    "admin_notify_shipping_trouble": ["orderNo", "carrier", "trackingNo", "eventAt"],
    "admin_notify_shipping_returned": ["orderNo", "carrier", "eventAt"],
    "admin_notify_buyback_request_new": ["buybackNo", "userName", "assessmentAmount", "eventAt"],
    "admin_notify_buyback_store_booking": ["buybackNo", "userName", "eventAt"],
    "admin_notify_buyback_parcel_received": ["buybackNo", "userName", "eventAt"],
    "admin_notify_buyback_assessment_started": ["buybackNo", "eventAt"],
    "admin_notify_buyback_assessment_completed": ["buybackNo", "assessmentAmount", "eventAt"],
    "admin_notify_buyback_approval_pending": ["buybackNo", "eventAt"],
    "admin_notify_buyback_payout_pending": ["buybackNo", "assessmentAmount", "eventAt"],
    "admin_notify_buyback_payout_completed": ["buybackNo", "assessmentAmount", "eventAt"],
    "admin_notify_buyback_return_pending": ["buybackNo", "eventAt"],
    "admin_notify_kyc_submitted": ["userName", "eventAt"],
    "admin_notify_kyc_resubmit": ["userName", "eventAt"],
    "admin_notify_kyc_approved": ["userName", "eventAt"],
    "admin_notify_kyc_guardian_consent_pending": ["userName", "eventAt"],
    "admin_notify_kyc_guardian_verify_pending": ["userName", "eventAt"],
    "admin_notify_inquiry_new": ["inquiryNo", "userName", "eventAt"],
    "admin_notify_inquiry_reply_pending": ["inquiryNo", "assignee", "eventAt"],
    "admin_notify_inquiry_stale": ["inquiryNo", "assignee", "eventAt"],
    "admin_notify_member_registered": ["userName", "eventAt"],
    "admin_notify_member_withdrawn": ["userName", "eventAt"],
    "admin_notify_member_locked": ["userName", "eventAt"],
    "admin_notify_member_suspicious_login": ["userName", "ipAddress", "eventAt"],
    "admin_notify_inventory_out_of_stock": ["productName", "eventAt"],
    "admin_notify_inventory_low_stock": ["productName", "eventAt"],
    "admin_notify_product_published": ["productName", "eventAt"],
    "admin_notify_product_unpublished": ["productName", "eventAt"],
    "admin_notify_product_price_changed": ["productName", "eventAt"],
    "admin_notify_system_backup_success": ["serverName", "eventAt"],
    "admin_notify_system_backup_failed": ["serverName", "eventAt"],
    "admin_notify_system_server_error": ["serverName", "systemName", "eventAt"],
    "admin_notify_system_email_failed": ["eventAt"],
    "admin_notify_system_stripe_webhook_error": ["eventAt"],
    "admin_notify_system_api_error": ["systemName", "eventAt"],
    "admin_notify_system_upload_error": ["eventAt"],
    "admin_notify_system_database_error": ["serverName", "eventAt"],
    "admin_notify_system_storage_error": ["serverName", "eventAt"],
    "admin_notify_system_job_failed": ["systemName", "eventAt"],
    "admin_notify_security_admin_login": ["adminName", "ipAddress", "eventAt"],
    "admin_notify_security_permission_changed": ["adminName", "userName", "eventAt"],
    "admin_notify_security_unauthorized_access": ["ipAddress", "eventAt"],
    "admin_notify_security_high_traffic": ["ipAddress", "eventAt"],
    "admin_notify_security_abnormal_operation": ["adminName", "eventAt"],
    "admin_notify_security_audit_log": ["adminName", "eventAt"],
    "admin_notify_other_important": ["eventAt"],
    "admin_notify_other_maintenance": ["systemName", "eventAt"],
    "admin_notify_other_recovered": ["systemName", "eventAt"],
}

RAW_ADMIN_NOTIFY_VARIABLE_KEYS = frozenset({
    "adminNotifyInfoBlock",
    "errorBlock",
    "logBlock",
    "buttonsBlock",
    "notesBlock",
    "contactBlock",
    "signatureBlock",
    "errorMessage",
    "logSnippet",
    "content",
})

_SENSITIVE_PATTERNS = re.compile(
    r"(password|secret|token|api_key|account_number|口座|カード番号|document_url|storage_path)",
    re.I,
)


def _format_jst(dt: datetime | None = None) -> str:
    value = dt or datetime.utcnow()
    return value.strftime("%Y/%m/%d %H:%M")


def _placeholder_copy() -> tuple[str, str, str, str]:
    return (
        "（本文タイトル）",
        "（本文説明を入力してください）",
        "（注意事項を入力してください）",
        "（フッター案内を入力してください）",
    )


def _sanitize_snippet(text: str | None, limit: int = 300) -> str:
    if not text:
        return ""
    t = (text or "").replace("\n", " ").strip()
    if _SENSITIVE_PATTERNS.search(t):
        return "（詳細は管理画面をご確認ください）"
    return t if len(t) <= limit else t[: limit - 1] + "…"


def _default_buttons(ctx: dict[str, str]) -> list[dict[str, str]]:
    url = ctx.get("url") or ctx.get("adminUrl") or ""
    if url:
        return [{"text": "（ボタンラベル）", "url": url}]
    return []


def _build_info_block(template_key: str, ctx: dict[str, str]) -> str:
    rows: list[tuple[str, str]] = []
    for fk in ADMIN_NOTIFY_EVENT_VISIBLE_FIELDS.get(template_key, []):
        if fk not in ADMIN_NOTIFY_INFO_FIELD_DEFS:
            continue
        label, var_key = ADMIN_NOTIFY_INFO_FIELD_DEFS[fk]
        value = ctx.get(var_key, "")
        if value and value != "—":
            rows.append((label, html.escape(str(value))))
    return build_admin_notify_info_block(rows)


def _build_error_block(error_message: str | None) -> str:
    if not error_message:
        return ""
    safe = html.escape(_sanitize_snippet(error_message, 500))
    return f'<div style="margin:0 0 20px;padding:12px 16px;background:#fef2f2;border:1px solid #fecaca;border-radius:8px;font-size:14px;color:#991b1b;">{safe}</div>'


def _build_log_block(log_snippet: str | None) -> str:
    if not log_snippet:
        return ""
    safe = html.escape(_sanitize_snippet(log_snippet, 500))
    return f'<pre style="margin:0 0 20px;padding:12px 16px;background:#f8fafc;border:1px solid #e2e8f0;border-radius:8px;font-size:12px;color:#475569;white-space:pre-wrap;word-break:break-word;">{safe}</pre>'


def build_admin_notify_email_variables(
    db,
    event_key: str,
    *,
    body_title: Optional[str] = None,
    body_description: Optional[str] = None,
    notes_html: Optional[str] = None,
    contact_html: Optional[str] = None,
    buttons: Optional[list[dict[str, str]]] = None,
    error_message: str | None = None,
    log_snippet: str | None = None,
    include_error: bool = False,
    include_log: bool = False,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    event_key = normalize_template_key(event_key)
    p_title, p_desc, p_notes, p_contact = _placeholder_copy()
    title = body_title or p_title
    desc = body_description or p_desc
    notes = notes_html if notes_html is not None else p_notes
    contact = contact_html if contact_html is not None else p_contact

    brand = get_brand_settings(db) if db is not None else None
    signature_html = (getattr(brand, "email_signature_html", None) if brand else None) or ""
    brand_color = (brand.brand_color if brand else None) or "#ca8a04"
    base_url = settings.FRONTEND_URL.rstrip("/") if settings.FRONTEND_URL else ""
    admin_url = f"{base_url}/admin" if base_url else ""
    event_at = _format_jst()

    ctx = {
        "orderNo": (extra or {}).get("orderNo", "ORD-SAMPLE-001"),
        "buybackNo": (extra or {}).get("buybackNo", "BB-SAMPLE-001"),
        "inquiryNo": (extra or {}).get("inquiryNo", "INQ-SAMPLE-001"),
        "userName": (extra or {}).get("userName", "山田 太郎"),
        "adminName": (extra or {}).get("adminName", "管理者"),
        "eventAt": event_at,
        "productName": (extra or {}).get("productName", "サンプル商品"),
        "orderAmount": (extra or {}).get("orderAmount", "¥12,800"),
        "assessmentAmount": (extra or {}).get("assessmentAmount", "¥8,500"),
        "carrier": (extra or {}).get("carrier", "ヤマト運輸"),
        "trackingNo": (extra or {}).get("trackingNo", "1234-5678-9012"),
        "assignee": (extra or {}).get("assignee", "担当者A"),
        "serverName": (extra or {}).get("serverName", "production"),
        "systemName": (extra or {}).get("systemName", settings.SITE_NAME or "KRX TCG"),
        "ipAddress": (extra or {}).get("ipAddress", "203.0.113.1"),
        "url": (extra or {}).get("url", admin_url),
        "adminUrl": admin_url,
    }
    if extra:
        for k, v in extra.items():
            if k not in ctx and v is not None:
                ctx[k] = v

    info_block = _build_info_block(event_key, ctx)
    err_block = _build_error_block(error_message) if include_error and error_message else ""
    log_block = _build_log_block(log_snippet) if include_log and log_snippet else ""
    btn_list = buttons if buttons is not None else _default_buttons(ctx)

    variables: dict[str, Any] = {
        "name": ctx["adminName"],
        "adminName": ctx["adminName"],
        "管理者名": ctx["adminName"],
        "userName": ctx["userName"],
        "ユーザー名": ctx["userName"],
        "shopName": settings.SITE_NAME or "KRX TCG",
        "orderNo": ctx["orderNo"],
        "注文番号": ctx["orderNo"],
        "buybackNo": ctx["buybackNo"],
        "買取番号": ctx["buybackNo"],
        "inquiryNo": ctx["inquiryNo"],
        "お問い合わせ番号": ctx["inquiryNo"],
        "eventAt": event_at,
        "日時": event_at,
        "date": event_at,
        "productName": ctx["productName"],
        "商品名": ctx["productName"],
        "orderAmount": ctx["orderAmount"],
        "注文金額": ctx["orderAmount"],
        "assessmentAmount": ctx["assessmentAmount"],
        "査定金額": ctx["assessmentAmount"],
        "carrier": ctx["carrier"],
        "配送会社": ctx["carrier"],
        "trackingNo": ctx["trackingNo"],
        "送り状番号": ctx["trackingNo"],
        "assignee": ctx["assignee"],
        "担当者": ctx["assignee"],
        "serverName": ctx["serverName"],
        "サーバー": ctx["serverName"],
        "systemName": ctx["systemName"],
        "システム名": ctx["systemName"],
        "ipAddress": ctx["ipAddress"],
        "IPアドレス": ctx["ipAddress"],
        "url": ctx["url"],
        "URL": ctx["url"],
        "adminUrl": admin_url,
        "bodyTitle": title,
        "bodyDescription": desc,
        "adminNotifyInfoBlock": info_block,
        "errorBlock": err_block,
        "logBlock": log_block,
        "errorMessage": html.escape(_sanitize_snippet(error_message)) if error_message else "",
        "エラー内容": html.escape(_sanitize_snippet(error_message)) if error_message else "",
        "logSnippet": html.escape(_sanitize_snippet(log_snippet)) if log_snippet else "",
        "ログ": html.escape(_sanitize_snippet(log_snippet)) if log_snippet else "",
        "content": err_block or log_block,
        "buttonsBlock": build_buttons_block(btn_list, brand_color=brand_color),
        "notesBlock": build_notes_block(notes),
        "contactBlock": build_contact_block(contact),
        "signatureBlock": build_signature_block(signature_html),
    }

    summary_lines = [
        f"{label}: {ctx.get(var_key, '')}"
        for fk in ADMIN_NOTIFY_EVENT_VISIBLE_FIELDS.get(event_key, [])
        if fk in ADMIN_NOTIFY_INFO_FIELD_DEFS
        for label, var_key in [ADMIN_NOTIFY_INFO_FIELD_DEFS[fk]]
        if ctx.get(var_key)
    ]
    variables["_text_body"] = build_text_body(
        name=ctx["adminName"],
        body_title=title,
        body_description=desc,
        order_summary_lines=summary_lines or None,
        notes=notes.replace("<br>", "\n") if notes else "",
        contact=contact.replace("<br>", "\n") if contact else "",
        buttons=btn_list,
    )
    event = get_admin_notify_email_event(event_key)
    if event:
        variables.setdefault("bodyTitle", f"（{event.description}）")
    return variables


def build_admin_notify_sample_variables(template_key: str) -> dict[str, Any]:
    key = normalize_template_key(template_key)
    include_error = key.startswith("admin_notify_system_") or "error" in key
    include_log = key in {"admin_notify_security_audit_log", "admin_notify_system_job_failed"}
    return build_admin_notify_email_variables(
        None,
        key,
        include_error=include_error,
        include_log=include_log,
        error_message="Sample error: connection timeout" if include_error else None,
        log_snippet="[INFO] job started\n[ERROR] retry exceeded" if include_log else None,
    )


def admin_notify_variables_for_template(template_key: str) -> list[str]:
    sample = build_admin_notify_sample_variables(template_key)
    return sorted(k for k in sample.keys() if not str(k).startswith("_"))
