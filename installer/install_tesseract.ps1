#Requires -Version 5.1
<#
.SYNOPSIS
    Download and install Tesseract OCR with Chinese Simplified language data.

.DESCRIPTION
    1. Fetches the latest UB-Mannheim Tesseract release URL from the GitHub API.
    2. Installs Tesseract silently (binary only — no relying on NSIS /COMPONENTS).
    3. Downloads chi_sim.traineddata directly from tessdata_fast GitHub repo
       into the Tesseract tessdata folder, guaranteeing Chinese Simplified support.
#>

Set-StrictMode -Version Latest
$ErrorActionPreference = "Continue"

# ---------------------------------------------------------------------------
# Step 1 — Resolve Tesseract installer URL via GitHub API
# ---------------------------------------------------------------------------
Write-Host "Fetching latest Tesseract release info..." -ForegroundColor Cyan

$TempDir      = $env:TEMP
$InstallerPath = Join-Path $TempDir "tesseract-ocr-setup.exe"
$DownloadUrl   = $null

try {
    $headers = @{ "User-Agent" = "zh-en-translator-installer" }
    $release = Invoke-RestMethod -Uri "https://api.github.com/repos/UB-Mannheim/tesseract/releases/latest" `
                                 -Headers $headers -UseBasicParsing
    $asset = $release.assets | Where-Object { $_.name -like "tesseract-ocr-w64-setup-*.exe" } | Select-Object -First 1
    if ($asset) {
        $DownloadUrl = $asset.browser_download_url
        Write-Host "Found: $($asset.name)" -ForegroundColor Green
    }
} catch {
    Write-Host "GitHub API lookup failed: $_" -ForegroundColor Yellow
}

# Pinned fallback if API is unavailable
if (-not $DownloadUrl) {
    Write-Host "Falling back to pinned Tesseract 5.5.0..." -ForegroundColor Yellow
    $DownloadUrl = "https://github.com/UB-Mannheim/tesseract/releases/download/v5.5.0.20241111/tesseract-ocr-w64-setup-5.5.0.20241111.exe"
}

# ---------------------------------------------------------------------------
# Step 2 — Download Tesseract installer
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
# Step 3 — Install Tesseract silently (binary only, no component selection)
# ---------------------------------------------------------------------------
Write-Host ""
Write-Host "Installing Tesseract..." -ForegroundColor Cyan

try {
    $proc = Start-Process -FilePath $InstallerPath `
        -ArgumentList "/VERYSILENT /NORESTART" `
        -Wait -PassThru

    if ($proc.ExitCode -ne 0) {
        Write-Host "WARNING: Installer exited with code $($proc.ExitCode)" -ForegroundColor Yellow
    } else {
        Write-Host "Tesseract installed." -ForegroundColor Green
    }
} catch {
    Write-Host "ERROR: Could not run Tesseract installer: $_" -ForegroundColor Red
    exit 1
} finally {
    Remove-Item $InstallerPath -Force -ErrorAction SilentlyContinue
}

# ---------------------------------------------------------------------------
# Step 4 — Find the Tesseract tessdata directory
# ---------------------------------------------------------------------------
$TessDataDir = $null
$Candidates = @(
    "C:\Program Files\Tesseract-OCR\tessdata",
    "C:\Program Files (x86)\Tesseract-OCR\tessdata"
)

foreach ($dir in $Candidates) {
    if (Test-Path $dir) {
        $TessDataDir = $dir
        break
    }
}

if (-not $TessDataDir) {
    # Try registry
    try {
        $RegPath = "HKLM:\SOFTWARE\Tesseract-OCR"
        if (Test-Path $RegPath) {
            $InstallDir = (Get-ItemProperty $RegPath).InstallDir
            $TessDataDir = Join-Path $InstallDir "tessdata"
        }
    } catch { }
}

if (-not $TessDataDir) {
    Write-Host "WARNING: Could not locate Tesseract tessdata directory." -ForegroundColor Yellow
    Write-Host "         Download chi_sim.traineddata manually from:" -ForegroundColor Yellow
    Write-Host "         https://github.com/tesseract-ocr/tessdata_fast/raw/main/chi_sim.traineddata"
    Write-Host "         and place it in your Tesseract tessdata folder."
    exit 0
}

Write-Host "Tesseract tessdata directory: $TessDataDir" -ForegroundColor Green

# ---------------------------------------------------------------------------
# Step 5 — Download chi_sim.traineddata directly from tessdata_fast
# ---------------------------------------------------------------------------
Write-Host ""
Write-Host "Downloading Chinese Simplified language data (chi_sim.traineddata)..." -ForegroundColor Cyan

$ChiSimUrl  = "https://github.com/tesseract-ocr/tessdata_fast/raw/main/chi_sim.traineddata"
$ChiSimDest = Join-Path $TessDataDir "chi_sim.traineddata"

try {
    (New-Object System.Net.WebClient).DownloadFile($ChiSimUrl, $ChiSimDest)
    Write-Host "chi_sim.traineddata installed to: $ChiSimDest" -ForegroundColor Green
} catch {
    Write-Host "ERROR: Could not download chi_sim.traineddata: $_" -ForegroundColor Red
    Write-Host ""
    Write-Host "Download manually from:" -ForegroundColor Yellow
    Write-Host "  $ChiSimUrl"
    Write-Host "and place it in: $TessDataDir"
    exit 1
}

Write-Host ""
Write-Host "Tesseract OCR with Chinese Simplified support installed successfully." -ForegroundColor Green
Write-Host "Windows OCR is used first; Tesseract is the OCR fallback."
