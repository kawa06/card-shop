# Card Shop

TCGカード販売サイト（Next.js + FastAPI）

## 技術スタック

### フロントエンド
- Next.js 14 (App Router)
- TypeScript
- Tailwind CSS
- shadcn/ui

### バックエンド
- FastAPI
- SQLAlchemy
- PostgreSQL（本番）/ SQLite（開発）

### その他
- Stripe（決済）
- JWT（認証）

## 開発環境構築

### バックエンド
```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload
```

### フロントエンド
```bash
cd frontend
npm install
npm run dev
```

## デプロイ

- バックエンド: **Railway**（`backend` サービス）
- フロントエンド（販売）: Vercel
- 買取サイト（card-vault-buylist）: Vercel

### 買取機能 — 本番必須環境変数（Railway backend）

振込口座登録にはサーバー専用の暗号化キーが必要です（フロントエンドに公開しないこと）:

```bash
node -e "console.log(require('crypto').randomBytes(32).toString('base64'))"
```

生成した値を Railway の **backend** サービスに `BUYBACK_PAYOUT_ENCRYPTION_KEY` として設定してください。詳細は `docs/buyback-phase6-compliance.md` を参照。
