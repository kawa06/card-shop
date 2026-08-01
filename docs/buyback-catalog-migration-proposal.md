# Buyback catalog additive migration proposal

This proposal is **not applied automatically** by this bugfix branch. Apply only after reviewing existing production data.

## Reason

Admin catalog CRUD stores optional identity fields on `buyback_products`:

- `card_number` (nullable)
- `rarity` (nullable)
- `pack_name` (nullable)

Existing PostgreSQL databases created before this change may only have the legacy columns (`name`, `category`, `image_url`, `notes`, `is_active`, `sort_order`).

## Safe additive SQL (PostgreSQL)

```sql
ALTER TABLE buyback_products
  ADD COLUMN IF NOT EXISTS card_number VARCHAR(128),
  ADD COLUMN IF NOT EXISTS rarity VARCHAR(128),
  ADD COLUMN IF NOT EXISTS pack_name VARCHAR(255);
```

## Notes

- No `DROP`, `TRUNCATE`, type changes, or new `NOT NULL` constraints.
- No new unique indexes are required for duplicate detection; conflicts are checked in application logic and return HTTP 409.
- Existing buyback requests and cart snapshots remain unchanged because catalog rows are soft-deleted (`is_active = false`) instead of hard-deleted.
