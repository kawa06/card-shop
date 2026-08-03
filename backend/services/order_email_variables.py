"""Build order email template variables from Order model."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

import models
from config import settings
from services.email_delivery import get_brand_settings
from services.email_order_layout import (
    build_buttons_block,
    build_contact_block,
    build_item_row,
    build_items_table_html,
    build_notes_block,
    build_order_summary_block,
    build_signature_block,
    build_text_body,
)
from services.order_email_utils import (
    SHIPPING_METHOD_LABELS,
    format_datetime_jst,
    format_jpy,
    order_subtotal,
    payment_method_label,
)


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


def _order_summary_block(order: models.Order) -> str:
    method_label = SHIPPING_METHOD_LABELS.get(order.shipping_method or "", order.shipping_method or "—")
    rows: list[tuple[str, str]] = []
    if order.order_number:
        rows.append(("注文番号", order.order_number))
    elif order.id:
        rows.append(("受付ID", f"#{order.id}"))
    order_date = format_datetime_jst(order.paid_at or order.created_at)
    if order_date:
        rows.append(("注文日時", order_date))
    rows.append(("お支払方法", payment_method_label(order)))
    if order.payment_deadline:
        rows.append(("お支払期限", format_datetime_jst(order.payment_deadline)))
    rows.append(("発送方法", method_label))
    subtotal = order_subtotal(order)
    shipping = order.shipping_fee or 0
    rows.append(("商品小計", format_jpy(subtotal)))
    rows.append(("送料", format_jpy(shipping)))
    rows.append(("合計", f'<strong style="color:#ca8a04;">{format_jpy(order.total_amount)}</strong>'))
    return build_order_summary_block(rows)


def _default_buttons(event_key: str, order: models.Order) -> list[dict[str, str]]:
    base = settings.FRONTEND_URL or ""
    order_url = f"{base}/orders" if base else ""
    if event_key in {"payment_pending", "payment_failed", "order_received"} and order_url:
        return [{"text": "（ボタンラベル）", "url": order_url}]
    if event_key == "payment_success" and order_url:
        return [{"text": "（ボタンラベル）", "url": order_url}]
    return []


def _placeholder_copy(event_key: str) -> tuple[str, str, str, str]:
    """Structure-only placeholders — admin replaces via template editor."""
    return (
        "（本文タイトル）",
        "（本文説明を入力してください）",
        "（注意事項を入力してください）",
        "（お問い合わせ案内を入力してください）",
    )


def build_order_email_variables(
    order: models.Order,
    event_key: str,
    *,
    db=None,
    body_title: Optional[str] = None,
    body_description: Optional[str] = None,
    notes_html: Optional[str] = None,
    contact_html: Optional[str] = None,
    buttons: Optional[list[dict[str, str]]] = None,
    brand_color: str = "#ca8a04",
) -> dict[str, Any]:
    name = _buyer_name(order)
    p_title, p_desc, p_notes, p_contact = _placeholder_copy(event_key)
    title = body_title or p_title
    desc = body_description or p_desc
    notes = notes_html if notes_html is not None else p_notes
    contact = contact_html if contact_html is not None else p_contact
    btn_list = buttons if buttons is not None else _default_buttons(event_key, order)

    brand = get_brand_settings(db)
    signature_html = getattr(brand, "email_signature_html", None) or ""

    items_table = _order_items_table(order)
    summary = _order_summary_block(order)
    buttons_block = build_buttons_block(btn_list, brand_color=brand_color)
    notes_block = build_notes_block(notes)
    contact_block = build_contact_block(contact)
    signature_block = build_signature_block(signature_html) if db else ""

    order_no = order.order_number or str(order.id)
    order_date = format_datetime_jst(order.paid_at or order.created_at)

    variables: dict[str, Any] = {
        "name": name,
        "ユーザー名": name,
        "email": order.user.email if order.user else "",
        "orderNo": order_no,
        "注文番号": order_no,
        "orderDate": order_date,
        "注文日時": order_date,
        "orderAmount": format_jpy(order.total_amount),
        "注文金額": format_jpy(order.total_amount),
        "paymentMethod": payment_method_label(order),
        "決済方法": payment_method_label(order),
        "totalAmount": format_jpy(order.total_amount),
        "bodyTitle": title,
        "bodyDescription": desc,
        "orderSummaryBlock": summary,
        "itemsTable": items_table,
        "注文商品": items_table,
        "buttonsBlock": buttons_block,
        "notesBlock": notes_block,
        "contactBlock": contact_block,
        "signatureBlock": signature_block,
        "url": settings.FRONTEND_URL or "",
        "shopName": settings.SITE_NAME or "KRX TCG",
        "date": datetime.utcnow().strftime("%Y/%m/%d %H:%M"),
    }
    variables["_text_body"] = build_text_body(
        name=name,
        body_title=title,
        body_description=desc,
        order_summary_lines=[
            f"注文番号: {order_no}",
            f"合計: {format_jpy(order.total_amount)}",
        ],
        notes=notes.replace("<br>", "\n").replace("<br/>", "\n") if notes else "",
        contact=contact.replace("<br>", "\n").replace("<br/>", "\n") if contact else "",
        buttons=btn_list,
    )
    return variables


RAW_ORDER_VARIABLE_KEYS = frozenset({
    "orderSummaryBlock",
    "itemsTable",
    "注文商品",
    "buttonsBlock",
    "notesBlock",
    "contactBlock",
    "signatureBlock",
    "content",
})
