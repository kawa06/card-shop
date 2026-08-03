"""Build shipping/delivery email template variables from Order model."""

from __future__ import annotations

import html
from datetime import datetime
from typing import Any, Optional

import models
from config import settings
from services.carrier_registry import resolve_carrier_id
from services.email_delivery import get_brand_settings
from services.email_order_layout import (
    build_buttons_block,
    build_contact_block,
    build_item_row,
    build_items_table_html,
    build_notes_block,
    build_order_summary_block,
    build_signature_block,
    build_shipping_info_block,
    build_text_body,
)
from services.order_email_utils import SHIPPING_METHOD_LABELS, format_datetime_jst, format_jpy
from services.shipping_email_registry import get_shipping_email_event, normalize_template_key
from services.tracking_urls import build_tracking_url, carrier_display_name

# Field key → (label, variable keys for value)
SHIPPING_INFO_FIELD_DEFS: dict[str, tuple[str, str]] = {
    "carrier": ("配送会社", "carrier"),
    "trackingNo": ("送り状番号", "trackingNo"),
    "shippedDate": ("発送日時", "shippedDate"),
    "shippingMethod": ("発送方法", "shippingMethod"),
    "shippingStatus": ("配送状況", "shippingStatus"),
    "deliveryDate": ("配送予定日", "deliveryDate"),
    "shippingAddress": ("配送先住所", "shippingAddress"),
    "inquiryNo": ("お問い合わせ番号", "inquiryNo"),
    "trackingUrl": ("追跡URL", "trackingUrl"),
}

# Per-event visible shipping info fields — extend without changing send code
SHIPPING_EVENT_VISIBLE_FIELDS: dict[str, list[str]] = {
    "shipping_preparing": ["shippingMethod", "shippingStatus", "shippingAddress"],
    "shipping_shipped": [
        "carrier", "trackingNo", "shippedDate", "shippingMethod",
        "shippingStatus", "shippingAddress", "trackingUrl",
    ],
    "shipping_handed_to_carrier": [
        "carrier", "trackingNo", "shippedDate", "shippingMethod", "trackingUrl",
    ],
    "shipping_tracking_issued": ["carrier", "trackingNo", "trackingUrl", "shippingMethod"],
    "shipping_delivered": ["carrier", "trackingNo", "shippedDate", "deliveryDate", "shippingAddress"],
    "shipping_delay_notice": ["carrier", "trackingNo", "deliveryDate", "shippingStatus", "trackingUrl"],
    "shipping_address_issue": ["shippingAddress", "shippingMethod", "carrier"],
    "shipping_absence_return": ["carrier", "trackingNo", "trackingUrl", "shippingAddress"],
    "shipping_return_started": ["carrier", "trackingNo", "trackingUrl", "shippingAddress"],
    "shipping_return_completed": ["carrier", "trackingNo", "shippingAddress"],
}

SHIPPING_STATUS_LABELS: dict[str, str] = {
    "unshipped": "未発送",
    "preparing": "発送準備中",
    "shipped": "発送済み",
    "in_transit": "配送中",
    "delivered": "配達完了",
    "returned": "返送",
    "delayed": "配送遅延",
    "address_issue": "住所不備",
    "absence_return": "持ち戻り",
}

RAW_SHIPPING_VARIABLE_KEYS = frozenset({
    "shippingInfoBlock",
    "orderSummaryBlock",
    "itemsTable",
    "注文商品",
    "buttonsBlock",
    "notesBlock",
    "contactBlock",
    "signatureBlock",
    "content",
})


def _buyer_name(order: models.Order) -> str:
    buyer = order.user
    if buyer and buyer.name:
        return buyer.name
    if buyer and buyer.email:
        return buyer.email.split("@")[0]
    return "お客様"


def _order_items_table(order: models.Order) -> str:
    rows = ""
    for item in order.items:
        name = item.card.name if item.card else (item.product_name or f"商品 #{item.card_id}")
        rows += build_item_row(name, item.quantity, format_jpy(item.unit_price))
    return build_items_table_html(rows) if rows else ""


def _minimal_order_summary(order: models.Order) -> str:
    rows: list[tuple[str, str]] = []
    if order.order_number:
        rows.append(("注文番号", order.order_number))
    return build_order_summary_block(rows)


def _placeholder_copy() -> tuple[str, str, str, str]:
    return (
        "（本文タイトル）",
        "（本文説明を入力してください）",
        "（注意事項を入力してください）",
        "（お問い合わせ案内を入力してください）",
    )


def _default_shipping_buttons(event_key: str, ctx: dict[str, Any]) -> list[dict[str, str]]:
    base = settings.FRONTEND_URL or ""
    orders_url = f"{base}/orders" if base else ""
    tracking_url = ctx.get("trackingUrl") or ctx.get("url") or ""
    contact_url = ctx.get("contactUrl") or ""

    if event_key in {"shipping_shipped", "shipping_tracking_issued", "shipping_handed_to_carrier"}:
        buttons = []
        if tracking_url:
            buttons.append({"text": "（ボタンラベル）", "url": tracking_url})
        if orders_url:
            buttons.append({"text": "（ボタンラベル）", "url": orders_url})
        return buttons
    if event_key == "shipping_delivered" and orders_url:
        return [{"text": "（ボタンラベル）", "url": orders_url}]
    if contact_url:
        return [{"text": "（ボタンラベル）", "url": contact_url}]
    return []


def _scalar_shipping_context(
    order: models.Order,
    *,
    delivery_date: Optional[str] = None,
    shipping_status: Optional[str] = None,
    inquiry_no: Optional[str] = None,
) -> dict[str, str]:
    tracking = (order.tracking_number or "").strip()
    carrier = carrier_display_name(order.shipping_method, order.shipping_carrier)
    method_label = SHIPPING_METHOD_LABELS.get(order.shipping_method or "", order.shipping_method or "—")
    tracking_url = build_tracking_url(
        tracking,
        shipping_method=order.shipping_method,
        shipping_carrier=order.shipping_carrier,
    ) or ""
    status_key = shipping_status or order.shipping_status or ""
    status_label = SHIPPING_STATUS_LABELS.get(status_key, status_key or "—")
    address = (order.shipping_address or "").replace("\n", "<br>")
    shipped = format_datetime_jst(order.shipped_at) if order.shipped_at else ""

    return {
        "carrier": carrier,
        "配送会社": carrier,
        "trackingNo": tracking,
        "送り状番号": tracking,
        "tracking": tracking,
        "shippedDate": shipped,
        "発送日": shipped,
        "date": shipped or datetime.utcnow().strftime("%Y/%m/%d %H:%M"),
        "shippingMethod": method_label,
        "配送方法": method_label,
        "shippingStatus": status_label,
        "配送状況": status_label,
        "deliveryDate": delivery_date or "",
        "配送予定日": delivery_date or "",
        "shippingAddress": address,
        "配送先住所": address,
        "inquiryNo": inquiry_no or tracking,
        "お問い合わせ番号": inquiry_no or tracking,
        "trackingUrl": tracking_url,
        "追跡URL": tracking_url,
        "url": tracking_url or (settings.FRONTEND_URL or ""),
        "carrierId": resolve_carrier_id(order.shipping_method, order.shipping_carrier) or "",
    }


def _build_shipping_info_block_for_event(event_key: str, ctx: dict[str, str]) -> str:
    field_keys = SHIPPING_EVENT_VISIBLE_FIELDS.get(event_key, list(SHIPPING_INFO_FIELD_DEFS.keys()))
    rows: list[tuple[str, str]] = []
    for fk in field_keys:
        if fk not in SHIPPING_INFO_FIELD_DEFS:
            continue
        label, var_key = SHIPPING_INFO_FIELD_DEFS[fk]
        value = ctx.get(var_key, "")
        if fk == "trackingUrl" and value:
            safe = html.escape(value, quote=True)
            value = f'<a href="{safe}" style="color:#ca8a04;font-weight:600;">{safe}</a>'
        elif fk == "trackingNo" and ctx.get("trackingUrl"):
            safe_num = html.escape(str(value), quote=True)
            safe_url = html.escape(ctx["trackingUrl"], quote=True)
            value = f'<a href="{safe_url}" style="color:#ca8a04;font-weight:600;">{safe_num}</a>'
        rows.append((label, value))
    return build_shipping_info_block(rows)


def build_shipping_email_variables(
    db,
    order: models.Order,
    event_key: str,
    *,
    body_title: Optional[str] = None,
    body_description: Optional[str] = None,
    notes_html: Optional[str] = None,
    contact_html: Optional[str] = None,
    buttons: Optional[list[dict[str, str]]] = None,
    brand_color: str = "#ca8a04",
    delivery_date: Optional[str] = None,
    shipping_status: Optional[str] = None,
    inquiry_no: Optional[str] = None,
    visible_fields: Optional[list[str]] = None,
) -> dict[str, Any]:
    event_key = normalize_template_key(event_key)
    name = _buyer_name(order)
    p_title, p_desc, p_notes, p_contact = _placeholder_copy()
    title = body_title or p_title
    desc = body_description or p_desc
    notes = notes_html if notes_html is not None else p_notes
    contact = contact_html if contact_html is not None else p_contact

    brand = get_brand_settings(db)
    signature_html = getattr(brand, "email_signature_html", None) or ""
    if brand.contact_url:
        contact_url = brand.contact_url
    else:
        contact_url = settings.FRONTEND_URL or ""

    ctx = _scalar_shipping_context(
        order,
        delivery_date=delivery_date,
        shipping_status=shipping_status,
        inquiry_no=inquiry_no,
    )
    if visible_fields is not None:
        field_keys = visible_fields
        shipping_info = build_shipping_info_block([
            (SHIPPING_INFO_FIELD_DEFS[fk][0], ctx.get(SHIPPING_INFO_FIELD_DEFS[fk][1], ""))
            for fk in field_keys if fk in SHIPPING_INFO_FIELD_DEFS
        ])
    else:
        shipping_info = _build_shipping_info_block_for_event(event_key, ctx)

    btn_list = buttons if buttons is not None else _default_shipping_buttons(event_key, {**ctx, "contactUrl": contact_url})
    items_table = _order_items_table(order)
    order_no = order.order_number or str(order.id)

    variables: dict[str, Any] = {
        "name": name,
        "ユーザー名": name,
        "email": order.user.email if order.user else "",
        "orderNo": order_no,
        "注文番号": order_no,
        "bodyTitle": title,
        "bodyDescription": desc,
        "shippingInfoBlock": shipping_info,
        "orderSummaryBlock": _minimal_order_summary(order),
        "itemsTable": items_table,
        "注文商品": items_table,
        "buttonsBlock": build_buttons_block(btn_list, brand_color=brand_color or brand.brand_color or "#ca8a04"),
        "notesBlock": build_notes_block(notes),
        "contactBlock": build_contact_block(contact),
        "signatureBlock": build_signature_block(signature_html),
        "shopName": settings.SITE_NAME or "KRX TCG",
        "contactUrl": contact_url,
        "お問い合わせURL": contact_url,
        **ctx,
    }

    summary_lines = [f"注文番号: {order_no}"]
    for fk in SHIPPING_EVENT_VISIBLE_FIELDS.get(event_key, []):
        if fk in SHIPPING_INFO_FIELD_DEFS:
            label, var_key = SHIPPING_INFO_FIELD_DEFS[fk]
            val = ctx.get(var_key, "")
            if val and fk != "trackingUrl":
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


def build_shipping_sample_variables(template_key: str) -> dict[str, Any]:
    """Sample data for admin preview/test-send."""
    template_key = normalize_template_key(template_key)
    event = get_shipping_email_event(template_key)
    event_key = event.event_key if event else template_key

    sample_ctx = {
        "carrier": "ヤマト運輸",
        "配送会社": "ヤマト運輸",
        "trackingNo": "1234-5678-9012",
        "送り状番号": "1234-5678-9012",
        "shippedDate": "2026/08/03 14:30",
        "発送日": "2026/08/03 14:30",
        "shippingMethod": "宅急便",
        "配送方法": "宅急便",
        "shippingStatus": "配送中",
        "配送状況": "配送中",
        "deliveryDate": "2026/08/05",
        "配送予定日": "2026/08/05",
        "shippingAddress": "東京都渋谷区〇〇 1-2-3",
        "配送先住所": "東京都渋谷区〇〇 1-2-3",
        "inquiryNo": "1234-5678-9012",
        "お問い合わせ番号": "1234-5678-9012",
        "trackingUrl": "https://track.kuronekoyamato.co.jp/english/tracking/inquiry?number=1234-5678-9012",
        "追跡URL": "https://track.kuronekoyamato.co.jp/english/tracking/inquiry?number=1234-5678-9012",
        "url": settings.FRONTEND_URL or "https://example.com",
        "contactUrl": settings.FRONTEND_URL or "https://example.com/contact",
        "お問い合わせURL": settings.FRONTEND_URL or "https://example.com/contact",
    }

    shipping_info = _build_shipping_info_block_for_event(event_key, sample_ctx)
    items_rows = build_item_row("サンプル商品 A", 2, "¥1,000")
    items_table = build_items_table_html(items_rows)
    buttons = _default_shipping_buttons(event_key, sample_ctx)
    brand_color = "#ca8a04"

    variables: dict[str, Any] = {
        "name": "山田 太郎",
        "ユーザー名": "山田 太郎",
        "email": "sample@example.com",
        "orderNo": "ORD-20260801-001",
        "注文番号": "ORD-20260801-001",
        "bodyTitle": "（本文タイトル）",
        "bodyDescription": "（本文説明を入力してください）",
        "shippingInfoBlock": shipping_info,
        "orderSummaryBlock": build_order_summary_block([("注文番号", "ORD-20260801-001")]),
        "itemsTable": items_table,
        "注文商品": items_table,
        "buttonsBlock": build_buttons_block(buttons, brand_color=brand_color),
        "notesBlock": build_notes_block("（注意事項を入力してください）"),
        "contactBlock": build_contact_block("（お問い合わせ案内を入力してください）"),
        "signatureBlock": build_signature_block("（署名）"),
        "shopName": settings.SITE_NAME or "KRX TCG",
        **sample_ctx,
    }
    return variables


def shipping_variables_for_template(template_key: str) -> list[str]:
    template_key = normalize_template_key(template_key)
    base = [
        "name", "orderNo", "bodyTitle", "bodyDescription",
        "shippingInfoBlock", "itemsTable", "buttonsBlock",
        "notesBlock", "contactBlock", "signatureBlock",
        "carrier", "trackingNo", "shippedDate", "shippingMethod",
        "shippingStatus", "deliveryDate", "shippingAddress",
        "inquiryNo", "trackingUrl", "contactUrl",
    ]
    event = get_shipping_email_event(template_key)
    if event:
        return base
    return base
