"""Configure Clerk allowed origins + redirect URLs for buylist (one-off ops script)."""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = ROOT / "frontend" / ".env.local"
BUYLIST_ORIGIN = "https://card-vault-public.vercel.app"
REDIRECT_PATHS = (
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


def _load_secret_key() -> str:
    if not ENV_FILE.exists():
        raise SystemExit(f"Missing {ENV_FILE}")
    text = ENV_FILE.read_text(encoding="utf-8")
    match = re.search(r"^CLERK_SECRET_KEY=(.+)$", text, re.M)
    if not match:
        raise SystemExit("CLERK_SECRET_KEY not found in .env.local")
    return match.group(1).strip().strip('"')


def _client(secret: str) -> httpx.Client:
    return httpx.Client(
        timeout=30.0,
        headers={
            "Authorization": f"Bearer {secret}",
            "Content-Type": "application/json",
        },
    )


def _get_allowed_origins(data: dict) -> list[str]:
    origins = data.get("allowed_origins") or data.get("allowedOrigins") or []
    return list(origins)


def _list_redirect_urls(client: httpx.Client) -> list[str]:
    res = client.get("https://api.clerk.com/v1/redirect_urls")
    res.raise_for_status()
    body = res.json()
    items = body if isinstance(body, list) else body.get("data") or []
    urls: list[str] = []
    for item in items:
        if isinstance(item, dict) and item.get("url"):
            urls.append(str(item["url"]))
    return urls


def main() -> int:
    secret = _load_secret_key()
    desired_redirects = [f"{BUYLIST_ORIGIN}{path}" for path in REDIRECT_PATHS]

    with _client(secret) as client:
        inst_res = client.get("https://api.clerk.com/v1/instance")
        inst_res.raise_for_status()
        inst = inst_res.json()
        current_origins = _get_allowed_origins(inst)
        merged_origins = sorted(set(current_origins) | {BUYLIST_ORIGIN})

        patch_payload: dict = {"allowed_origins": merged_origins}
        current_name = (
            inst.get("application_name")
            or inst.get("applicationName")
            or inst.get("display_config", {}).get("application_name")
        )
        if current_name != "KRX TCG":
            patch_payload["application_name"] = "KRX TCG"

        if BUYLIST_ORIGIN not in current_origins or current_name != "KRX TCG":
            patch_res = client.patch(
                "https://api.clerk.com/v1/instance",
                json=patch_payload,
            )
            patch_res.raise_for_status()
            if BUYLIST_ORIGIN not in current_origins:
                print(f"updated_allowed_origins: added {BUYLIST_ORIGIN}")
            if current_name != "KRX TCG":
                print("updated_application_name: KRX TCG")
        else:
            print(f"allowed_origins_ok: {BUYLIST_ORIGIN}")
            print("application_name_ok: KRX TCG")

        existing = set(_list_redirect_urls(client))
        added = 0
        for url in desired_redirects:
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
                    f"redirect_skip: {url} status={create_res.status_code} body={create_res.text[:200]}",
                    file=sys.stderr,
                )

        print(f"redirect_urls_added: {added}")
        print("done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
