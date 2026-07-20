#!/usr/bin/env python3
"""Upload buylist-export.json to production admin import API (Phase 8)."""

from __future__ import annotations

import argparse
import json
import os
import sys
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
        default=os.getenv("ADMIN_PROXY_SECRET", "card-shop-internal-admin-v1"),
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
    headers = {
        "Content-Type": "application/json",
        "X-Internal-Admin-Secret": args.admin_secret,
        "X-Admin-Email": args.admin_email,
    }
    response = httpx.post(url, headers=headers, json=body, timeout=120)
    print(response.status_code, response.text)
    return 0 if response.is_success else 1


if __name__ == "__main__":
    raise SystemExit(main())
