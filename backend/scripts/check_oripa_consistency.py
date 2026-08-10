"""Detect oripa reservation / payment consistency issues (monthly + CI helper)."""

from __future__ import annotations

import json
import sys

from database import SessionLocal
from services.oripa_payment import list_oripa_consistency_issues


def main() -> int:
    db = SessionLocal()
    try:
        issues = list_oripa_consistency_issues(db)
    finally:
        db.close()
    print(json.dumps({"ok": len(issues) == 0, "issues": issues}, ensure_ascii=False, indent=2))
    return 0 if not issues else 1


if __name__ == "__main__":
    sys.exit(main())
