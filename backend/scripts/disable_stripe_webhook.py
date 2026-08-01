"""Disable a Stripe webhook endpoint by ID."""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: disable_stripe_webhook.py <we_...>")
        return 1
    endpoint_id = sys.argv[1]
    key = os.environ["STRIPE_SECRET_KEY"].strip()
    data = urllib.parse.urlencode({"disabled": "true"}).encode("utf-8")
    req = urllib.request.Request(
        f"https://api.stripe.com/v1/webhook_endpoints/{endpoint_id}",
        data=data,
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            payload = json.load(response)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")[:300]
        print(f"ERROR HTTP {exc.code}: {body}")
        return 2
    print(f"DISABLED={payload.get('id')} STATUS={payload.get('status')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
