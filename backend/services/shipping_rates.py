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
        "name_ja": "宅急便コンパクト",
        "name_en": "Takkyubin Compact",
        "fee_jpy": 600,
        "has_tracking": True,
        "has_insurance": True,
        "max_size": "25cm x 20cm x 5cm",
        "source_url": "https://www.kuronekoyamato.co.jp/ytc/customer/send/services/compact/",
    },
    "click_post": {
        "name_ja": "クリックポスト",
        "name_en": "Click Post",
        "fee_jpy": 185,
        "has_tracking": True,
        "has_insurance": False,
        "max_size": "34cm x 25cm x 3cm",
        "source_url": "https://www.post.japanpost.jp/service/click_post/",
    },
    "nekopos": {
        "name_ja": "ネコポス",
        "name_en": "Nekopos",
        "fee_jpy": 385,
        "has_tracking": True,
        "has_insurance": True, # Limited to 3000 yen
        "max_size": "31.2cm x 22.8cm x 3cm",
        "source_url": "https://www.kuronekoyamato.co.jp/ytc/customer/send/services/nekopos/",
    },
    "letter_pack_light": {
        "name_ja": "レターパックライト",
        "name_en": "Letter Pack Light",
        "fee_jpy": 430,
        "has_tracking": True,
        "has_insurance": False,
        "max_size": "34cm x 24.8cm x 3cm",
        "source_url": "https://www.post.japanpost.jp/service/letterpack/",
    },
    "letter_pack_plus": {
        "name_ja": "レターパックプラス",
        "name_en": "Letter Pack Plus",
        "fee_jpy": 600,
        "has_tracking": True,
        "has_insurance": False,
        "max_size": "34cm x 24.8cm",
        "source_url": "https://www.post.japanpost.jp/service/letterpack/",
    },
    "yu_pack_60": {
        "name_ja": "ゆうパック (60サイズ)",
        "name_en": "Yu-Pack (Size 60)",
        "fee_jpy": 970,
        "has_tracking": True,
        "has_insurance": True,
        "max_size": "60cm total",
        "source_url": "https://www.post.japanpost.jp/service/you_pack/",
    },
    "takkyubin_60": {
        "name_ja": "宅急便 (60サイズ)",
        "name_en": "Takkyubin (Size 60)",
        "fee_jpy": 940,
        "has_tracking": True,
        "has_insurance": True,
        "max_size": "60cm total",
        "source_url": "https://www.kuronekoyamato.co.jp/ytc/customer/send/services/takkyubin/",
    },
    "takkyubin_80": {
        "name_ja": "宅急便 (80サイズ)",
        "name_en": "Takkyubin (Size 80)",
        "fee_jpy": 1150,
        "has_tracking": True,
        "has_insurance": True,
        "max_size": "80cm total",
        "source_url": "https://www.kuronekoyamato.co.jp/ytc/customer/send/services/takkyubin/",
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

    # 2. Click Post
    click_html = await fetch_page(FALLBACK_RATES["click_post"]["source_url"])
    click_fee = extract_fee(click_html, r'一律\s*([0-9,]+)円')
    if not click_fee:
        logger.warning("Failed to fetch Click Post fee, using existing or fallback.")
        click_fee = None

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
                db_rate.updated_at = datetime.utcnow()
            # If fee is None, we maintain the previous value in db_rate.fee_jpy
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
