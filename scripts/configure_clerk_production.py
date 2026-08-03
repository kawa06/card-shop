"""Configure Clerk Production instance: origins, redirects, Google OAuth prep."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
PROD_ENV = ROOT / "frontend" / ".env.clerk.prod"

SHOP_ORIGIN = "https://frontend-one-topaz-20.vercel.app"
BUYLIST_ORIGIN = "https://card-vault-public.vercel.app"

SHOP_REDIRECTS = (
    "/",
    "/sign-in",
    "/sign-up",
    "/auth/after-sign-in",
    "/mypage",
    "/cart",
    "/checkout",
)

BUYLIST_REDIRECTS = (
    "/",
    "/sign-in.html",
    "/sign-up.html",
    "/account.html",
    "/cart.html",
    "/requests.html",
    "/request.html",
    "/settings.html",
    "/guardian-consent.html",
)


def _load_prod_secret() -> str:
    if not PROD_ENV.exists():
        raise SystemExit(
            f"Missing {PROD_ENV}. Run: clerk env pull --instance ins_3Gao4fQ3ZL1I0hTNH6mkc6J9ixh --file .env.clerk.prod --mode agent"
        )
    text = PROD_ENV.read_text(encoding="utf-8")
    match = re.search(r"^CLERK_SECRET_KEY=(.+)$", text, re.M)
    if not match:
        raise SystemExit("CLERK_SECRET_KEY not found in .env.clerk.prod")
    key = match.group(1).strip().strip('"')
    if not key.startswith("sk_live_"):
        raise SystemExit("Expected sk_live_ secret in .env.clerk.prod")
    return key


def _client(secret: str) -> httpx.Client:
    return httpx.Client(
        timeout=30.0,
        headers={
            "Authorization": f"Bearer {secret}",
            "Content-Type": "application/json",
        },
    )


def _origins(data: dict) -> list[str]:
    return list(data.get("allowed_origins") or data.get("allowedOrigins") or [])


def _redirect_urls(client: httpx.Client) -> set[str]:
    res = client.get("https://api.clerk.com/v1/redirect_urls")
    res.raise_for_status()
    body = res.json()
    items = body if isinstance(body, list) else body.get("data") or []
    return {str(item["url"]) for item in items if isinstance(item, dict) and item.get("url")}


def main() -> int:
    secret = _load_prod_secret()
    desired = sorted(
        {f"{SHOP_ORIGIN}{path}" for path in SHOP_REDIRECTS}
        | {f"{BUYLIST_ORIGIN}{path}" for path in BUYLIST_REDIRECTS}
    )

    with _client(secret) as client:
        inst_res = client.get("https://api.clerk.com/v1/instance")
        inst_res.raise_for_status()
        inst = inst_res.json()
        current = set(_origins(inst))
        merged = sorted(current | {SHOP_ORIGIN, BUYLIST_ORIGIN})

        patch: dict = {"allowed_origins": merged}
        name = inst.get("application_name") or inst.get("applicationName")
        if name != "KRX TCG":
            patch["application_name"] = "KRX TCG"

        if current != set(merged) or name != "KRX TCG":
            patch_res = client.patch("https://api.clerk.com/v1/instance", json=patch)
            patch_res.raise_for_status()
            added = sorted(set(merged) - current)
            for origin in added:
                print(f"added_origin: {origin}")
            if name != "KRX TCG":
                print("updated_application_name: KRX TCG")
        else:
            print("origins_ok")

        existing = _redirect_urls(client)
        added = 0
        for url in desired:
            if url in existing:
                continue
            create_res = client.post(
                "https://api.clerk.com/v1/redirect_urls",
                json={"url": url},
            )
            if create_res.status_code in (200, 201):
                added += 1
                print(f"added_redirect: {url}")
            else:
                print(
                    f"redirect_skip: {url} status={create_res.status_code}",
                    file=sys.stderr,
                )
        print(f"redirect_urls_added: {added}")

        domains_res = client.get("https://api.clerk.com/v1/domains")
        if domains_res.status_code == 200:
            domains = domains_res.json()
            items = domains if isinstance(domains, list) else domains.get("data") or []
            print(f"domains_count: {len(items)}")
            for item in items:
                if isinstance(item, dict):
                    print(
                        "domain:",
                        item.get("name") or item.get("domain"),
                        "status=",
                        item.get("status") or item.get("verification_status"),
                    )

    print("done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
