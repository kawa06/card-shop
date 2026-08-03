# Finish Clerk Production: Google OAuth (requires Google Cloud credentials)
# Usage:
#   $env:GOOGLE_CLIENT_ID='123456789-abc.apps.googleusercontent.com'
#   $env:GOOGLE_CLIENT_SECRET='GOCSPX-...'
#   powershell -ExecutionPolicy Bypass -File .\scripts\setup_clerk_google_oauth_prod.ps1
$ErrorActionPreference = 'Stop'
$Root = Split-Path $PSScriptRoot -Parent
$Frontend = Join-Path $Root 'frontend'
$PatchFile = Join-Path $PSScriptRoot 'clerk-google-credentials.json'
$ProdInstance = 'ins_3Gao4fQ3ZL1I0hTNH6mkc6J9ixh'

$clientId = $env:GOOGLE_CLIENT_ID
$clientSecret = $env:GOOGLE_CLIENT_SECRET
if (-not $clientId -or -not $clientSecret) {
  Write-Error 'Set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET environment variables first.'
}

$payload = @{
  connection_oauth_google = @{
    enabled = $true
    authenticatable = $true
    block_email_subaddresses = $true
    show_account_selector_prompt = $true
    client_id = $clientId
    client_secret = $clientSecret
  }
} | ConvertTo-Json -Depth 5
Set-Content -Path $PatchFile -Value $payload -Encoding UTF8

Push-Location $Frontend
try {
  npx clerk config patch --instance $ProdInstance --file $PatchFile --mode agent
  npx clerk deploy status
} finally {
  Pop-Location
  Remove-Item $PatchFile -Force -ErrorAction SilentlyContinue
}

Write-Host 'Google OAuth enabled on Clerk Production.'
