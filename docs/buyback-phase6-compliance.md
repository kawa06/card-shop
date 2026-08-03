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

### R2 credentials (important)

Create tokens at **Cloudflare Dashboard → R2 → Manage R2 API Tokens** (not general API tokens).

- `R2_ACCESS_KEY_ID` must be **32 characters** (UUID-style tokens may include dashes — strip before use)
- `R2_SECRET_ACCESS_KEY` is shown once when the token is created
- Set on **Railway backend** only; never expose to the buylist frontend

Validate after setting:

```bash
cd backend && railway run python scripts/validate_r2_storage.py
```

## Env (Railway — backend service)

**必須（本番）:** 振込口座の口座番号を暗号化するサーバー専用キー。フロントエンドや `NEXT_PUBLIC_*` には設定しないこと。

```bash
# 32バイト以上のランダム値を生成（Node.js）
node -e "console.log(require('crypto').randomBytes(32).toString('base64'))"
```

Railway の **backend** サービスに設定:

```
BUYBACK_PAYOUT_ENCRYPTION_KEY=<上記で生成した値>
```

- 既存本番でキーが設定済みの場合、**変更しない**（既存口座が復号不能になります）
- 未設定時は口座登録 API が 503 を返し、利用者には内部エラー名を表示しません

その他:

```
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
