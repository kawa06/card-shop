# Set buylist Vercel CLERK_PUBLISHABLE_KEY from local config.js (pk_live only).
$ErrorActionPreference = 'Stop'
$BuylistConfig = 'C:/users/user1/projects/card-vault-buylist/config.js'

if (-not (Test-Path $BuylistConfig)) {
  Write-Error "Missing $BuylistConfig"
}

$config = Get-Content $BuylistConfig -Raw
if ($config -notmatch 'clerkPublishableKey:\s*"(pk_(?:live|test)_[^"]+)"') {
  Write-Error 'Expected clerkPublishableKey in config.js'
}
$pk = $Matches[1]

Push-Location 'C:/users/user1/projects/card-vault-buylist'
$prevEap = $ErrorActionPreference
$ErrorActionPreference = 'Continue'
try {
  vercel env rm CLERK_PUBLISHABLE_KEY production --yes 2>&1 | Out-Null
  vercel env add CLERK_PUBLISHABLE_KEY production --value $pk --yes --force 2>&1 | Out-Null
  if ($LASTEXITCODE -ne 0) { throw 'Failed to set CLERK_PUBLISHABLE_KEY on buylist Vercel' }
} finally {
  $ErrorActionPreference = $prevEap
  Pop-Location
}

Write-Host 'Buylist Vercel CLERK_PUBLISHABLE_KEY updated (pk_live).'
