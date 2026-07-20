# KRX Card Shop — Database Backup Guide

本番データを変更・削除せず、変更前の状態を復元できるようにするための手順です。

## 使用中のデータベース

| 項目 | 内容 |
|------|------|
| エンジン | **PostgreSQL**（本番） |
| ホスティング | **Railway**（`backend` サービスの `DATABASE_URL`） |
| ローカル開発 | SQLite（`backend/card_shop.db`）— 非永続 |

確認方法:

```powershell
# Railway CLI（backend ディレクトリで）
cd backend
railway variables
# DATABASE_URL を確認（値そのものは Git / ログに出力しない）
```

ヘルスチェック API:

```
GET https://backend-production-054e.up.railway.app/api/health
```

レスポンスの `database.engine` が `postgresql` であることを確認してください。

## バックアップ方法

### 本番（PostgreSQL / Railway）

**手動論理バックアップ（推奨・変更前に実施）**

```powershell
# 1. DATABASE_URL を Railway ダッシュボードまたは CLI から取得（秘密情報）
# 2. pg_dump で SQL ダンプを作成（本番 DB は読み取りのみ — DELETE/ALTER しない）

$env:DATABASE_URL = "<Railway の DATABASE_URL>"
$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$outFile = ".\backups\card-shop-prod-$timestamp.sql"

New-Item -ItemType Directory -Force -Path (Split-Path $outFile) | Out-Null
pg_dump $env:DATABASE_URL --format=plain --no-owner --no-acl -f $outFile
```

ラッパースクリプト: `scripts/db_backup.ps1`（上記コマンドのテンプレート）

**前提:** ローカルに PostgreSQL クライアント（`pg_dump`）がインストールされていること。

### ローカル（SQLite）

```powershell
Copy-Item backend\card_shop.db "backups\card-shop-local-$(Get-Date -Format 'yyyyMMdd-HHmmss').db"
```

## 復元方法

> **注意:** 本番復元はデータ上書きになります。必ずメンテナンス時間帯に実施し、復元前に再度バックアップを取得してください。

### PostgreSQL

```powershell
# 空の DB または別スキーマへリストア（本番上書きは慎重に）
psql $env:DATABASE_URL -f .\backups\card-shop-prod-YYYYMMDD-HHMMSS.sql
```

Railway では一時的に別 PostgreSQL サービスを作成し、そこへリストアして検証する方法が安全です。

### SQLite

```powershell
Copy-Item backups\card-shop-local-YYYYMMDD-HHMMSS.db backend\card_shop.db -Force
```

## 自動バックアップの有無

| 環境 | 自動バックアップ |
|------|------------------|
| Railway PostgreSQL | Railway プランに応じた **自動スナップショット**（ダッシュボード → Database → Backups で確認） |
| 本アプリコード | **自動バックアップジョブは未実装**（今回のスコープ外） |
| SQLite ローカル | なし |

## 保存期間

- **Railway 自動スナップショット:** プラン依存（Hobby / Pro 等）。Railway ダッシュボードで保持期間を確認してください。
- **手動 `pg_dump`:** 運用ポリシーに従い、推奨 **90 日以上**（別ストレージに保管）。

## 別プロジェクト / 別ストレージへの保存

1. **Cloudflare R2**（既存 KYC 用バケットとは別プレフィックス推奨）
   ```powershell
   aws s3 cp $outFile s3://<bucket>/db-backups/card-shop-prod-$timestamp.sql `
     --endpoint-url https://<account>.r2.cloudflarestorage.com
   ```

2. **ローカル暗号化ディスク / NAS**

3. **別 Railway PostgreSQL インスタンス**（検証用コピー）

## 今回実装していないもの

- アプリ内からの本番ワンクリック復元 UI
- スケジュール実行される自動バックアップ Cron
- Supabase（本プロジェクトでは未使用）

## 管理者セキュリティ変更前のチェックリスト

1. [ ] `pg_dump` で本番 SQL ダンプを取得
2. [ ] ダンプファイルを Git 以外の安全な場所に保存
3. [ ] Railway ダッシュボードで最新スナップショット時刻を記録
4. [ ] `git log -1` で `backup: before KRX admin security implementation` コミットを確認
