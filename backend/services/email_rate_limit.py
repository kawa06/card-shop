"""In-memory rate limiting for email sends (per-recipient, per-admin, global)."""

from __future__ import annotations

import threading
import time
from collections import defaultdict
from dataclasses import dataclass


@dataclass
class RateLimitResult:
    allowed: bool
    retry_after_seconds: float = 0.0
    reason: str = ""


_lock = threading.Lock()
_buckets: dict[str, list[float]] = defaultdict(list)

# Limits: (max_count, window_seconds)
LIMITS = {
    "test_send_admin": (10, 3600),
    "recipient": (5, 3600),
    "global_minute": (120, 60),
    "campaign_confirm": (20, 3600),
}


def _prune(key: str, window: float, now: float) -> None:
    _buckets[key] = [t for t in _buckets[key] if now - t < window]


def check_rate_limit(bucket: str, *, limit_key: str = "global_minute") -> RateLimitResult:
    max_count, window = LIMITS.get(limit_key, (100, 60))
    now = time.monotonic()
    full_key = f"{limit_key}:{bucket}"
    with _lock:
        _prune(full_key, window, now)
        if len(_buckets[full_key]) >= max_count:
            oldest = min(_buckets[full_key]) if _buckets[full_key] else now
            return RateLimitResult(
                allowed=False,
                retry_after_seconds=max(0.0, window - (now - oldest)),
                reason=f"Rate limit exceeded ({limit_key})",
            )
        _buckets[full_key].append(now)
    return RateLimitResult(allowed=True)


def reset_for_tests() -> None:
    with _lock:
        _buckets.clear()
