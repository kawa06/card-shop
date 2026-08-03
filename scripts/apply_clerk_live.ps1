# Apply already-pulled Clerk production keys (.env.clerk.prod) to all services.
$ErrorActionPreference = 'Stop'
$Root = Split-Path $PSScriptRoot -Parent
$Frontend = Join-Path $Root 'frontend'
$BuylistConfig = 'C:/users/user1/projects/card-vault-buylist/config.js'
$ClerkEnvFile = Join-Path $Frontend '.env.clerk.prod'

if (-not (Test-Path $ClerkEnvFile)) {
  Write-Error "Missing $ClerkEnvFile. Run: clerk env pull --instance ins_3Gao4fQ3ZL1I0hTNH6mkc6J9ixh --file .env.clerk.prod --mode agent"
}

$vars = @{}
Get-Content $ClerkEnvFile | ForEach-Object {
  if ($_ -match '^\s*([A-Z0-9_]+)\s*=\s*(.+)\s*$') {
    $vars[$Matches[1]] = $Matches[2].Trim().Trim('"')
  }
}

$pk = $vars['NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY']
$sk = $vars['CLERK_SECRET_KEY']
if (-not $pk -or -not $pk.StartsWith('pk_live_')) {
  Write-Error "Expected pk_live publishable key in $ClerkEnvFile"
}
if (-not $sk -or -not $sk.StartsWith('sk_live_')) {
  Write-Error "Expected sk_live secret key in $ClerkEnvFile"
}

Write-Host 'Keys OK (pk_live/sk_live)'

Write-Host 'Updating Vercel Production env...'
Push-Location $Frontend
$prevEap = $ErrorActionPreference
$ErrorActionPreference = 'Continue'
try {
  vercel env rm NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY production --yes 2>&1 | Out-Null
  vercel env add NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY production --value $pk --yes --force 2>&1 | Out-Null
  if ($LASTEXITCODE -ne 0) { throw 'Failed to set NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY on Vercel' }
  vercel env rm CLERK_SECRET_KEY production --yes 2>&1 | Out-Null
  vercel env add CLERK_SECRET_KEY production --value $sk --yes --force --sensitive 2>&1 | Out-Null
  if ($LASTEXITCODE -ne 0) { throw 'Failed to set CLERK_SECRET_KEY on Vercel' }
} finally {
  $ErrorActionPreference = $prevEap
  Pop-Location
}

Write-Host 'Updating Railway env...'
Push-Location (Join-Path $Root 'backend')
try {
  railway variables --set "CLERK_PUBLISHABLE_KEY=$pk"
  railway variables --set "CLERK_SECRET_KEY=$sk"
} finally {
  Pop-Location
}

Write-Host 'Updating buylist Vercel Production env (card-vault-public)...'
Push-Location 'C:/users/user1/projects/card-vault-buylist'
$prevEap2 = $ErrorActionPreference
$ErrorActionPreference = 'Continue'
try {
  vercel env rm CLERK_PUBLISHABLE_KEY production --yes 2>&1 | Out-Null
  vercel env add CLERK_PUBLISHABLE_KEY production --value $pk --yes --force 2>&1 | Out-Null
  if ($LASTEXITCODE -ne 0) { throw 'Failed to set CLERK_PUBLISHABLE_KEY on buylist Vercel' }
} finally {
  $ErrorActionPreference = $prevEap2
  Pop-Location
}

Write-Host 'Updating buylist config.js...'
if (-not (Test-Path $BuylistConfig)) {
  Write-Error "Missing buylist config: $BuylistConfig"
}
$config = Get-Content $BuylistConfig -Raw
$config = $config -replace 'clerkPublishableKey:\s*"pk_[^"]*"', "clerkPublishableKey: `"$pk`""
Set-Content -Path $BuylistConfig -Value $config -NoNewline -Encoding UTF8

Write-Host 'Configuring Clerk Production allowed origins for buylist...'
$localEnv = Join-Path $Frontend '.env.local'
$backup = Get-Content $localEnv -Raw
try {
  $newLocal = $backup -replace '(?m)^NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=.*$', "NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=$pk"
  $newLocal = $newLocal -replace '(?m)^CLERK_SECRET_KEY=.*$', "CLERK_SECRET_KEY=$sk"
  Set-Content -Path $localEnv -Value $newLocal -NoNewline -Encoding UTF8
  python (Join-Path $Root 'scripts/configure_clerk_buylist.py')
  python (Join-Path $Root 'scripts/configure_clerk_production.py')
} finally {
  Set-Content -Path $localEnv -Value $backup -NoNewline -Encoding UTF8
}

Remove-Item $ClerkEnvFile -Force
Write-Host 'Apply complete.'
