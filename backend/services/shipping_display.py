"""Display metadata for shipping methods (insurance labels, notes)."""

from __future__ import annotations

LEGACY_METHOD_ALIASES = {"international": "ems"}


def normalize_method_code(method_code: str | None) -> str | None:
    if not method_code:
        return method_code
    return LEGACY_METHOD_ALIASES.get(method_code, method_code)


METHOD_DISPLAY: dict[str, dict] = {
    "click_post": {
        "has_tracking": True,
        "has_insurance": False,
        "insurance_max_amount": 0,
    },
    "teikei_post": {
        "has_tracking": False,
        "has_insurance": False,
        "insurance_max_amount": 0,
    },
    "teigai_post": {
        "has_tracking": False,
        "has_insurance": False,
        "insurance_max_amount": 0,
    },
    "letter_pack_light": {
        "has_tracking": True,
        "has_insurance": False,
        "insurance_max_amount": 0,
    },
    "letter_pack_plus": {
        "has_tracking": True,
        "has_insurance": False,
        "insurance_max_amount": 0,
    },
    "yu_pack_60": {
        "has_tracking": True,
        "has_insurance": True,
        "insurance_max_amount": 300000,
        "insurance_note_ja": "セキュリティサービス利用時のみ最大500,000円",
        "insurance_note_en": "Up to ¥500,000 only with Security Service",
    },
    "yu_pack_80": {
        "has_tracking": True,
        "has_insurance": True,
        "insurance_max_amount": 300000,
        "insurance_note_ja": "セキュリティサービス利用時のみ最大500,000円",
        "insurance_note_en": "Up to ¥500,000 only with Security Service",
    },
    "yu_pack_100": {
        "has_tracking": True,
        "has_insurance": True,
        "insurance_max_amount": 300000,
        "insurance_note_ja": "セキュリティサービス利用時のみ最大500,000円",
        "insurance_note_en": "Up to ¥500,000 only with Security Service",
    },
    "takkyubin_60": {
        "has_tracking": True,
        "has_insurance": True,
        "insurance_max_amount": 300000,
    },
    "takkyubin_80": {
        "has_tracking": True,
        "has_insurance": True,
        "insurance_max_amount": 300000,
    },
    "takkyubin_compact": {
        "has_tracking": True,
        "has_insurance": True,
        "insurance_max_amount": 30000,
        "extra_note_ja": "専用BOX代70円が別途必要です",
        "extra_note_en": "Dedicated compact box (¥70) required separately",
    },
    "nekopos": {
        "has_tracking": True,
        "has_insurance": True,
        "insurance_max_amount": 3000,
    },
    "ems": {
        "has_tracking": True,
        "has_insurance": True,
        "insurance_max_amount": 20000,
        "insurance_detail_ja": "基本20,000円まで。追加料金で最大2,000,000円まで",
        "insurance_detail_en": "Basic up to ¥20,000; optional add-ons up to ¥2,000,000",
    },
    "yamato_global": {
        "has_tracking": True,
        "has_insurance": True,
        "insurance_max_amount": 20000,
    },
}


def enrich_shipping_quote(method_code: str, quote: dict) -> dict:
    code = normalize_method_code(method_code) or method_code
    meta = METHOD_DISPLAY.get(code, {})
    enriched = {**quote, "method_code": code}
    for key, value in meta.items():
        enriched[key] = value
    return enriched
