"""Shared order email formatting helpers."""

from __future__ import annotations

from datetime import datetime

import models

SHIPPING_METHOD_LABELS: dict[str, str] = {
    "click_post": "クリックポスト",
    "teikei_post": "定形郵便",
    "teigai_post": "定形外郵便",
    "letter_pack_light": "レターパックライト",
    "letter_pack_plus": "レターパックプラス",
    "yu_pack_60": "ゆうパック 60サイズ",
    "yu_pack_80": "ゆうパック 80サイズ",
    "yu_pack_100": "ゆうパック 100サイズ",
    "takkyubin_compact": "宅急便コンパクト",
    "takkyubin_60": "宅急便 60サイズ",
    "takkyubin_80": "宅急便 80サイズ",
    "ems": "EMS",
    "yamato_global": "ヤマトグローバル",
}

PAYMENT_METHOD_LABELS: dict[str, str] = {
    "stripe_card": "クレジットカード",
    "stripe_bank_transfer": "銀行振込",
    "bank_transfer": "銀行振込",
    "konbini": "コンビニ決済",
    "cvs": "コンビニ決済",
}

BANK_TRANSFER_METHODS = {"stripe_bank_transfer", "bank_transfer"}


def format_jpy(amount: float | int) -> str:
    return f"¥{int(round(float(amount))):,}"


def format_datetime_jst(dt: datetime | None) -> str:
    if not dt:
        return ""
    return dt.strftime("%Y/%m/%d %H:%M") + " (UTC)"


def payment_method_label(order: models.Order) -> str:
    return PAYMENT_METHOD_LABELS.get(order.payment_method or "", order.payment_method or "—")


def order_subtotal(order: models.Order) -> float:
    return sum(item.unit_price * item.quantity for item in order.items)
