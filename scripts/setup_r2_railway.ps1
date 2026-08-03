# Setup Cloudflare R2 for buyback KYC storage and push vars to Railway.
#
# Recommended (paste Cloudflare values into env FIRST, then run):
#   $env:R2_ACCOUNT_ID='5b536e63c43501107c034ea91f668c0c'
#   $env:R2_ACCESS_KEY_ID='<from Cloudflare R2 token screen>'
#   $env:R2_SECRET_ACCESS_KEY='<from Cloudflare R2 token screen>'
#   powershell -ExecutionPolicy Bypass -File .\scripts\setup_r2_railway.ps1
#
# Do NOT paste shell commands at the prompts. Only paste the token values from Cloudflare.

$ErrorActionPreference = 'Stop'
$DefaultAccountId = '5b536e63c43501107c034ea91f668c0c'
$BucketName = if ($env:R2_BUCKET_NAME) { $env:R2_BUCKET_NAME } else { 'krx-buyback-kyc' }
$RepoRoot = Split-Path -Parent $PSScriptRoot
$BackendDir = Join-Path $RepoRoot 'backend'

function Get-WranglerAccountId {
  $whoami = npx wrangler whoami 2>&1 | Out-String
  if ($whoami -match 'not authenticated') { return $null }
  foreach ($line in ($whoami -split "`n")) {
    if ($line -match 'Account ID:\s*(\S+)') { return $Matches[1] }
  }
  return $null
}

function Test-LooksLikeCommand([string]$Value) {
  if ([string]::IsNullOrWhiteSpace($Value)) { return $true }
  $v = $Value.Trim().ToLower()
  return (
    $v -match '^(cd|powershell|npm|npx|railway|python)\s' -or
    $v -match '\\scripts\\' -or
    $v -match 'executionpolicy'
  )
}

function Read-Required([string]$Label) {
  while ($true) {
    $value = Read-Host $Label
    $value = $value.Trim()
    if ([string]::IsNullOrWhiteSpace($value)) {
      Write-Host 'Empty input. Paste the value from Cloudflare, not a shell command.' -ForegroundColor Yellow
      continue
    }
    if (Test-LooksLikeCommand $value) {
      Write-Host 'That looks like a command, not a token. Open Cloudflare R2 -> Manage R2 API Tokens and copy Access Key ID / Secret.' -ForegroundColor Yellow
      continue
    }
    return $value
  }
}

$accountId = $env:R2_ACCOUNT_ID
if (-not $accountId) { $accountId = Get-WranglerAccountId }
if (-not $accountId) { $accountId = $DefaultAccountId }
Write-Host "Using R2_ACCOUNT_ID: $accountId"

$wranglerOk = -not ((npx wrangler whoami 2>&1 | Out-String) -match 'not authenticated')
if ($wranglerOk) {
  Write-Host "Ensuring R2 bucket exists: $BucketName"
  $bucketList = npx wrangler r2 bucket list 2>&1 | Out-String
  if ($bucketList -notmatch [regex]::Escape($BucketName)) {
    npx wrangler r2 bucket create $BucketName
  } else {
    Write-Host 'Bucket already exists.'
  }
}

$accessKey = $env:R2_ACCESS_KEY_ID
$secretKey = $env:R2_SECRET_ACCESS_KEY
if (-not $accessKey -or -not $secretKey) {
  Write-Host ''
  Write-Host 'Paste ONLY the two values from Cloudflare after creating the R2 API token.'
  Write-Host 'Cloudflare: Dashboard -> R2 -> Manage R2 API Tokens -> Create API token'
  Write-Host "Bucket: $BucketName / Permission: Object Read and Write"
  Write-Host ''
}
if (-not $accessKey) { $accessKey = Read-Required 'R2_ACCESS_KEY_ID' }
if (-not $secretKey) {
  $secure = Read-Host 'R2_SECRET_ACCESS_KEY' -AsSecureString
  if ($secure.Length -eq 0) {
    throw 'R2_SECRET_ACCESS_KEY is empty. Create a new R2 API token in Cloudflare and paste the Secret Access Key.'
  }
  $secretKey = [Runtime.InteropServices.Marshal]::PtrToStringAuto(
    [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
  )
  if (Test-LooksLikeCommand $secretKey) {
    throw 'R2_SECRET_ACCESS_KEY looks invalid. Paste the Secret Access Key from Cloudflare.'
  }
}

$normalizedAccess = ($accessKey -replace '-', '').Trim().ToLower()
if ($normalizedAccess.Length -ne 32) {
  throw "R2_ACCESS_KEY_ID must be exactly 32 characters (Cloudflare R2 -> Manage R2 API Tokens). Current length: $($normalizedAccess.Length)"
}
$accessKey = $normalizedAccess

Write-Host 'Setting Railway variables...'
Push-Location $BackendDir
try {
  railway variable set "R2_ACCOUNT_ID=$accountId" --skip-deploys
  railway variable set "R2_ACCESS_KEY_ID=$accessKey" --skip-deploys
  $secretKey | railway variable set R2_SECRET_ACCESS_KEY --stdin --skip-deploys
  railway variable set "R2_BUCKET_NAME=$BucketName" --skip-deploys
  Write-Host 'Triggering Railway redeploy...'
  railway up --detach
} finally {
  Pop-Location
}

Write-Host "Done. Railway R2 vars set (bucket: $BucketName)."
