COUNTRIES = [
    {"code": "JP", "name_ja": "日本", "name_en": "Japan", "zone": "Domestic"},
    {"code": "US", "name_ja": "アメリカ合衆国", "name_en": "United States", "zone": "North America"},
    {"code": "CN", "name_ja": "中国", "name_en": "China", "zone": "Asia"},
    {"code": "KR", "name_ja": "韓国", "name_en": "South Korea", "zone": "Asia"},
    {"code": "TW", "name_ja": "台湾", "name_en": "Taiwan", "zone": "Asia"},
    {"code": "HK", "name_ja": "香港", "name_en": "Hong Kong", "zone": "Asia"},
    {"code": "SG", "name_ja": "シンガポール", "name_en": "Singapore", "zone": "Asia"},
    {"code": "TH", "name_ja": "タイ", "name_en": "Thailand", "zone": "Asia"},
    {"code": "GB", "name_ja": "イギリス", "name_en": "United Kingdom", "zone": "Europe"},
    {"code": "FR", "name_ja": "フランス", "name_en": "France", "zone": "Europe"},
    {"code": "DE", "name_ja": "ドイツ", "name_en": "Germany", "zone": "Europe"},
    {"code": "IT", "name_ja": "イタリア", "name_en": "Italy", "zone": "Europe"},
    {"code": "ES", "name_ja": "スペイン", "name_en": "Spain", "zone": "Europe"},
    {"code": "CA", "name_ja": "カナダ", "name_en": "Canada", "zone": "North America"},
    {"code": "AU", "name_ja": "オーストラリア", "name_en": "Australia", "zone": "Oceania"},
    {"code": "NZ", "name_ja": "ニュージーランド", "name_en": "New Zealand", "zone": "Oceania"},
    # Add more as needed or use a standard library if allowed, but here we use a constant list for credits/performance
]

def get_country_zone(country_code_or_name: str) -> str:
    for c in COUNTRIES:
        if c["code"] == country_code_or_name or c["name_en"] == country_code_or_name or c["name_ja"] == country_code_or_name:
            return c["zone"]
    return "Other"

def get_all_countries():
    return COUNTRIES
