"""Inspect Stripe webhook endpoints (no secrets printed)."""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

TARGET = "https://backend-production-054e.up.railway.app/api/payments/stripe/webhook"
NEEDED = {
    "checkout.session.completed",
    "checkout.session.async_payment_succeeded",
    "checkout.session.async_payment_failed",
    "checkout.session.expired",
}


def main() -> int:
    key = os.environ.get("STRIPE_SECRET_KEY", "").strip()
    if not key:
        print("ERROR: STRIPE_SECRET_KEY not set")
        return 1

    req = urllib.request.Request(
        "https://api.stripe.com/v1/webhook_endpoints?limit=20",
        headers={"Authorization": f"Bearer {key}"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            payload = json.load(response)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")[:300]
        print(f"ERROR: Stripe API HTTP {exc.code}: {body}")
        return 2
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: {type(exc).__name__}: {exc}")
        return 3

    endpoints = payload.get("data", [])
    print(f"ENDPOINT_COUNT={len(endpoints)}")
    matched = False
    for ep in endpoints:
        url = (ep.get("url") or "").rstrip("/")
        events = set(ep.get("enabled_events") or [])
        print(f"ID={ep.get('id')} STATUS={ep.get('status')}")
        print(f"URL={url}")
        print(f"EVENTS={','.join(sorted(events))}")
        if url == TARGET.rstrip("/"):
            matched = True
            missing = sorted(NEEDED - events)
            print(f"MATCH=YES MISSING={','.join(missing) if missing else 'NONE'}")
        print("---")

    print(f"HAS_TARGET={'YES' if matched else 'NO'}")
    return 0 if matched else 4


if __name__ == "__main__":
    raise SystemExit(main())
