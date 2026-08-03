"""Admin notification email event registry — extensible for new features and channels."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional

AdminNotifyCategory = Literal[
    "order", "shipping", "buyback", "kyc", "inquiry", "member",
    "inventory", "system", "security", "other",
]
NotifyChannel = Literal["email", "in_app", "both"]


@dataclass(frozen=True)
class AdminNotifyEmailEventDef:
    event_key: str
    default_template_key: str
    description: str
    category: AdminNotifyCategory
    auto_send_default: bool = True
    channel_default: NotifyChannel = "both"


LEGACY_TEMPLATE_ALIASES: dict[str, str] = {
    "buyback_request_admin_alert": "admin_notify_buyback_request_new",
}


def _ev(category: AdminNotifyCategory, key: str, desc: str, *, channel: NotifyChannel = "both", auto_send: bool = True) -> AdminNotifyEmailEventDef:
    return AdminNotifyEmailEventDef(key, key, desc, category, auto_send_default=auto_send, channel_default=channel)


_EVENT_SPECS: list[tuple[AdminNotifyCategory, str, str, NotifyChannel]] = [
    # order
    ("order", "admin_notify_order_received", "新規注文受付", "both"),
    ("order", "admin_notify_order_cancelled", "注文キャンセル", "both"),
    ("order", "admin_notify_order_refund_requested", "返金申請", "both"),
    ("order", "admin_notify_order_refund_completed", "返金完了", "both"),
    ("order", "admin_notify_order_payment_failed", "決済失敗", "both"),
    ("order", "admin_notify_order_payment_error", "決済エラー", "both"),
    ("order", "admin_notify_order_unpaid", "未入金注文", "both"),
    ("order", "admin_notify_order_payment_expired", "支払期限切れ", "both"),
    # shipping
    ("shipping", "admin_notify_shipping_pending", "発送待ち", "both"),
    ("shipping", "admin_notify_shipping_completed", "発送完了", "both"),
    ("shipping", "admin_notify_shipping_trouble", "配送トラブル", "both"),
    ("shipping", "admin_notify_shipping_returned", "返送発生", "both"),
    # buyback
    ("buyback", "admin_notify_buyback_request_new", "新規買取申請", "both"),
    ("buyback", "admin_notify_buyback_store_booking", "店舗買取予約", "both"),
    ("buyback", "admin_notify_buyback_parcel_received", "郵送買取荷物到着", "both"),
    ("buyback", "admin_notify_buyback_assessment_started", "査定開始", "both"),
    ("buyback", "admin_notify_buyback_assessment_completed", "査定完了", "both"),
    ("buyback", "admin_notify_buyback_approval_pending", "承認待ち", "both"),
    ("buyback", "admin_notify_buyback_payout_pending", "振込待ち", "both"),
    ("buyback", "admin_notify_buyback_payout_completed", "振込完了", "both"),
    ("buyback", "admin_notify_buyback_return_pending", "返送待ち", "both"),
    # kyc
    ("kyc", "admin_notify_kyc_submitted", "本人確認申請", "both"),
    ("kyc", "admin_notify_kyc_resubmit", "本人確認差し戻し", "both"),
    ("kyc", "admin_notify_kyc_approved", "本人確認承認", "both"),
    ("kyc", "admin_notify_kyc_guardian_consent_pending", "保護者同意待ち", "both"),
    ("kyc", "admin_notify_kyc_guardian_verify_pending", "保護者本人確認待ち", "both"),
    # inquiry
    ("inquiry", "admin_notify_inquiry_new", "新規お問い合わせ", "both"),
    ("inquiry", "admin_notify_inquiry_reply_pending", "返信待ち", "both"),
    ("inquiry", "admin_notify_inquiry_stale", "長期間未対応", "both"),
    # member
    ("member", "admin_notify_member_registered", "新規会員登録", "both"),
    ("member", "admin_notify_member_withdrawn", "退会", "both"),
    ("member", "admin_notify_member_locked", "アカウントロック", "both"),
    ("member", "admin_notify_member_suspicious_login", "不審ログイン", "both"),
    # inventory
    ("inventory", "admin_notify_inventory_out_of_stock", "在庫切れ", "both"),
    ("inventory", "admin_notify_inventory_low_stock", "在庫不足", "both"),
    ("inventory", "admin_notify_product_published", "商品公開", "both"),
    ("inventory", "admin_notify_product_unpublished", "商品非公開", "both"),
    ("inventory", "admin_notify_product_price_changed", "価格変更", "both"),
    # system
    ("system", "admin_notify_system_backup_success", "バックアップ完了", "email"),
    ("system", "admin_notify_system_backup_failed", "バックアップ失敗", "both"),
    ("system", "admin_notify_system_server_error", "サーバーエラー", "both"),
    ("system", "admin_notify_system_email_failed", "メール送信失敗", "both"),
    ("system", "admin_notify_system_stripe_webhook_error", "Stripe Webhookエラー", "both"),
    ("system", "admin_notify_system_api_error", "APIエラー", "both"),
    ("system", "admin_notify_system_upload_error", "画像アップロードエラー", "both"),
    ("system", "admin_notify_system_database_error", "データベースエラー", "both"),
    ("system", "admin_notify_system_storage_error", "ストレージエラー", "both"),
    ("system", "admin_notify_system_job_failed", "ジョブ失敗", "both"),
    # security
    ("security", "admin_notify_security_admin_login", "管理者ログイン", "in_app"),
    ("security", "admin_notify_security_permission_changed", "権限変更", "both"),
    ("security", "admin_notify_security_unauthorized_access", "不正アクセス検知", "both"),
    ("security", "admin_notify_security_high_traffic", "大量アクセス", "both"),
    ("security", "admin_notify_security_abnormal_operation", "管理画面異常操作", "both"),
    ("security", "admin_notify_security_audit_log", "監査ログ通知", "in_app"),
    # other
    ("other", "admin_notify_other_important", "重要なお知らせ", "both"),
    ("other", "admin_notify_other_maintenance", "システムメンテナンス", "both"),
    ("other", "admin_notify_other_recovered", "システム復旧", "both"),
]

ADMIN_NOTIFY_EMAIL_EVENTS: dict[str, AdminNotifyEmailEventDef] = {
    key: _ev(cat, key, desc, channel=channel)
    for cat, key, desc, channel in _EVENT_SPECS
}


def normalize_template_key(template_key: str) -> str:
    return LEGACY_TEMPLATE_ALIASES.get(template_key, template_key)


def resolve_admin_notify_template_key(event_key: str) -> str:
    key = LEGACY_TEMPLATE_ALIASES.get(event_key, event_key)
    event = ADMIN_NOTIFY_EMAIL_EVENTS.get(key)
    if event:
        return event.default_template_key
    return key


def get_admin_notify_email_event(event_key: str) -> Optional[AdminNotifyEmailEventDef]:
    key = LEGACY_TEMPLATE_ALIASES.get(event_key, event_key)
    return ADMIN_NOTIFY_EMAIL_EVENTS.get(key)


def is_admin_notify_template_key(template_key: str) -> bool:
    normalized = normalize_template_key(template_key)
    if normalized in ADMIN_NOTIFY_EMAIL_EVENTS:
        return True
    return normalized.startswith("admin_notify_")


def all_auto_send_defaults() -> dict[str, bool]:
    return {ev.event_key: ev.auto_send_default for ev in ADMIN_NOTIFY_EMAIL_EVENTS.values()}


def all_channel_defaults() -> dict[str, str]:
    return {ev.event_key: ev.channel_default for ev in ADMIN_NOTIFY_EMAIL_EVENTS.values()}
