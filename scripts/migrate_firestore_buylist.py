#!/usr/bin/env python3
"""Import Firestore buylist export JSON into PostgreSQL buyback_products (Phase 8)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from database import SessionLocal  # noqa: E402
from services.buyback_firestore_import import (  # noqa: E402
    import_firestore_buylist_export,
    validate_import_counts,
)


def load_payload(path: Path) -> dict:
    with path.open(encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, dict):
        raise SystemExit("Export JSON must be an object with items/images")
    return data


def main() -> int:
    parser = argparse.ArgumentParser(description="Migrate Firestore buylist export to PostgreSQL")
    parser.add_argument("export_file", type=Path, help="Path to buylist-export.json")
    parser.add_argument("--dry-run", action="store_true", help="Validate and count without writing")
    parser.add_argument("--validate-only", action="store_true", help="Compare counts after import")
    args = parser.parse_args()

    if not args.export_file.exists():
        print(f"File not found: {args.export_file}", file=sys.stderr)
        return 1

    payload = load_payload(args.export_file)
    db = SessionLocal()
    try:
        if args.validate_only:
            stats = validate_import_counts(db, payload)
            print(json.dumps(stats, ensure_ascii=False, indent=2))
            return 0

        result = import_firestore_buylist_export(db, payload, dry_run=args.dry_run)
        print(
            json.dumps(
                {
                    "created": result.created,
                    "updated": result.updated,
                    "skipped": result.skipped,
                    "price_rows_upserted": result.price_rows_upserted,
                    "image_failures": result.image_failures,
                    "errors": result.errors,
                    "dry_run": args.dry_run,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        if not args.dry_run:
            stats = validate_import_counts(db, payload)
            print("validation:", json.dumps(stats, ensure_ascii=False))
        return 0 if not result.errors else 2
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
