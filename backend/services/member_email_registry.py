"""Member / login / security email event registry — extensible without changing send code."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional

MemberEmailCategory = Literal["member", "login", "password", "security"]


@dataclass(frozen=True)
class MemberEmailEventDef:
    event_key: str
    default_template_key: str
    description: str
    category: MemberEmailCategory = "member"
    auto_send_default: bool = True


LEGACY_TEMPLATE_ALIASES: dict[str, str] = {
    "member_register": "member_register_completed",
    "member_email_change": "member_email_change_completed",
    "member_password_change": "password_changed",
    "member_password_reset": "password_reset_received",
    "member_login_notify": "login_success",
    "member_2fa_otp": "security_2fa_otp_sent",
}


MEMBER_EMAIL_EVENTS: dict[str, MemberEmailEventDef] = {
    # 会員登録
    "member_register_completed": MemberEmailEventDef(
        "member_register_completed", "member_register_completed", "会員登録完了", "member"
    ),
    "member_email_verify": MemberEmailEventDef(
        "member_email_verify", "member_email_verify", "メールアドレス認証", "member"
    ),
    "member_email_verify_completed": MemberEmailEventDef(
        "member_email_verify_completed", "member_email_verify_completed", "メールアドレス認証完了", "member"
    ),
    "member_email_change_received": MemberEmailEventDef(
        "member_email_change_received", "member_email_change_received", "メールアドレス変更受付", "member"
    ),
    "member_email_change_completed": MemberEmailEventDef(
        "member_email_change_completed", "member_email_change_completed", "メールアドレス変更完了", "member"
    ),
    "member_phone_verify": MemberEmailEventDef(
        "member_phone_verify", "member_phone_verify", "電話番号認証", "member"
    ),
    "member_phone_verify_completed": MemberEmailEventDef(
        "member_phone_verify_completed", "member_phone_verify_completed", "電話番号認証完了", "member"
    ),
    "member_profile_updated": MemberEmailEventDef(
        "member_profile_updated", "member_profile_updated", "プロフィール変更完了", "member"
    ),
    "member_withdrawal_received": MemberEmailEventDef(
        "member_withdrawal_received", "member_withdrawal_received", "退会受付", "member"
    ),
    "member_withdrawal_completed": MemberEmailEventDef(
        "member_withdrawal_completed", "member_withdrawal_completed", "退会完了", "member"
    ),
    # ログイン
    "login_success": MemberEmailEventDef(
        "login_success", "login_success", "ログイン成功通知", "login"
    ),
    "login_new_device": MemberEmailEventDef(
        "login_new_device", "login_new_device", "新しい端末からのログイン", "login"
    ),
    "login_failed": MemberEmailEventDef(
        "login_failed", "login_failed", "ログイン失敗通知", "login", auto_send_default=False
    ),
    "login_failed_repeated": MemberEmailEventDef(
        "login_failed_repeated", "login_failed_repeated", "連続ログイン失敗", "login"
    ),
    "login_account_locked": MemberEmailEventDef(
        "login_account_locked", "login_account_locked", "アカウントロック", "login"
    ),
    "login_account_unlocked": MemberEmailEventDef(
        "login_account_unlocked", "login_account_unlocked", "アカウントロック解除", "login"
    ),
    # パスワード
    "password_reset_received": MemberEmailEventDef(
        "password_reset_received", "password_reset_received", "パスワード再設定受付", "password"
    ),
    "password_reset_completed": MemberEmailEventDef(
        "password_reset_completed", "password_reset_completed", "パスワード再設定完了", "password"
    ),
    "password_changed": MemberEmailEventDef(
        "password_changed", "password_changed", "パスワード変更完了", "password"
    ),
    # セキュリティ
    "security_important_notice": MemberEmailEventDef(
        "security_important_notice", "security_important_notice", "重要なお知らせ", "security"
    ),
    "security_suspicious_access": MemberEmailEventDef(
        "security_suspicious_access", "security_suspicious_access", "不審なアクセス検知", "security"
    ),
    "security_settings_changed": MemberEmailEventDef(
        "security_settings_changed", "security_settings_changed", "セキュリティ設定変更", "security"
    ),
    "security_2fa_enabled": MemberEmailEventDef(
        "security_2fa_enabled", "security_2fa_enabled", "二段階認証有効", "security"
    ),
    "security_2fa_disabled": MemberEmailEventDef(
        "security_2fa_disabled", "security_2fa_disabled", "二段階認証無効", "security"
    ),
    "security_2fa_otp_sent": MemberEmailEventDef(
        "security_2fa_otp_sent", "security_2fa_otp_sent", "二段階認証コード送信", "security"
    ),
    "security_terms_updated": MemberEmailEventDef(
        "security_terms_updated", "security_terms_updated", "利用規約改定", "security"
    ),
    "security_privacy_updated": MemberEmailEventDef(
        "security_privacy_updated", "security_privacy_updated", "プライバシーポリシー改定", "security"
    ),
    "security_system_error": MemberEmailEventDef(
        "security_system_error", "security_system_error", "システムエラー", "security", auto_send_default=False
    ),
}


def normalize_template_key(template_key: str) -> str:
    return LEGACY_TEMPLATE_ALIASES.get(template_key, template_key)


def resolve_member_template_key(event_key: str) -> str:
    key = LEGACY_TEMPLATE_ALIASES.get(event_key, event_key)
    event = MEMBER_EMAIL_EVENTS.get(key)
    if event:
        return event.default_template_key
    return key


def get_member_email_event(event_key: str) -> Optional[MemberEmailEventDef]:
    key = LEGACY_TEMPLATE_ALIASES.get(event_key, event_key)
    return MEMBER_EMAIL_EVENTS.get(key)


def all_auto_send_defaults() -> dict[str, bool]:
    return {ev.event_key: ev.auto_send_default for ev in MEMBER_EMAIL_EVENTS.values()}
