"""One-shot production migration presence check (no writes)."""
from __future__ import annotations

import json

from database import SessionLocal
from sqlalchemy import text


def main() -> None:
    db = SessionLocal()
    try:
        cols = db.execute(
            text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name='oripa_purchases' "
                "AND column_name IN ('reserved_expires_at','stripe_checkout_session_id') "
                "ORDER BY 1"
            )
        ).fetchall()
        nulls = db.execute(
            text(
                "SELECT is_nullable FROM information_schema.columns "
                "WHERE table_name='order_items' AND column_name='card_id'"
            )
        ).fetchone()
        print(
            json.dumps(
                {
                    "oripa_purchase_cols": [r[0] for r in cols],
                    "order_items_card_id_nullable": nulls[0] if nulls else None,
                }
            )
        )
    finally:
        db.close()


if __name__ == "__main__":
    main()
