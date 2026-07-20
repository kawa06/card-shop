# Buyback Phase 8 — Firestore product migration

## Scope

- Import buylist product data from Firestore export JSON into `buyback_products` + `buyback_product_prices`
- Idempotent upsert keyed by `firestore_item_id`
- Images: import when present in export; **never overwrite with empty** on update
- Validation: compare export vs DB counts
- Firestore remains the read fallback for the buylist site until cutover — **Phase 10 complete** (see `buyback-phase10-cutover.md`)

## Export format

Create `buylist-export.json`:

```json
{
  "items": [ ... contents of Firestore buylist/main.items ... ],
  "images": { "123": "data:image/jpeg;base64,..." }
}
```

### How to export

1. Firebase Console → Firestore → `buylist/main` → copy `items` array into JSON file
2. For each doc in `product-images`, add `"<productId>": dataUrl` to `images`
3. Or use your existing edit/admin tooling to dump JSON locally

**Do not delete Firestore data** — keep as rollback backup.

## Import

```bash
# 1) Export from Firestore
python scripts/export_firestore_buylist.py -o data/buylist-export.json

# 2) Import into PostgreSQL (local DATABASE_URL)
cd backend
python ../scripts/migrate_firestore_buylist.py ../data/buylist-export.json --dry-run
python ../scripts/migrate_firestore_buylist.py ../data/buylist-export.json

# Production (after backend deploy): admin API import
python scripts/run_phase8_import.py data/buylist-export.json
python scripts/run_phase8_import.py data/buylist-export.json --dry-run

# Validate counts
python ../scripts/migrate_firestore_buylist.py ../data/buylist-export.json --validate-only
```

Requires `DATABASE_URL` (Railway PostgreSQL or local SQLite).

## API read path

`GET /api/buyback/products` reads PostgreSQL only. After import, verify product count matches export.

Buylist HTML site reads PostgreSQL via API only after Phase 10 cutover (`productsSource: "postgresql"` in buylist config).

## Tests

```bash
cd backend && pytest tests/test_buyback_firestore_import.py -q
```

## Rollback

- Revert to Firestore as product source of truth (buylist site unchanged)
- Optional: delete imported rows where `firestore_item_id IS NOT NULL` if no live requests reference them
