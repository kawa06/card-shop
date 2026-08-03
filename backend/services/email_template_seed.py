"""Seed default email templates for admin-managed mail platform."""

from __future__ import annotations

import json

from sqlalchemy.orm import Session

import models_email
from config import settings

DEFAULT_BRAND = {
    "logo_url": "",
    "sender_name": "KRX TCG",
    "brand_color": "#fbbf24",
    "footer_text": "© KRX TCG. All rights reserved.",
    "sns_links_json": json.dumps([
        {"label": "X (Twitter)", "url": ""},
        {"label": "Instagram", "url": ""},
    ]),
    "terms_url": "",
    "contact_url": "",
    "privacy_url": "",
    "company_name": "KRX TCG",
    "company_address": "",
    "contact_email": "",
    "contact_phone": "",
}

VARIABLES_COMMON = "{{name}} / {{名前}}, {{email}}, {{orderNo}} / {{注文番号}}, {{shopName}}, {{url}}, {{date}} / {{日付}}"

TEMPLATE_DEFS: list[dict] = [
    # member templates seeded via member_email_templates_seed.py
    # order
    {"key": "order_completed", "category": "order", "name": "注文完了", "subject": "【{{shopName}}】ご注文ありがとうございます（{{orderNo}}）"},
    {"key": "order_bank_transfer", "category": "order", "name": "銀行振込案内", "subject": "【{{shopName}}】銀行振込のご案内（{{orderNo}}）"},
    {"key": "order_payment_confirmed", "category": "order", "name": "入金確認", "subject": "【{{shopName}}】入金を確認しました（{{orderNo}}）"},
    {"key": "order_payment_failed", "category": "order", "name": "決済失敗", "subject": "【{{shopName}}】決済に失敗しました（{{orderNo}}）"},
    {"key": "order_cancelled", "category": "order", "name": "キャンセル", "subject": "【{{shopName}}】ご注文キャンセル（{{orderNo}}）"},
    {"key": "order_shipping_prep", "category": "order", "name": "発送準備開始", "subject": "【{{shopName}}】発送準備を開始しました（{{orderNo}}）"},
    {"key": "order_shipped", "category": "order", "name": "発送完了", "subject": "【{{shopName}}】商品を発送しました（{{orderNo}}）"},
    {"key": "order_tracking", "category": "order", "name": "送り状番号通知", "subject": "【{{shopName}}】送り状番号のお知らせ（{{orderNo}}）"},
    {"key": "order_delivered", "category": "order", "name": "配達完了", "subject": "【{{shopName}}】配達が完了しました（{{orderNo}}）"},
    {"key": "order_refund", "category": "order", "name": "返金完了", "subject": "【{{shopName}}】返金が完了しました（{{orderNo}}）"},
    {"key": "order_cancel_complete", "category": "order", "name": "注文キャンセル完了", "subject": "【{{shopName}}】キャンセル処理完了（{{orderNo}}）"},
    # buyback (includes legacy alias keys)
    {"key": "buyback_request_submitted", "category": "buyback", "name": "買取申請受付", "subject": "【{{shopName}}】買取申請を受け付けました（{{buyNo}}）"},
    {"key": "buyback_store_reservation", "category": "buyback", "name": "店舗予約受付", "subject": "【{{shopName}}】店舗買取予約を受け付けました"},
    {"key": "buyback_mail_received", "category": "buyback", "name": "郵送受付", "subject": "【{{shopName}}】郵送買取の受付"},
    {"key": "buyback_inbound_received", "category": "buyback", "name": "荷物到着", "subject": "【{{shopName}}】荷物を受け取りました（{{buyNo}}）"},
    {"key": "buyback_assessing", "category": "buyback", "name": "査定開始", "subject": "【{{shopName}}】査定を開始しました（{{buyNo}}）"},
    {"key": "buyback_assessment_ready", "category": "buyback", "name": "査定完了", "subject": "【{{shopName}}】査定が完了しました（{{buyNo}}）"},
    {"key": "buyback_assessment_amount", "category": "buyback", "name": "査定金額通知", "subject": "【{{shopName}}】査定金額のお知らせ（{{buyNo}}）"},
    {"key": "buyback_reduction_notice", "category": "buyback", "name": "減額理由通知", "subject": "【{{shopName}}】減額理由のお知らせ（{{buyNo}}）"},
    {"key": "buyback_assessment_detail", "category": "buyback", "name": "査定詳細通知", "subject": "【{{shopName}}】査定詳細（{{buyNo}}）"},
    {"key": "buyback_awaiting_approval", "category": "buyback", "name": "承認待ち", "subject": "【{{shopName}}】査定結果のご確認をお願いします"},
    {"key": "buyback_accepted", "category": "buyback", "name": "承認完了", "subject": "【{{shopName}}】買取承認完了（{{buyNo}}）"},
    {"key": "buyback_rejected", "category": "buyback", "name": "キャンセル/却下", "subject": "【{{shopName}}】買取結果のお知らせ（{{buyNo}}）"},
    {"key": "buyback_cancelled", "category": "buyback", "name": "キャンセル", "subject": "【{{shopName}}】買取キャンセル（{{buyNo}}）"},
    {"key": "buyback_return_started", "category": "buyback", "name": "返送開始", "subject": "【{{shopName}}】返送手続き開始（{{buyNo}}）"},
    {"key": "buyback_package_shipped", "category": "buyback", "name": "返送完了", "subject": "【{{shopName}}】返送商品を発送しました（{{buyNo}}）"},
    {"key": "buyback_return_tracking", "category": "buyback", "name": "返送送り状番号", "subject": "【{{shopName}}】返送送り状番号（{{buyNo}}）"},
    {"key": "buyback_payout_scheduled", "category": "buyback", "name": "振込予定", "subject": "【{{shopName}}】振込予定のお知らせ（{{buyNo}}）"},
    {"key": "buyback_payout_completed", "category": "buyback", "name": "振込完了", "subject": "【{{shopName}}】振込が完了しました（{{buyNo}}）"},
    {"key": "buyback_request_admin_alert", "category": "buyback", "name": "買取申請（管理者）", "subject": "【{{shopName}}】新規買取申請"},
    {"key": "buyback_guardian_consent", "category": "buyback", "name": "保護者同意依頼", "subject": "【{{shopName}}】保護者同意のお願い"},
    # point
    {"key": "point_granted", "category": "point", "name": "ポイント付与", "subject": "【{{shopName}}】ポイント付与のお知らせ"},
    {"key": "point_expired", "category": "point", "name": "ポイント失効", "subject": "【{{shopName}}】ポイント失効のお知らせ"},
    {"key": "point_referral", "category": "point", "name": "紹介ポイント付与", "subject": "【{{shopName}}】紹介ポイント付与"},
    {"key": "coupon_issued", "category": "point", "name": "クーポン発行", "subject": "【{{shopName}}】クーポン発行のお知らせ"},
    # ops
    {"key": "inquiry_received", "category": "ops", "name": "お問い合わせ受付", "subject": "【{{shopName}}】お問い合わせを受け付けました"},
    {"key": "inquiry_reply", "category": "ops", "name": "お問い合わせ返信", "subject": "【{{shopName}}】お問い合わせへの返信"},
    {"key": "announcement_broadcast", "category": "ops", "name": "お知らせ配信", "subject": "【{{shopName}}】お知らせ"},
    {"key": "maintenance_notice", "category": "ops", "name": "メンテナンス案内", "subject": "【{{shopName}}】メンテナンスのお知らせ"},
    {"key": "incident_notice", "category": "ops", "name": "障害発生通知", "subject": "【{{shopName}}】障害発生のお知らせ"},
    {"key": "incident_resolved", "category": "ops", "name": "復旧通知", "subject": "【{{shopName}}】復旧のお知らせ"},
]


def _default_html(name: str) -> str:
    return (
        "<p>{{name}} 様</p>"
        f"<p>{name}に関するご案内です。</p>"
        "<div style=\"background:#f8fafc;border:1px solid #e2e8f0;border-radius:8px;"
        "padding:16px;margin:16px 0;\">{{content}}</div>"
        "<p style=\"font-size:14px;color:#64748b;\">"
        "ご不明点は<a href=\"{{contactUrl}}\" style=\"color:#6366f1;\">お問い合わせ</a>"
        "よりご連絡ください。</p>"
    )


def seed_email_templates(db: Session) -> None:
    brand = db.query(models_email.EmailBrandSettings).first()
    if brand is None:
        brand = models_email.EmailBrandSettings(**DEFAULT_BRAND)
        db.add(brand)

    shop = settings.SITE_NAME or "KRX TCG"
    for item in TEMPLATE_DEFS:
        existing = (
            db.query(models_email.EmailTemplate)
            .filter(models_email.EmailTemplate.template_key == item["key"])
            .first()
        )
        if existing:
            continue
        db.add(
            models_email.EmailTemplate(
                template_key=item["key"],
                category=item["category"],
                name=item["name"],
                subject=item["subject"].replace("{{shopName}}", shop),
                html_body=_default_html(item["name"]),
                text_body=None,
                variables_hint=VARIABLES_COMMON,
                is_active=True,
            )
        )
    db.commit()
