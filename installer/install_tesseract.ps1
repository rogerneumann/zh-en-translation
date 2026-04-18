#Requires -Version 5.1
<#
.SYNOPSIS
    Install Tesseract OCR + Chinese Simplified language data.
    Exits 0 in all cases — OCR is optional, failures are informational only.
#>

Set-StrictMode -Version Latest
$ErrorActionPreference = "Continue"

# ---------------------------------------------------------------------------
# Helper: locate tessdata directory from any known install location
# ---------------------------------------------------------------------------
function Find-TessDataDir {
    $candidates = @(
        "C:\Program Files\Tesseract-OCR\tessdata",
        "C:\Program Files (x86)\Tesseract-OCR\tessdata",
        "$env:LOCALAPPDATA\Programs\Tesseract-OCR\tessdata",   # winget user install
        "$env:LOCALAPPDATA\Tesseract-OCR\tessdata",
        "$env:APPDATA\Tesseract-OCR\tessdata"
    )
    foreach ($d in $candidates) {
        if (Test-Path $d) { return $d }
    }
    # Registry (system + user)
    foreach ($hive in @("HKLM:\SOFTWARE\Tesseract-OCR","HKCU:\SOFTWARE\Tesseract-OCR")) {
        try {
            $reg = Get-ItemProperty $hive -ErrorAction Stop
            $d = Join-Path $reg.InstallDir "tessdata"
            if (Test-Path $d) { return $d }
        } catch {}
    }
    # Last resort: find tesseract.exe on PATH and derive from there
    try {
        $exe = (Get-Command tesseract -ErrorAction Stop).Source
        $d = Join-Path (Split-Path $exe) "tessdata"
        if (Test-Path $d) { return $d }
    } catch {}
    return $null
}

# ---------------------------------------------------------------------------
# Step 1 — Skip install if Tesseract already present
# ---------------------------------------------------------------------------
$TessDataDir = Find-TessDataDir
if ($TessDataDir) {
    Write-Host "Tesseract already installed. tessdata: $TessDataDir" -ForegroundColor Green
} else {
    # -----------------------------------------------------------------------
    # Attempt A — winget (handles UAC via its own broker, works non-elevated)
    # -----------------------------------------------------------------------
    Write-Host "Attempting Tesseract install via winget..." -ForegroundColor Cyan
    $WingetOk = $false
    try {
        winget --version 2>&1 | Out-Null
        if ($LASTEXITCODE -eq 0) {
            winget install --id UB-Mannheim.TesseractOCR `
                --silent --accept-package-agreements --accept-source-agreements `
                --scope user 2>&1
            # 0 = success; -1978335189 = already installed
            if ($LASTEXITCODE -eq 0 -or $LASTEXITCODE -eq -1978335189) {
                Write-Host "winget install succeeded." -ForegroundColor Green
                $WingetOk = $true
            }
        }
    } catch {}

    if (-not $WingetOk) {
        # -------------------------------------------------------------------
        # Attempt B — direct download + silent install
        # -------------------------------------------------------------------
        Write-Host "winget unavailable or failed — trying direct install..." -ForegroundColor Yellow
        $TempDir       = $env:TEMP
        $InstallerPath = Join-Path $TempDir "tesseract-ocr-setup.exe"
        $DownloadUrl   = $null

        try {
            $rel = Invoke-RestMethod `
                -Uri "https://api.github.com/repos/UB-Mannheim/tesseract/releases/latest" `
                -Headers @{"User-Agent"="zh-en-translator"} -UseBasicParsing
            $asset = $rel.assets | Where-Object { $_.name -like "tesseract-ocr-w64-setup-*.exe" } | Select-Object -First 1
            if ($asset) { $DownloadUrl = $asset.browser_download_url }
        } catch {}
        if (-not $DownloadUrl) {
            $DownloadUrl = "https://github.com/UB-Mannheim/tesseract/releases/download/v5.5.0.20241111/tesseract-ocr-w64-setup-5.5.0.20241111.exe"
        }

        try {
            (New-Object System.Net.WebClient).DownloadFile($DownloadUrl, $InstallerPath)
            # Try user-level install (no UAC needed)
            $p = Start-Process $InstallerPath `
                -ArgumentList "/VERYSILENT /NORESTART /DIR=""$env:LOCALAPPDATA\Programs\Tesseract-OCR""" `
                -Wait -PassThru
            if ($p.ExitCode -eq 0) {
                Write-Host "Direct install to LocalAppData succeeded." -ForegroundColor Green
            }
        } catch {
            Write-Host "Direct install failed: $_" -ForegroundColor Yellow
        } finally {
            Remove-Item $InstallerPath -Force -ErrorAction SilentlyContinue
        }
    }

    # Give installer a moment to finish writing files
    Start-Sleep -Seconds 2
    $TessDataDir = Find-TessDataDir
}

# ---------------------------------------------------------------------------
# Step 2 — Download chi_sim.traineddata
# ---------------------------------------------------------------------------
if ($TessDataDir) {
    Write-Host "Downloading chi_sim.traineddata..." -ForegroundColor Cyan
    New-Item -ItemType Directory -Force -Path $TessDataDir | Out-Null
    $dest = Join-Path $TessDataDir "chi_sim.traineddata"
    try {
        (New-Object System.Net.WebClient).DownloadFile(
            "https://github.com/tesseract-ocr/tessdata_fast/raw/main/chi_sim.traineddata",
            $dest
        )
        Write-Host "chi_sim installed: $dest" -ForegroundColor Green
    } catch {
        Write-Host "WARNING: chi_sim download failed: $_" -ForegroundColor Yellow
        Write-Host "Download manually: https://github.com/tesseract-ocr/tessdata_fast/raw/main/chi_sim.traineddata"
        Write-Host "Place in: $TessDataDir"
    }
} else {
    Write-Host ""
    Write-Host "Tesseract could not be installed automatically." -ForegroundColor Yellow
    Write-Host "Install manually: https://github.com/UB-Mannheim/tesseract/wiki" -ForegroundColor Yellow
    Write-Host "Then download chi_sim.traineddata from:" -ForegroundColor Yellow
    Write-Host "  https://github.com/tesseract-ocr/tessdata_fast/raw/main/chi_sim.traineddata"
    Write-Host "and place it in your Tesseract tessdata folder."
    Start-Process "https://github.com/UB-Mannheim/tesseract/wiki"
}

# Always exit 0 — Tesseract is optional; Windows OCR is the primary engine
exit 0
