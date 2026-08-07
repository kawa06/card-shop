"""In-memory rate limiting for live offer creation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from threading import Lock
from typing import Dict, Tuple

_BUCKETS: Dict[str, Tuple[int, datetime]] = {}
_LOCK = Lock()


@dataclass
class RateLimitResult:
    allowed: bool
    retry_after_seconds: int = 0
    reason: str | None = None


def check_live_offer_rate_limit(
    user_id: int,
    stream_id: int,
    *,
    max_count: int,
    window_seconds: int,
) -> RateLimitResult:
    bucket = f"live_offer:{stream_id}:{user_id}"
    window = timedelta(seconds=window_seconds)
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
                reason="Offer rate limit exceeded",
            )
        _BUCKETS[bucket] = (count + 1, reset_at)
    return RateLimitResult(allowed=True)


def reset_live_offer_rate_limits() -> None:
    with _LOCK:
        _BUCKETS.clear()
