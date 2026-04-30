#Requires -Version 5.1
<#
.SYNOPSIS
    Install Tesseract OCR (user-level) + Chinese Simplified/Traditional language data.
    Does NOT require administrator rights -- installs to LocalAppData or via winget.
    For a system-wide install to Program Files, run setup_elevated.ps1 instead.
    Exits 0 in all cases. Log: %TEMP%\zh-en-translator-elevated-setup.log
#>

$ErrorActionPreference = "Continue"

# Set up logging
$LogPath = Join-Path $env:TEMP "zh-en-translator-elevated-setup.log"
$LogStream = [System.IO.StreamWriter]::new($LogPath, $false)

function Log-Message {
    param([string]$Message, [string]$Color = "White")
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $logEntry = "[$timestamp] $Message"
    Write-Host $Message -ForegroundColor $Color
    $LogStream.WriteLine($logEntry)
    $LogStream.Flush()
}

function Log-Error {
    param([string]$Message)
    Log-Message $Message "Red"
}

function Log-Success {
    param([string]$Message)
    Log-Message $Message "Green"
}

function Log-Info {
    param([string]$Message)
    Log-Message $Message "Cyan"
}

# ---------------------------------------------------------------------------
# Helper: locate tessdata directory from any known install location
# ---------------------------------------------------------------------------
function Find-TessDataDir {
    $candidates = @(
        "C:\Program Files\Tesseract-OCR\tessdata",
        "C:\Program Files (x86)\Tesseract-OCR\tessdata",
        "$env:LOCALAPPDATA\Programs\Tesseract-OCR\tessdata",
        "$env:LOCALAPPDATA\Tesseract-OCR\tessdata",
        "$env:APPDATA\Tesseract-OCR\tessdata"
    )
    foreach ($d in $candidates) {
        if (Test-Path $d) { return $d }
    }
    foreach ($hive in @("HKLM:\SOFTWARE\Tesseract-OCR","HKCU:\SOFTWARE\Tesseract-OCR")) {
        try {
            $reg = Get-ItemProperty $hive -ErrorAction Stop
            $d = Join-Path $reg.InstallDir "tessdata"
            if (Test-Path $d) { return $d }
        } catch {}
    }
    try {
        $exe = (Get-Command tesseract -ErrorAction Stop).Source
        $d = Join-Path (Split-Path $exe) "tessdata"
        if (Test-Path $d) { return $d }
    } catch {}
    return $null
}

# ---------------------------------------------------------------------------
# Main -- wrapped so any unexpected error still reaches exit 0
# ---------------------------------------------------------------------------
try {

    # Step 1 -- Skip if already installed
    $TessDataDir = Find-TessDataDir
    if ($TessDataDir) {
        Log-Success "Tesseract already installed. tessdata: $TessDataDir"
    } else {
        # Attempt A -- winget (no UAC required)
        Log-Info "Attempting Tesseract install via winget..."
        $WingetOk = $false
        try {
            winget --version 2>&1 | Out-Null
            if ($LASTEXITCODE -eq 0) {
                Log-Info "winget is available; installing UB-Mannheim.TesseractOCR..."
                winget install --id UB-Mannheim.TesseractOCR `
                    --silent --accept-package-agreements --accept-source-agreements `
                    2>&1 | ForEach-Object { Log-Message $_ }
                # 0 = success; -1978335189 = already installed
                if ($LASTEXITCODE -eq 0 -or $LASTEXITCODE -eq -1978335189) {
                    Log-Success "winget install succeeded."
                    $WingetOk = $true
                } else {
                    Log-Error "winget install failed with exit code: $LASTEXITCODE"
                }
            } else {
                Log-Error "winget --version check failed; skipping winget install."
            }
        } catch {
            Log-Error "Exception during winget attempt: $_"
        }

        if (-not $WingetOk) {
            # Attempt B -- direct download + silent install to LocalAppData (no UAC)
            Log-Info "winget unavailable or failed -- trying direct install to LocalAppData..."
            $InstallerPath = Join-Path $env:TEMP "tesseract-ocr-setup.exe"
            $DownloadUrl   = $null

            try {
                Log-Info "Querying GitHub API for latest Tesseract release..."
                $rel = Invoke-RestMethod `
                    -Uri "https://api.github.com/repos/UB-Mannheim/tesseract/releases/latest" `
                    -Headers @{"User-Agent"="zh-en-translator"} -UseBasicParsing
                $asset = $rel.assets |
                    Where-Object { $_.name -like "tesseract-ocr-w64-setup-*.exe" } |
                    Select-Object -First 1
                if ($asset) {
                    $DownloadUrl = $asset.browser_download_url
                    Log-Info "Found latest release: $($asset.name)"
                }
            } catch {
                Log-Error "GitHub API query failed: $_"
            }

            if (-not $DownloadUrl) {
                # Pinned UB-Mannheim 5.4.0 (latest in their repo; 5.5.0 lives under tesseract-ocr/tesseract)
                $DownloadUrl = "https://github.com/UB-Mannheim/tesseract/releases/download/v5.4.0.20240606/tesseract-ocr-w64-setup-5.4.0.20240606.exe"
                Log-Info "Using pinned fallback UB-Mannheim 5.4.0"
            }

            try {
                Log-Info "Downloading Tesseract from: $DownloadUrl"
                (New-Object System.Net.WebClient).DownloadFile($DownloadUrl, $InstallerPath)
                Log-Info "Download complete. Running NSIS silent installer to LocalAppData..."

                # Tesseract uses NSIS, not Inno Setup.
                # Correct silent flag is /S; install dir is /D= as the LAST argument, no quotes.
                $TessLocalDir = "$env:LOCALAPPDATA\Programs\Tesseract-OCR"
                $p = Start-Process $InstallerPath -ArgumentList "/S /D=$TessLocalDir" -Wait -PassThru

                if ($p -eq $null) {
                    Log-Error "Start-Process returned null"
                } elseif ($p.ExitCode -eq 0) {
                    Log-Success "Direct install to LocalAppData succeeded (exit code 0)."
                } else {
                    Log-Error "Direct install failed with exit code: $($p.ExitCode)"
                    Log-Info "For a system-wide install to Program Files, run setup_elevated.ps1"
                }
            } catch {
                Log-Error "Direct install exception: $_"
            } finally {
                if (Test-Path $InstallerPath) {
                    Remove-Item $InstallerPath -Force -ErrorAction SilentlyContinue
                    Log-Info "Cleaned up installer file."
                }
            }
        }

        Start-Sleep -Seconds 2
        Log-Info "Re-probing for Tesseract installation..."
        $TessDataDir = Find-TessDataDir
        if ($TessDataDir) {
            Log-Success "Found tessdata at: $TessDataDir"
        } else {
            Log-Error "Tesseract tessdata not found after install attempt."
            Log-Info "For a system-wide install (Program Files), run setup_elevated.ps1 from the app folder."
        }
    }

    # Step 2 -- Download chi_sim.traineddata and chi_tra.traineddata
    # Use raw.githubusercontent.com -- it resolves Git LFS automatically and returns real binaries.
    # The tessdata_fast releases/download/4.1.0 URL has no binary assets (only source archives) -- 404.
    $TESSDATA_BASE = "https://raw.githubusercontent.com/tesseract-ocr/tessdata_fast/main"
    $TrainedFiles = @("chi_sim.traineddata", "chi_tra.traineddata")

    if ($TessDataDir) {
        New-Item -ItemType Directory -Force -Path $TessDataDir | Out-Null

        foreach ($fname in $TrainedFiles) {
            $dest = Join-Path $TessDataDir $fname
            if (Test-Path $dest) {
                $size = (Get-Item $dest).Length / 1MB
                Log-Success "$fname already exists ($([Math]::Round($size, 2)) MB) -- skipping download."
            } else {
                Log-Info "Downloading $fname ..."
                $url = "$TESSDATA_BASE/$fname"
                try {
                    (New-Object System.Net.WebClient).DownloadFile($url, $dest)
                    if (Test-Path $dest) {
                        $size = (Get-Item $dest).Length / 1MB
                        Log-Success "$fname downloaded successfully ($([Math]::Round($size, 2)) MB)."
                    } else {
                        Log-Error "$fname not found after download."
                    }
                } catch {
                    Log-Error "Failed to download ${fname}: $_"
                }
            }
        }

        # Final validation
        $simOk = Test-Path (Join-Path $TessDataDir "chi_sim.traineddata")
        $traOk = Test-Path (Join-Path $TessDataDir "chi_tra.traineddata")
        if ($simOk -or $traOk) {
            Log-Success "Tesseract setup complete. chi_sim=$simOk chi_tra=$traOk"
        } else {
            Log-Error "Neither chi_sim nor chi_tra traineddata found. Chinese OCR will not work."
        }
    } else {
        Log-Error "Tesseract tessdata directory not found. Manual installation may be required."
        Log-Info "Install manually: https://github.com/UB-Mannheim/tesseract/wiki"
    }

} catch {
    Log-Error "Tesseract setup error (non-fatal): $_"
}

Log-Success "Tesseract installation script completed. Log: $LogPath"
$LogStream.Close()

exit 0
