#Requires -Version 5.1
<#
.SYNOPSIS
    Download and install Tesseract OCR (v5.x) with Chinese Simplified language pack.

.DESCRIPTION
    Called by Inno Setup post-install when the "tesseract" task is checked.
    Downloads the UB-Mannheim Tesseract installer and runs it silently.

.EXAMPLE
    .\install_tesseract.ps1
#>

Set-StrictMode -Version Latest
$ErrorActionPreference = "Continue"

Write-Host "Downloading Tesseract OCR (Chinese Simplified support)..." -ForegroundColor Cyan

$TempDir = $env:TEMP
$InstallerUrl = "https://github.com/UB-Mannheim/tesseract/releases/download/v5.3.3.20231005/tesseract-ocr-w64-setup-5.3.3.20231005.exe"
$InstallerPath = Join-Path $TempDir "tesseract-ocr-setup.exe"

# ---------------------------------------------------------------------------
# Download Tesseract installer
# ---------------------------------------------------------------------------
try {
    $wc = New-Object System.Net.WebClient
    $wc.DownloadFile($InstallerUrl, $InstallerPath)
    Write-Host "Download complete: $InstallerPath" -ForegroundColor Green
} catch {
    Write-Host "ERROR: Could not download Tesseract from $InstallerUrl" -ForegroundColor Red
    Write-Host "Details: $_" -ForegroundColor Red
    Write-Host ""
    Write-Host "You can install Tesseract manually later from:" -ForegroundColor Yellow
    Write-Host "  https://github.com/UB-Mannheim/tesseract/wiki" -ForegroundColor Yellow
    Write-Host "  Make sure to select the 'chi_sim' (Chinese Simplified) language pack during install." -ForegroundColor Yellow
    exit 1
}

# ---------------------------------------------------------------------------
# Run Tesseract installer silently with chi_sim language pack
# ---------------------------------------------------------------------------
Write-Host "Installing Tesseract (this may take a minute)..." -ForegroundColor Cyan

try {
    $proc = Start-Process -FilePath $InstallerPath `
        -ArgumentList '/VERYSILENT /NORESTART /COMPONENTS="tesseract,langdata_fast\chi_sim"' `
        -Wait -PassThru

    if ($proc.ExitCode -eq 0) {
        Write-Host "Tesseract installed successfully." -ForegroundColor Green
        Write-Host "OCR will use Windows OCR first; Tesseract is available as a fallback." -ForegroundColor Green
    } else {
        Write-Host "WARNING: Tesseract installer exited with code $($proc.ExitCode)" -ForegroundColor Yellow
        Write-Host "The installation may have partially succeeded. Check Tesseract settings if OCR fails." -ForegroundColor Yellow
    }
} catch {
    Write-Host "ERROR: Could not run Tesseract installer: $_" -ForegroundColor Red
    Write-Host ""
    Write-Host "You can install Tesseract manually later from:" -ForegroundColor Yellow
    Write-Host "  https://github.com/UB-Mannheim/tesseract/wiki" -ForegroundColor Yellow
    Write-Host "  Make sure to select the 'chi_sim' (Chinese Simplified) language pack during install." -ForegroundColor Yellow
    exit 1
} finally {
    # Clean up
    if (Test-Path $InstallerPath) {
        Remove-Item $InstallerPath -Force -ErrorAction SilentlyContinue
    }
}

Write-Host ""
Write-Host "Done!" -ForegroundColor Green
