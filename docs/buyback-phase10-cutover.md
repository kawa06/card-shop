# Buyback Phase 10 — Production cutover

## Scope

Complete the Firestore → PostgreSQL cutover for **public buylist product reads**.

| Component | Before (Phase 8–9) | After (Phase 10) |
|-----------|-------------------|------------------|
| Public buylist products | API first → Firestore fallback | **PostgreSQL API only** |
| Shop notice (`loadShop`) | Firestore | Firestore (unchanged) |
| Edit/admin save | Firestore | Firestore + manual re-import |
| Health API | `phase: "9"` | `phase: "10"`, `cutover_complete: true` |

Firestore product data is **kept as rollback backup** — do not delete.

## Buylist config

`card-vault-buylist/config.js`:

```js
productsSource: "postgresql",
apiUrl: "https://backend-production-054e.up.railway.app",
```

When `productsSource` is `"postgresql"` or `"api"`, `loadProducts()` skips Firestore entirely.

## Product price updates after cutover

The legacy `/edit/:token` UI still **writes to Firestore**. To reflect changes on the public buylist:

```bash
python scripts/export_firestore_buylist.py -o data/buylist-export.json
python scripts/run_phase8_import.py data/buylist-export.json
```

Future work: card-shop admin UI for direct PostgreSQL product edits.

## Verification

```bash
# Backend
curl https://backend-production-054e.up.railway.app/api/buyback/health
# → phase "10", cutover_complete true, products_source "postgresql"

# Production smoke
cd backend && E2E_RUN=1 pytest tests/e2e/test_production_smoke.py -q

# Browser (optional)
E2E_RUN_PLAYWRIGHT=1 pytest tests/e2e/test_buylist_browser.py -q
```

## Rollback

1. Remove or comment `productsSource: "postgresql"` in buylist `config.js`
2. Redeploy buylist (Firestore fallback restored)
3. PostgreSQL data remains; no DB deletion required

## DNS / URLs

No DNS change required if already on:

- Buylist: https://card-vault-public.vercel.app
- Shop: https://frontend-one-topaz-20.vercel.app
- API: https://backend-production-054e.up.railway.app
