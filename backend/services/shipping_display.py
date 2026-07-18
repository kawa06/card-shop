"""Display metadata for shipping methods (insurance labels, notes)."""

from __future__ import annotations

LEGACY_METHOD_ALIASES = {"international": "ems"}

# Shop packaging materials added to Yamato shipping quotes at checkout.
PACKAGING_SURCHARGES: dict[str, int] = {
    "takkyubin_compact": 77,
    "takkyubin_60": 110,
    "takkyubin_80": 110,
}


def normalize_method_code(method_code: str | None) -> str | None:
    if not method_code:
        return method_code
    return LEGACY_METHOD_ALIASES.get(method_code, method_code)


def get_packaging_surcharge(method_code: str | None) -> int:
    code = normalize_method_code(method_code) or method_code
    if not code:
        return 0
    return PACKAGING_SURCHARGES.get(code, 0)


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
        "extra_note_ja": "表示料金に段ボール代110円を含みます",
        "extra_note_en": "Price includes ¥110 cardboard box",
    },
    "takkyubin_80": {
        "has_tracking": True,
        "has_insurance": True,
        "insurance_max_amount": 300000,
        "extra_note_ja": "表示料金に段ボール代110円を含みます",
        "extra_note_en": "Price includes ¥110 cardboard box",
    },
    "takkyubin_compact": {
        "has_tracking": True,
        "has_insurance": True,
        "insurance_max_amount": 30000,
        "extra_note_ja": "表示料金に専用BOX代77円を含みます",
        "extra_note_en": "Price includes ¥77 dedicated compact box",
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
