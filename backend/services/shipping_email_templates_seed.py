"""Production-grade shipping/delivery email template definitions (structure-only placeholders)."""

from __future__ import annotations

from sqlalchemy.orm import Session

import models_email
from config import settings
from services.email_order_layout import SHIPPING_EMAIL_BODY_SKELETON, SHIPPING_VARIABLES_HINT

_PLACEHOLDER = {
    "preheader": "（プリヘッダーを入力）",
    "bodyTitle": "（本文タイトル）",
    "bodyDescription": "（本文説明を入力してください）",
    "notesBlock": "（注意事項を入力してください）",
    "contactBlock": "（お問い合わせ案内を入力してください）",
    "signatureBlock": "（署名）",
}

SHIPPING_EMAIL_TEMPLATES: list[dict] = [
    {
        "key": "shipping_preparing",
        "name": "発送準備中",
        "subject": "【{{shopName}}】発送準備中のお知らせ（{{orderNo}}）",
        "preheader": "（プリヘッダー：発送準備中）",
    },
    {
        "key": "shipping_shipped",
        "name": "発送完了",
        "subject": "【{{shopName}}】商品を発送しました（{{orderNo}}）",
        "preheader": "（プリヘッダー：発送完了）",
    },
    {
        "key": "shipping_handed_to_carrier",
        "name": "配送会社引渡し完了",
        "subject": "【{{shopName}}】配送会社へお引渡ししました（{{orderNo}}）",
        "preheader": "（プリヘッダー：引渡し完了）",
    },
    {
        "key": "shipping_tracking_issued",
        "name": "追跡番号発行",
        "subject": "【{{shopName}}】追跡番号のお知らせ（{{orderNo}}）",
        "preheader": "（プリヘッダー：追跡番号）",
    },
    {
        "key": "shipping_delivered",
        "name": "配達完了",
        "subject": "【{{shopName}}】配達が完了しました（{{orderNo}}）",
        "preheader": "（プリヘッダー：配達完了）",
    },
    {
        "key": "shipping_delay_notice",
        "name": "配送遅延のお知らせ",
        "subject": "【{{shopName}}】配送遅延のお知らせ（{{orderNo}}）",
        "preheader": "（プリヘッダー：配送遅延）",
    },
    {
        "key": "shipping_address_issue",
        "name": "住所不備のお知らせ",
        "subject": "【{{shopName}}】配送先住所の確認のお願い（{{orderNo}}）",
        "preheader": "（プリヘッダー：住所不備）",
    },
    {
        "key": "shipping_absence_return",
        "name": "長期不在による持ち戻り",
        "subject": "【{{shopName}}】不在のため持ち戻りました（{{orderNo}}）",
        "preheader": "（プリヘッダー：持ち戻り）",
    },
    {
        "key": "shipping_return_started",
        "name": "返送開始",
        "subject": "【{{shopName}}】返送手続きを開始しました（{{orderNo}}）",
        "preheader": "（プリヘッダー：返送開始）",
    },
    {
        "key": "shipping_return_completed",
        "name": "返送完了",
        "subject": "【{{shopName}}】返送が完了しました（{{orderNo}}）",
        "preheader": "（プリヘッダー：返送完了）",
    },
]


def _build_text_body_template() -> str:
    return (
        "{{name}} 様\n\n"
        "{{bodyTitle}}\n\n"
        "{{bodyDescription}}\n\n"
        "注文番号: {{orderNo}}\n"
        "配送会社: {{carrier}}\n"
        "送り状番号: {{trackingNo}}\n\n"
        "{{notesBlock}}\n\n"
        "{{contactBlock}}\n\n"
        "{{signatureBlock}}"
    )


def seed_shipping_email_templates(db: Session, *, force_upgrade: bool = False) -> int:
    """Insert or upgrade shipping templates. Returns count of upserted rows."""
    shop = settings.SITE_NAME or "KRX TCG"
    count = 0
    text_tpl = _build_text_body_template()
    html_body = SHIPPING_EMAIL_BODY_SKELETON

    for item in SHIPPING_EMAIL_TEMPLATES:
        existing = (
            db.query(models_email.EmailTemplate)
            .filter(models_email.EmailTemplate.template_key == item["key"])
            .first()
        )
        subject = item["subject"].replace("{{shopName}}", shop)

        if existing:
            if force_upgrade or "{{shippingInfoBlock}}" not in (existing.html_body or ""):
                existing.name = item["name"]
                existing.subject = subject
                existing.preheader = item.get("preheader", _PLACEHOLDER["preheader"])
                existing.html_body = html_body
                existing.text_body = text_tpl
                existing.variables_hint = SHIPPING_VARIABLES_HINT
                existing.category = "shipping"
                count += 1
            continue

        db.add(
            models_email.EmailTemplate(
                template_key=item["key"],
                category="shipping",
                name=item["name"],
                subject=subject,
                preheader=item.get("preheader", _PLACEHOLDER["preheader"]),
                html_body=html_body,
                text_body=text_tpl,
                variables_hint=SHIPPING_VARIABLES_HINT,
                is_active=True,
            )
        )
        count += 1
    return count


def upgrade_shipping_email_templates(db: Session) -> int:
    return seed_shipping_email_templates(db, force_upgrade=True)
