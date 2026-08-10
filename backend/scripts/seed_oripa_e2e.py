"""Seed a sale-ready Oripa for Phase 3-9 local Playwright (no admin HTTP)."""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from database import SessionLocal
import models
import models_oripa
from services.admin_seed import seed_admin_rbac
from services.oripa_admin import create_oripa, generate_entries, link_entry_product, update_oripa
from services.oripa_constants import ORIPA_STATUS_ON_SALE


def main() -> int:
    out = Path(__file__).resolve().parents[2] / "artifacts" / "phase3-9-oripa"
    out.mkdir(parents=True, exist_ok=True)

    db = SessionLocal()
    try:
        seed_admin_rbac(db)
        stamp = time.time_ns() // 1_000_000
        card = models.Card(
            name=f"SECRET_PRIZE_CARD_{stamp}",
            price=5000,
            stock=10,
            condition="a",
            is_active=True,
            allowed_shipping_methods=json.dumps(["takkyubin_compact"]),
        )
        db.add(card)
        db.commit()
        db.refresh(card)

        oripa = create_oripa(
            db,
            title=f"E2E Oripa {stamp}",
            description="numbers only",
            price_per_entry=300,
            total_entries=5,
            max_entries_per_purchase=3,
        )
        generate_entries(db, oripa.id)
        entry = (
            db.query(models_oripa.OripaEntry)
            .filter(models_oripa.OripaEntry.oripa_id == oripa.id)
            .order_by(models_oripa.OripaEntry.entry_number.asc())
            .first()
        )
        assert entry is not None
        link_entry_product(db, entry.id, linked_product_id=card.id)
        update_oripa(db, oripa.id, status=ORIPA_STATUS_ON_SALE)
        db.commit()

        payload = {
            "oripa_id": oripa.id,
            "card_id": card.id,
            "title": oripa.title,
            "secret_name": card.name,
        }
        (out / "seed.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        (out / "oripa-id.txt").write_text(str(oripa.id), encoding="utf-8")
        print(json.dumps(payload))
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
