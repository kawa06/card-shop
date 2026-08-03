"""Build buyback email template variables from BuybackRequest model."""

from __future__ import annotations

import html
from datetime import datetime
from typing import Any, Optional

import models
import models_buyback
from config import settings
from services.buyback_email_registry import (
    BUYBACK_EMAIL_EVENTS,
    get_buyback_email_event,
    normalize_template_key,
)
from services.buyback_request_status import STATUS_LABELS
from services.carrier_registry import resolve_carrier_id
from services.email_delivery import get_brand_settings
from services.email_order_layout import (
    build_buttons_block,
    build_buyback_info_block,
    build_contact_block,
    build_notes_block,
    build_order_summary_block,
    build_signature_block,
    build_text_body,
)
from services.tracking_urls import build_tracking_url, carrier_display_name

BUYBACK_METHOD_LABELS = {
    "mail": "郵送買取",
    "store": "店舗買取",
}

BUYBACK_INFO_FIELD_DEFS: dict[str, tuple[str, str]] = {
    "buyNo": ("買取番号", "buyNo"),
    "receivedAt": ("受付日時", "receivedAt"),
    "buybackMethod": ("買取方法", "buybackMethod"),
    "storeName": ("店舗名", "storeName"),
    "visitAt": ("来店日時", "visitAt"),
    "statusLabel": ("ステータス", "statusLabel"),
    "assessmentStartedAt": ("査定開始日時", "assessmentStartedAt"),
    "assessmentCompletedAt": ("査定完了日時", "assessmentCompletedAt"),
    "assessedAmount": ("査定金額", "assessedAmount"),
    "approvalDeadline": ("承認期限", "approvalDeadline"),
    "payoutAmount": ("振込金額", "payoutAmount"),
    "paidAt": ("振込日時", "paidAt"),
    "returnReason": ("返送理由", "returnReason"),
    "carrier": ("配送会社", "carrier"),
    "trackingNo": ("送り状番号", "trackingNo"),
    "trackingUrl": ("追跡URL", "trackingUrl"),
}

BUYBACK_EVENT_VISIBLE_FIELDS: dict[str, list[str]] = {
    "buyback_request_submitted": ["buyNo", "receivedAt", "buybackMethod", "statusLabel"],
    "buyback_request_updated": ["buyNo", "statusLabel", "buybackMethod"],
    "buyback_request_cancelled": ["buyNo", "statusLabel"],
    "buyback_awaiting_shipment": ["buyNo", "buybackMethod", "statusLabel"],
    "buyback_ship_deadline_notice": ["buyNo", "approvalDeadline"],
    "buyback_ship_deadline_soon": ["buyNo", "approvalDeadline"],
    "buyback_ship_deadline_expired": ["buyNo", "approvalDeadline"],
    "buyback_shipment_confirmed": ["buyNo", "trackingNo", "carrier", "trackingUrl"],
    "buyback_inbound_received": ["buyNo", "receivedAt", "statusLabel"],
    "buyback_store_reservation": ["buyNo", "storeName", "visitAt", "buybackMethod"],
    "buyback_store_reschedule": ["buyNo", "storeName", "visitAt"],
    "buyback_store_reminder": ["buyNo", "storeName", "visitAt"],
    "buyback_store_checkin": ["buyNo", "storeName", "visitAt"],
    "buyback_store_assessing_start": ["buyNo", "assessmentStartedAt"],
    "buyback_assessing": ["buyNo", "assessmentStartedAt", "statusLabel"],
    "buyback_assessing_in_progress": ["buyNo", "assessmentStartedAt", "statusLabel"],
    "buyback_assessment_ready": ["buyNo", "assessedAmount", "assessmentCompletedAt"],
    "buyback_assessment_result": ["buyNo", "assessedAmount", "assessmentCompletedAt"],
    "buyback_assessment_amount_changed": ["buyNo", "assessedAmount"],
    "buyback_awaiting_approval": ["buyNo", "assessedAmount", "approvalDeadline"],
    "buyback_accepted": ["buyNo", "assessedAmount", "payoutAmount"],
    "buyback_rejected": ["buyNo", "assessedAmount", "returnReason"],
    "buyback_approval_deadline_soon": ["buyNo", "approvalDeadline"],
    "buyback_approval_deadline_expired": ["buyNo", "approvalDeadline"],
    "buyback_payout_preparing": ["buyNo", "payoutAmount"],
    "buyback_payout_completed": ["buyNo", "payoutAmount", "paidAt"],
    "buyback_payout_on_hold": ["buyNo", "payoutAmount", "statusLabel"],
    "buyback_return_received": ["buyNo", "returnReason"],
    "buyback_return_preparing": ["buyNo", "returnReason"],
    "buyback_return_shipped": ["buyNo", "trackingNo", "carrier", "trackingUrl"],
    "buyback_return_completed": ["buyNo", "trackingNo"],
    "buyback_cancelled": ["buyNo", "statusLabel"],
    "buyback_system_error": ["buyNo", "statusLabel"],
}

RAW_BUYBACK_VARIABLE_KEYS = frozenset({
    "buybackInfoBlock",
    "buybackSummaryBlock",
    "itemsTable",
    "assessmentDetail",
    "buttonsBlock",
    "notesBlock",
    "contactBlock",
    "signatureBlock",
    "content",
})


def _format_jpy(amount: int | None) -> str:
    return f"¥{int(amount or 0):,}"


def _format_dt(value: datetime | None) -> str:
    if not value:
        return ""
    return value.strftime("%Y/%m/%d %H:%M")


def _request_link(request_id: int) -> str:
    base = (settings.BUYLIST_URL or settings.FRONTEND_URL or "").rstrip("/")
    return f"{base}/request.html?id={request_id}" if base else ""


def _items_table_html(request: models_buyback.BuybackRequest) -> str:
    rows = ""
    for item in request.items or []:
        line_total = (item.listed_unit_price or 0) * (item.quantity or 0)
        rows += (
            "<tr>"
            f"<td style='padding:12px 14px;border-top:1px solid #e2e8f0;color:#1e293b;'>"
            f"{html.escape(item.product_name_snapshot or '')}</td>"
            f"<td style='padding:12px 10px;border-top:1px solid #e2e8f0;text-align:center;color:#475569;'>"
            f"{html.escape(item.condition_code or '')}</td>"
            f"<td style='padding:12px 10px;border-top:1px solid #e2e8f0;text-align:center;color:#475569;'>"
            f"{item.quantity or 0}</td>"
            f"<td style='padding:12px 14px;border-top:1px solid #e2e8f0;text-align:right;color:#1e293b;'>"
            f"{_format_jpy(line_total)}</td>"
            "</tr>"
        )
    if not rows:
        return ""
    return (
        "<table role='presentation' width='100%' cellpadding='0' cellspacing='0' "
        "style='border-collapse:collapse;margin:0 0 24px;font-size:14px;border:1px solid #e2e8f0;border-radius:8px;'>"
        "<thead><tr style='background:#f8fafc;'>"
        "<th style='padding:12px 14px;text-align:left;font-size:12px;color:#64748b;'>商品</th>"
        "<th style='padding:12px 10px;text-align:left;font-size:12px;color:#64748b;'>状態</th>"
        "<th style='padding:12px 10px;text-align:center;font-size:12px;color:#64748b;'>数量</th>"
        "<th style='padding:12px 14px;text-align:right;font-size:12px;color:#64748b;'>参考小計</th>"
        "</tr></thead><tbody>"
        + rows
        + "</tbody></table>"
    )


def _assessment_detail_html(request: models_buyback.BuybackRequest) -> str:
    rows = ""
    shipping_total = 0
    for item in request.items or []:
        assessed = item.assessed_unit_price if item.assessed_unit_price is not None else item.listed_unit_price
        line_total = (assessed or 0) * (item.quantity or 0)
        reduction = item.rejection_reason_text or item.rejection_reason_code or ""
        if item.return_shipping_cost:
            shipping_total += int(item.return_shipping_cost)
        rows += (
            "<tr>"
            f"<td style='padding:8px;border-bottom:1px solid #eee;'>{html.escape(item.product_name_snapshot or '')}</td>"
            f"<td style='padding:8px;border-bottom:1px solid #eee;text-align:right;'>{_format_jpy(assessed)}</td>"
            f"<td style='padding:8px;border-bottom:1px solid #eee;text-align:center;'>{item.quantity or 0}</td>"
            f"<td style='padding:8px;border-bottom:1px solid #eee;text-align:right;'>{_format_jpy(line_total)}</td>"
            f"<td style='padding:8px;border-bottom:1px solid #eee;font-size:12px;color:#666;'>"
            f"{html.escape(reduction) if reduction else '—'}</td>"
            "</tr>"
        )
    if not rows:
        return ""
    assessed_total = request.assessed_total or 0
    payout_total = request.payout_total or assessed_total
    footer = (
        f"<tr><td colspan='4' style='padding:8px;text-align:right;font-weight:bold;'>査定合計</td>"
        f"<td style='padding:8px;text-align:right;font-weight:bold;'>{_format_jpy(assessed_total)}</td></tr>"
        f"<tr><td colspan='4' style='padding:8px;text-align:right;font-weight:bold;color:#ca8a04;'>お支払予定額</td>"
        f"<td style='padding:8px;text-align:right;font-weight:bold;color:#ca8a04;'>{_format_jpy(payout_total)}</td></tr>"
    )
    return (
        "<table role='presentation' width='100%' style='border-collapse:collapse;font-size:14px;margin:12px 0;'>"
        "<thead><tr>"
        "<th style='text-align:left;padding:8px;border-bottom:2px solid #ddd;'>商品</th>"
        "<th style='text-align:right;padding:8px;border-bottom:2px solid #ddd;'>査定単価</th>"
        "<th style='text-align:center;padding:8px;border-bottom:2px solid #ddd;'>数量</th>"
        "<th style='text-align:right;padding:8px;border-bottom:2px solid #ddd;'>小計</th>"
        "<th style='text-align:left;padding:8px;border-bottom:2px solid #ddd;'>減額理由</th>"
        "</tr></thead><tbody>"
        + rows
        + footer
        + "</tbody></table>"
    )


def _build_info_block_for_event(event_key: str, ctx: dict[str, str]) -> str:
    field_keys = BUYBACK_EVENT_VISIBLE_FIELDS.get(event_key, ["buyNo", "statusLabel"])
    rows: list[tuple[str, str]] = []
    for fk in field_keys:
        if fk not in BUYBACK_INFO_FIELD_DEFS:
            continue
        label, var_key = BUYBACK_INFO_FIELD_DEFS[fk]
        value = ctx.get(var_key, "")
        if fk == "trackingUrl" and value:
            safe = html.escape(value, quote=True)
            value = f'<a href="{safe}" style="color:#ca8a04;font-weight:600;">{safe}</a>'
        elif fk == "trackingNo" and ctx.get("trackingUrl"):
            safe_num = html.escape(str(value), quote=True)
            safe_url = html.escape(ctx["trackingUrl"], quote=True)
            value = f'<a href="{safe_url}" style="color:#ca8a04;font-weight:600;">{safe_num}</a>'
        rows.append((label, value))
    return build_buyback_info_block(rows)


def _default_buttons(event_key: str, ctx: dict[str, Any]) -> list[dict[str, str]]:
    link = ctx.get("requestUrl") or ctx.get("url") or ""
    contact = ctx.get("contactUrl") or ""
    tracking = ctx.get("trackingUrl") or ""
    buttons: list[dict[str, str]] = []
    if event_key in {"buyback_return_shipped", "buyback_shipment_confirmed"} and tracking:
        buttons.append({"text": "（ボタンラベル）", "url": tracking})
    if link:
        buttons.append({"text": "（ボタンラベル）", "url": link})
    elif contact:
        buttons.append({"text": "（ボタンラベル）", "url": contact})
    return buttons


def _scalar_context(
    request: models_buyback.BuybackRequest,
    *,
    return_reason: Optional[str] = None,
    approval_deadline: Optional[str] = None,
    package_tracking: Optional[str] = None,
    package_carrier: Optional[str] = None,
) -> dict[str, str]:
    tracking = (package_tracking or request.tracking_number or "").strip()
    carrier = carrier_display_name(request.shipping_method, package_carrier)
    tracking_url = build_tracking_url(
        tracking,
        shipping_method=request.shipping_method,
        shipping_carrier=package_carrier,
    ) or ""
    buy_no = request.public_buyback_code or request.request_number or str(request.id)
    return {
        "buyNo": buy_no,
        "買取番号": buy_no,
        "receivedAt": _format_dt(request.submitted_at or request.created_at),
        "受付日時": _format_dt(request.submitted_at or request.created_at),
        "buybackMethod": BUYBACK_METHOD_LABELS.get(request.buyback_method or "", request.buyback_method or "—"),
        "買取方法": BUYBACK_METHOD_LABELS.get(request.buyback_method or "", request.buyback_method or "—"),
        "storeName": settings.SITE_NAME or "KRX TCG",
        "店舗名": settings.SITE_NAME or "KRX TCG",
        "visitAt": _format_dt(request.store_visit_at),
        "来店日時": _format_dt(request.store_visit_at),
        "statusLabel": STATUS_LABELS.get(request.status, request.status),
        "assessmentStartedAt": _format_dt(request.assessed_at if request.status == "assessing" else None),
        "査定開始日時": _format_dt(request.assessed_at),
        "assessmentCompletedAt": _format_dt(request.assessed_at),
        "査定完了日時": _format_dt(request.assessed_at),
        "assessedAmount": _format_jpy(request.assessed_total),
        "査定金額": _format_jpy(request.assessed_total),
        "approvalDeadline": approval_deadline or "",
        "承認期限": approval_deadline or "",
        "payoutAmount": _format_jpy(request.payout_total or request.assessed_total),
        "振込金額": _format_jpy(request.payout_total or request.assessed_total),
        "paidAt": _format_dt(request.paid_at),
        "振込日時": _format_dt(request.paid_at),
        "returnReason": return_reason or "",
        "返送理由": return_reason or "",
        "carrier": carrier,
        "配送会社": carrier,
        "trackingNo": tracking,
        "送り状番号": tracking,
        "trackingUrl": tracking_url,
        "追跡URL": tracking_url,
        "requestUrl": _request_link(request.id),
        "url": _request_link(request.id),
        "carrierId": resolve_carrier_id(request.shipping_method, package_carrier) or "",
    }


def build_buyback_email_variables(
    db,
    user: models.User,
    request: models_buyback.BuybackRequest,
    event_key: str,
    *,
    body_title: Optional[str] = None,
    body_description: Optional[str] = None,
    notes_html: Optional[str] = None,
    contact_html: Optional[str] = None,
    buttons: Optional[list[dict[str, str]]] = None,
    include_assessment_detail: bool = False,
    return_reason: Optional[str] = None,
    approval_deadline: Optional[str] = None,
    package_tracking: Optional[str] = None,
    package_carrier: Optional[str] = None,
) -> dict[str, Any]:
    event_key = normalize_template_key(event_key)
    name = user.name or user.email.split("@")[0] if user.email else "お客様"
    title = body_title or "（本文タイトル）"
    desc = body_description or "（本文説明を入力してください）"
    notes = notes_html if notes_html is not None else "（注意事項を入力してください）"
    contact = contact_html if contact_html is not None else "（お問い合わせ案内を入力してください）"

    brand = get_brand_settings(db)
    signature_html = getattr(brand, "email_signature_html", None) or ""
    contact_url = brand.contact_url or settings.FRONTEND_URL or ""

    ctx = _scalar_context(
        request,
        return_reason=return_reason,
        approval_deadline=approval_deadline,
        package_tracking=package_tracking,
        package_carrier=package_carrier,
    )
    ctx["contactUrl"] = contact_url
    ctx["お問い合わせURL"] = contact_url

    buyback_info = _build_info_block_for_event(event_key, ctx)
    items_table = _items_table_html(request)
    assessment_detail = _assessment_detail_html(request) if include_assessment_detail else ""
    btn_list = buttons if buttons is not None else _default_buttons(event_key, ctx)

    summary_rows = [("買取番号", ctx["buyNo"]), ("ステータス", ctx["statusLabel"])]
    variables: dict[str, Any] = {
        "name": name,
        "ユーザー名": name,
        "email": user.email or "",
        "bodyTitle": title,
        "bodyDescription": desc,
        "buybackInfoBlock": buyback_info,
        "buybackSummaryBlock": build_order_summary_block(summary_rows),
        "itemsTable": items_table,
        "assessmentDetail": assessment_detail,
        "buttonsBlock": build_buttons_block(btn_list, brand_color=brand.brand_color or "#ca8a04"),
        "notesBlock": build_notes_block(notes),
        "contactBlock": build_contact_block(contact),
        "signatureBlock": build_signature_block(signature_html),
        "shopName": settings.SITE_NAME or "KRX TCG",
        "content": desc,
        **ctx,
    }
    variables["_text_body"] = build_text_body(
        name=name,
        body_title=title,
        body_description=desc,
        order_summary_lines=[f"買取番号: {ctx['buyNo']}", f"ステータス: {ctx['statusLabel']}"],
        notes=notes.replace("<br>", "\n") if notes else "",
        contact=contact.replace("<br>", "\n") if contact else "",
        buttons=btn_list,
    )
    return variables


def build_buyback_sample_variables(template_key: str) -> dict[str, Any]:
    template_key = normalize_template_key(template_key)
    event = get_buyback_email_event(template_key)
    event_key = event.event_key if event else template_key

    sample_ctx = {
        "buyNo": "BB-20260801-001",
        "買取番号": "BB-20260801-001",
        "receivedAt": "2026/08/01 10:30",
        "受付日時": "2026/08/01 10:30",
        "buybackMethod": "郵送買取",
        "買取方法": "郵送買取",
        "storeName": settings.SITE_NAME or "KRX TCG",
        "店舗名": settings.SITE_NAME or "KRX TCG",
        "visitAt": "2026/08/05 14:00",
        "来店日時": "2026/08/05 14:00",
        "statusLabel": "査定中",
        "assessmentStartedAt": "2026/08/03 11:00",
        "査定開始日時": "2026/08/03 11:00",
        "assessmentCompletedAt": "2026/08/03 15:30",
        "査定完了日時": "2026/08/03 15:30",
        "assessedAmount": "¥50,000",
        "査定金額": "¥50,000",
        "approvalDeadline": "2026/08/10 23:59",
        "承認期限": "2026/08/10 23:59",
        "payoutAmount": "¥48,000",
        "振込金額": "¥48,000",
        "paidAt": "2026/08/12 09:00",
        "振込日時": "2026/08/12 09:00",
        "returnReason": "（返送理由）",
        "返送理由": "（返送理由）",
        "carrier": "ヤマト運輸",
        "配送会社": "ヤマト運輸",
        "trackingNo": "1234-5678-9012",
        "送り状番号": "1234-5678-9012",
        "trackingUrl": "https://track.kuronekoyamato.co.jp/english/tracking/inquiry?number=1234-5678-9012",
        "追跡URL": "https://track.kuronekoyamato.co.jp/english/tracking/inquiry?number=1234-5678-9012",
        "contactUrl": settings.FRONTEND_URL or "https://example.com/contact",
        "お問い合わせURL": settings.FRONTEND_URL or "https://example.com/contact",
        "requestUrl": "https://example.com/request.html?id=1",
        "url": "https://example.com/request.html?id=1",
    }

    items_table = (
        "<table role='presentation'><tr><td>サンプル商品</td><td>美品</td><td>2</td><td>¥2,000</td></tr></table>"
    )
    buttons = _default_buttons(event_key, sample_ctx)

    return {
        "name": "山田 太郎",
        "ユーザー名": "山田 太郎",
        "email": "sample@example.com",
        "bodyTitle": "（本文タイトル）",
        "bodyDescription": "（本文説明を入力してください）",
        "buybackInfoBlock": _build_info_block_for_event(event_key, sample_ctx),
        "buybackSummaryBlock": build_order_summary_block([("買取番号", "BB-20260801-001")]),
        "itemsTable": items_table,
        "assessmentDetail": "",
        "buttonsBlock": build_buttons_block(buttons),
        "notesBlock": build_notes_block("（注意事項を入力してください）"),
        "contactBlock": build_contact_block("（お問い合わせ案内を入力してください）"),
        "signatureBlock": build_signature_block("（署名）"),
        "shopName": settings.SITE_NAME or "KRX TCG",
        **sample_ctx,
    }


def buyback_variables_for_template(template_key: str) -> list[str]:
    return [
        "name", "buyNo", "bodyTitle", "bodyDescription",
        "buybackInfoBlock", "itemsTable", "assessmentDetail", "buttonsBlock",
        "notesBlock", "contactBlock", "signatureBlock",
        "receivedAt", "buybackMethod", "storeName", "visitAt",
        "assessmentStartedAt", "assessmentCompletedAt", "assessedAmount",
        "approvalDeadline", "payoutAmount", "paidAt", "returnReason",
        "carrier", "trackingNo", "trackingUrl", "contactUrl",
    ]
