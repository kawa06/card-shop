"""Premium order/payment email inner layout — structure-only, content via variables."""

from __future__ import annotations

import html
import json
from typing import Any


def _esc(value: Any) -> str:
    return html.escape(str(value if value is not None else ""), quote=True)


# Standard inner body skeleton — admin edits copy via {{bodyTitle}} etc.
ORDER_EMAIL_BODY_SKELETON = """
<p style="margin:0 0 20px;font-size:15px;color:#475569;">{{name}} 様</p>

<h1 style="margin:0 0 12px;font-size:20px;font-weight:600;color:#0f172a;letter-spacing:0.01em;line-height:1.4;">{{bodyTitle}}</h1>

<p style="margin:0 0 24px;font-size:15px;line-height:1.75;color:#475569;">{{bodyDescription}}</p>

{{orderSummaryBlock}}

{{itemsTable}}

{{buttonsBlock}}

{{notesBlock}}

{{contactBlock}}

{{signatureBlock}}
""".strip()


SHIPPING_EMAIL_BODY_SKELETON = """
<p style="margin:0 0 20px;font-size:15px;color:#475569;">{{name}} 様</p>

<h1 style="margin:0 0 12px;font-size:20px;font-weight:600;color:#0f172a;letter-spacing:0.01em;line-height:1.4;">{{bodyTitle}}</h1>

<p style="margin:0 0 24px;font-size:15px;line-height:1.75;color:#475569;">{{bodyDescription}}</p>

{{shippingInfoBlock}}

{{orderSummaryBlock}}

{{itemsTable}}

{{buttonsBlock}}

{{notesBlock}}

{{contactBlock}}

{{signatureBlock}}
""".strip()


SHIPPING_VARIABLES_HINT = (
    "{{name}} / {{ユーザー名}}, {{orderNo}} / {{注文番号}}, {{itemsTable}} / {{注文商品}}, "
    "{{carrier}} / {{配送会社}}, {{trackingNo}} / {{送り状番号}}, {{shippedDate}} / {{発送日}}, "
    "{{deliveryDate}} / {{配送予定日}}, {{trackingUrl}} / {{追跡URL}}, {{shippingMethod}} / {{配送方法}}, "
    "{{shippingStatus}} / {{配送状況}}, {{shippingAddress}} / {{配送先住所}}, "
    "{{inquiryNo}} / {{お問い合わせ番号}}, {{contactUrl}} / {{お問い合わせURL}}, "
    "{{bodyTitle}}, {{bodyDescription}}, {{shippingInfoBlock}}, {{buttonsBlock}}, "
    "{{notesBlock}}, {{contactBlock}}, {{signatureBlock}}"
)

ORDER_VARIABLES_HINT = (
    "{{name}} / {{ユーザー名}}, {{orderNo}} / {{注文番号}}, {{orderDate}} / {{注文日時}}, "
    "{{orderAmount}} / {{注文金額}}, {{paymentMethod}} / {{決済方法}}, {{itemsTable}} / {{注文商品}}, "
    "{{bodyTitle}}, {{bodyDescription}}, {{buttonsBlock}}, {{notesBlock}}, {{contactBlock}}, "
    "{{signatureBlock}}, {{url}}"
)


def build_items_table_html(rows_html: str) -> str:
    if not rows_html.strip():
        return ""
    return f"""
<table role="presentation" width="100%" cellpadding="0" cellspacing="0"
  style="border-collapse:collapse;margin:0 0 24px;font-size:14px;border:1px solid #e2e8f0;border-radius:8px;overflow:hidden;">
  <thead>
    <tr style="background:#f8fafc;">
      <th style="padding:12px 14px;text-align:left;font-weight:600;color:#64748b;font-size:12px;">商品</th>
      <th style="padding:12px 10px;text-align:center;font-weight:600;color:#64748b;font-size:12px;width:56px;">数量</th>
      <th style="padding:12px 14px;text-align:right;font-weight:600;color:#64748b;font-size:12px;width:88px;">単価</th>
    </tr>
  </thead>
  <tbody>{rows_html}</tbody>
</table>""".strip()


def build_item_row(name: str, quantity: int, unit_price: str) -> str:
    return (
        f'<tr>'
        f'<td style="padding:12px 14px;border-top:1px solid #e2e8f0;color:#1e293b;">{_esc(name)}</td>'
        f'<td style="padding:12px 10px;border-top:1px solid #e2e8f0;text-align:center;color:#475569;">{quantity}</td>'
        f'<td style="padding:12px 14px;border-top:1px solid #e2e8f0;text-align:right;color:#1e293b;">{_esc(unit_price)}</td>'
        f"</tr>"
    )


def build_order_summary_block(rows: list[tuple[str, str]]) -> str:
    if not rows:
        return ""
    inner = ""
    for label, value in rows:
        inner += (
            f'<tr>'
            f'<td style="padding:10px 14px;color:#64748b;font-size:13px;width:38%;border-top:1px solid #f1f5f9;">{_esc(label)}</td>'
            f'<td style="padding:10px 14px;color:#1e293b;font-size:14px;border-top:1px solid #f1f5f9;">{value}</td>'
            f"</tr>"
        )
    return f"""
<table role="presentation" width="100%" cellpadding="0" cellspacing="0"
  style="border-collapse:collapse;margin:0 0 20px;background:#fafafa;border:1px solid #e2e8f0;border-radius:8px;overflow:hidden;">
  <tbody>{inner}</tbody>
</table>""".strip()


def build_buttons_block(buttons: list[dict[str, str]], *, brand_color: str = "#ca8a04") -> str:
    """Render CTA buttons only when configured. buttons: [{text, url, style?}]"""
    visible = [b for b in buttons if b.get("text") and b.get("url")]
    if not visible:
        return ""
    parts: list[str] = []
    for btn in visible:
        color = btn.get("style") or brand_color
        parts.append(
            f'<table role="presentation" cellpadding="0" cellspacing="0" style="margin:0 auto 12px;">'
            f'<tr><td align="center" style="border-radius:8px;background:{_esc(color)};">'
            f'<a href="{_esc(btn["url"])}" target="_blank" rel="noopener" '
            f'style="display:inline-block;padding:14px 32px;font-size:15px;font-weight:600;'
            f'color:#111827;text-decoration:none;border-radius:8px;letter-spacing:0.02em;">'
            f'{_esc(btn["text"])}</a></td></tr></table>'
        )
    return (
        '<div style="text-align:center;margin:28px 0 8px;">'
        + "".join(parts)
        + "</div>"
    )


def build_notes_block(notes_html: str) -> str:
    if not notes_html.strip():
        return ""
    return f"""
<div style="margin:24px 0 0;padding:16px 18px;background:#fffbeb;border:1px solid #fde68a;border-radius:8px;">
  <p style="margin:0 0 6px;font-size:12px;font-weight:600;color:#92400e;letter-spacing:0.04em;">ご注意</p>
  <div style="font-size:13px;line-height:1.7;color:#78350f;">{notes_html}</div>
</div>""".strip()


def build_contact_block(contact_html: str) -> str:
    if not contact_html.strip():
        return ""
    return f"""
<div style="margin:24px 0 0;padding-top:20px;border-top:1px solid #e2e8f0;">
  <p style="margin:0 0 6px;font-size:12px;font-weight:600;color:#64748b;">お問い合わせ</p>
  <div style="font-size:13px;line-height:1.7;color:#475569;">{contact_html}</div>
</div>""".strip()


def build_signature_block(signature_html: str) -> str:
    if not signature_html.strip():
        return ""
    return f"""
<div style="margin:20px 0 0;font-size:13px;line-height:1.6;color:#64748b;">{signature_html}</div>""".strip()


def build_shipping_info_block(rows: list[tuple[str, str]]) -> str:
    """Dynamic shipping info table — only non-empty rows are included."""
    visible = [(label, value) for label, value in rows if value and str(value).strip()]
    if not visible:
        return ""
    return build_order_summary_block(visible)


def build_preheader_html(preheader: str) -> str:
    """Hidden preheader for inbox preview — XSS-safe escaped."""
    if not preheader.strip():
        return ""
    return (
        f'<div style="display:none;max-height:0;overflow:hidden;mso-hide:all;font-size:1px;line-height:1px;'
        f'color:#f1f5f9;opacity:0;">{_esc(preheader)}</div>'
    )


def build_text_body(
    *,
    name: str,
    body_title: str,
    body_description: str,
    order_summary_lines: list[str] | None = None,
    notes: str = "",
    contact: str = "",
    buttons: list[dict[str, str]] | None = None,
) -> str:
    """Plain-text fallback for multipart emails."""
    lines = [f"{name} 様", "", body_title, "", body_description, ""]
    if order_summary_lines:
        lines.extend(order_summary_lines)
        lines.append("")
    if buttons:
        for btn in buttons:
            if btn.get("text") and btn.get("url"):
                lines.append(f"{btn['text']}: {btn['url']}")
        lines.append("")
    if notes:
        lines.extend(["【ご注意】", notes, ""])
    if contact:
        lines.extend(["【お問い合わせ】", contact, ""])
    return "\n".join(lines).strip()


def parse_buttons_json(raw: str | None) -> list[dict[str, str]]:
    if not raw:
        return []
    try:
        data = json.loads(raw)
        if isinstance(data, list):
            return [b for b in data if isinstance(b, dict)]
    except json.JSONDecodeError:
        pass
    return []
