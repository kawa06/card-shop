#!/usr/bin/env python3
"""Show Resend DNS records for oripa-kawa.com and trigger verification."""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx

from config import settings

TARGET_DOMAIN = "oripa-kawa.com"


def main() -> int:
    api_key = settings.RESEND_API_KEY or os.environ.get("RESEND_API_KEY")
    if not api_key:
        print("RESEND_API_KEY is not configured", file=sys.stderr)
        return 1

    headers = {"Authorization": f"Bearer {api_key}"}
    with httpx.Client(timeout=30.0) as client:
        list_resp = client.get("https://api.resend.com/domains", headers=headers)
        if list_resp.status_code != 200:
            print(f"Failed to list domains ({list_resp.status_code})", file=sys.stderr)
            return 1

        domains = list_resp.json().get("data") or []
        target = next((d for d in domains if d.get("name") == TARGET_DOMAIN), None)

        if not target:
            print(f"Domain {TARGET_DOMAIN} not found in Resend. Add it in the Resend dashboard first.")
            return 1

        domain_id = target.get("id")
        status = target.get("status")
        print(f"Domain: {TARGET_DOMAIN}")
        print(f"Status: {status}")
        print(f"ID: {domain_id}")

        detail_resp = client.get(f"https://api.resend.com/domains/{domain_id}", headers=headers)
        if detail_resp.status_code == 200:
            detail = detail_resp.json()
            records = detail.get("records") or []
            if records:
                print("\nAdd these DNS records (Cloudflare or your DNS provider):")
                for rec in records:
                    rtype = rec.get("type") or rec.get("record") or "?"
                    name = rec.get("name") or rec.get("host") or "?"
                    value = rec.get("value") or rec.get("content") or "?"
                    priority = rec.get("priority")
                    rec_status = rec.get("status") or "unknown"
                    line = f"  [{rec_status}] {rtype} {name} -> {value}"
                    if priority is not None:
                        line += f" (priority {priority})"
                    print(line)
            else:
                print("\nNo DNS records returned. Check Resend dashboard > Domains > oripa-kawa.com")

        verify_resp = client.post(f"https://api.resend.com/domains/{domain_id}/verify", headers=headers)
        if verify_resp.status_code in (200, 201):
            print("\nVerification check triggered.")
            refreshed = client.get(f"https://api.resend.com/domains/{domain_id}", headers=headers)
            if refreshed.status_code == 200:
                print(f"Updated status: {refreshed.json().get('status', status)}")
        else:
            print(f"\nVerify request returned {verify_resp.status_code} (DNS may still be pending).")

    print(f"\nRailway: ensure MAIL_FROM=noreply@{TARGET_DOMAIN} (not only EMAIL_FROM)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
