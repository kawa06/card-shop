"""Country metadata and international shipping zone groups (EMS / Yamato Global)."""

from __future__ import annotations

from typing import TypedDict


class InternationalZoneProfile(TypedDict):
    label_ja: str
    label_en: str
    ems_fee_500g: int
    yamato_global_fee_500g: int
    ems_delivery_min_days: int
    ems_delivery_max_days: int
    yamato_delivery_min_days: int
    yamato_delivery_max_days: int
    ems_insurance_max_amount: int
    yamato_insurance_max_amount: int


# Japan Post EMS 500g tier + Yamato Global reference (managed by zone, not per country)
# https://www.post.japanpost.jp/send/oversea/charge/list-ems/all.html
INTERNATIONAL_SHIPPING_ZONES: dict[int, InternationalZoneProfile] = {
    1: {
        "label_ja": "アジア近隣（中国・韓国・台湾）",
        "label_en": "Near Asia (China, Korea, Taiwan)",
        "ems_fee_500g": 1450,
        "yamato_global_fee_500g": 1700,
        "ems_delivery_min_days": 2,
        "ems_delivery_max_days": 4,
        "yamato_delivery_min_days": 3,
        "yamato_delivery_max_days": 6,
        "ems_insurance_max_amount": 20000,
        "yamato_insurance_max_amount": 20000,
    },
    2: {
        "label_ja": "アジアその他（香港・シンガポール・タイ等）",
        "label_en": "Other Asia (Hong Kong, Singapore, Thailand, etc.)",
        "ems_fee_500g": 1900,
        "yamato_global_fee_500g": 2200,
        "ems_delivery_min_days": 3,
        "ems_delivery_max_days": 6,
        "yamato_delivery_min_days": 4,
        "yamato_delivery_max_days": 8,
        "ems_insurance_max_amount": 20000,
        "yamato_insurance_max_amount": 20000,
    },
    3: {
        "label_ja": "欧州・オセアニア・カナダ",
        "label_en": "Europe, Oceania & Canada",
        "ems_fee_500g": 3150,
        "yamato_global_fee_500g": 3600,
        "ems_delivery_min_days": 4,
        "ems_delivery_max_days": 10,
        "yamato_delivery_min_days": 5,
        "yamato_delivery_max_days": 14,
        "ems_insurance_max_amount": 20000,
        "yamato_insurance_max_amount": 20000,
    },
    4: {
        "label_ja": "アメリカ合衆国",
        "label_en": "United States",
        "ems_fee_500g": 3900,
        "yamato_global_fee_500g": 4500,
        "ems_delivery_min_days": 3,
        "ems_delivery_max_days": 7,
        "yamato_delivery_min_days": 4,
        "yamato_delivery_max_days": 12,
        "ems_insurance_max_amount": 20000,
        "yamato_insurance_max_amount": 20000,
    },
    5: {
        "label_ja": "中南米・アフリカ",
        "label_en": "Central/South America & Africa",
        "ems_fee_500g": 3600,
        "yamato_global_fee_500g": 4100,
        "ems_delivery_min_days": 5,
        "ems_delivery_max_days": 14,
        "yamato_delivery_min_days": 6,
        "yamato_delivery_max_days": 16,
        "ems_insurance_max_amount": 20000,
        "yamato_insurance_max_amount": 20000,
    },
}

# Legacy aliases (zone JSON in DB)
EMS_ZONE_FEES_500G = {z: p["ems_fee_500g"] for z, p in INTERNATIONAL_SHIPPING_ZONES.items()}
YAMATO_GLOBAL_ZONE_FEES_500G = {z: p["yamato_global_fee_500g"] for z, p in INTERNATIONAL_SHIPPING_ZONES.items()}

DOMESTIC_COUNTRY_VALUES = frozenset({"JP", "Japan", "日本", "japan", "jp"})

INTERNATIONAL_METHOD_CODES = frozenset({"ems", "yamato_global"})

COUNTRIES = [
    {"code": "JP", "name_ja": "日本", "name_en": "Japan", "zone": "Domestic", "ems_zone": None},
    {"code": "CN", "name_ja": "中国", "name_en": "China", "zone": "Asia", "ems_zone": 1},
    {"code": "KR", "name_ja": "韓国", "name_en": "South Korea", "zone": "Asia", "ems_zone": 1},
    {"code": "TW", "name_ja": "台湾", "name_en": "Taiwan", "zone": "Asia", "ems_zone": 1},
    {"code": "HK", "name_ja": "香港", "name_en": "Hong Kong", "zone": "Asia", "ems_zone": 2},
    {"code": "SG", "name_ja": "シンガポール", "name_en": "Singapore", "zone": "Asia", "ems_zone": 2},
    {"code": "TH", "name_ja": "タイ", "name_en": "Thailand", "zone": "Asia", "ems_zone": 2},
    {"code": "US", "name_ja": "アメリカ合衆国", "name_en": "United States", "zone": "North America", "ems_zone": 4},
    {"code": "CA", "name_ja": "カナダ", "name_en": "Canada", "zone": "North America", "ems_zone": 3},
    {"code": "AU", "name_ja": "オーストラリア", "name_en": "Australia", "zone": "Oceania", "ems_zone": 3},
    {"code": "NZ", "name_ja": "ニュージーランド", "name_en": "New Zealand", "zone": "Oceania", "ems_zone": 3},
    {"code": "GB", "name_ja": "イギリス", "name_en": "United Kingdom", "zone": "Europe", "ems_zone": 3},
    {"code": "FR", "name_ja": "フランス", "name_en": "France", "zone": "Europe", "ems_zone": 3},
    {"code": "DE", "name_ja": "ドイツ", "name_en": "Germany", "zone": "Europe", "ems_zone": 3},
    {"code": "IT", "name_ja": "イタリア", "name_en": "Italy", "zone": "Europe", "ems_zone": 3},
    {"code": "ES", "name_ja": "スペイン", "name_en": "Spain", "zone": "Europe", "ems_zone": 3},
]


def normalize_country_code(country: str | None) -> str:
    if not country:
        return "JP"
    value = country.strip()
    if value in DOMESTIC_COUNTRY_VALUES:
        return "JP"
    for row in COUNTRIES:
        if value in (row["code"], row["name_en"], row["name_ja"]):
            return row["code"]
    return value


def is_domestic_japan(country: str | None) -> bool:
    return normalize_country_code(country) == "JP"


def is_supported_checkout_country(country: str | None) -> bool:
    code = normalize_country_code(country)
    return any(row["code"] == code for row in COUNTRIES)


def get_country_row(country: str | None) -> dict | None:
    code = normalize_country_code(country)
    for row in COUNTRIES:
        if row["code"] == code:
            return row
    return None


def get_country_zone(country_code_or_name: str) -> str:
    row = get_country_row(country_code_or_name)
    if row:
        return row["zone"]
    return "Other"


def get_country_ems_zone(country: str | None) -> int:
    row = get_country_row(country)
    if row and row.get("ems_zone"):
        return int(row["ems_zone"])
    return 3


def get_international_zone_profile(country: str | None) -> InternationalZoneProfile:
    zone = get_country_ems_zone(country)
    return INTERNATIONAL_SHIPPING_ZONES.get(zone, INTERNATIONAL_SHIPPING_ZONES[3])


def _resolve_international_method(method_code: str) -> str:
    if method_code in ("international", "ems"):
        return "ems"
    if method_code == "yamato_global":
        return "yamato_global"
    return "ems"


def get_ems_fee_500g(country: str | None) -> int:
    return get_international_zone_profile(country)["ems_fee_500g"]


def get_yamato_global_fee_500g(country: str | None) -> int:
    return get_international_zone_profile(country)["yamato_global_fee_500g"]


def get_international_shipping_quote(method_code: str, country: str | None) -> dict:
    """Return fee, delivery estimate, and insurance for an international method."""
    resolved = _resolve_international_method(method_code)
    profile = get_international_zone_profile(country)
    zone = get_country_ems_zone(country)

    if resolved == "yamato_global":
        return {
            "method_code": "yamato_global",
            "fee_jpy": profile["yamato_global_fee_500g"],
            "ems_zone": zone,
            "zone_label_ja": profile["label_ja"],
            "zone_label_en": profile["label_en"],
            "estimated_delivery_min_days": profile["yamato_delivery_min_days"],
            "estimated_delivery_max_days": profile["yamato_delivery_max_days"],
            "has_insurance": True,
            "insurance_max_amount": profile["yamato_insurance_max_amount"],
        }

    return {
        "method_code": "ems",
        "fee_jpy": profile["ems_fee_500g"],
        "ems_zone": zone,
        "zone_label_ja": profile["label_ja"],
        "zone_label_en": profile["label_en"],
        "estimated_delivery_min_days": profile["ems_delivery_min_days"],
        "estimated_delivery_max_days": profile["ems_delivery_max_days"],
        "has_insurance": True,
        "insurance_max_amount": profile["ems_insurance_max_amount"],
        "insurance_detail_ja": "基本20,000円まで。追加料金で最大2,000,000円まで",
        "insurance_detail_en": "Basic up to ¥20,000; optional add-ons up to ¥2,000,000",
    }


def get_all_countries():
    return COUNTRIES
