# Roll back Clerk to Development (pk_test) — required for auth on *.vercel.app without custom domain.
$ErrorActionPreference = 'Stop'
$Root = Split-Path $PSScriptRoot -Parent
$Frontend = Join-Path $Root 'frontend'
$LocalEnv = Join-Path $Frontend '.env.local'
$BuylistConfig = 'C:/users/user1/projects/card-vault-buylist/config.js'

if (-not (Test-Path $LocalEnv)) {
  Write-Error "Missing $LocalEnv"
}

$vars = @{}
Get-Content $LocalEnv | ForEach-Object {
  if ($_ -match '^\s*([A-Z0-9_]+)\s*=\s*(.+)\s*$') {
    $vars[$Matches[1]] = $Matches[2].Trim().Trim('"')
  }
}

$pk = $vars['NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY']
$sk = $vars['CLERK_SECRET_KEY']
if (-not $pk -or -not $pk.StartsWith('pk_test_')) {
  Write-Error 'Expected pk_test in frontend/.env.local'
}
if (-not $sk -or -not $sk.StartsWith('sk_test_')) {
  Write-Error 'Expected sk_test in frontend/.env.local'
}

Write-Host 'Rolling back to pk_test/sk_test...'

Push-Location $Frontend
$prevEap = $ErrorActionPreference
$ErrorActionPreference = 'Continue'
try {
  vercel env rm NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY production --yes 2>&1 | Out-Null
  vercel env add NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY production --value $pk --yes --force 2>&1 | Out-Null
  if ($LASTEXITCODE -ne 0) { throw 'Failed Vercel publishable key' }
  vercel env rm CLERK_SECRET_KEY production --yes 2>&1 | Out-Null
  vercel env add CLERK_SECRET_KEY production --value $sk --yes --force --sensitive 2>&1 | Out-Null
  if ($LASTEXITCODE -ne 0) { throw 'Failed Vercel secret key' }
} finally {
  $ErrorActionPreference = $prevEap
  Pop-Location
}

Push-Location (Join-Path $Root 'backend')
try {
  railway variables --set "CLERK_PUBLISHABLE_KEY=$pk"
  railway variables --set "CLERK_SECRET_KEY=$sk"
} finally {
  Pop-Location
}

$config = Get-Content $BuylistConfig -Raw
$config = $config -replace 'clerkPublishableKey:\s*"pk_[^"]*"', "clerkPublishableKey: `"$pk`""
Set-Content -Path $BuylistConfig -Value $config -NoNewline -Encoding UTF8
Write-Host 'Updated buylist config.js'

python (Join-Path $Root 'scripts/configure_clerk_buylist.py')
Write-Host 'Rollback complete. Redeploy shop, buylist, and Railway.'
