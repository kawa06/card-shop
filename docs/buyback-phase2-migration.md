# Buyback Phase 2 — DB Migration Notes

Phase 2 adds **additive** schema only. No data migration, no Firestore changes.

## What runs automatically

On backend startup (`main.py` → `run_schema_upgrades()`):

1. `users.clerk_user_id` column (nullable `VARCHAR(255)`)
2. Unique index `ix_users_clerk_user_id` on `users(clerk_user_id)`
3. Empty buyback tables (see below)

## New tables

| Table | Purpose |
|-------|---------|
| `buyback_products` | Buyback catalog (future Firestore migration target) |
| `buyback_product_prices` | Condition/tier prices per product |
| `buyback_price_history` | Price change audit |
| `buyback_carts` | Per-user buyback cart |
| `buyback_cart_items` | Cart lines |
| `buyback_requests` | Buyback applications |
| `buyback_request_items` | Application line items |
| `identity_verifications` | KYC submissions (R2 keys) |
| `guardian_consents` | Minor guardian consent |
| `payout_accounts` | Encrypted bank accounts |
| `buyback_status_history` | Request status transitions |
| `buyback_audit_logs` | Admin/ system audit |
| `notification_deliveries` | Email delivery log |

## Rollback (manual, if needed before Phase 3 data exists)

**Only safe when all buyback tables are empty.**

PostgreSQL example:

```sql
DROP TABLE IF EXISTS notification_deliveries;
DROP TABLE IF EXISTS buyback_audit_logs;
DROP TABLE IF EXISTS buyback_status_history;
DROP TABLE IF EXISTS payout_accounts;
DROP TABLE IF EXISTS guardian_consents;
DROP TABLE IF EXISTS identity_verifications;
DROP TABLE IF EXISTS buyback_request_items;
DROP TABLE IF EXISTS buyback_requests;
DROP TABLE IF EXISTS buyback_cart_items;
DROP TABLE IF EXISTS buyback_carts;
DROP TABLE IF EXISTS buyback_price_history;
DROP TABLE IF EXISTS buyback_product_prices;
DROP TABLE IF EXISTS buyback_products;
DROP INDEX IF EXISTS ix_users_clerk_user_id;
-- Do NOT drop users.clerk_user_id column if any values are populated.
```

SQLite: same `DROP TABLE` order; index name may differ — check `sqlite_master`.

## Not in Phase 2

- `/api/buyback/*` routes
- Clerk on buylist site
- Firestore rules / data migration
- Populating `clerk_user_id` (Phase 3 linking logic)

## Manual dashboard settings (user)

See `backend/.env.example` and `frontend/.env.example` for new variable **names**.

- **Vercel (card-shop):** `NEXT_PUBLIC_BUYLIST_URL`
- **Railway (backend):** `BUYLIST_URL`, R2 vars (Phase 3+)
- **Vercel (buylist):** redeploy after branding changes; no new secrets required in Phase 2
