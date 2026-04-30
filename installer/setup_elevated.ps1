#Requires -Version 5.1
<#
.SYNOPSIS
    Elevated one-shot OCR setup -- Windows OCR Chinese capability + Tesseract Program Files.
    Called once by the installer (ShellExec runas) or from Preferences.
    Exits 0 in all cases. Log: %TEMP%\zh-en-translator-elevated-setup.log
#>

$ErrorActionPreference = "Continue"

$LogPath = Join-Path $env:TEMP "zh-en-translator-elevated-setup.log"
$LogStream = $null

function Write-Log {
    param([string]$Message, [string]$Color = "White")
    $ts = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Write-Host $Message -ForegroundColor $Color
    if ($LogStream) {
        $LogStream.WriteLine("[$ts] $Message")
        $LogStream.Flush()
    }
}

Write-Host "=== Elevated OCR setup starting (log: $LogPath) ===" -ForegroundColor Cyan

try {

    try {
        $LogStream = [System.IO.StreamWriter]::new($LogPath, $false)
    } catch {
        Write-Host "WARNING: Could not open log file at $LogPath -- $_" -ForegroundColor Yellow
    }

    Write-Log "=== Elevated OCR setup started ===" "Cyan"

    # -------------------------------------------------------------------------
    # Part 1 -- Windows OCR Chinese capability
    # -------------------------------------------------------------------------
    Write-Log "Checking Windows OCR Chinese capabilities..." "Cyan"

    # Enumerate all Language.OCR capabilities that match Chinese (handles locale variants)
    $chineseCaps = @()
    try {
        $chineseCaps = Get-WindowsCapability -Online -ErrorAction Stop |
            Where-Object { $_.Name -like "Language.OCR*zh*" }
    } catch {
        Write-Log "Get-WindowsCapability failed: $_ -- using known names" "Yellow"
    }

    # Fallback to known names if query returned nothing
    if (-not $chineseCaps) {
        $chineseCaps = @(
            [pscustomobject]@{ Name = "Language.OCR~~~~~zh-Hans-CN~0.0.1.0"; State = "NotPresent" },
            [pscustomobject]@{ Name = "Language.OCR~~~~~zh-Hant-TW~0.0.1.0"; State = "NotPresent" }
        )
    }

    $ocrInstalled = $false
    foreach ($cap in $chineseCaps) {
        try {
            if ($cap.State -eq "Installed") {
                Write-Log "Already installed: $($cap.Name)" "Green"
                $ocrInstalled = $true
            } else {
                Write-Log "Installing: $($cap.Name) ..." "Cyan"
                Add-WindowsCapability -Online -Name $cap.Name -ErrorAction Stop | Out-Null
                Write-Log "Installed: $($cap.Name)" "Green"
                $ocrInstalled = $true
            }
        } catch {
            Write-Log "Could not install $($cap.Name): $_" "Yellow"
        }
    }

    if ($ocrInstalled) {
        Write-Log "Windows OCR Chinese: OK" "Green"
    } else {
        Write-Log "WARNING: Could not install Chinese OCR capability. OCR will fall back to Tesseract." "Yellow"
    }

    # -------------------------------------------------------------------------
    # Part 2 -- Tesseract to Program Files (elevated fallback only)
    # -------------------------------------------------------------------------
    $tessExe = "C:\Program Files\Tesseract-OCR\tesseract.exe"
    if (Test-Path $tessExe) {
        Write-Log "Tesseract already at Program Files -- skipping install." "Green"
    } else {
        Write-Log "Tesseract not found at Program Files. Attempting elevated install..." "Cyan"

        $DownloadUrl = $null
        try {
            $GhApi = "https://api.github.com/repos/UB-Mannheim/tesseract/releases/latest"
            $rel = Invoke-RestMethod -Uri $GhApi -Headers @{"User-Agent"="zh-en-translator"} -UseBasicParsing
            $asset = $rel.assets | Where-Object { $_.name -like "tesseract-ocr-w64-setup-*.exe" } | Select-Object -First 1
            if ($asset) {
                $DownloadUrl = $asset.browser_download_url
                Write-Log "Latest release: $($asset.name)" "Cyan"
            }
        } catch {
            Write-Log "GitHub API unavailable: $_" "Yellow"
        }

        if (-not $DownloadUrl) {
            # Pinned UB-Mannheim 5.4.0 (their latest; 5.5.0 is under tesseract-ocr/tesseract not UB-Mannheim)
            $DownloadUrl = "https://github.com/UB-Mannheim/tesseract/releases/download/v5.4.0.20240606/tesseract-ocr-w64-setup-5.4.0.20240606.exe"
            Write-Log "Using pinned fallback UB-Mannheim 5.4.0" "Cyan"
        }

        $InstallerPath = Join-Path $env:TEMP "tesseract-ocr-setup-elevated.exe"
        $TessInstallDir = "C:\Program Files\Tesseract-OCR"
        try {
            Write-Log "Downloading Tesseract installer..." "Cyan"
            (New-Object System.Net.WebClient).DownloadFile($DownloadUrl, $InstallerPath)
            # Tesseract uses NSIS, not Inno Setup. Silent flag is /S; dir is /D= as LAST arg, no quotes.
            $p = Start-Process $InstallerPath -ArgumentList "/S /D=$TessInstallDir" -Wait -PassThru
            if ($p -and $p.ExitCode -eq 0) {
                Write-Log "Tesseract installed to Program Files (exit 0)." "Green"
            } else {
                Write-Log "Tesseract installer exit code: $($p.ExitCode)." "Yellow"
            }
        } catch {
            Write-Log "Tesseract install failed: $_" "Yellow"
        } finally {
            if (Test-Path $InstallerPath) {
                Remove-Item $InstallerPath -Force -ErrorAction SilentlyContinue
            }
        }
    }

    # -------------------------------------------------------------------------
    # Part 3 -- tessdata for Program Files Tesseract (chi_sim + chi_tra)
    # -------------------------------------------------------------------------
    $pfTessData = "C:\Program Files\Tesseract-OCR\tessdata"
    if (Test-Path (Split-Path $pfTessData)) {
        New-Item -ItemType Directory -Force -Path $pfTessData | Out-Null
        # raw.githubusercontent.com resolves Git LFS -- returns real binaries, not pointer stubs.
        # The tessdata_fast releases/download/4.1.0 tag has NO binary assets (only source archives).
        $TESSDATA_BASE = "https://raw.githubusercontent.com/tesseract-ocr/tessdata_fast/main"
        foreach ($fname in @("chi_sim.traineddata", "chi_tra.traineddata")) {
            $dest = Join-Path $pfTessData $fname
            if (-not (Test-Path $dest)) {
                try {
                    Write-Log "Downloading $fname to Program Files tessdata..." "Cyan"
                    (New-Object System.Net.WebClient).DownloadFile("$TESSDATA_BASE/$fname", $dest)
                    $size = (Get-Item $dest -ErrorAction SilentlyContinue).Length / 1MB
                    Write-Log "Downloaded $fname ($([Math]::Round($size, 2)) MB)" "Green"
                } catch {
                    Write-Log "Failed to download ${fname}: $_" "Yellow"
                }
            } else {
                Write-Log "$fname already present in Program Files tessdata." "Green"
            }
        }
    }

    Write-Log "" "White"
    Write-Log "=== Elevated OCR setup complete. Log saved to: $LogPath ===" "Green"

} catch {
    Write-Host "[FATAL] $_" -ForegroundColor Red
    if ($LogStream) { try { $LogStream.WriteLine("[FATAL] $_") } catch {} }
}

if ($LogStream) { $LogStream.Close() }
exit 0
