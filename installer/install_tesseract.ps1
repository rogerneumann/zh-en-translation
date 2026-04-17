#Requires -Version 5.1
<#
.SYNOPSIS
    Download and install Tesseract OCR with Chinese Simplified language data.

.DESCRIPTION
    Tries three approaches in order:
      1. winget  — handles UAC elevation internally (Win 10 1809+ / Win 11)
      2. Direct  — downloads UB-Mannheim installer and runs it
      3. Manual  — opens the download page in the browser if both fail
    Then downloads chi_sim.traineddata directly from tessdata_fast GitHub.
#>

Set-StrictMode -Version Latest
$ErrorActionPreference = "Continue"

$TessSystemDir  = "C:\Program Files\Tesseract-OCR"
$TessUserDir    = "$env:LOCALAPPDATA\Tesseract-OCR"
$TessDataDir    = $null

# ---------------------------------------------------------------------------
# Helper: find tessdata directory after install
# ---------------------------------------------------------------------------
function Find-TessDataDir {
    foreach ($dir in @($TessSystemDir, $TessUserDir)) {
        if (Test-Path "$dir\tessdata") { return "$dir\tessdata" }
    }
    # Registry fallback
    try {
        $reg = Get-ItemProperty "HKLM:\SOFTWARE\Tesseract-OCR" -ErrorAction Stop
        $candidate = Join-Path $reg.InstallDir "tessdata"
        if (Test-Path $candidate) { return $candidate }
    } catch {}
    # User registry
    try {
        $reg = Get-ItemProperty "HKCU:\SOFTWARE\Tesseract-OCR" -ErrorAction Stop
        $candidate = Join-Path $reg.InstallDir "tessdata"
        if (Test-Path $candidate) { return $candidate }
    } catch {}
    return $null
}

# ---------------------------------------------------------------------------
# Attempt 1 — winget (preferred: handles UAC via its own broker service)
# ---------------------------------------------------------------------------
Write-Host "Attempting Tesseract install via winget..." -ForegroundColor Cyan

$WingetOk = $false
try {
    $wgVer = winget --version 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host "winget $wgVer found — installing..." -ForegroundColor Gray
        winget install --id UB-Mannheim.TesseractOCR `
            --silent --accept-package-agreements --accept-source-agreements 2>&1
        if ($LASTEXITCODE -eq 0 -or $LASTEXITCODE -eq -1978335189) {
            # -1978335189 = APPINSTALLER_ERROR_ALREADY_INSTALLED (that's fine)
            Write-Host "Tesseract installed via winget." -ForegroundColor Green
            $WingetOk = $true
        } else {
            Write-Host "winget exited with code $LASTEXITCODE — trying direct install..." -ForegroundColor Yellow
        }
    }
} catch {
    Write-Host "winget not available: $_ — trying direct install..." -ForegroundColor Yellow
}

# ---------------------------------------------------------------------------
# Attempt 2 — Direct download + install (if winget failed/unavailable)
# ---------------------------------------------------------------------------
if (-not $WingetOk) {
    Write-Host ""
    Write-Host "Fetching latest Tesseract release from GitHub..." -ForegroundColor Cyan

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
        if ($asset) { $DownloadUrl = $asset.browser_download_url }
    } catch {}

    if (-not $DownloadUrl) {
        $DownloadUrl = "https://github.com/UB-Mannheim/tesseract/releases/download/v5.5.0.20241111/tesseract-ocr-w64-setup-5.5.0.20241111.exe"
        Write-Host "API unavailable — using pinned 5.5.0 URL." -ForegroundColor Yellow
    }

    Write-Host "Downloading: $DownloadUrl" -ForegroundColor Gray
    try {
        (New-Object System.Net.WebClient).DownloadFile($DownloadUrl, $InstallerPath)
    } catch {
        Write-Host "Download failed: $_" -ForegroundColor Red
        $InstallerPath = $null
    }

    if ($InstallerPath -and (Test-Path $InstallerPath)) {
        # Try elevated install first, then user-level as fallback
        $Installed = $false

        # Elevated (UAC prompt will appear in the foreground)
        try {
            $p = Start-Process $InstallerPath -ArgumentList "/VERYSILENT /NORESTART" `
                -Verb RunAs -Wait -PassThru -ErrorAction Stop
            if ($p.ExitCode -eq 0) { $Installed = $true }
        } catch {}

        # User-level fallback (no UAC, installs to %LOCALAPPDATA%)
        if (-not $Installed) {
            try {
                $p = Start-Process $InstallerPath `
                    -ArgumentList "/VERYSILENT /NORESTART /DIR=""$TessUserDir""" `
                    -Wait -PassThru -ErrorAction Stop
                if ($p.ExitCode -eq 0) { $Installed = $true }
            } catch {}
        }

        Remove-Item $InstallerPath -Force -ErrorAction SilentlyContinue

        if ($Installed) {
            Write-Host "Tesseract installed via direct installer." -ForegroundColor Green
        } else {
            Write-Host "Direct install failed." -ForegroundColor Yellow
        }
    }
}

# ---------------------------------------------------------------------------
# Check whether Tesseract landed anywhere we know about
# ---------------------------------------------------------------------------
$TessDataDir = Find-TessDataDir

if (-not $TessDataDir) {
    Write-Host ""
    Write-Host "Tesseract could not be installed automatically." -ForegroundColor Red
    Write-Host "Opening download page in your browser..." -ForegroundColor Yellow
    Start-Process "https://github.com/UB-Mannheim/tesseract/wiki"
    Write-Host ""
    Write-Host "After installing, download chi_sim.traineddata from:" -ForegroundColor Yellow
    Write-Host "  https://github.com/tesseract-ocr/tessdata_fast/raw/main/chi_sim.traineddata"
    Write-Host "and place it in your Tesseract tessdata folder."
    exit 1
}

Write-Host "tessdata directory: $TessDataDir" -ForegroundColor Green
New-Item -ItemType Directory -Force -Path $TessDataDir | Out-Null

# ---------------------------------------------------------------------------
# Download chi_sim.traineddata directly from tessdata_fast
# ---------------------------------------------------------------------------
Write-Host ""
Write-Host "Downloading chi_sim.traineddata (Chinese Simplified)..." -ForegroundColor Cyan

$ChiSimDest = Join-Path $TessDataDir "chi_sim.traineddata"
try {
    (New-Object System.Net.WebClient).DownloadFile(
        "https://github.com/tesseract-ocr/tessdata_fast/raw/main/chi_sim.traineddata",
        $ChiSimDest
    )
    Write-Host "Installed: $ChiSimDest" -ForegroundColor Green
} catch {
    Write-Host "ERROR downloading chi_sim.traineddata: $_" -ForegroundColor Red
    Write-Host "Download manually from:" -ForegroundColor Yellow
    Write-Host "  https://github.com/tesseract-ocr/tessdata_fast/raw/main/chi_sim.traineddata"
    Write-Host "Place it in: $TessDataDir"
    exit 1
}

Write-Host ""
Write-Host "Tesseract OCR with Chinese Simplified support installed successfully." -ForegroundColor Green
