# Buyback Phase 3 — Auth + API Skeleton

## Backend

### New endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/api/buyback/health` | Public | Health check |
| POST | `/api/buyback/auth/sync` | Clerk JWT | Link user + return backend JWT |
| GET | `/api/buyback/me` | Backend JWT or Clerk JWT | Current user |
| GET | `/api/buyback/products` | Public | PostgreSQL catalog (empty until migration) |
| GET | `/api/buyback/cart` | Backend JWT or Clerk JWT | Empty cart skeleton |

### User linking (`services/user_linking.py`)

1. Match `users.clerk_user_id` exactly
2. Else single email match → set `clerk_user_id` (never overwrite `password_hash`)
3. Clerk ID conflict → 409, audit log
4. No match → create verified user with `clerk_user_id`

`clerk_auth.py` uses the same linker for admin/buyback Clerk JWT auth.

### Unchanged (by design)

- `frontend/app/api/auth/backend-sync/route.ts`
- `POST /api/auth/clerk-provision` body/flow
- Firestore rules/data
- Stripe / shop cart / orders

## Buylist site (static + Clerk JS)

- `auth-clerk.js` — Clerk load, header auth UI, `/api/buyback/auth/sync`
- `sign-in.html`, `sign-up.html`, `account.html`
- Header login on `index.html` / `buylist.html`

## Manual dashboard setup

### Clerk Dashboard

1. Same Application as card shop
2. Add **Allowed origin**: `https://card-vault-public.vercel.app`
3. Add redirect URLs:
   - `https://card-vault-public.vercel.app/account.html`
   - `https://card-vault-public.vercel.app/sign-in.html`
   - `https://card-vault-public.vercel.app/sign-up.html`
4. (Local dev) `http://localhost:5500` or your static server origin

### Vercel (card-vault-public)

Set in `config.js` deploy or build-time injection:

```javascript
clerkPublishableKey: "pk_live_...",  // same as card shop
apiUrl: "https://backend-production-054e.up.railway.app",
```

Or use env → build script in a later phase.

### Railway

No new secrets required if `CLERK_PUBLISHABLE_KEY` / `CLERK_SECRET_KEY` already set.

Optional: `BUYLIST_URL=https://card-vault-public.vercel.app`

## Rollback

1. Remove `buyback_router` from `main.py`
2. Revert `clerk_auth.py` / `user_linking.py` if needed
3. Buylist: remove auth scripts/pages; price table still works via Firestore

## Next (Phase 4–5)

- Next.js buylist app (optional migration path)
- Buyback cart mutations + application flow
- Firestore → PostgreSQL product migration
