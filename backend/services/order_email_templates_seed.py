"""Production-grade order/payment email template definitions (structure-only placeholders)."""

from __future__ import annotations

from sqlalchemy.orm import Session

import models_email
from config import settings
from services.email_order_layout import ORDER_EMAIL_BODY_SKELETON, ORDER_VARIABLES_HINT

# Placeholder copy — admin replaces via template editor
_PLACEHOLDER = {
    "preheader": "（プリヘッダーを入力）",
    "bodyTitle": "（本文タイトル）",
    "bodyDescription": "（本文説明を入力してください）",
    "notesBlock": "（注意事項を入力してください）",
    "contactBlock": "（お問い合わせ案内を入力してください）",
}

ORDER_PAYMENT_TEMPLATES: list[dict] = [
    {
        "key": "order_completed",
        "name": "注文完了",
        "subject": "【{{shopName}}】ご注文ありがとうございます（{{orderNo}}）",
        "preheader": "（プリヘッダー：注文完了）",
        "buttons": [{"text": "（ボタンラベル）", "url": "{{url}}/orders"}],
    },
    {
        "key": "order_received",
        "name": "注文受付",
        "subject": "【{{shopName}}】ご注文を受け付けました（{{orderNo}}）",
        "preheader": "（プリヘッダー：注文受付）",
        "buttons": [{"text": "（ボタンラベル）", "url": "{{url}}/orders"}],
    },
    {
        "key": "order_payment_pending",
        "name": "決済待ち",
        "subject": "【{{shopName}}】お支払いのご案内（{{orderNo}}）",
        "preheader": "（プリヘッダー：決済待ち）",
        "buttons": [{"text": "（ボタンラベル）", "url": "{{url}}/orders"}],
    },
    {
        "key": "order_bank_transfer",
        "name": "銀行振込待ち",
        "subject": "【{{shopName}}】銀行振込のご案内（{{orderNo}}）",
        "preheader": "（プリヘッダー：銀行振込）",
        "buttons": [],
    },
    {
        "key": "order_konbini_pending",
        "name": "コンビニ支払い待ち",
        "subject": "【{{shopName}}】コンビニお支払いのご案内（{{orderNo}}）",
        "preheader": "（プリヘッダー：コンビニ支払い）",
        "buttons": [],
    },
    {
        "key": "order_payment_confirmed",
        "name": "決済成功",
        "subject": "【{{shopName}}】お支払いを確認しました（{{orderNo}}）",
        "preheader": "（プリヘッダー：決済成功）",
        "buttons": [{"text": "（ボタンラベル）", "url": "{{url}}/orders"}],
    },
    {
        "key": "order_payment_failed",
        "name": "決済失敗",
        "subject": "【{{shopName}}】決済に失敗しました（{{orderNo}}）",
        "preheader": "（プリヘッダー：決済失敗）",
        "buttons": [{"text": "（ボタンラベル）", "url": "{{url}}/orders"}],
    },
    {
        "key": "order_payment_expired",
        "name": "決済期限切れ",
        "subject": "【{{shopName}}】お支払期限のご案内（{{orderNo}}）",
        "preheader": "（プリヘッダー：決済期限切れ）",
        "buttons": [{"text": "（ボタンラベル）", "url": "{{url}}"}],
    },
    {
        "key": "order_cancelled",
        "name": "注文キャンセル",
        "subject": "【{{shopName}}】ご注文キャンセルのお知らせ（{{orderNo}}）",
        "preheader": "（プリヘッダー：キャンセル）",
        "buttons": [{"text": "（ボタンラベル）", "url": "{{url}}"}],
    },
    {
        "key": "order_refund",
        "name": "返金完了",
        "subject": "【{{shopName}}】返金が完了しました（{{orderNo}}）",
        "preheader": "（プリヘッダー：返金完了）",
        "buttons": [],
    },
]


def _build_html_body(item: dict) -> str:
    buttons_block = ""
    if item.get("buttons"):
        buttons_block = "{{buttonsBlock}}"
    return ORDER_EMAIL_BODY_SKELETON.replace("{{buttonsBlock}}", buttons_block or "{{buttonsBlock}}")


def _build_text_body_template() -> str:
    return (
        "{{name}} 様\n\n"
        "{{bodyTitle}}\n\n"
        "{{bodyDescription}}\n\n"
        "注文番号: {{orderNo}}\n"
        "合計: {{orderAmount}}\n\n"
        "{{notesBlock}}\n\n"
        "{{contactBlock}}"
    )


def seed_order_payment_templates(db: Session, *, force_upgrade: bool = False) -> int:
    """Insert or upgrade order/payment templates. Returns count of upserted rows."""
    shop = settings.SITE_NAME or "KRX TCG"
    count = 0
    text_tpl = _build_text_body_template()

    for item in ORDER_PAYMENT_TEMPLATES:
        existing = (
            db.query(models_email.EmailTemplate)
            .filter(models_email.EmailTemplate.template_key == item["key"])
            .first()
        )
        subject = item["subject"].replace("{{shopName}}", shop)
        html_body = _build_html_body(item)

        if existing:
            if force_upgrade or "{{bodyTitle}}" not in (existing.html_body or ""):
                existing.name = item["name"]
                existing.subject = subject
                existing.preheader = item.get("preheader", _PLACEHOLDER["preheader"])
                existing.html_body = html_body
                existing.text_body = text_tpl
                existing.variables_hint = ORDER_VARIABLES_HINT
                existing.category = "order"
                count += 1
            continue

        db.add(
            models_email.EmailTemplate(
                template_key=item["key"],
                category="order",
                name=item["name"],
                subject=subject,
                preheader=item.get("preheader", _PLACEHOLDER["preheader"]),
                html_body=html_body,
                text_body=text_tpl,
                variables_hint=ORDER_VARIABLES_HINT,
                is_active=True,
            )
        )
        count += 1
    return count


def upgrade_order_payment_templates(db: Session) -> int:
    return seed_order_payment_templates(db, force_upgrade=True)
