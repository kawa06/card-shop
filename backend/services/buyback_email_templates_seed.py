"""Production-grade buyback email template definitions (structure-only placeholders)."""

from __future__ import annotations

from sqlalchemy.orm import Session

import models_email
from config import settings
from services.buyback_email_registry import BUYBACK_EMAIL_EVENTS
from services.email_order_layout import BUYBACK_EMAIL_BODY_SKELETON, BUYBACK_VARIABLES_HINT

_PLACEHOLDER = {
    "preheader": "（プリヘッダーを入力）",
    "bodyTitle": "（本文タイトル）",
    "bodyDescription": "（本文説明を入力してください）",
    "notesBlock": "（注意事項を入力してください）",
    "contactBlock": "（お問い合わせ案内を入力してください）",
    "signatureBlock": "（署名）",
}

# Customer-facing templates derived from registry
BUYBACK_EMAIL_TEMPLATES: list[dict] = [
    {
        "key": ev.default_template_key,
        "name": ev.description,
        "subject": f"【{{{{shopName}}}}】{ev.description}（{{{{buyNo}}}}）",
        "preheader": f"（プリヘッダー：{ev.description}）",
    }
    for ev in BUYBACK_EMAIL_EVENTS.values()
    if ev.event_key not in {"buyback_request_admin_alert", "buyback_guardian_consent"}
]

# Extra templates not in main registry loop
EXTRA_BUYBACK_TEMPLATES: list[dict] = [
    {
        "key": "buyback_identity_approved",
        "name": "本人確認承認",
        "subject": "【{{shopName}}】本人確認が承認されました",
        "preheader": "（プリヘッダー：本人確認承認）",
    },
    {
        "key": "buyback_identity_rejected",
        "name": "本人確認否認",
        "subject": "【{{shopName}}】本人確認の審査結果",
        "preheader": "（プリヘッダー：本人確認否認）",
    },
    {
        "key": "buyback_identity_resubmit_requested",
        "name": "本人確認再提出依頼",
        "subject": "【{{shopName}}】本人確認書類の再提出のお願い",
        "preheader": "（プリヘッダー：本人確認再提出）",
    },
    {
        "key": "buyback_store_appraisal_estimate",
        "name": "店舗査定時間見込み",
        "subject": "【{{shopName}}】店舗買取の査定時間について",
        "preheader": "（プリヘッダー：査定時間）",
    },
]


def _build_text_body_template() -> str:
    return (
        "{{name}} 様\n\n"
        "{{bodyTitle}}\n\n"
        "{{bodyDescription}}\n\n"
        "買取番号: {{buyNo}}\n"
        "ステータス: {{statusLabel}}\n\n"
        "{{notesBlock}}\n\n"
        "{{contactBlock}}\n\n"
        "{{signatureBlock}}"
    )


def seed_buyback_email_templates(db: Session, *, force_upgrade: bool = False) -> int:
    shop = settings.SITE_NAME or "KRX TCG"
    count = 0
    text_tpl = _build_text_body_template()
    html_body = BUYBACK_EMAIL_BODY_SKELETON
    all_defs = BUYBACK_EMAIL_TEMPLATES + EXTRA_BUYBACK_TEMPLATES
    seen: set[str] = set()

    for item in all_defs:
        key = item["key"]
        if key in seen:
            continue
        seen.add(key)

        existing = (
            db.query(models_email.EmailTemplate)
            .filter(models_email.EmailTemplate.template_key == key)
            .first()
        )
        subject = item["subject"].replace("{{shopName}}", shop)

        if existing:
            if force_upgrade or "{{buybackInfoBlock}}" not in (existing.html_body or ""):
                existing.name = item["name"]
                existing.subject = subject
                existing.preheader = item.get("preheader", _PLACEHOLDER["preheader"])
                existing.html_body = html_body
                existing.text_body = text_tpl
                existing.variables_hint = BUYBACK_VARIABLES_HINT
                existing.category = "buyback"
                count += 1
            continue

        db.add(
            models_email.EmailTemplate(
                template_key=key,
                category="buyback",
                name=item["name"],
                subject=subject,
                preheader=item.get("preheader", _PLACEHOLDER["preheader"]),
                html_body=html_body,
                text_body=text_tpl,
                variables_hint=BUYBACK_VARIABLES_HINT,
                is_active=True,
            )
        )
        count += 1
    return count


def upgrade_buyback_email_templates(db: Session) -> int:
    return seed_buyback_email_templates(db, force_upgrade=True)
