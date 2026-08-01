#!/usr/bin/env python3
"""Upload buylist-export.json to production admin import API (Phase 8)."""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import sys
import time
from pathlib import Path

import httpx


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Phase 8 import against production admin API")
    parser.add_argument(
        "export_file",
        type=Path,
        nargs="?",
        default=Path("data/buylist-export.json"),
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--backend-url",
        default=os.getenv("BACKEND_URL", "https://backend-production-054e.up.railway.app"),
    )
    parser.add_argument(
        "--admin-email",
        default=os.getenv("ADMIN_EMAIL", "rikukai0609@icloud.com"),
    )
    parser.add_argument(
        "--admin-secret",
        default=os.getenv("ADMIN_PROXY_SECRET", ""),
    )
    args = parser.parse_args()

    if not args.export_file.exists():
        print(f"Export file not found: {args.export_file}", file=sys.stderr)
        return 1

    payload = json.loads(args.export_file.read_text(encoding="utf-8"))
    body = {
        "items": payload.get("items") or [],
        "images": payload.get("images") or {},
        "dry_run": args.dry_run,
    }
    url = args.backend_url.rstrip("/") + "/api/admin/buyback/import-firestore"
    secret = (args.admin_secret or "").strip()
    email = (args.admin_email or "").strip().lower()
    if not secret or not email:
        print("Admin proxy credentials are required", file=sys.stderr)
        return 2
    timestamp = str(int(time.time()))
    signature = hmac.new(
        secret.encode("utf-8"),
        f"{timestamp}\n{email}".encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    headers = {
        "Content-Type": "application/json",
        "X-Admin-Email": email,
        "X-Admin-Timestamp": timestamp,
        "X-Admin-Signature": signature,
    }
    response = httpx.post(url, headers=headers, json=body, timeout=120)
    print(response.status_code, response.text)
    return 0 if response.is_success else 1


if __name__ == "__main__":
    raise SystemExit(main())
