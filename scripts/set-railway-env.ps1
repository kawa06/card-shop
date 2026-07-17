# Sync shared env vars from frontend/.env.local to Railway (run after `railway login` + `railway link`).
$ErrorActionPreference = 'Stop'
$envFile = Join-Path $PSScriptRoot '..\frontend\.env.local'
if (-not (Test-Path $envFile)) {
  Write-Error "Missing $envFile"
}

$vars = @{}
Get-Content $envFile | ForEach-Object {
  if ($_ -match '^\s*([A-Z0-9_]+)\s*=\s*(.+)\s*$') {
    $vars[$Matches[1]] = $Matches[2].Trim()
  }
}

$toSet = @(
  'AUTH_SYNC_SECRET',
  'CLERK_PUBLISHABLE_KEY',
  'CLERK_SECRET_KEY'
)

foreach ($name in $toSet) {
  if ($name -eq 'CLERK_PUBLISHABLE_KEY') {
    $value = $vars['NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY']
  } else {
    $value = $vars[$name]
  }
  if (-not $value) {
    Write-Warning "Skip $name (not in .env.local)"
    continue
  }
  Write-Host "Setting $name on Railway..."
  railway variables --set "${name}=$value"
}

Write-Host 'Done.'
