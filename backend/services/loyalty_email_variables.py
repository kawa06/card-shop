"""Build point / coupon / rank email template variables (display-only snapshot, no calculation)."""

from __future__ import annotations

import html
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

import models
from config import settings
from services.email_delivery import get_brand_settings
from services.email_order_layout import (
    build_buttons_block,
    build_contact_block,
    build_loyalty_info_block,
    build_notes_block,
    build_signature_block,
    build_text_body,
)
from services.loyalty_email_registry import get_loyalty_email_event, normalize_template_key

LOYALTY_INFO_FIELD_DEFS: dict[str, tuple[str, str]] = {
    "eventAt": ("日時", "eventAt"),
    "expiresAt": ("有効期限", "expiresAt"),
    "currentPoints": ("現在ポイント", "currentPoints"),
    "grantedPoints": ("付与ポイント", "grantedPoints"),
    "usedPoints": ("利用ポイント", "usedPoints"),
    "expiredPoints": ("失効ポイント", "expiredPoints"),
    "scheduledPoints": ("付与予定ポイント", "scheduledPoints"),
    "adjustedPoints": ("調整ポイント", "adjustedPoints"),
    "couponName": ("クーポン名", "couponName"),
    "couponCode": ("クーポンコード", "couponCode"),
    "discountAmount": ("割引金額", "discountAmount"),
    "discountRate": ("割引率", "discountRate"),
    "memberRank": ("会員ランク", "memberRank"),
    "nextRank": ("次ランク", "nextRank"),
    "requiredPoints": ("必要ポイント", "requiredPoints"),
    "campaignName": ("キャンペーン名", "campaignName"),
    "startAt": ("開始日時", "startAt"),
    "endAt": ("終了日時", "endAt"),
}

LOYALTY_EVENT_VISIBLE_FIELDS: dict[str, list[str]] = {
    "point_granted": ["eventAt", "grantedPoints", "currentPoints"],
    "point_used": ["eventAt", "usedPoints", "currentPoints"],
    "point_scheduled": ["eventAt", "scheduledPoints", "startAt"],
    "point_expiry_notice": ["expiresAt", "currentPoints"],
    "point_expiry_scheduled": ["expiresAt", "expiredPoints"],
    "point_expired": ["eventAt", "expiredPoints", "currentPoints"],
    "point_adjusted": ["eventAt", "adjustedPoints", "currentPoints"],
    "coupon_distributed": ["eventAt", "couponName", "couponCode", "discountAmount", "discountRate", "expiresAt"],
    "coupon_limited": ["eventAt", "couponName", "couponCode", "discountAmount", "discountRate", "expiresAt"],
    "coupon_birthday": ["eventAt", "couponName", "couponCode", "discountAmount", "discountRate", "expiresAt"],
    "coupon_used": ["eventAt", "couponName", "discountAmount", "discountRate"],
    "coupon_expiry_notice": ["expiresAt", "couponName", "couponCode"],
    "coupon_expiry_soon": ["expiresAt", "couponName", "couponCode"],
    "coupon_expired": ["eventAt", "couponName"],
    "coupon_cancelled": ["eventAt", "couponName", "couponCode"],
    "rank_up": ["eventAt", "memberRank", "nextRank"],
    "rank_down": ["eventAt", "memberRank"],
    "rank_maintained": ["eventAt", "memberRank"],
    "rank_update_notice": ["eventAt", "memberRank", "nextRank"],
    "rank_next_notice": ["eventAt", "memberRank", "nextRank", "requiredPoints"],
    "rank_benefit_granted": ["eventAt", "memberRank"],
    "campaign_point_up": ["campaignName", "startAt", "endAt"],
    "campaign_rank_up": ["campaignName", "startAt", "endAt"],
    "campaign_limited_event": ["campaignName", "startAt", "endAt"],
    "loyalty_system_error": ["eventAt"],
}

RAW_LOYALTY_VARIABLE_KEYS = frozenset({
    "loyaltyInfoBlock",
    "buttonsBlock",
    "notesBlock",
    "contactBlock",
    "signatureBlock",
    "content",
})


@dataclass
class LoyaltyEmailSnapshot:
    """Display-only values passed from point/rank/coupon services — no calculation here."""

    current_points: str | None = None
    granted_points: str | None = None
    used_points: str | None = None
    expired_points: str | None = None
    scheduled_points: str | None = None
    adjusted_points: str | None = None
    expires_at: datetime | str | None = None
    coupon_name: str | None = None
    coupon_code: str | None = None
    discount_amount: str | None = None
    discount_rate: str | None = None
    member_rank: str | None = None
    next_rank: str | None = None
    required_points: str | None = None
    campaign_name: str | None = None
    start_at: datetime | str | None = None
    end_at: datetime | str | None = None
    action_url: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)


def _format_jst(dt: datetime | str | None = None) -> str:
    if isinstance(dt, str):
        return dt
    value = dt or datetime.utcnow()
    return value.strftime("%Y/%m/%d %H:%M")


def _mask_email(email: str) -> str:
    parts = (email or "").split("@")
    if len(parts) != 2:
        return "****"
    local, domain = parts
    if len(local) <= 2:
        masked_local = local[0] + "*"
    else:
        masked_local = local[0] + "*" * (len(local) - 2) + local[-1]
    return f"{masked_local}@{domain}"


def _placeholder_copy() -> tuple[str, str, str, str]:
    return (
        "（本文タイトル）",
        "（本文説明を入力してください）",
        "（注意事項を入力してください）",
        "（お問い合わせ案内を入力してください）",
    )


def _snapshot_to_ctx(snapshot: LoyaltyEmailSnapshot | None, event_at: str) -> dict[str, str]:
    snap = snapshot or LoyaltyEmailSnapshot()
    expires = _format_jst(snap.expires_at) if snap.expires_at else ""
    start = _format_jst(snap.start_at) if snap.start_at else ""
    end = _format_jst(snap.end_at) if snap.end_at else ""
    return {
        "eventAt": event_at,
        "日時": event_at,
        "date": event_at,
        "expiresAt": expires,
        "有効期限": expires,
        "currentPoints": snap.current_points or "",
        "現在ポイント": snap.current_points or "",
        "grantedPoints": snap.granted_points or "",
        "付与ポイント": snap.granted_points or "",
        "usedPoints": snap.used_points or "",
        "利用ポイント": snap.used_points or "",
        "expiredPoints": snap.expired_points or "",
        "失効ポイント": snap.expired_points or "",
        "scheduledPoints": snap.scheduled_points or "",
        "付与予定ポイント": snap.scheduled_points or "",
        "adjustedPoints": snap.adjusted_points or "",
        "調整ポイント": snap.adjusted_points or "",
        "couponName": snap.coupon_name or "",
        "クーポン名": snap.coupon_name or "",
        "couponCode": snap.coupon_code or "",
        "クーポンコード": snap.coupon_code or "",
        "discountAmount": snap.discount_amount or "",
        "割引金額": snap.discount_amount or "",
        "discountRate": snap.discount_rate or "",
        "割引率": snap.discount_rate or "",
        "memberRank": snap.member_rank or "",
        "会員ランク": snap.member_rank or "",
        "nextRank": snap.next_rank or "",
        "次ランク": snap.next_rank or "",
        "requiredPoints": snap.required_points or "",
        "必要ポイント": snap.required_points or "",
        "campaignName": snap.campaign_name or "",
        "キャンペーン名": snap.campaign_name or "",
        "startAt": start,
        "開始日時": start,
        "endAt": end,
        "終了日時": end,
        "url": snap.action_url or "",
        "URL": snap.action_url or "",
    }


def _default_loyalty_buttons(event_key: str, ctx: dict[str, str]) -> list[dict[str, str]]:
    action_url = ctx.get("url") or ctx.get("URL") or ""
    account_url = ctx.get("accountUrl") or ""
    contact_url = ctx.get("contactUrl") or ""
    coupons_url = ctx.get("couponsUrl") or ""

    if event_key.startswith("coupon_") and coupons_url:
        return [{"text": "（ボタンラベル）", "url": coupons_url}]
    if event_key.startswith("campaign_") and action_url:
        return [{"text": "（ボタンラベル）", "url": action_url}]
    if action_url:
        return [{"text": "（ボタンラベル）", "url": action_url}]
    if account_url:
        return [{"text": "（ボタンラベル）", "url": account_url}]
    if contact_url:
        return [{"text": "（ボタンラベル）", "url": contact_url}]
    return []


def _build_loyalty_info_block_for_event(event_key: str, ctx: dict[str, str]) -> str:
    field_keys = LOYALTY_EVENT_VISIBLE_FIELDS.get(event_key, [])
    rows: list[tuple[str, str]] = []
    for fk in field_keys:
        if fk not in LOYALTY_INFO_FIELD_DEFS:
            continue
        label, var_key = LOYALTY_INFO_FIELD_DEFS[fk]
        value = ctx.get(var_key, "")
        if value:
            rows.append((label, html.escape(str(value))))
    return build_loyalty_info_block(rows)


def build_loyalty_email_variables(
    db,
    user: models.User | None,
    event_key: str,
    *,
    to_email: str | None = None,
    snapshot: LoyaltyEmailSnapshot | None = None,
    body_title: Optional[str] = None,
    body_description: Optional[str] = None,
    notes_html: Optional[str] = None,
    contact_html: Optional[str] = None,
    buttons: Optional[list[dict[str, str]]] = None,
    brand_color: str = "#ca8a04",
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    event_key = normalize_template_key(event_key)
    name = (user.name if user else None) or "お客"
    email = to_email or (user.email if user else "")
    p_title, p_desc, p_notes, p_contact = _placeholder_copy()
    title = body_title or p_title
    desc = body_description or p_desc
    notes = notes_html if notes_html is not None else p_notes
    contact = contact_html if contact_html is not None else p_contact

    brand = get_brand_settings(db)
    signature_html = getattr(brand, "email_signature_html", None) or ""
    contact_url = brand.contact_url or settings.FRONTEND_URL or ""
    base_url = settings.FRONTEND_URL.rstrip("/") if settings.FRONTEND_URL else ""
    account_url = f"{base_url}/account" if base_url else ""
    coupons_url = f"{base_url}/account/coupons" if base_url else ""
    event_at = _format_jst()

    ctx = _snapshot_to_ctx(snapshot, event_at)
    ctx.update({
        "accountUrl": account_url,
        "couponsUrl": coupons_url,
        "contactUrl": contact_url,
        "お問い合わせURL": contact_url,
    })
    if not ctx.get("url") and snapshot and snapshot.action_url:
        ctx["url"] = snapshot.action_url
        ctx["URL"] = snapshot.action_url

    loyalty_info = _build_loyalty_info_block_for_event(event_key, ctx)
    btn_list = buttons if buttons is not None else _default_loyalty_buttons(event_key, ctx)

    variables: dict[str, Any] = {
        "name": name,
        "ユーザー名": name,
        "email": _mask_email(email),
        "メールアドレス": _mask_email(email),
        "bodyTitle": title,
        "bodyDescription": desc,
        "loyaltyInfoBlock": loyalty_info,
        "buttonsBlock": build_buttons_block(btn_list, brand_color=brand_color or brand.brand_color or "#ca8a04"),
        "notesBlock": build_notes_block(notes),
        "contactBlock": build_contact_block(contact),
        "signatureBlock": build_signature_block(signature_html),
        "shopName": settings.SITE_NAME or "KRX TCG",
        **ctx,
    }
    if extra:
        variables.update(extra)
    if snapshot and snapshot.extra:
        variables.update(snapshot.extra)

    summary_lines = []
    for fk in LOYALTY_EVENT_VISIBLE_FIELDS.get(event_key, []):
        if fk in LOYALTY_INFO_FIELD_DEFS:
            label, var_key = LOYALTY_INFO_FIELD_DEFS[fk]
            val = ctx.get(var_key, "")
            if val:
                summary_lines.append(f"{label}: {val}")

    variables["_text_body"] = build_text_body(
        name=name,
        body_title=title,
        body_description=desc,
        order_summary_lines=summary_lines or None,
        notes=notes.replace("<br>", "\n").replace("<br/>", "\n") if notes else "",
        contact=contact.replace("<br>", "\n").replace("<br/>", "\n") if contact else "",
        buttons=btn_list,
    )
    return variables


def build_loyalty_sample_variables(template_key: str) -> dict[str, Any]:
    template_key = normalize_template_key(template_key)
    event = get_loyalty_email_event(template_key)
    event_key = event.event_key if event else template_key
    base_url = settings.FRONTEND_URL or "https://example.com"

    snapshot = LoyaltyEmailSnapshot(
        current_points="1,250 pt",
        granted_points="500 pt",
        used_points="300 pt",
        expired_points="100 pt",
        scheduled_points="200 pt",
        adjusted_points="+50 pt",
        expires_at="2026/12/31 23:59",
        coupon_name="サンプルクーポン",
        coupon_code="SAMPLE-2026",
        discount_amount="¥1,000",
        discount_rate="10%",
        member_rank="ゴールド",
        next_rank="プラチナ",
        required_points="750 pt",
        campaign_name="サンプルキャンペーン",
        start_at="2026/08/01 00:00",
        end_at="2026/08/31 23:59",
        action_url=f"{base_url}/campaigns/sample",
    )

    sample_ctx = _snapshot_to_ctx(snapshot, "2026/08/03 14:30")
    sample_ctx.update({
        "accountUrl": f"{base_url}/account",
        "couponsUrl": f"{base_url}/account/coupons",
        "contactUrl": f"{base_url}/contact",
        "お問い合わせURL": f"{base_url}/contact",
    })

    loyalty_info = _build_loyalty_info_block_for_event(event_key, sample_ctx)
    buttons = _default_loyalty_buttons(event_key, sample_ctx)

    return {
        "name": "山田 太郎",
        "ユーザー名": "山田 太郎",
        "email": "y***o@example.com",
        "メールアドレス": "y***o@example.com",
        "bodyTitle": "（本文タイトル）",
        "bodyDescription": "（本文説明を入力してください）",
        "loyaltyInfoBlock": loyalty_info,
        "buttonsBlock": build_buttons_block(buttons, brand_color="#ca8a04"),
        "notesBlock": build_notes_block("（注意事項を入力してください）"),
        "contactBlock": build_contact_block("（お問い合わせ案内を入力してください）"),
        "signatureBlock": build_signature_block("（署名）"),
        "shopName": settings.SITE_NAME or "KRX TCG",
        **sample_ctx,
    }


def loyalty_variables_for_template(template_key: str) -> list[str]:
    template_key = normalize_template_key(template_key)
    base = [
        "name", "email", "bodyTitle", "bodyDescription",
        "loyaltyInfoBlock", "buttonsBlock", "notesBlock", "contactBlock", "signatureBlock",
        "eventAt", "expiresAt", "currentPoints", "grantedPoints", "usedPoints", "expiredPoints",
        "scheduledPoints", "adjustedPoints", "couponName", "couponCode", "discountAmount",
        "discountRate", "memberRank", "nextRank", "requiredPoints", "campaignName",
        "startAt", "endAt", "url", "contactUrl", "accountUrl", "couponsUrl",
    ]
    if get_loyalty_email_event(template_key):
        return base
    return base
