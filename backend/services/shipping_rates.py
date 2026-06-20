import httpx
from bs4 import BeautifulSoup
import logging
import asyncio
from datetime import datetime
from sqlalchemy.orm import Session
import models
import re

logger = logging.getLogger(__name__)

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
        "has_insurance": True, # Limited to 3000 yen
        "is_individual_available": True, # Updated for individual use
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
        "is_individual_available": False, # Business only
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
        "is_individual_available": False, # Business only
        "max_size": "60cm total",
        "source_url": "https://www.kuronekoyamato.co.jp/ytc/customer/send/services/takkyubin/",
    },
    "takkyubin_80": {
        "carrier": "yamato",
        "name_ja": "宅急便 (80サイズ)",
        "name_en": "Takkyubin (Size 80)",
        "fee_jpy": 1150,
        "has_tracking": True,
        "has_insurance": True,
        "is_individual_available": False, # Business only
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
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 (KRX-TCG-Bot)"
}

async def fetch_page(url):
    async with httpx.AsyncClient(headers=HEADERS, timeout=15.0, follow_redirects=True) as client:
        for i in range(3): # 3 retries
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
    
    # 1. Yamato Compact
    compact_html = await fetch_page(FALLBACK_RATES["takkyubin_compact"]["source_url"])
    compact_fee = extract_fee(compact_html, r'([0-9,]+)円') # This is generic, might need refinement
    if not compact_fee or compact_fee < 400:
        logger.warning("Failed to fetch Yamato Compact fee, using existing or fallback.")
        compact_fee = None

    # 2. Click Post (Fixed to 200 JPY as per requirements)
    click_fee = 200

    # 3. Letter Pack
    lp_html = await fetch_page(FALLBACK_RATES["letter_pack_light"]["source_url"])
    lp_light = extract_fee(lp_html, r'レターパックライト[^\d]+(\d+)円')
    lp_plus = extract_fee(lp_html, r'レターパックプラス[^\d]+(\d+)円')
    if not lp_light: logger.warning("Failed to fetch Letter Pack Light fee")
    if not lp_plus: logger.warning("Failed to fetch Letter Pack Plus fee")

    # 4. Nekopos
    neko_html = await fetch_page(FALLBACK_RATES["nekopos"]["source_url"])
    neko_fee = extract_fee(neko_html, r'([0-9,]+)円')
    if not neko_fee or neko_fee > 500:
        logger.warning("Failed to fetch Nekopos fee")
        neko_fee = None

    # For Yu-pack and Takkyubin 60/80, they are regional. We use base (Kanto or similar) or fallback.
    # Usually the main page lists starting prices.
    
    updates = {
        "takkyubin_compact": compact_fee,
        "click_post": click_fee,
        "nekopos": neko_fee,
        "letter_pack_light": lp_light,
        "letter_pack_plus": lp_plus,
        "yu_pack_60": None, # Use fallback or previous
        "takkyubin_60": None,
        "takkyubin_80": None,
    }
    
    for code, fee in updates.items():
        db_rate = db.query(models.ShippingRate).filter(models.ShippingRate.method_code == code).first()
        if db_rate:
            if fee is not None:
                db_rate.fee_jpy = fee
            # Update other metadata if changed
            if code in FALLBACK_RATES:
                db_rate.carrier = FALLBACK_RATES[code].get("carrier")
                db_rate.name_ja = FALLBACK_RATES[code].get("name_ja")
                db_rate.name_en = FALLBACK_RATES[code].get("name_en")
                db_rate.is_individual_available = FALLBACK_RATES[code].get("is_individual_available", True)
            db_rate.updated_at = datetime.utcnow()
        else:
            # New entry: use fee if available, else FALLBACK_RATES
            final_fee = fee if fee is not None else FALLBACK_RATES[code]["fee_jpy"]
            rate_data = FALLBACK_RATES[code].copy()
            rate_data["fee_jpy"] = final_fee
            db_rate = models.ShippingRate(
                method_code=code,
                **rate_data
            )
            db.add(db_rate)
    
    try:
        db.commit()
        logger.info("Shipping rates refreshed successfully.")
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to commit shipping rates: {e}")

def calculate_shipping_fee(method_code: str, region: str = None, country: str = "Japan") -> int:
    """
    Calculate shipping fee based on method, region (prefecture) and country.
    
    If country is not Japan, it's considered international.
    If region is provided for Japan, it applies regional pricing for certain methods.
    """
    if country != "Japan" or method_code == "international":
        # International shipping zones (approximate)
        if not country or country == "Other":
            return 3000 # Default high fallback
        
        zones = {
            "Asia": ["China", "South Korea", "Taiwan", "Hong Kong", "Singapore", "Thailand"],
            "North America": ["United States", "Canada", "Mexico"],
            "Oceania": ["Australia", "New Zealand"],
            "Europe": ["United Kingdom", "France", "Germany", "Italy", "Spain"]
        }
        
        if any(c in zones["Asia"] for c in [country]): return 1400
        if any(c in zones["North America"] for c in [country]): return 2500
        if any(c in zones["Europe"] for c in [country]): return 2800
        if any(c in zones["Oceania"] for c in [country]): return 2500
        
        return 2000 # Base international

    # Japan Domestic
    base_rate = FALLBACK_RATES.get(method_code, {}).get("fee_jpy", 0)
    
    # Flat rate methods
    if method_code == "click_post":
        return 200 # National flat rate per requirements
    
    if method_code in ["nekopos", "letter_pack_light", "letter_pack_plus"]:
        return base_rate
    
    # Regional methods (Takkyubin, Yu-pack)
    if not region:
        return base_rate
        
    # Simplify prefectures into blocks and remove common suffixes for robust matching
    region_str = str(region).replace("都", "").replace("府", "").replace("県", "").replace(" ", "").strip()
    
    hokkaido = ["北海道"]
    okinawa = ["沖縄"]
    
    # Prefectures for regional pricing (other than Hokkaido/Okinawa)
    tohoku = ["青森", "岩手", "宮城", "秋田", "山形", "福島"]
    kanto = ["茨城", "栃木", "群馬", "埼玉", "千葉", "東京", "神奈川", "山梨"]
    shinetsu = ["新潟", "長野"]
    hokuriku = ["富山", "石川", "福井"]
    chubu = ["岐阜", "静岡", "愛知", "三重"]
    kansai = ["滋賀", "京都", "大阪", "兵庫", "奈良", "和歌山"]
    chugoku = ["鳥取", "島根", "岡山", "広島", "山口"]
    shikoku = ["徳島", "香川", "愛媛", "高知"]
    kyushu = ["福岡", "佐賀", "長崎", "熊本", "大分", "宮崎", "鹿児島"]

    def match_region(target_list):
        # Match if the region_str starts with any of the prefectures or vice versa
        return any(r in region_str or region_str in r for r in target_list)

    # Base is Kanto (approx 600 for compact, 940 for 60)
    if method_code == "takkyubin_compact":
        if match_region(hokkaido + okinawa): return 850
        return 600 # "その他は600円" per requirements
        
    if method_code in ["takkyubin_60", "yu_pack_60"]:
        if match_region(kanto + shinetsu + hokuriku + chubu + kansai): return 940
        if match_region(tohoku + chugoku + shikoku): return 1060
        if match_region(hokkaido + kyushu + okinawa): return 1460
        return 940

    if method_code == "takkyubin_80":
        if match_region(kanto + shinetsu + hokuriku + chubu + kansai): return 1150
        if match_region(tohoku + chugoku + shikoku): return 1280
        if match_region(hokkaido + kyushu + okinawa): return 1650
        return 1150

    return base_rate

async def background_shipping_update_task(db_factory):
    """Periodic update every 24 hours"""
    # Wait a bit after startup to not interfere with initialization
    await asyncio.sleep(60)
    while True:
        try:
            with db_factory() as db:
                await refresh_all_rates(db)
        except Exception as e:
            logger.error(f"Background shipping update error: {e}")
        
        await asyncio.sleep(86400) # 24 hours
