"""Create or update Stripe webhook endpoint for card-shop backend."""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

TARGET = "https://backend-production-054e.up.railway.app/api/payments/stripe/webhook"
NEEDED = [
    "checkout.session.completed",
    "checkout.session.async_payment_succeeded",
    "checkout.session.async_payment_failed",
    "checkout.session.expired",
]


def stripe_request(method: str, path: str, data: dict | None = None) -> dict:
    key = os.environ["STRIPE_SECRET_KEY"].strip()
    url = f"https://api.stripe.com/v1{path}"
    body = None
    headers = {"Authorization": f"Bearer {key}"}
    if data is not None:
        body = urllib.parse.urlencode(data, doseq=True).encode("utf-8")
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=30) as response:
        return json.load(response)


def list_endpoints() -> list[dict]:
    payload = stripe_request("GET", "/webhook_endpoints?limit=20")
    return payload.get("data", [])


def create_endpoint() -> dict:
    data = {
        "url": TARGET,
        "enabled_events[]": NEEDED,
        "description": "card-shop production checkout webhooks",
    }
    return stripe_request("POST", "/webhook_endpoints", data)


def update_endpoint(endpoint_id: str, enabled_events: list[str]) -> dict:
    data = {"enabled_events[]": enabled_events}
    return stripe_request("POST", f"/webhook_endpoints/{endpoint_id}", data)


def main() -> int:
    if not os.environ.get("STRIPE_SECRET_KEY", "").strip():
        print("ERROR: STRIPE_SECRET_KEY not set")
        return 1

    endpoints = list_endpoints()
    target = TARGET.rstrip("/")
    existing = None
    for ep in endpoints:
        if (ep.get("url") or "").rstrip("/") == target:
            existing = ep
            break

    if existing is None:
        try:
            created = create_endpoint()
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")[:400]
            print(f"ERROR: create failed HTTP {exc.code}: {body}")
            return 2
        print(f"CREATED={created.get('id')}")
        print(f"URL={created.get('url')}")
        secret = created.get("secret")
        if secret:
            print(f"SIGNING_SECRET={secret}")
        print("ACTION=created")
        return 0

    current = set(existing.get("enabled_events") or [])
    needed = set(NEEDED)
    if current >= needed:
        print(f"EXISTS={existing.get('id')}")
        print("ACTION=noop")
        return 0

    merged = sorted(current | needed)
    try:
        updated = update_endpoint(existing["id"], merged)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")[:400]
        print(f"ERROR: update failed HTTP {exc.code}: {body}")
        return 3

    print(f"UPDATED={updated.get('id')}")
    print(f"EVENTS={','.join(updated.get('enabled_events') or [])}")
    print("ACTION=updated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
