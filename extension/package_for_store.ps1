#requires -Version 5.1
<#
.SYNOPSIS
    Package the DMRE Chrome extension into a zip ready for the Chrome Web Store.

.DESCRIPTION
    Validates manifest.json, swaps `config.prod.js` in as `config.js` inside the
    zip (so the runtime filename stays `config.js`), refuses to build while the
    production URLs still point at localhost or placeholders, and produces a
    clean zip in dist/. Run from the extension/ directory.

.EXAMPLE
    .\package_for_store.ps1
    .\package_for_store.ps1 -AllowLocalhost   # skip the localhost guard for a dev zip
#>
param(
    [switch]$AllowLocalhost
)

$ErrorActionPreference = 'Stop'
Set-Location -Path $PSScriptRoot

# --- 1. Manifest validation ---
$manifest = Get-Content -Raw -Path .\manifest.json | ConvertFrom-Json
if (-not $manifest.version) { throw "manifest.json is missing a version." }
if ($manifest.manifest_version -ne 3) { throw "manifest_version must be 3 for new submissions." }
$version = $manifest.version
Write-Host "Manifest OK: $($manifest.name) v$version"

# --- 2. Required files ---
$required = @('manifest.json', 'config.js', 'config.prod.js', 'background.js', 'content.js', 'popup.html', 'popup.js', 'icons/icon16.png', 'icons/icon48.png', 'icons/icon128.png')
foreach ($f in $required) {
    if (-not (Test-Path $f)) { throw "Missing required file: $f" }
}

# --- 3. Pick which config to ship ---
# Production zips ship config.prod.js renamed to config.js so the runtime
# (popup.html / background.js) keeps loading "config.js" unchanged.
$configToShip = if ($AllowLocalhost) { 'config.js' } else { 'config.prod.js' }
$configContent = Get-Content -Raw -Path $configToShip

if (-not $AllowLocalhost) {
    if ($configContent -match 'localhost|127\.0\.0\.1') {
        throw "$configToShip still points at localhost. Edit BACKEND_URL / DASHBOARD_URL to your production URLs first, or pass -AllowLocalhost for a dev build."
    }
    if ($configContent -match 'CHANGE-ME|example\.com|TODO|REPLACE_ME') {
        throw "$configToShip still contains a placeholder URL. Set real production URLs first."
    }
}

# --- 4. Stage the contents into a temp directory ---
$staging = Join-Path $env:TEMP "dmre-ext-$([guid]::NewGuid().ToString('N'))"
New-Item -ItemType Directory -Path $staging | Out-Null
try {
    # Files that ship as-is.
    $include = @('manifest.json', 'background.js', 'content.js', 'popup.html', 'popup.js')
    foreach ($f in $include) {
        Copy-Item -Path $f -Destination (Join-Path $staging $f)
    }
    Copy-Item -Path 'icons' -Destination (Join-Path $staging 'icons') -Recurse

    # The chosen config (dev or prod) is written into the staging dir AS config.js
    # so runtime loaders don't need to change between dev and store builds.
    Set-Content -Path (Join-Path $staging 'config.js') -Value $configContent -Encoding utf8

    # --- 5. Build the zip ---
    $dist = Join-Path $PSScriptRoot 'dist'
    if (-not (Test-Path $dist)) { New-Item -ItemType Directory -Path $dist | Out-Null }

    $zipName = "dmre-extension-v$version.zip"
    $zipPath = Join-Path $dist $zipName
    if (Test-Path $zipPath) { Remove-Item $zipPath }

    Compress-Archive -Path (Join-Path $staging '*') -DestinationPath $zipPath -CompressionLevel Optimal

    $size = (Get-Item $zipPath).Length
    Write-Host ""
    Write-Host "Package built:" -ForegroundColor Green
    Write-Host "  $zipPath"
    Write-Host "  $([math]::Round($size / 1KB, 1)) KB"
    Write-Host "  shipped config: $configToShip"
    Write-Host ""
    Write-Host "Next steps:"
    Write-Host "  1. Open https://chrome.google.com/webstore/devconsole and click 'New Item'."
    Write-Host "  2. Upload $zipName."
    Write-Host "  3. Fill in the listing using PRIVACY.md and DEPLOY.md as a guide."
}
finally {
    Remove-Item -Path $staging -Recurse -Force -ErrorAction SilentlyContinue
}
