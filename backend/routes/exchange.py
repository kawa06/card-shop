from fastapi import APIRouter
import httpx
from datetime import datetime, timedelta
import time
from config import settings
from schemas import ExchangeRateResponse

# Exchange rate router (Updated 2026-06-20)
router = APIRouter(prefix="/api", tags=["exchange"])

# In-memory cache
_cache = {
    "rate": None,
    "last_fetched": None
}

CACHE_DURATION_MINUTES = 40

@router.get("/exchange-rate", response_model=ExchangeRateResponse)
async def get_exchange_rate():
    global _cache
    
    now = datetime.now()
    
    # Check cache
    if _cache["rate"] and _cache["last_fetched"]:
        if now < _cache["last_fetched"] + timedelta(minutes=CACHE_DURATION_MINUTES):
            return ExchangeRateResponse(
                rate=_cache["rate"],
                last_updated=int(_cache["last_fetched"].timestamp())
            )
            
    # Fetch from API
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get("https://api.exchangerate-api.com/v4/latest/USD", timeout=5.0)
            response.raise_for_status()
            data = response.json()
            rate = data.get("rates", {}).get("JPY")
            
            if rate:
                _cache["rate"] = float(rate)
                _cache["last_fetched"] = now
                return ExchangeRateResponse(
                    rate=_cache["rate"],
                    last_updated=int(_cache["last_fetched"].timestamp())
                )
    except Exception as e:
        # Log error in real application, here we just print
        print(f"Error fetching exchange rate: {e}")
        
    # Fallback to setting value or cache if available
    fallback_rate = settings.EXCHANGE_RATE_USD_JPY
    
    return ExchangeRateResponse(
        rate=_cache["rate"] if _cache["rate"] else fallback_rate,
        last_updated=int(_cache["last_fetched"].timestamp()) if _cache["last_fetched"] else int(time.time())
    )
