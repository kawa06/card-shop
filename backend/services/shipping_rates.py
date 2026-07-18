import httpx
from bs4 import BeautifulSoup
import logging
import asyncio
import json
from datetime import datetime
from sqlalchemy.orm import Session
import models
import re
from services.countries import (
    EMS_ZONE_FEES_500G,
    INTERNATIONAL_METHOD_CODES,
    YAMATO_GLOBAL_ZONE_FEES_500G,
    get_international_shipping_quote,
    is_domestic_japan,
)

logger = logging.getLogger(__name__)

# Shipped from Hyogo prefecture (兵庫県)
SHIPPING_ORIGIN_PREFECTURE = "兵庫県"

# Prefectures by Yamato zones (from Hyogo / Kansai shop origin)
YAMATO_ZONES = {
    "hokkaido": ["北海道"],
    "kita_tohoku": ["青森県", "岩手県", "秋田県"],
    "minami_tohoku": ["宮城県", "山形県", "福島県"],
    "kanto": ["茨城県", "栃木県", "群馬県", "埼玉県", "千葉県", "東京都", "神奈川県", "山梨県"],
    "shinetsu": ["新潟県", "長野県"],
    "hokuriku": ["富山県", "石川県", "福井県"],
    "chubu": ["岐阜県", "静岡県", "愛知県", "三重県"],
    "kansai": ["滋賀県", "京都府", "大阪府", "兵庫県", "奈良県", "和歌山県"],
    "chugoku": ["鳥取県", "島根県", "岡山県", "広島県", "山口県"],
    "shikoku": ["徳島県", "香川県", "愛媛県", "高知県"],
    "kyushu": ["福岡県", "佐賀県", "長崎県", "熊本県", "大分県", "宮崎県", "鹿児島県"],
    "okinawa": ["沖縄県"]
}

# Regional rates from Hyogo (兵庫県 / 関西発) — Yamato Oct 2025 cash table
# https://www.yamato-hd.co.jp/important/pdf/info_250501_1.pdf
REGIONAL_RATES_MASTER = {
    "takkyubin_compact": {
        "hokkaido": 1040,
        "kita_tohoku": 820,
        "minami_tohoku": 760,
        "kanto": 710,
        "shinetsu": 710,
        "hokuriku": 650,
        "chubu": 650,
        "kansai": 650,
        "chugoku": 650,
        "shikoku": 650,
        "kyushu": 710,
        "okinawa": 870,
    },
    "takkyubin_60": {
        "hokkaido": 1920,
        "kita_tohoku": 1320,
        "minami_tohoku": 1190,
        "kanto": 1060,
        "shinetsu": 1060,
        "hokuriku": 940,
        "chubu": 940,
        "kansai": 940,
        "chugoku": 940,
        "shikoku": 940,
        "kyushu": 1060,
        "okinawa": 1460,
    },
    "takkyubin_80": {
        "hokkaido": 2200,
        "kita_tohoku": 1610,
        "minami_tohoku": 1480,
        "kanto": 1350,
        "shinetsu": 1350,
        "hokuriku": 1230,
        "chubu": 1230,
        "kansai": 1230,
        "chugoku": 1230,
        "shikoku": 1230,
        "kyushu": 1350,
        "okinawa": 2070,
    },
}

EMS_ZONE_RATES_JSON = json.dumps({str(k): v for k, v in EMS_ZONE_FEES_500G.items()})
YAMATO_GLOBAL_ZONE_RATES_JSON = json.dumps({str(k): v for k, v in YAMATO_GLOBAL_ZONE_FEES_500G.items()})

# Fallback values (2024 pricing)
FALLBACK_RATES = {
    "takkyubin_compact": {
        "carrier": "yamato",
        "name_ja": "ヤマト運輸コンパクト",
        "name_en": "Takkyubin Compact",
        "fee_jpy": 650,
        "has_tracking": True,
        "has_insurance": True,
        "is_individual_available": True,
        "max_size": "25cm x 20cm x 5cm",
        "source_url": "https://www.kuronekoyamato.co.jp/ytc/customer/send/services/compact/",
    },
    "click_post": {
        "carrier": "japan_post",
        "name_ja": "クリックポスト",
        "name_en": "Click Post",
        "fee_jpy": 200,
        "has_tracking": True,
        "has_insurance": False,
        "is_individual_available": True,
        "max_size": "34cm x 25cm x 3cm",
        "source_url": "https://www.post.japanpost.jp/service/click_post/",
    },
    "teikei_post": {
        "carrier": "japan_post",
        "name_ja": "定形郵便",
        "name_en": "Standard Letter Post",
        "fee_jpy": 110,
        "has_tracking": False,
        "has_insurance": False,
        "is_individual_available": True,
        "max_size": "14cm x 9cm x 1cm (50g以内)",
        "source_url": "https://www.post.japanpost.jp/service/standard/",
    },
    "nekopos": {
        "carrier": "yamato",
        "name_ja": "ネコポス",
        "name_en": "Nekopos",
        "fee_jpy": 385,
        "has_tracking": True,
        "has_insurance": True,
        "is_individual_available": False,
        "max_size": "31.2cm x 22.8cm x 3cm",
        "source_url": "https://www.kuronekoyamato.co.jp/ytc/customer/send/services/nekopos/",
    },
    "letter_pack_light": {
        "carrier": "japan_post",
        "name_ja": "レターパックライト",
        "name_en": "Letter Pack Light",
        "fee_jpy": 430,
        "has_tracking": True,
        "has_insurance": False,
        "is_individual_available": True,
        "max_size": "34cm x 24.8cm x 3cm",
        "source_url": "https://www.post.japanpost.jp/service/letterpack/",
    },
    "letter_pack_plus": {
        "carrier": "japan_post",
        "name_ja": "レターパックプラス",
        "name_en": "Letter Pack Plus",
        "fee_jpy": 600,
        "has_tracking": True,
        "has_insurance": False,
        "is_individual_available": True,
        "max_size": "34cm x 24.8cm",
        "source_url": "https://www.post.japanpost.jp/service/letterpack/",
    },
    "yu_pack_60": {
        "carrier": "japan_post",
        "name_ja": "ゆうパック (60サイズ)",
        "name_en": "Yu-Pack (Size 60)",
        "fee_jpy": 970,
        "has_tracking": True,
        "has_insurance": True,
        "is_individual_available": False,
        "max_size": "60cm total",
        "source_url": "https://www.post.japanpost.jp/service/you_pack/",
    },
    "takkyubin_60": {
        "carrier": "yamato",
        "name_ja": "宅急便 (60サイズ)",
        "name_en": "Takkyubin (Size 60)",
        "fee_jpy": 940,
        "has_tracking": True,
        "has_insurance": True,
        "is_individual_available": True,
        "max_size": "60cm total",
        "source_url": "https://www.kuronekoyamato.co.jp/ytc/customer/send/services/takkyubin/",
    },
    "takkyubin_80": {
        "carrier": "yamato",
        "name_ja": "宅急便 (80サイズ)",
        "name_en": "Takkyubin (Size 80)",
        "fee_jpy": 1230,
        "has_tracking": True,
        "has_insurance": True,
        "is_individual_available": True,
        "max_size": "80cm total",
        "source_url": "https://www.kuronekoyamato.co.jp/ytc/customer/send/services/takkyubin/",
    },
    "international": {
        "carrier": "japan_post",
        "name_ja": "EMS（国際スピード郵便）",
        "name_en": "EMS (International Express)",
        "fee_jpy": 1450,
        "has_tracking": True,
        "has_insurance": True,
        "is_individual_available": True,
        "is_international_available": True,
        "international_zones": EMS_ZONE_RATES_JSON,
        "insurance_max_amount": 20000,
        "insurance_url": "https://www.post.japanpost.jp/int/service/ems_all.html",
        "estimated_delivery_min_days": 3,
        "estimated_delivery_max_days": 14,
        "max_size": "500gまで（標準）",
        "source_url": "https://www.post.japanpost.jp/send/oversea/charge/list-ems/all.html",
    },
    "ems": {
        "carrier": "japan_post",
        "name_ja": "EMS（国際スピード郵便）",
        "name_en": "EMS (International Express)",
        "fee_jpy": 1450,
        "has_tracking": True,
        "has_insurance": True,
        "is_individual_available": True,
        "is_international_available": True,
        "international_zones": EMS_ZONE_RATES_JSON,
        "insurance_max_amount": 20000,
        "insurance_url": "https://www.post.japanpost.jp/int/service/ems_all.html",
        "estimated_delivery_min_days": 3,
        "estimated_delivery_max_days": 14,
        "max_size": "500gまで（標準）",
        "source_url": "https://www.post.japanpost.jp/send/oversea/charge/list-ems/all.html",
    },
    "yamato_global": {
        "carrier": "yamato",
        "name_ja": "ヤマト国際宅急便",
        "name_en": "Yamato Global TA-Q-BIN",
        "fee_jpy": 1700,
        "has_tracking": True,
        "has_insurance": True,
        "is_individual_available": True,
        "is_international_available": True,
        "international_zones": YAMATO_GLOBAL_ZONE_RATES_JSON,
        "insurance_max_amount": 20000,
        "insurance_url": "https://www.kuronekoyamato.co.jp/ytc/customer/send/services/international/",
        "estimated_delivery_min_days": 4,
        "estimated_delivery_max_days": 16,
        "max_size": "500gまで（標準）",
        "source_url": "https://www.kuronekoyamato.co.jp/ytc/customer/send/services/international/",
    },
}

# Default values for existing methods
METHOD_DEFAULTS = {
    "takkyubin_compact": {
        "is_recommended": True,
        "insurance_max_amount": 30000,
        "insurance_url": "https://www.kuronekoyamato.co.jp/ytc/customer/send/services/compact/",
        "estimated_delivery_min_days": 1,
        "estimated_delivery_max_days": 3,
    },
    "click_post": {
        "insurance_max_amount": 0,
        "insurance_url": "https://www.post.japanpost.jp/service/click_post/",
        "estimated_delivery_min_days": 2,
        "estimated_delivery_max_days": 5,
    },
    "teikei_post": {
        "insurance_max_amount": 0,
        "insurance_url": "https://www.post.japanpost.jp/service/standard/",
        "estimated_delivery_min_days": 2,
        "estimated_delivery_max_days": 4,
    },
    "ems": {
        "is_recommended": True,
        "estimated_delivery_min_days": 3,
        "estimated_delivery_max_days": 14,
    },
    "yamato_global": {
        "estimated_delivery_min_days": 4,
        "estimated_delivery_max_days": 16,
    },
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

def generate_prefecture_rates(method_code):
    """Generate a map of all 47 prefectures to their respective fees for a method"""
    if method_code not in REGIONAL_RATES_MASTER:
        return None

    rates = {}
    master = REGIONAL_RATES_MASTER[method_code]
    for zone, prefectures in YAMATO_ZONES.items():
        fee = master.get(zone)
        if fee:
            for pref in prefectures:
                rates[pref] = fee
    return rates


def _prefecture_to_zone(region: str | None) -> str | None:
    if not region:
        return None
    region_str = str(region).replace("都", "").replace("府", "").replace("県", "").replace(" ", "").strip()
    for zone, prefectures in YAMATO_ZONES.items():
        for pref in prefectures:
            clean_pref = pref.replace("都", "").replace("府", "").replace("県", "")
            if region_str == clean_pref or region_str in clean_pref or clean_pref in region_str:
                return zone
    return None


def _domestic_regional_fee(method_code: str, region: str | None) -> int | None:
    if method_code not in REGIONAL_RATES_MASTER:
        return None
    zone = _prefecture_to_zone(region)
    if not zone:
        return None
    return REGIONAL_RATES_MASTER[method_code].get(zone)

async def fetch_page(url):
    async with httpx.AsyncClient(headers=HEADERS, timeout=15.0, follow_redirects=True) as client:
        for i in range(2):
            try:
                resp = await client.get(url)
                resp.raise_for_status()
                return resp.text
            except Exception as e:
                logger.warning(f"Retry {i+1} for {url} failed: {e}")
                await asyncio.sleep(2)
    return None

def extract_fee(html, regex):
    if not html:
        return None
    soup = BeautifulSoup(html, 'html.parser')
    text = soup.get_text()
    match = re.search(regex, text)
    if match:
        return int(match.group(1).replace(',', ''))
    return None

async def refresh_all_rates(db: Session):
    logger.info("Starting shipping rates refresh from official pages...")
    
    # 1. Yamato Compact (Kanto base)
    compact_html = await fetch_page(FALLBACK_RATES["takkyubin_compact"]["source_url"])
    compact_fee = extract_fee(compact_html, r'([0-9,]+)円')
    if not compact_fee or compact_fee < 650:
        compact_fee = 650  # Kansai local base (Yamato Oct 2025)

    # 2. Click Post (Fixed to 200 JPY as per requirements)
    click_fee = 200

    # 3. Letter Pack
    lp_html = await fetch_page(FALLBACK_RATES["letter_pack_light"]["source_url"])
    lp_light = extract_fee(lp_html, r'レターパックライト[^\d]+(\d+)円')
    lp_plus = extract_fee(lp_html, r'レターパックプラス[^\d]+(\d+)円')

    updates = {
        "takkyubin_compact": compact_fee,
        "click_post": click_fee,
        "teikei_post": 110,
        "letter_pack_light": lp_light,
        "letter_pack_plus": lp_plus,
        "takkyubin_60": 940,
        "takkyubin_80": 1230,
    }
    
    for code, fee in updates.items():
        db_rate = db.query(models.ShippingRate).filter(models.ShippingRate.method_code == code).first()
        reg_rates = generate_prefecture_rates(code)
        reg_rates_json = json.dumps(reg_rates, ensure_ascii=False) if reg_rates else None

        defaults = METHOD_DEFAULTS.get(code, {})

        if db_rate:
            if fee is not None:
                db_rate.fee_jpy = fee
            db_rate.regional_rates = reg_rates_json
            if code in FALLBACK_RATES:
                db_rate.carrier = FALLBACK_RATES[code].get("carrier")
                db_rate.name_ja = FALLBACK_RATES[code].get("name_ja")
                db_rate.name_en = FALLBACK_RATES[code].get("name_en")
                db_rate.is_individual_available = FALLBACK_RATES[code].get("is_individual_available", True)
                
                # Apply new fields if they are None (initial migration)
                if db_rate.is_recommended is None: db_rate.is_recommended = defaults.get("is_recommended", False)
                if db_rate.insurance_max_amount is None: db_rate.insurance_max_amount = defaults.get("insurance_max_amount")
                if db_rate.insurance_url is None: db_rate.insurance_url = defaults.get("insurance_url")
                if db_rate.estimated_delivery_min_days is None: db_rate.estimated_delivery_min_days = defaults.get("estimated_delivery_min_days")
                if db_rate.estimated_delivery_max_days is None: db_rate.estimated_delivery_max_days = defaults.get("estimated_delivery_max_days")
                
            db_rate.updated_at = datetime.utcnow()
        else:
            final_fee = fee if fee is not None else FALLBACK_RATES[code]["fee_jpy"]
            rate_data = FALLBACK_RATES[code].copy()
            rate_data["fee_jpy"] = final_fee
            # Merge with defaults
            for k, v in defaults.items():
                if k not in rate_data:
                    rate_data[k] = v
            
            db_rate = models.ShippingRate(
                method_code=code,
                regional_rates=reg_rates_json,
                **rate_data
            )
            db.add(db_rate)
    
    # Disable Nekopos for individual sellers
    neko_rate = db.query(models.ShippingRate).filter(models.ShippingRate.method_code == "nekopos").first()
    if neko_rate:
        neko_rate.is_individual_available = False
        neko_rate.updated_at = datetime.utcnow()

    # International methods (EMS + Yamato global)
    for intl_code in ("international", "ems", "yamato_global"):
        if intl_code not in FALLBACK_RATES:
            continue
        db_intl = db.query(models.ShippingRate).filter(models.ShippingRate.method_code == intl_code).first()
        rate_data = FALLBACK_RATES[intl_code].copy()
        defaults = METHOD_DEFAULTS.get(intl_code, {})
        for key, value in defaults.items():
            if key not in rate_data:
                rate_data[key] = value
        if not db_intl:
            db_intl = models.ShippingRate(method_code=intl_code, **rate_data)
            db.add(db_intl)
        else:
            db_intl.name_ja = rate_data.get("name_ja", db_intl.name_ja)
            db_intl.name_en = rate_data.get("name_en", db_intl.name_en)
            db_intl.carrier = rate_data.get("carrier", db_intl.carrier)
            db_intl.is_international_available = True
            db_intl.is_individual_available = rate_data.get("is_individual_available", True)
            db_intl.international_zones = rate_data.get("international_zones", db_intl.international_zones)
            db_intl.insurance_max_amount = rate_data.get("insurance_max_amount", db_intl.insurance_max_amount)
            db_intl.insurance_url = rate_data.get("insurance_url", db_intl.insurance_url)
            db_intl.estimated_delivery_min_days = rate_data.get(
                "estimated_delivery_min_days", db_intl.estimated_delivery_min_days
            )
            db_intl.estimated_delivery_max_days = rate_data.get(
                "estimated_delivery_max_days", db_intl.estimated_delivery_max_days
            )
            db_intl.source_url = rate_data.get("source_url", db_intl.source_url)
            db_intl.updated_at = datetime.utcnow()
    
    try:
        db.commit()
        logger.info("Shipping rates refreshed successfully.")
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to commit shipping rates: {e}")

def _international_fee(method_code: str, country: str, db: Session | None) -> int:
    quote = get_international_shipping_quote(method_code, country)
    return int(quote["fee_jpy"])


def calculate_shipping_quote(
    method_code: str,
    region: str | None = None,
    country: str = "Japan",
    db: Session | None = None,
) -> dict:
    """Full shipping quote including fee, delivery estimate, and insurance."""
    fee = calculate_shipping_fee(method_code, region, country, db=db)

    if not is_domestic_japan(country) and method_code in INTERNATIONAL_METHOD_CODES:
        quote = get_international_shipping_quote(method_code, country)
        quote["fee_jpy"] = fee
        return quote

    db_rate = None
    if db:
        db_rate = db.query(models.ShippingRate).filter(models.ShippingRate.method_code == method_code).first()

    return {
        "method_code": method_code,
        "fee_jpy": fee,
        "ems_zone": None,
        "zone_label_ja": None,
        "zone_label_en": None,
        "estimated_delivery_min_days": db_rate.estimated_delivery_min_days if db_rate else None,
        "estimated_delivery_max_days": db_rate.estimated_delivery_max_days if db_rate else None,
        "has_insurance": db_rate.has_insurance if db_rate else FALLBACK_RATES.get(method_code, {}).get("has_insurance", False),
        "insurance_max_amount": db_rate.insurance_max_amount if db_rate else FALLBACK_RATES.get(method_code, {}).get("insurance_max_amount"),
    }


def calculate_shipping_fee(method_code: str, region: str = None, country: str = "Japan", db: Session = None) -> int:
    """
    Calculate shipping fee based on method, region (prefecture) and country.
    Domestic rates are from Hyogo prefecture (兵庫県).
    International EMS/Yamato rates use Japan Post EMS zones (500g tier).
    """
    if is_domestic_japan(country):
        if method_code in INTERNATIONAL_METHOD_CODES:
            return 0

        # Japan Domestic — official 関西発 zone table takes precedence over DB cache
        regional = _domestic_regional_fee(method_code, region)
        if regional is not None:
            return regional

        if db and region:
            db_rate = db.query(models.ShippingRate).filter(models.ShippingRate.method_code == method_code).first()
            if db_rate and db_rate.regional_rates:
                try:
                    rates_map = json.loads(db_rate.regional_rates)
                    clean_region = region.replace("都", "").replace("府", "").replace("県", "").strip()
                    for pref, fee in rates_map.items():
                        if clean_region in pref.replace("都", "").replace("府", "").replace("県", ""):
                            return fee
                except Exception as e:
                    logger.error(f"Error parsing regional_rates for {method_code}: {e}")

        base_rate = FALLBACK_RATES.get(method_code, {}).get("fee_jpy", 0)

        if method_code == "click_post":
            return 200
        if method_code in ["teikei_post"]:
            return 110
        if method_code in ["letter_pack_light", "letter_pack_plus"]:
            return base_rate

        return base_rate

    if method_code in INTERNATIONAL_METHOD_CODES:
        resolved = "ems" if method_code == "international" else method_code
        return _international_fee(resolved, country, db)

    return _international_fee("ems", country, db)

async def background_shipping_update_task(db_factory):
    await asyncio.sleep(10) # Reduced wait for testing/first run
    while True:
        try:
            with db_factory() as db:
                await refresh_all_rates(db)
        except Exception as e:
            logger.error(f"Background shipping update error: {e}")
        await asyncio.sleep(86400)
