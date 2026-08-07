"""In-memory rate limiting for live auction bids."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from threading import Lock
from typing import Dict, Tuple

_BUCKETS: Dict[str, Tuple[int, datetime]] = {}
_LOCK = Lock()

LIMITS = {
    "live_bid": (30, timedelta(minutes=1)),
}


@dataclass
class RateLimitResult:
    allowed: bool
    retry_after_seconds: int = 0
    reason: str | None = None


def check_live_bid_rate_limit(user_id: int, auction_id: int) -> RateLimitResult:
    bucket = f"live_bid:{auction_id}:{user_id}"
    return _check(bucket, "live_bid")


def _check(bucket: str, limit_key: str) -> RateLimitResult:
    max_count, window = LIMITS[limit_key]
    now = datetime.utcnow()
    with _LOCK:
        count, reset_at = _BUCKETS.get(bucket, (0, now + window))
        if now >= reset_at:
            count = 0
            reset_at = now + window
        if count >= max_count:
            retry = max(1, int((reset_at - now).total_seconds()))
            return RateLimitResult(
                allowed=False,
                retry_after_seconds=retry,
                reason="Bid rate limit exceeded",
            )
        _BUCKETS[bucket] = (count + 1, reset_at)
    return RateLimitResult(allowed=True)
