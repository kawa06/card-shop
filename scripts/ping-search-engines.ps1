#!/usr/bin/env pwsh
# Notify search engines that the sitemap has been updated.
# Run after deploy: pwsh scripts/ping-search-engines.ps1

param(
  [string]$SiteUrl = $(if ($env:NEXT_PUBLIC_SITE_URL) { $env:NEXT_PUBLIC_SITE_URL } else { 'https://frontend-one-topaz-20.vercel.app' })
)

$SiteUrl = $SiteUrl.TrimEnd('/')
$sitemapUrl = [uri]::EscapeDataString("$SiteUrl/sitemap.xml")

$endpoints = @(
  "https://www.google.com/ping?sitemap=$sitemapUrl",
  "https://www.bing.com/ping?sitemap=$sitemapUrl"
)

foreach ($url in $endpoints) {
  try {
    $response = Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 30
    Write-Host "OK $($response.StatusCode): $url"
  } catch {
    Write-Host "WARN: $url — $($_.Exception.Message)"
  }
}

Write-Host ""
Write-Host "Next: submit sitemap in Google Search Console"
Write-Host "  https://search.google.com/search-console"
Write-Host "  Sitemap URL: $SiteUrl/sitemap.xml"
