# KRX Card Shop — manual PostgreSQL backup (read-only dump)
# Usage:
#   1. Install PostgreSQL client tools (pg_dump in PATH)
#   2. Set DATABASE_URL to a reachable connection string:
#        - Railway Postgres → Connect → Public Network (TCP proxy URL), OR
#        - `railway variables` internal URL only works from Railway network
#   3. Run: .\scripts\db_backup.ps1
#
# Optional: .\scripts\db_backup.ps1 -UseRailway
#   Injects Railway production env vars locally, then runs pg_dump (still needs pg_dump in PATH).
#
# This script performs a read-only dump; it does not modify production data.

param(
    [string]$DatabaseUrl = $env:DATABASE_URL,
    [switch]$UseRailway
)

$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$outDir = Join-Path $PSScriptRoot "..\backups"
$outFile = Join-Path $outDir "card-shop-prod-$timestamp.sql"

New-Item -ItemType Directory -Force -Path $outDir | Out-Null

if ($UseRailway) {
    $railway = Get-Command railway -ErrorAction SilentlyContinue
    if (-not $railway) {
        Write-Error "Railway CLI not found. Install: npm i -g @railway/cli"
        exit 1
    }
    Write-Host "Creating backup via Railway: $outFile"
    railway run pg_dump `$DATABASE_URL --format=plain --no-owner --no-acl -f $outFile
} else {
    if (-not $DatabaseUrl) {
        Write-Error "DATABASE_URL is not set. Export it from Railway or pass -UseRailway."
        exit 1
    }
    $pgDump = Get-Command pg_dump -ErrorAction SilentlyContinue
    if (-not $pgDump) {
        Write-Error "pg_dump not found in PATH. Install PostgreSQL client tools or use -UseRailway."
        exit 1
    }
    Write-Host "Creating backup: $outFile"
    pg_dump $DatabaseUrl --format=plain --no-owner --no-acl -f $outFile
}

if ($LASTEXITCODE -eq 0) {
    Write-Host "Backup completed successfully."
} else {
    Write-Error "pg_dump failed with exit code $LASTEXITCODE"
    exit $LASTEXITCODE
}
