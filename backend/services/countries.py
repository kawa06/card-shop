"""Country metadata for international shipping (EMS zones per Japan Post)."""

from __future__ import annotations

# EMS 500g tier (Japan Post zone table)
# https://www.post.japanpost.jp/send/oversea/charge/list-ems/all.html
EMS_ZONE_FEES_500G = {
    1: 1450,  # China, Korea, Taiwan
    2: 1900,  # Asia (excluding CN/KR/TW)
    3: 3150,  # Oceania, Canada, Mexico, Middle East, Europe
    4: 3900,  # United States
    5: 3600,  # Central/South America (excl. Mexico), Africa
}

# Yamato 国際宅急便 approx. 500g reference (individual sender)
YAMATO_GLOBAL_ZONE_FEES_500G = {
    1: 1700,
    2: 2200,
    3: 3600,
    4: 4500,
    5: 4100,
}

DOMESTIC_COUNTRY_VALUES = frozenset({"JP", "Japan", "日本", "japan", "jp"})

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


def get_ems_fee_500g(country: str | None) -> int:
    zone = get_country_ems_zone(country)
    return EMS_ZONE_FEES_500G.get(zone, EMS_ZONE_FEES_500G[3])


def get_yamato_global_fee_500g(country: str | None) -> int:
    zone = get_country_ems_zone(country)
    return YAMATO_GLOBAL_ZONE_FEES_500G.get(zone, YAMATO_GLOBAL_ZONE_FEES_500G[3])


def get_all_countries():
    return COUNTRIES
