#!/usr/bin/env python3
"""List Resend verified domains and suggest MAIL_FROM for Railway."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx

from config import settings


def main() -> int:
    api_key = settings.RESEND_API_KEY or os.environ.get("RESEND_API_KEY")
    if not api_key:
        print("RESEND_API_KEY is not configured", file=sys.stderr)
        return 1

    current_from = settings.MAIL_FROM
    print(f"Current MAIL_FROM: {current_from}")

    with httpx.Client(timeout=30.0) as client:
        response = client.get(
            "https://api.resend.com/domains",
            headers={"Authorization": f"Bearer {api_key}"},
        )

    if response.status_code != 200:
        print(f"Failed to list domains ({response.status_code}): {response.text}", file=sys.stderr)
        return 1

    domains = response.json().get("data") or []
    if not domains:
        print("No domains found in Resend. Add and verify a domain in the Resend dashboard.")
        return 1

    print("\nResend domains:")
    verified: list[str] = []
    for row in domains:
        name = row.get("name")
        status = row.get("status")
        print(f"  - {name}: {status}")
        if status == "verified" and name:
            verified.append(name)

    if not verified:
        print("\nNo verified domains. Verify oripa-kawa.com (or your sending domain) in Resend.")
        return 1

    suggested = f"noreply@{verified[0]}"
    print(f"\nSuggested MAIL_FROM: {suggested}")
    if current_from.split("@")[-1] not in verified:
        print(
            f"WARNING: {current_from} uses an unverified domain. "
            f"Set MAIL_FROM={suggested} on Railway backend."
        )
    else:
        print("MAIL_FROM domain appears verified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
