import httpx
from bs4 import BeautifulSoup
import logging
import asyncio
import json
from datetime import datetime
from sqlalchemy.orm import Session
import models
import re

logger = logging.getLogger(__name__)

# Prefectures by Yamato zones (from Kanto/Tokyo shop origin)
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

# Standard rates from Kanto (approx 2025/2026 cash price)
# Note: Compact is set to 600 base as per user requirement
REGIONAL_RATES_MASTER = {
    "takkyubin_compact": {
        "hokkaido": 850, "kita_tohoku": 710, "minami_tohoku": 650, "kanto": 600, 
        "shinetsu": 650, "hokuriku": 650, "chubu": 650, "kansai": 710, 
        "chugoku": 770, "shikoku": 770, "kyushu": 880, "okinawa": 850
    },
    "takkyubin_60": {
        "hokkaido": 1460, "kita_tohoku": 1060, "minami_tohoku": 940, "kanto": 940,
        "shinetsu": 940, "hokuriku": 940, "chubu": 940, "kansai": 1060,
        "chugoku": 1190, "shikoku": 1190, "kyushu": 1460, "okinawa": 1460
    },
    "takkyubin_80": {
        "hokkaido": 1750, "kita_tohoku": 1350, "minami_tohoku": 1230, "kanto": 1230,
        "shinetsu": 1230, "hokuriku": 1230, "chubu": 1230, "kansai": 1350,
        "chugoku": 1480, "shikoku": 1480, "kyushu": 1750, "okinawa": 2010
    }
}

# Fallback values (2024 pricing)
FALLBACK_RATES = {
    "takkyubin_compact": {
        "carrier": "yamato",
        "name_ja": "ヤマト運輸コンパクト",
        "name_en": "Takkyubin Compact",
        "fee_jpy": 600,
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
    "nekopos": {
        "carrier": "yamato",
        "name_ja": "ネコポス",
        "name_en": "Nekopos",
        "fee_jpy": 385,
        "has_tracking": True,
        "has_insurance": True,
        "is_individual_available": True,
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
        "name_ja": "国際郵便 / 国際配送",
        "name_en": "International Shipping",
        "fee_jpy": 2000,
        "has_tracking": True,
        "has_insurance": True,
        "is_individual_available": True,
        "max_size": "Variable",
        "source_url": "https://www.post.japanpost.jp/int/index.html",
    }
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
    if not compact_fee or compact_fee < 400:
        compact_fee = 600 # Force base 600 per requirements

    # 2. Click Post (Fixed to 200 JPY as per requirements)
    click_fee = 200

    # 3. Letter Pack
    lp_html = await fetch_page(FALLBACK_RATES["letter_pack_light"]["source_url"])
    lp_light = extract_fee(lp_html, r'レターパックライト[^\d]+(\d+)円')
    lp_plus = extract_fee(lp_html, r'レターパックプラス[^\d]+(\d+)円')

    # 4. Nekopos
    neko_html = await fetch_page(FALLBACK_RATES["nekopos"]["source_url"])
    neko_fee = extract_fee(neko_html, r'([0-9,]+)円')

    updates = {
        "takkyubin_compact": compact_fee,
        "click_post": click_fee,
        "nekopos": neko_fee,
        "letter_pack_light": lp_light,
        "letter_pack_plus": lp_plus,
        "takkyubin_60": 940,
        "takkyubin_80": 1230,
    }
    
    for code, fee in updates.items():
        db_rate = db.query(models.ShippingRate).filter(models.ShippingRate.method_code == code).first()
        reg_rates = generate_prefecture_rates(code)
        reg_rates_json = json.dumps(reg_rates, ensure_ascii=False) if reg_rates else None

        if db_rate:
            if fee is not None:
                db_rate.fee_jpy = fee
            db_rate.regional_rates = reg_rates_json
            if code in FALLBACK_RATES:
                db_rate.carrier = FALLBACK_RATES[code].get("carrier")
                db_rate.name_ja = FALLBACK_RATES[code].get("name_ja")
                db_rate.name_en = FALLBACK_RATES[code].get("name_en")
                db_rate.is_individual_available = FALLBACK_RATES[code].get("is_individual_available", True)
            db_rate.updated_at = datetime.utcnow()
        else:
            final_fee = fee if fee is not None else FALLBACK_RATES[code]["fee_jpy"]
            rate_data = FALLBACK_RATES[code].copy()
            rate_data["fee_jpy"] = final_fee
            db_rate = models.ShippingRate(
                method_code=code,
                regional_rates=reg_rates_json,
                **rate_data
            )
            db.add(db_rate)
    
    try:
        db.commit()
        logger.info("Shipping rates refreshed successfully.")
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to commit shipping rates: {e}")

def calculate_shipping_fee(method_code: str, region: str = None, country: str = "Japan", db: Session = None) -> int:
    """
    Calculate shipping fee based on method, region (prefecture) and country.
    """
    if country != "Japan" or method_code == "international":
        if not country or country == "Other":
            return 3000
        zones = {
            "Asia": ["China", "South Korea", "Taiwan", "Hong Kong", "Singapore", "Thailand"],
            "North America": ["United States", "Canada", "Mexico"],
            "Oceania": ["Australia", "New Zealand"],
            "Europe": ["United Kingdom", "France", "Germany", "Italy", "Spain"]
        }
        if any(c == country for c in zones["Asia"]): return 1400
        if any(c == country for c in zones["North America"]): return 2500
        if any(c == country for c in zones["Europe"]): return 2800
        if any(c == country for c in zones["Oceania"]): return 2500
        return 2000

    # Japan Domestic
    # Try to get from DB first if Session is provided
    if db and region:
        db_rate = db.query(models.ShippingRate).filter(models.ShippingRate.method_code == method_code).first()
        if db_rate and db_rate.regional_rates:
            try:
                rates_map = json.loads(db_rate.regional_rates)
                # Robust match (remove 都府県)
                clean_region = region.replace("都", "").replace("府", "").replace("県", "").strip()
                for pref, fee in rates_map.items():
                    if clean_region in pref:
                        return fee
            except Exception as e:
                logger.error(f"Error parsing regional_rates for {method_code}: {e}")

    # Fallback logic
    base_rate = FALLBACK_RATES.get(method_code, {}).get("fee_jpy", 0)
    
    if method_code == "click_post": return 200
    if method_code in ["nekopos", "letter_pack_light", "letter_pack_plus"]: return base_rate
    if not region: return base_rate
        
    region_str = str(region).replace("都", "").replace("府", "").replace("県", "").replace(" ", "").strip()
    
    def match_region(target_list):
        return any(r.replace("都", "").replace("府", "").replace("県", "") in region_str for r in target_list)

    if method_code == "takkyubin_compact":
        if match_region(YAMATO_ZONES["hokkaido"] + YAMATO_ZONES["okinawa"]): return 850
        if match_region(YAMATO_ZONES["kyushu"]): return 880
        if match_region(YAMATO_ZONES["chugoku"] + YAMATO_ZONES["shikoku"]): return 770
        if match_region(YAMATO_ZONES["kansai"] + YAMATO_ZONES["kita_tohoku"]): return 710
        return 600
        
    if method_code in ["takkyubin_60", "yu_pack_60"]:
        if match_region(YAMATO_ZONES["hokkaido"] + YAMATO_ZONES["kyushu"] + YAMATO_ZONES["okinawa"]): return 1460
        if match_region(YAMATO_ZONES["chugoku"] + YAMATO_ZONES["shikoku"]): return 1190
        if match_region(YAMATO_ZONES["kansai"] + YAMATO_ZONES["kita_tohoku"]): return 1060
        return 940

    if method_code == "takkyubin_80":
        if match_region(YAMATO_ZONES["okinawa"]): return 2010
        if match_region(YAMATO_ZONES["hokkaido"] + YAMATO_ZONES["kyushu"]): return 1750
        if match_region(YAMATO_ZONES["chugoku"] + YAMATO_ZONES["shikoku"]): return 1480
        if match_region(YAMATO_ZONES["kansai"] + YAMATO_ZONES["kita_tohoku"]): return 1350
        return 1230

    return base_rate

async def background_shipping_update_task(db_factory):
    await asyncio.sleep(10) # Reduced wait for testing/first run
    while True:
        try:
            with db_factory() as db:
                await refresh_all_rates(db)
        except Exception as e:
            logger.error(f"Background shipping update error: {e}")
        await asyncio.sleep(86400)
