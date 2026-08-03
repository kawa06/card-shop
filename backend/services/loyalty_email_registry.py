"""Point / coupon / rank / campaign email event registry — extensible without changing send code."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional

LoyaltyEmailCategory = Literal["point", "coupon", "rank", "campaign", "other"]


@dataclass(frozen=True)
class LoyaltyEmailEventDef:
    event_key: str
    default_template_key: str
    description: str
    category: LoyaltyEmailCategory = "point"
    auto_send_default: bool = True


LEGACY_TEMPLATE_ALIASES: dict[str, str] = {
    "coupon_issued": "coupon_distributed",
    "point_referral": "point_granted",
}


LOYALTY_EMAIL_EVENTS: dict[str, LoyaltyEmailEventDef] = {
    # ポイント
    "point_granted": LoyaltyEmailEventDef("point_granted", "point_granted", "ポイント付与", "point"),
    "point_used": LoyaltyEmailEventDef("point_used", "point_used", "ポイント利用完了", "point"),
    "point_scheduled": LoyaltyEmailEventDef("point_scheduled", "point_scheduled", "ポイント付与予定", "point"),
    "point_expiry_notice": LoyaltyEmailEventDef(
        "point_expiry_notice", "point_expiry_notice", "ポイント有効期限のお知らせ", "point"
    ),
    "point_expiry_scheduled": LoyaltyEmailEventDef(
        "point_expiry_scheduled", "point_expiry_scheduled", "ポイント失効予定", "point"
    ),
    "point_expired": LoyaltyEmailEventDef("point_expired", "point_expired", "ポイント失効完了", "point"),
    "point_adjusted": LoyaltyEmailEventDef("point_adjusted", "point_adjusted", "ポイント調整", "point"),
    # クーポン
    "coupon_distributed": LoyaltyEmailEventDef(
        "coupon_distributed", "coupon_distributed", "クーポン配布", "coupon"
    ),
    "coupon_limited": LoyaltyEmailEventDef("coupon_limited", "coupon_limited", "限定クーポン配布", "coupon"),
    "coupon_birthday": LoyaltyEmailEventDef("coupon_birthday", "coupon_birthday", "誕生日クーポン", "coupon"),
    "coupon_used": LoyaltyEmailEventDef("coupon_used", "coupon_used", "クーポン利用完了", "coupon"),
    "coupon_expiry_notice": LoyaltyEmailEventDef(
        "coupon_expiry_notice", "coupon_expiry_notice", "クーポン利用期限のお知らせ", "coupon"
    ),
    "coupon_expiry_soon": LoyaltyEmailEventDef(
        "coupon_expiry_soon", "coupon_expiry_soon", "クーポン期限間近", "coupon"
    ),
    "coupon_expired": LoyaltyEmailEventDef("coupon_expired", "coupon_expired", "クーポン期限切れ", "coupon"),
    "coupon_cancelled": LoyaltyEmailEventDef("coupon_cancelled", "coupon_cancelled", "クーポン取消", "coupon"),
    # 会員ランク
    "rank_up": LoyaltyEmailEventDef("rank_up", "rank_up", "ランクアップ", "rank"),
    "rank_down": LoyaltyEmailEventDef("rank_down", "rank_down", "ランクダウン", "rank"),
    "rank_maintained": LoyaltyEmailEventDef("rank_maintained", "rank_maintained", "ランク維持", "rank"),
    "rank_update_notice": LoyaltyEmailEventDef(
        "rank_update_notice", "rank_update_notice", "ランク更新のお知らせ", "rank"
    ),
    "rank_next_notice": LoyaltyEmailEventDef(
        "rank_next_notice", "rank_next_notice", "次ランクまでのお知らせ", "rank"
    ),
    "rank_benefit_granted": LoyaltyEmailEventDef(
        "rank_benefit_granted", "rank_benefit_granted", "ランク特典付与", "rank"
    ),
    # キャンペーン
    "campaign_point_up": LoyaltyEmailEventDef(
        "campaign_point_up", "campaign_point_up", "ポイントアップキャンペーン", "campaign"
    ),
    "campaign_rank_up": LoyaltyEmailEventDef(
        "campaign_rank_up", "campaign_rank_up", "ランクアップキャンペーン", "campaign"
    ),
    "campaign_limited_event": LoyaltyEmailEventDef(
        "campaign_limited_event", "campaign_limited_event", "期間限定イベント", "campaign"
    ),
    # その他
    "loyalty_system_error": LoyaltyEmailEventDef(
        "loyalty_system_error", "loyalty_system_error", "システムエラー", "other", auto_send_default=False
    ),
}


def normalize_template_key(template_key: str) -> str:
    return LEGACY_TEMPLATE_ALIASES.get(template_key, template_key)


def resolve_loyalty_template_key(event_key: str) -> str:
    key = LEGACY_TEMPLATE_ALIASES.get(event_key, event_key)
    event = LOYALTY_EMAIL_EVENTS.get(key)
    if event:
        return event.default_template_key
    return key


def get_loyalty_email_event(event_key: str) -> Optional[LoyaltyEmailEventDef]:
    key = LEGACY_TEMPLATE_ALIASES.get(event_key, event_key)
    return LOYALTY_EMAIL_EVENTS.get(key)


def is_loyalty_template_key(template_key: str) -> bool:
    key = normalize_template_key(template_key)
    if key in LOYALTY_EMAIL_EVENTS:
        return True
    return key.startswith(("point_", "coupon_", "rank_", "campaign_", "loyalty_"))


def all_auto_send_defaults() -> dict[str, bool]:
    return {ev.event_key: ev.auto_send_default for ev in LOYALTY_EMAIL_EVENTS.values()}
