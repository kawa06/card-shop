# KRX Card Shop — manual PostgreSQL backup (read-only dump)
# Usage:
#   1. Set DATABASE_URL from Railway (do NOT commit this value)
#   2. Run: .\scripts\db_backup.ps1
#
# Requires: pg_dump in PATH

param(
    [string]$DatabaseUrl = $env:DATABASE_URL
)

if (-not $DatabaseUrl) {
    Write-Error "DATABASE_URL is not set. Export it from Railway first."
    exit 1
}

$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$outDir = Join-Path $PSScriptRoot "..\backups"
$outFile = Join-Path $outDir "card-shop-prod-$timestamp.sql"

New-Item -ItemType Directory -Force -Path $outDir | Out-Null

Write-Host "Creating backup: $outFile"
pg_dump $DatabaseUrl --format=plain --no-owner --no-acl -f $outFile

if ($LASTEXITCODE -eq 0) {
    Write-Host "Backup completed successfully."
} else {
    Write-Error "pg_dump failed with exit code $LASTEXITCODE"
    exit $LASTEXITCODE
}
