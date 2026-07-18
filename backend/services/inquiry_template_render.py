"""Template variable substitution for inquiry messages."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any

import models

VARIABLE_PATTERN = re.compile(r"\{(\w+)\}")


def _format_datetime(dt: datetime | None) -> str:
    if not dt:
        return ""
    return dt.strftime("%Y/%m/%d %H:%M")


def _format_date(dt: datetime | None) -> str:
    if not dt:
        return ""
    return dt.strftime("%Y/%m/%d")


def _format_yen(amount: float | int | None) -> str:
    if amount is None:
        return ""
    return f"¥{int(round(float(amount))):,}"


def build_template_context(
    *,
    inquiry: models.Inquiry | None = None,
    order: models.Order | None = None,
    product: models.Card | None = None,
    user: models.User | None = None,
    admin: models.User | None = None,
    reason: str | None = None,
) -> dict[str, str]:
    ctx: dict[str, str] = {}
    if inquiry:
        ctx["inquiryNumber"] = inquiry.inquiry_number or ""
    if user:
        ctx["customerName"] = user.name or ""
    if admin:
        ctx["adminName"] = admin.name or ""
    if order:
        ctx["orderNumber"] = order.order_number or ""
        ctx["orderedAt"] = _format_date(order.paid_at or order.created_at)
        status = order.status.value if hasattr(order.status, "value") else str(order.status)
        ctx["orderStatus"] = status
        ctx["totalAmount"] = _format_yen(order.total_amount)
        ctx["shippingCarrier"] = order.shipping_carrier or ""
        ctx["trackingNumber"] = order.tracking_number or ""
        ctx["shippedAt"] = _format_datetime(order.shipped_at)
    if product:
        ctx["productName"] = product.name or ""
    if reason:
        ctx["reason"] = reason
    # Points not implemented — leave empty so lines are removed
    ctx["pointBalance"] = ""
    return ctx


def render_template_body(body: str, context: dict[str, str], *, warn_missing: bool = False) -> tuple[str, list[str]]:
    """Render template; remove lines with empty variables. Returns (text, warnings)."""
    warnings: list[str] = []

    def replace_var(match: re.Match[str]) -> str:
        key = match.group(1)
        value = context.get(key, "")
        if not value and warn_missing:
            warnings.append(key)
        return value

    rendered = VARIABLE_PATTERN.sub(replace_var, body)
    lines = rendered.splitlines()
    cleaned: list[str] = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            cleaned.append("")
            continue
        # Drop lines that still contain unresolved placeholders
        if VARIABLE_PATTERN.search(line):
            if warn_missing:
                for m in VARIABLE_PATTERN.findall(line):
                    warnings.append(m)
            continue
        # Drop lines that became empty labels like "配送会社：" with no value
        if stripped.endswith("：") or stripped.endswith(":"):
            continue
        cleaned.append(line)

    text = "\n".join(cleaned)
    while "\n\n\n" in text:
        text = text.replace("\n\n\n", "\n\n")
    return text.strip(), list(dict.fromkeys(warnings))
