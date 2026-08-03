"""Buyback email event registry — extensible without changing send code."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Optional

BuybackMethodFilter = Literal["all", "mail", "store"]


@dataclass(frozen=True)
class BuybackEmailEventDef:
    event_key: str
    default_template_key: str
    description: str
    method_filter: BuybackMethodFilter = "all"
    auto_send_default: bool = True
    dedupe_reference_suffix: str = ""
    method_templates: dict[str, str] = field(default_factory=dict)


# Legacy template keys → new canonical keys
LEGACY_TEMPLATE_ALIASES: dict[str, str] = {
    "buyback_mail_received": "buyback_shipment_confirmed",
    "buyback_reduction_notice": "buyback_assessment_amount_changed",
    "buyback_assessment_amount": "buyback_assessment_amount_changed",
    "buyback_assessment_detail": "buyback_assessment_result",
    "buyback_return_started": "buyback_return_preparing",
    "buyback_package_shipped": "buyback_return_shipped",
    "buyback_return_tracking": "buyback_return_shipped",
    "buyback_payout_scheduled": "buyback_payout_preparing",
    "buyback_status_changed": "buyback_request_updated",
}


BUYBACK_EMAIL_EVENTS: dict[str, BuybackEmailEventDef] = {
    # Common
    "buyback_request_submitted": BuybackEmailEventDef(
        "buyback_request_submitted", "buyback_request_submitted", "買取申請受付"
    ),
    "buyback_request_updated": BuybackEmailEventDef(
        "buyback_request_updated", "buyback_request_updated", "買取申請内容変更"
    ),
    "buyback_request_cancelled": BuybackEmailEventDef(
        "buyback_request_cancelled", "buyback_request_cancelled", "買取申請キャンセル"
    ),
    # Mail
    "buyback_awaiting_shipment": BuybackEmailEventDef(
        "buyback_awaiting_shipment", "buyback_awaiting_shipment", "発送待ち", "mail"
    ),
    "buyback_ship_deadline_notice": BuybackEmailEventDef(
        "buyback_ship_deadline_notice", "buyback_ship_deadline_notice", "発送期限のお知らせ", "mail"
    ),
    "buyback_ship_deadline_soon": BuybackEmailEventDef(
        "buyback_ship_deadline_soon", "buyback_ship_deadline_soon", "発送期限間近", "mail"
    ),
    "buyback_ship_deadline_expired": BuybackEmailEventDef(
        "buyback_ship_deadline_expired", "buyback_ship_deadline_expired", "発送期限超過", "mail"
    ),
    "buyback_shipment_confirmed": BuybackEmailEventDef(
        "buyback_shipment_confirmed", "buyback_shipment_confirmed", "荷物発送確認", "mail"
    ),
    "buyback_inbound_received": BuybackEmailEventDef(
        "buyback_inbound_received", "buyback_inbound_received", "荷物到着", "mail"
    ),
    # Store
    "buyback_store_reservation": BuybackEmailEventDef(
        "buyback_store_reservation", "buyback_store_reservation", "来店予約完了", "store"
    ),
    "buyback_store_reschedule": BuybackEmailEventDef(
        "buyback_store_reschedule", "buyback_store_reschedule", "来店日時変更", "store"
    ),
    "buyback_store_reminder": BuybackEmailEventDef(
        "buyback_store_reminder", "buyback_store_reminder", "来店日時リマインド", "store"
    ),
    "buyback_store_checkin": BuybackEmailEventDef(
        "buyback_store_checkin", "buyback_store_checkin", "来店受付", "store"
    ),
    "buyback_store_assessing_start": BuybackEmailEventDef(
        "buyback_store_assessing_start", "buyback_store_assessing_start", "査定開始（店舗）", "store"
    ),
    # Assessment
    "buyback_assessing": BuybackEmailEventDef(
        "buyback_assessing", "buyback_assessing", "査定開始", "all",
        method_templates={"store": "buyback_store_assessing_start"},
    ),
    "buyback_assessing_in_progress": BuybackEmailEventDef(
        "buyback_assessing_in_progress", "buyback_assessing_in_progress", "査定中"
    ),
    "buyback_assessment_ready": BuybackEmailEventDef(
        "buyback_assessment_ready", "buyback_assessment_ready", "査定完了"
    ),
    "buyback_assessment_result": BuybackEmailEventDef(
        "buyback_assessment_result", "buyback_assessment_result", "査定結果のお知らせ"
    ),
    "buyback_assessment_amount_changed": BuybackEmailEventDef(
        "buyback_assessment_amount_changed", "buyback_assessment_amount_changed", "査定金額変更"
    ),
    # Approval
    "buyback_awaiting_approval": BuybackEmailEventDef(
        "buyback_awaiting_approval", "buyback_awaiting_approval", "査定結果承認待ち"
    ),
    "buyback_accepted": BuybackEmailEventDef(
        "buyback_accepted", "buyback_accepted", "承認完了"
    ),
    "buyback_rejected": BuybackEmailEventDef(
        "buyback_rejected", "buyback_rejected", "買取不可（却下）"
    ),
    "buyback_approval_deadline_soon": BuybackEmailEventDef(
        "buyback_approval_deadline_soon", "buyback_approval_deadline_soon", "承認期限間近"
    ),
    "buyback_approval_deadline_expired": BuybackEmailEventDef(
        "buyback_approval_deadline_expired", "buyback_approval_deadline_expired", "承認期限切れ"
    ),
    # Payout
    "buyback_payout_preparing": BuybackEmailEventDef(
        "buyback_payout_preparing", "buyback_payout_preparing", "振込準備中"
    ),
    "buyback_payout_completed": BuybackEmailEventDef(
        "buyback_payout_completed", "buyback_payout_completed", "振込完了"
    ),
    "buyback_payout_on_hold": BuybackEmailEventDef(
        "buyback_payout_on_hold", "buyback_payout_on_hold", "振込保留"
    ),
    # Return
    "buyback_return_received": BuybackEmailEventDef(
        "buyback_return_received", "buyback_return_received", "返送受付"
    ),
    "buyback_return_preparing": BuybackEmailEventDef(
        "buyback_return_preparing", "buyback_return_preparing", "返送準備中"
    ),
    "buyback_return_shipped": BuybackEmailEventDef(
        "buyback_return_shipped", "buyback_return_shipped", "返送発送", dedupe_reference_suffix=":return"
    ),
    "buyback_return_completed": BuybackEmailEventDef(
        "buyback_return_completed", "buyback_return_completed", "返送完了"
    ),
    # Other
    "buyback_cancelled": BuybackEmailEventDef(
        "buyback_cancelled", "buyback_cancelled", "買取キャンセル完了"
    ),
    "buyback_system_error": BuybackEmailEventDef(
        "buyback_system_error", "buyback_system_error", "システムエラー", auto_send_default=False
    ),
    # Ops / identity (existing)
    "buyback_request_admin_alert": BuybackEmailEventDef(
        "buyback_request_admin_alert", "buyback_request_admin_alert", "買取申請（管理者）", auto_send_default=True
    ),
    "buyback_guardian_consent": BuybackEmailEventDef(
        "buyback_guardian_consent", "buyback_guardian_consent", "保護者同意依頼"
    ),
}


# Status transition → event (when admin/customer changes status)
STATUS_TO_EVENT: dict[str, str] = {
    "awaiting_shipment": "buyback_awaiting_shipment",
    "shipped": "buyback_shipment_confirmed",
    "received": "buyback_inbound_received",
    "awaiting_visit": "buyback_store_reservation",
    "store_visited": "buyback_store_checkin",
    "assessing": "buyback_assessing",
    "assessed": "buyback_assessment_ready",
    "awaiting_customer": "buyback_awaiting_approval",
    "accepted": "buyback_accepted",
    "rejected": "buyback_rejected",
    "payout_pending": "buyback_payout_preparing",
    "paid": "buyback_payout_completed",
    "return_preparing": "buyback_return_preparing",
    "sent_back": "buyback_return_shipped",
    "returned": "buyback_return_completed",
    "cancelled": "buyback_cancelled",
    "on_hold": "buyback_payout_on_hold",
}


def normalize_template_key(template_key: str) -> str:
    return LEGACY_TEMPLATE_ALIASES.get(template_key, template_key)


def get_buyback_email_event(event_key: str) -> Optional[BuybackEmailEventDef]:
    key = LEGACY_TEMPLATE_ALIASES.get(event_key, event_key)
    return BUYBACK_EMAIL_EVENTS.get(key)


def resolve_buyback_template_key(
    event_key: str,
    buyback_method: str | None = None,
) -> str:
    key = LEGACY_TEMPLATE_ALIASES.get(event_key, event_key)
    event = BUYBACK_EMAIL_EVENTS.get(key)
    if not event:
        return key
    method = (buyback_method or "").strip().lower()
    if method and method in event.method_templates:
        return event.method_templates[method]
    return event.default_template_key


def resolve_status_change_event(
    *,
    to_status: str,
    buyback_method: str | None = None,
) -> str | None:
    event_key = STATUS_TO_EVENT.get(to_status)
    if not event_key:
        return None
    event = get_buyback_email_event(event_key)
    if not event:
        return event_key
    if event.method_filter == "mail" and buyback_method != "mail":
        return "buyback_request_updated"
    if event.method_filter == "store" and buyback_method != "store":
        return "buyback_request_updated"
    return event_key


def all_auto_send_defaults() -> dict[str, bool]:
    return {
        key: ev.auto_send_default
        for key, ev in BUYBACK_EMAIL_EVENTS.items()
    }
