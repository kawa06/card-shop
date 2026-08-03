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
    raw_html_variables: frozenset[str] = frozenset({
        "content", "itemsTable", "assessmentDetail",
        "orderSummaryBlock", "itemsTable", "buttonsBlock", "notesBlock", "contactBlock",
        "shippingInfoBlock", "signatureBlock",
    })
    sample_variables: dict[str, str] = field(default_factory=dict)


# Japanese alias → canonical key (used by render_template_string)
VARIABLE_ALIASES: dict[str, str] = {
    "名前": "name",
    "氏名": "name",
    "メール": "email",
    "メールアドレス": "email",
    "注文番号": "orderNo",
    "注文日時": "orderDate",
    "注文金額": "orderAmount",
    "注文商品": "itemsTable",
    "決済方法": "paymentMethod",
    "ユーザー名": "name",
    "本文タイトル": "bodyTitle",
    "本文説明": "bodyDescription",
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
    "配送会社": "carrier",
    "追跡URL": "trackingUrl",
    "配送方法": "shippingMethod",
    "配送状況": "shippingStatus",
    "配送予定日": "deliveryDate",
    "配送先住所": "shippingAddress",
    "お問い合わせ番号": "inquiryNo",
    "お問い合わせURL": "contactUrl",
    "署名": "signatureBlock",
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
        "order_payment_confirmed", "order", "決済成功",
        ["name", "orderNo", "orderDate", "orderAmount", "paymentMethod", "itemsTable", "bodyTitle", "bodyDescription"],
        sample_variables={
            "name": "山田 太郎", "orderNo": "ORD-20260801-001", "orderAmount": "¥12,800",
            "paymentMethod": "クレジットカード", "bodyTitle": "（本文タイトル）",
        },
    ),
    "order.received": EmailEventDef(
        "order_received", "order", "注文受付",
        ["name", "orderNo", "orderDate", "orderAmount", "paymentMethod", "itemsTable"],
        sample_variables={"name": "山田 太郎", "orderNo": "ORD-20260801-001", "orderAmount": "¥12,800"},
    ),
    "order.payment_pending": EmailEventDef(
        "order_payment_pending", "order", "決済待ち",
        ["name", "orderNo", "orderAmount", "paymentMethod", "itemsTable"],
        sample_variables={"name": "山田 太郎", "orderNo": "ORD-20260801-001", "paymentMethod": "銀行振込"},
    ),
    "order.bank_transfer": EmailEventDef(
        "order_bank_transfer", "order", "銀行振込待ち",
        ["name", "orderNo", "orderAmount", "paymentMethod", "itemsTable"],
        sample_variables={"name": "山田 太郎", "orderNo": "ORD-20260801-001", "paymentMethod": "銀行振込"},
    ),
    "order.konbini_pending": EmailEventDef(
        "order_konbini_pending", "order", "コンビニ支払い待ち",
        ["name", "orderNo", "orderAmount", "paymentMethod"],
        sample_variables={"name": "山田 太郎", "orderNo": "ORD-20260801-001", "paymentMethod": "コンビニ決済"},
    ),
    "order.payment_failed": EmailEventDef(
        "order_payment_failed", "order", "決済失敗",
        ["name", "orderNo", "orderAmount", "paymentMethod"],
        sample_variables={"name": "山田 太郎", "orderNo": "ORD-20260801-001"},
    ),
    "order.payment_expired": EmailEventDef(
        "order_payment_expired", "order", "決済期限切れ",
        ["name", "orderNo", "orderAmount"],
        sample_variables={"name": "山田 太郎", "orderNo": "ORD-20260801-001"},
    ),
    "order.cancelled": EmailEventDef(
        "order_cancelled", "order", "注文キャンセル",
        ["name", "orderNo"],
        sample_variables={"name": "山田 太郎", "orderNo": "ORD-20260801-001"},
    ),
    "order.refund": EmailEventDef(
        "order_refund", "order", "返金完了",
        ["name", "orderNo", "orderAmount"],
        sample_variables={"name": "山田 太郎", "orderNo": "ORD-20260801-001", "orderAmount": "¥12,800"},
    ),
    "order.completed": EmailEventDef(
        "order_completed", "order", "注文完了",
        ["name", "orderNo", "orderDate", "orderAmount", "itemsTable"],
        sample_variables={"name": "山田 太郎", "orderNo": "ORD-20260801-001", "orderAmount": "¥12,800"},
    ),
    "order.shipped": EmailEventDef(
        "shipping_shipped", "shipping", "発送完了",
        ["name", "orderNo", "trackingNo", "shippedDate", "carrier", "trackingUrl", "shippingInfoBlock"],
        sample_variables={
            "name": "山田 太郎",
            "orderNo": "ORD-20260801-001",
            "trackingNo": "1234-5678-9012",
            "shippedDate": "2026/08/03",
            "carrier": "ヤマト運輸",
            "trackingUrl": "https://track.kuronekoyamato.co.jp/english/tracking/inquiry?number=1234-5678-9012",
        },
    ),
    "shipping.preparing": EmailEventDef(
        "shipping_preparing", "shipping", "発送準備中",
        ["name", "orderNo", "shippingMethod", "shippingAddress", "shippingInfoBlock"],
    ),
    "shipping.shipped": EmailEventDef(
        "shipping_shipped", "shipping", "発送完了",
        ["name", "orderNo", "trackingNo", "carrier", "trackingUrl", "shippingInfoBlock"],
        sample_variables={
            "name": "山田 太郎",
            "orderNo": "ORD-20260801-001",
            "trackingNo": "1234-5678-9012",
            "carrier": "ヤマト運輸",
        },
    ),
    "shipping.handed_to_carrier": EmailEventDef(
        "shipping_handed_to_carrier", "shipping", "配送会社引渡し完了",
        ["name", "orderNo", "carrier", "trackingNo", "trackingUrl"],
    ),
    "shipping.tracking_issued": EmailEventDef(
        "shipping_tracking_issued", "shipping", "追跡番号発行",
        ["name", "orderNo", "trackingNo", "trackingUrl"],
    ),
    "shipping.delivered": EmailEventDef(
        "shipping_delivered", "shipping", "配達完了",
        ["name", "orderNo", "deliveryDate", "shippingAddress"],
    ),
    "shipping.delay_notice": EmailEventDef(
        "shipping_delay_notice", "shipping", "配送遅延のお知らせ",
        ["name", "orderNo", "deliveryDate", "shippingStatus"],
    ),
    "shipping.address_issue": EmailEventDef(
        "shipping_address_issue", "shipping", "住所不備のお知らせ",
        ["name", "orderNo", "shippingAddress"],
    ),
    "shipping.absence_return": EmailEventDef(
        "shipping_absence_return", "shipping", "長期不在による持ち戻り",
        ["name", "orderNo", "trackingNo", "trackingUrl"],
    ),
    "shipping.return_started": EmailEventDef(
        "shipping_return_started", "shipping", "返送開始",
        ["name", "orderNo", "trackingNo"],
    ),
    "shipping.return_completed": EmailEventDef(
        "shipping_return_completed", "shipping", "返送完了",
        ["name", "orderNo", "shippingAddress"],
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
    from services.shipping_email_registry import normalize_template_key
    from services.shipping_email_variables import build_shipping_sample_variables

    normalized = normalize_template_key(template_key)
    if normalized.startswith("shipping_") or template_key.startswith("shipping_"):
        sample = build_shipping_sample_variables(normalized)
        return {k: v for k, v in sample.items() if not str(k).startswith("_")}

    base = {
        "shopName": settings.SITE_NAME or "KRX TCG",
        "url": settings.FRONTEND_URL or "https://example.com",
        "date": datetime.utcnow().strftime("%Y/%m/%d %H:%M"),
        "name": "山田 太郎",
        "email": "sample@example.com",
        "orderNo": "ORD-20260801-001",
        "orderDate": datetime.utcnow().strftime("%Y/%m/%d %H:%M"),
        "orderAmount": "¥12,800",
        "paymentMethod": "クレジットカード",
        "bodyTitle": "（本文タイトル）",
        "bodyDescription": "（本文説明を入力してください）",
        "notesBlock": "（注意事項を入力してください）",
        "contactBlock": "（お問い合わせ案内を入力してください）",
        "buttonsBlock": "",
        "orderSummaryBlock": "",
        "itemsTable": "",
        "signatureBlock": "（署名）",
    }
    event = get_event_by_template(template_key)
    if event:
        base.update(event.sample_variables)
    if template_key.startswith("order_"):
        base["itemsTable"] = (
            '<table role="presentation"><tr><td>サンプル商品</td><td>1</td><td>¥1,000</td></tr></table>'
        )
    return base


def normalize_variable_key(key: str) -> str:
    key = key.strip()
    return VARIABLE_ALIASES.get(key, key)
