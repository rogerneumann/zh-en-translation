#Requires -Version 5.1
<#
.SYNOPSIS
    Download and install Tesseract OCR with Chinese Simplified language data.

.DESCRIPTION
    1. Fetches the latest UB-Mannheim Tesseract release URL from the GitHub API.
    2. Tries elevated install (UAC prompt) to C:\Program Files\Tesseract-OCR.
       Falls back to user-level install to %LOCALAPPDATA%\Tesseract-OCR if UAC fails.
    3. Downloads chi_sim.traineddata directly from tessdata_fast GitHub repo.
#>

Set-StrictMode -Version Latest
$ErrorActionPreference = "Continue"

# ---------------------------------------------------------------------------
# Step 1 — Resolve Tesseract installer URL via GitHub API
# ---------------------------------------------------------------------------
Write-Host "Fetching latest Tesseract release info..." -ForegroundColor Cyan

$TempDir       = $env:TEMP
$InstallerPath = Join-Path $TempDir "tesseract-ocr-setup.exe"
$DownloadUrl   = $null

try {
    $headers = @{ "User-Agent" = "zh-en-translator-installer" }
    $release = Invoke-RestMethod `
        -Uri "https://api.github.com/repos/UB-Mannheim/tesseract/releases/latest" `
        -Headers $headers -UseBasicParsing
    $asset = $release.assets |
        Where-Object { $_.name -like "tesseract-ocr-w64-setup-*.exe" } |
        Select-Object -First 1
    if ($asset) {
        $DownloadUrl = $asset.browser_download_url
        Write-Host "Found: $($asset.name)" -ForegroundColor Green
    }
} catch {
    Write-Host "GitHub API lookup failed: $_" -ForegroundColor Yellow
}

if (-not $DownloadUrl) {
    Write-Host "Falling back to pinned Tesseract 5.5.0..." -ForegroundColor Yellow
    $DownloadUrl = "https://github.com/UB-Mannheim/tesseract/releases/download/v5.5.0.20241111/tesseract-ocr-w64-setup-5.5.0.20241111.exe"
}

# ---------------------------------------------------------------------------
# Step 2 — Download installer
# ---------------------------------------------------------------------------
Write-Host ""
Write-Host "Downloading Tesseract installer..." -ForegroundColor Cyan
Write-Host "  $DownloadUrl"

try {
    (New-Object System.Net.WebClient).DownloadFile($DownloadUrl, $InstallerPath)
    Write-Host "Download complete." -ForegroundColor Green
} catch {
    Write-Host "ERROR: Download failed: $_" -ForegroundColor Red
    Write-Host "Install Tesseract manually from: https://github.com/UB-Mannheim/tesseract/wiki"
    exit 1
}

# ---------------------------------------------------------------------------
# Step 3 — Install Tesseract
# First attempt: elevated install to Program Files (UAC prompt will appear).
# Fallback:      user-level install to %LOCALAPPDATA%\Tesseract-OCR (no UAC).
# ---------------------------------------------------------------------------
Write-Host ""
Write-Host "Installing Tesseract (a UAC prompt may appear)..." -ForegroundColor Cyan

$SystemInstallDir = "C:\Program Files\Tesseract-OCR"
$UserInstallDir   = "$env:LOCALAPPDATA\Tesseract-OCR"
$TessDataDir      = $null

# Attempt 1: elevated install — triggers UAC so it can write to Program Files
try {
    $proc = Start-Process -FilePath $InstallerPath `
        -ArgumentList "/VERYSILENT /NORESTART" `
        -Verb RunAs `
        -Wait -PassThru

    if ($proc.ExitCode -eq 0 -and (Test-Path $SystemInstallDir)) {
        Write-Host "Tesseract installed to $SystemInstallDir" -ForegroundColor Green
        $TessDataDir = "$SystemInstallDir\tessdata"
    } else {
        Write-Host "Elevated install returned code $($proc.ExitCode) — trying user-level install..." -ForegroundColor Yellow
    }
} catch {
    Write-Host "Elevated install failed ($_) — trying user-level install..." -ForegroundColor Yellow
}

# Attempt 2: user-level install to %LOCALAPPDATA% (no admin needed)
if (-not $TessDataDir) {
    try {
        $proc = Start-Process -FilePath $InstallerPath `
            -ArgumentList "/VERYSILENT /NORESTART /DIR=""$UserInstallDir""" `
            -Wait -PassThru

        if ($proc.ExitCode -eq 0 -and (Test-Path $UserInstallDir)) {
            Write-Host "Tesseract installed to $UserInstallDir" -ForegroundColor Green
            $TessDataDir = "$UserInstallDir\tessdata"
        } else {
            Write-Host "ERROR: User-level install also failed (exit $($proc.ExitCode))." -ForegroundColor Red
        }
    } catch {
        Write-Host "ERROR: Could not run Tesseract installer: $_" -ForegroundColor Red
    }
}

Remove-Item $InstallerPath -Force -ErrorAction SilentlyContinue

if (-not $TessDataDir) {
    Write-Host ""
    Write-Host "Tesseract could not be installed automatically." -ForegroundColor Red
    Write-Host "Install manually from: https://github.com/UB-Mannheim/tesseract/wiki" -ForegroundColor Yellow
    Write-Host "Select the 'chi_sim' (Chinese Simplified) language pack during setup." -ForegroundColor Yellow
    exit 1
}

# Ensure tessdata folder exists
New-Item -ItemType Directory -Force -Path $TessDataDir | Out-Null

# ---------------------------------------------------------------------------
# Step 4 — Download chi_sim.traineddata from tessdata_fast
# ---------------------------------------------------------------------------
Write-Host ""
Write-Host "Downloading Chinese Simplified language data (chi_sim.traineddata)..." -ForegroundColor Cyan

$ChiSimUrl  = "https://github.com/tesseract-ocr/tessdata_fast/raw/main/chi_sim.traineddata"
$ChiSimDest = Join-Path $TessDataDir "chi_sim.traineddata"

try {
    (New-Object System.Net.WebClient).DownloadFile($ChiSimUrl, $ChiSimDest)
    Write-Host "Installed: $ChiSimDest" -ForegroundColor Green
} catch {
    Write-Host "ERROR: Could not download chi_sim.traineddata: $_" -ForegroundColor Red
    Write-Host "Download manually from: $ChiSimUrl" -ForegroundColor Yellow
    Write-Host "Place it in: $TessDataDir" -ForegroundColor Yellow
    exit 1
}

Write-Host ""
Write-Host "Tesseract OCR with Chinese Simplified support installed successfully." -ForegroundColor Green
Write-Host "Windows OCR is used first; Tesseract is the OCR fallback."
