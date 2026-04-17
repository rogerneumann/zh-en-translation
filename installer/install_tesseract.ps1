#Requires -Version 5.1
<#
.SYNOPSIS
    Download and install Tesseract OCR (v5.x) with Chinese Simplified language pack.

.DESCRIPTION
    Called by Inno Setup post-install when the "tesseract" task is checked.
    Fetches the latest UB-Mannheim release URL from the GitHub API, downloads the
    installer, and runs it silently with the chi_sim language pack.
#>

Set-StrictMode -Version Latest
$ErrorActionPreference = "Continue"

Write-Host "Fetching latest Tesseract release info..." -ForegroundColor Cyan

$TempDir = $env:TEMP
$InstallerPath = Join-Path $TempDir "tesseract-ocr-setup.exe"

# ---------------------------------------------------------------------------
# Resolve download URL via GitHub releases API (always gets the latest version)
# ---------------------------------------------------------------------------
$DownloadUrl = $null
try {
    $ApiUrl = "https://api.github.com/repos/UB-Mannheim/tesseract/releases/latest"
    $headers = @{ "User-Agent" = "zh-en-translator-installer" }
    $release = Invoke-RestMethod -Uri $ApiUrl -Headers $headers -UseBasicParsing
    $asset = $release.assets | Where-Object { $_.name -like "tesseract-ocr-w64-setup-*.exe" } | Select-Object -First 1
    if ($asset) {
        $DownloadUrl = $asset.browser_download_url
        Write-Host "Found: $($asset.name)" -ForegroundColor Green
    }
} catch {
    Write-Host "GitHub API lookup failed: $_" -ForegroundColor Yellow
}

# Fallback: known-good pinned URL if API is unavailable
if (-not $DownloadUrl) {
    Write-Host "Falling back to pinned Tesseract 5.5.0 URL..." -ForegroundColor Yellow
    $DownloadUrl = "https://github.com/UB-Mannheim/tesseract/releases/download/v5.5.0.20241111/tesseract-ocr-w64-setup-5.5.0.20241111.exe"
}

# ---------------------------------------------------------------------------
# Download Tesseract installer
# ---------------------------------------------------------------------------
Write-Host "Downloading Tesseract from:" -ForegroundColor Cyan
Write-Host "  $DownloadUrl"

try {
    $wc = New-Object System.Net.WebClient
    $wc.DownloadFile($DownloadUrl, $InstallerPath)
    Write-Host "Download complete." -ForegroundColor Green
} catch {
    Write-Host "ERROR: Download failed: $_" -ForegroundColor Red
    Write-Host ""
    Write-Host "Install Tesseract manually from:" -ForegroundColor Yellow
    Write-Host "  https://github.com/UB-Mannheim/tesseract/wiki"
    Write-Host "  Select the 'chi_sim' (Chinese Simplified) language pack during setup."
    exit 1
}

# ---------------------------------------------------------------------------
# Run Tesseract installer silently with chi_sim language pack
# ---------------------------------------------------------------------------
Write-Host "Installing Tesseract with Chinese Simplified (chi_sim) support..." -ForegroundColor Cyan

try {
    $proc = Start-Process -FilePath $InstallerPath `
        -ArgumentList '/VERYSILENT /NORESTART /COMPONENTS="tesseract,langdata_fast\chi_sim"' `
        -Wait -PassThru

    if ($proc.ExitCode -eq 0) {
        Write-Host "Tesseract installed successfully." -ForegroundColor Green
        Write-Host "Windows OCR is used first; Tesseract is the OCR fallback."
    } else {
        Write-Host "WARNING: Installer exited with code $($proc.ExitCode)." -ForegroundColor Yellow
        Write-Host "OCR may still work if Tesseract partially installed."
    }
} catch {
    Write-Host "ERROR: Could not run Tesseract installer: $_" -ForegroundColor Red
    Write-Host ""
    Write-Host "Install Tesseract manually from:" -ForegroundColor Yellow
    Write-Host "  https://github.com/UB-Mannheim/tesseract/wiki"
    exit 1
} finally {
    if (Test-Path $InstallerPath) {
        Remove-Item $InstallerPath -Force -ErrorAction SilentlyContinue
    }
}

Write-Host ""
Write-Host "Done!" -ForegroundColor Green
