# Buyback Phase 9 — E2E tests

## Scope

End-to-end verification for the buyback integration:

| Area | Coverage |
|------|----------|
| 認証 | Backend JWT cart/request access; Clerk sync 401 without token |
| 買取価格 | PostgreSQL products API + buylist page render |
| カート / 申込 | Full HTTP flow: cart → request → empty cart |
| KYC / 振込 | Identity upload, admin approve, payout account, payout complete |
| 移行 | Admin import-firestore idempotency |
| カードショップ回帰 | Shop homepage + `/cards` smoke |

Stripe: **test mode only** for manual checkout (existing `MANUAL_CHECKLIST.md`). Automated E2E does not hit live Stripe.

## Test layers

### 1. API E2E (default, no extra setup)

In-memory SQLite + FastAPI `TestClient`:

```bash
cd backend
pip install -r requirements-dev.txt
pytest tests/test_buyback_e2e_flow.py tests/test_buyback_auth.py -q
```

### 2. Production smoke (HTTP only)

```bash
cd backend
E2E_RUN=1 pytest tests/e2e/test_production_smoke.py -q
```

Optional URLs:

- `E2E_BACKEND_URL` (default: Railway production)
- `E2E_BUYLIST_URL` (default: card-vault-public.vercel.app)
- `E2E_SHOP_URL` (default: frontend-one-topaz-20.vercel.app)

### 3. Playwright browser E2E

```bash
cd backend
pip install -r requirements-dev.txt
playwright install chromium
E2E_RUN_PLAYWRIGHT=1 pytest tests/e2e/test_buylist_browser.py tests/e2e/test_shop_regression.py -q
```

## Run all buyback tests

```bash
cd backend
pytest tests/test_buyback_*.py tests/test_admin_buyback.py tests/test_user_linking.py -q
```

## Health endpoint

After Phase 9 deploy, `GET /api/buyback/health` returns:

```json
{"status":"ok","phase":"9","products_source":"postgresql"}
```

## Manual checklist

See `backend/tests/MANUAL_CHECKLIST.md` for order/inquiry regression and Stripe test cards.
