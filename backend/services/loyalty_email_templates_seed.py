"""Production-grade point/coupon/rank email template definitions (structure-only placeholders)."""

from __future__ import annotations

from sqlalchemy.orm import Session

import models_email
from config import settings
from services.email_order_layout import LOYALTY_EMAIL_BODY_SKELETON, LOYALTY_VARIABLES_HINT
from services.loyalty_email_registry import LOYALTY_EMAIL_EVENTS

_PLACEHOLDER = {
    "preheader": "（プリヘッダーを入力）",
    "bodyTitle": "（本文タイトル）",
    "bodyDescription": "（本文説明を入力してください）",
    "notesBlock": "（注意事項を入力してください）",
    "contactBlock": "（お問い合わせ案内を入力してください）",
    "signatureBlock": "（署名）",
}

LOYALTY_EMAIL_TEMPLATES: list[dict] = [
    {
        "key": ev.default_template_key,
        "name": ev.description,
        "category": ev.category,
        "subject": f"【{{{{shopName}}}}】{ev.description}",
        "preheader": f"（プリヘッダー：{ev.description}）",
    }
    for ev in LOYALTY_EMAIL_EVENTS.values()
]


def _build_text_body_template() -> str:
    return (
        "{{name}} 様\n\n"
        "{{bodyTitle}}\n\n"
        "{{bodyDescription}}\n\n"
        "{{loyaltyInfoBlock}}\n\n"
        "{{notesBlock}}\n\n"
        "{{contactBlock}}\n\n"
        "{{signatureBlock}}"
    )


def seed_loyalty_email_templates(db: Session, *, force_upgrade: bool = False) -> int:
    shop = settings.SITE_NAME or "KRX TCG"
    count = 0
    text_tpl = _build_text_body_template()
    html_body = LOYALTY_EMAIL_BODY_SKELETON

    for item in LOYALTY_EMAIL_TEMPLATES:
        key = item["key"]
        existing = (
            db.query(models_email.EmailTemplate)
            .filter(models_email.EmailTemplate.template_key == key)
            .first()
        )
        subject = item["subject"].replace("{{shopName}}", shop)

        if existing:
            if force_upgrade or "{{loyaltyInfoBlock}}" not in (existing.html_body or ""):
                existing.name = item["name"]
                existing.subject = subject
                existing.preheader = item.get("preheader", _PLACEHOLDER["preheader"])
                existing.html_body = html_body
                existing.text_body = text_tpl
                existing.variables_hint = LOYALTY_VARIABLES_HINT
                existing.category = item["category"]
                count += 1
            continue

        db.add(
            models_email.EmailTemplate(
                template_key=key,
                category=item["category"],
                name=item["name"],
                subject=subject,
                preheader=item.get("preheader", _PLACEHOLDER["preheader"]),
                html_body=html_body,
                text_body=text_tpl,
                variables_hint=LOYALTY_VARIABLES_HINT,
                is_active=True,
            )
        )
        count += 1
    return count


def upgrade_loyalty_email_templates(db: Session) -> int:
    return seed_loyalty_email_templates(db, force_upgrade=True)
