# Buyback Phase 6 — Compliance (KYC, guardian, payout)

## Scope

- Identity verification upload + submit (`identity_verifications`)
- Guardian consent request + public sign link
- Encrypted payout bank accounts (`payout_accounts`)
- Compliance readiness API for payout prerequisites
- Buylist UI: `settings.html`, `guardian-consent.html`

## API

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/api/buyback/compliance` | JWT | Payout readiness checklist |
| GET | `/api/buyback/identity` | JWT | KYC status |
| POST | `/api/buyback/identity/documents?side=front\|back` | JWT | Upload ID image (multipart) |
| POST | `/api/buyback/identity/submit` | JWT | Submit for review |
| GET | `/api/buyback/guardian-consent` | JWT | Guardian status |
| POST | `/api/buyback/guardian-consent/request` | JWT | Email guardian |
| GET | `/api/buyback/guardian-consent/preview?token=` | Public | Preview consent |
| POST | `/api/buyback/guardian-consent/sign` | Public | Sign consent |
| GET | `/api/buyback/payout-accounts` | JWT | List masked accounts |
| POST | `/api/buyback/payout-accounts` | JWT | Register account |
| PUT | `/api/buyback/payout-accounts/{id}/default` | JWT | Set default |
| DELETE | `/api/buyback/payout-accounts/{id}` | JWT | Remove account |

## Storage & security

- **KYC images:** Cloudflare R2 when `R2_*` env vars set; local `backend/data/kyc/` in DEBUG only
- **Account numbers:** Fernet encryption via `BUYBACK_PAYOUT_ENCRYPTION_KEY` (required in production)
- API never returns full account numbers (masked only)

## Env (Railway)

```
BUYBACK_PAYOUT_ENCRYPTION_KEY=<32+ char secret>
R2_ACCOUNT_ID=
R2_ACCESS_KEY_ID=
R2_SECRET_ACCESS_KEY=
R2_BUCKET_NAME=
BUYLIST_URL=https://card-vault-public.vercel.app
```

## Tests

```bash
cd backend && pytest tests/test_buyback_*.py tests/test_user_linking.py -q
```

## Not in Phase 6

- Admin KYC review UI / approve-reject API
- R2 presigned direct upload (uploads go through API)
- Automatic minor age detection from Clerk metadata
