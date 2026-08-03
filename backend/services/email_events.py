"""Central registry of email notification events — add new notifications here without touching send code."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Optional


@dataclass(frozen=True)
class EmailEventDef:
    template_key: str
    category: str
    description: str
    variables: list[str] = field(default_factory=list)
    raw_html_variables: frozenset[str] = frozenset({"content", "itemsTable", "assessmentDetail"})
    sample_variables: dict[str, str] = field(default_factory=dict)


# Japanese alias → canonical key (used by render_template_string)
VARIABLE_ALIASES: dict[str, str] = {
    "名前": "name",
    "氏名": "name",
    "メール": "email",
    "メールアドレス": "email",
    "注文番号": "orderNo",
    "商品名": "productName",
    "発送日": "shippedDate",
    "買取番号": "buyNo",
    "査定金額": "amount",
    "ショップ名": "shopName",
    "URL": "url",
    "日付": "date",
    "タイトル": "title",
    "本文": "content",
    "内容": "content",
    "送り状番号": "trackingNo",
    "認証コード": "otpCode",
    "確認URL": "verifyUrl",
    "同意URL": "consentUrl",
}


EMAIL_EVENTS: dict[str, EmailEventDef] = {
    "member.register": EmailEventDef(
        "member_register", "member", "会員登録完了",
        ["name", "email", "shopName", "url"],
        sample_variables={"name": "山田 太郎", "email": "taro@example.com"},
    ),
    "member.email_verify": EmailEventDef(
        "member_email_verify", "member", "メール認証",
        ["name", "verifyUrl", "shopName"],
        sample_variables={"name": "山田 太郎", "verifyUrl": "https://example.com/verify/token"},
    ),
    "member.login_notify": EmailEventDef(
        "member_login_notify", "member", "ログイン通知",
        ["name", "date", "ipAddress"],
        sample_variables={"name": "山田 太郎", "ipAddress": "203.0.113.1"},
    ),
    "member.2fa_otp": EmailEventDef(
        "member_2fa_otp", "member", "2段階認証コード",
        ["name", "otpCode"],
        sample_variables={"name": "山田 太郎", "otpCode": "123456"},
    ),
    "order.payment_confirmed": EmailEventDef(
        "order_payment_confirmed", "order", "入金確認",
        ["name", "orderNo", "itemsTable", "totalAmount"],
        sample_variables={"name": "山田 太郎", "orderNo": "ORD-20260801-001", "totalAmount": "¥12,800"},
    ),
    "order.shipped": EmailEventDef(
        "order_shipped", "order", "発送完了",
        ["name", "orderNo", "trackingNo", "shippedDate"],
        sample_variables={
            "name": "山田 太郎",
            "orderNo": "ORD-20260801-001",
            "trackingNo": "1234-5678-9012",
            "shippedDate": "2026/08/03",
        },
    ),
    "order.bank_transfer": EmailEventDef(
        "order_bank_transfer", "order", "銀行振込案内",
        ["name", "orderNo", "totalAmount", "bankInfo"],
        sample_variables={"name": "山田 太郎", "orderNo": "ORD-20260801-001", "totalAmount": "¥12,800"},
    ),
    "buyback.request_submitted": EmailEventDef(
        "buyback_request_submitted", "buyback", "買取申請受付",
        ["name", "buyNo", "url"],
        sample_variables={"name": "山田 太郎", "buyNo": "BB-20260801-001"},
    ),
    "buyback.guardian_consent": EmailEventDef(
        "buyback_guardian_consent", "buyback", "保護者同意依頼",
        ["guardianName", "minorName", "consentUrl"],
        sample_variables={
            "guardianName": "山田 花子",
            "minorName": "山田 太郎",
            "consentUrl": "https://example.com/guardian-consent",
        },
    ),
    "buyback.payout_completed": EmailEventDef(
        "buyback_payout_completed", "buyback", "振込完了",
        ["name", "buyNo", "amount"],
        sample_variables={"name": "山田 太郎", "buyNo": "BB-20260801-001", "amount": "¥50,000"},
    ),
    "inquiry.received": EmailEventDef(
        "inquiry_received", "ops", "お問い合わせ受付",
        ["name", "inquiryNo", "content"],
        sample_variables={"name": "山田 太郎", "inquiryNo": "INQ-001", "content": "商品について質問があります。"},
    ),
    "inquiry.reply": EmailEventDef(
        "inquiry_reply", "ops", "お問い合わせ返信",
        ["name", "inquiryNo", "content"],
        sample_variables={"name": "山田 太郎", "inquiryNo": "INQ-001", "content": "ご返信内容です。"},
    ),
    "announcement.broadcast": EmailEventDef(
        "announcement_broadcast", "ops", "お知らせ配信",
        ["name", "title", "content", "url"],
        frozenset({"content"}),
        sample_variables={
            "name": "山田 太郎",
            "title": "夏季休業のお知らせ",
            "content": "<p>8月13日〜15日は休業いたします。</p>",
        },
    ),
}


def get_event(event_key: str) -> Optional[EmailEventDef]:
    return EMAIL_EVENTS.get(event_key)


def get_event_by_template(template_key: str) -> Optional[EmailEventDef]:
    for event in EMAIL_EVENTS.values():
        if event.template_key == template_key:
            return event
    return None


def sample_variables_for_template(template_key: str) -> dict[str, str]:
    from datetime import datetime

    from config import settings

    base = {
        "shopName": settings.SITE_NAME or "KRX TCG",
        "url": settings.FRONTEND_URL or "https://example.com",
        "date": datetime.utcnow().strftime("%Y/%m/%d %H:%M"),
        "name": "山田 太郎",
        "email": "sample@example.com",
    }
    event = get_event_by_template(template_key)
    if event:
        base.update(event.sample_variables)
    return base


def normalize_variable_key(key: str) -> str:
    key = key.strip()
    return VARIABLE_ALIASES.get(key, key)
