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

- バックエンド: Render
- フロントエンド: Vercel
