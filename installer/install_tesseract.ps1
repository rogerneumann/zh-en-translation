#Requires -Version 5.1
<#
.SYNOPSIS
    Install Tesseract OCR + Chinese Simplified language data.
    Exits 0 in all cases — OCR is optional, failures are informational only.
    Logs all output to %TEMP%\zh-en-translator-tesseract-install.log for diagnostics.
#>

$ErrorActionPreference = "Continue"

# Set up logging
$LogPath = Join-Path $env:TEMP "zh-en-translator-tesseract-install.log"
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
# Main — wrapped so any unexpected error still reaches exit 0
# ---------------------------------------------------------------------------
try {

    # Step 1 — Skip if already installed
    $TessDataDir = Find-TessDataDir
    if ($TessDataDir) {
        Log-Success "Tesseract already installed. tessdata: $TessDataDir"
    } else {
        # Attempt A — winget
        Log-Info "Attempting Tesseract install via winget..."
        $WingetOk = $false
        try {
            winget --version 2>&1 | Out-Null
            if ($LASTEXITCODE -eq 0) {
                Log-Info "winget is available; installing UB-Mannheim.TesseractOCR..."
                winget install --id UB-Mannheim.TesseractOCR `
                    --silent --accept-package-agreements --accept-source-agreements `
                    --scope user 2>&1 | ForEach-Object { Log-Message $_ }
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
            # Attempt B — direct download + silent install to LocalAppData (no UAC)
            Log-Info "winget unavailable or failed — trying direct install..."
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
                $DownloadUrl = "https://github.com/UB-Mannheim/tesseract/releases/download/v5.5.0.20241111/tesseract-ocr-w64-setup-5.5.0.20241111.exe"
                Log-Info "Using pinned fallback version 5.5.0"
            }

            try {
                Log-Info "Downloading Tesseract from: $DownloadUrl"
                (New-Object System.Net.WebClient).DownloadFile($DownloadUrl, $InstallerPath)
                Log-Info "Download complete. Running silent installer..."

                $p = Start-Process $InstallerPath `
                    -ArgumentList "/VERYSILENT /NORESTART /DIR=""$env:LOCALAPPDATA\Programs\Tesseract-OCR""" `
                    -Wait -PassThru

                if ($p -eq $null) {
                    Log-Error "Start-Process returned null (elevation may have been blocked)"
                } elseif ($p.ExitCode -eq 0) {
                    Log-Success "Direct install to LocalAppData succeeded (exit code 0)."
                } else {
                    Log-Error "Direct install failed with exit code: $($p.ExitCode)"
                }
            } catch {
                Log-Error "Direct install exception: $_"
            } finally {
                if (Test-Path $InstallerPath) {
                    Remove-Item $InstallerPath -Force -ErrorAction SilentlyContinue
                    Log-Info "Cleaned up installer file."
                }
            }

            # Attempt C — elevated install to Program Files (triggers UAC prompt)
            $TessDataDirAfterB = Find-TessDataDir
            if (-not $TessDataDirAfterB) {
                Log-Info "Attempt B did not produce a working install. Trying elevated install to 'C:\Program Files\Tesseract-OCR'..."
                $ElevatedInstallerPath = Join-Path $env:TEMP "tesseract-ocr-setup-elevated.exe"

                # Re-download the installer for the elevated attempt
                try {
                    Log-Info "Downloading Tesseract installer for elevated install..."
                    (New-Object System.Net.WebClient).DownloadFile($DownloadUrl, $ElevatedInstallerPath)
                    Log-Info "Download complete. Launching elevated installer (UAC prompt will appear)..."

                    try {
                        $p = Start-Process $ElevatedInstallerPath `
                            -ArgumentList "/VERYSILENT /NORESTART /DIR=""C:\Program Files\Tesseract-OCR""" `
                            -Verb RunAs -Wait -PassThru

                        if ($p -eq $null) {
                            Log-Error "Elevated Start-Process returned null (UAC may have been denied or elevation failed)"
                        } elseif ($p.ExitCode -eq 0) {
                            Log-Success "Elevated install to 'C:\Program Files\Tesseract-OCR' succeeded (exit code 0)."
                        } else {
                            Log-Error "Elevated install failed with exit code: $($p.ExitCode)"
                        }
                    } catch {
                        Log-Error "Elevated install exception (UAC may have been cancelled): $_"
                    }
                } catch {
                    Log-Error "Download for elevated install failed: $_"
                } finally {
                    if (Test-Path $ElevatedInstallerPath) {
                        Remove-Item $ElevatedInstallerPath -Force -ErrorAction SilentlyContinue
                        Log-Info "Cleaned up elevated installer file."
                    }
                }

                # Re-probe after Attempt C
                $TessDataDirAfterC = Find-TessDataDir
                if ($TessDataDirAfterC) {
                    Log-Success "Elevated install succeeded. Found tessdata at: $TessDataDirAfterC"
                } else {
                    Log-Error "Tesseract tessdata directory not found after elevated install attempt."
                }
            }
        }

        Start-Sleep -Seconds 2
        Log-Info "Re-probing for Tesseract installation..."
        $TessDataDir = Find-TessDataDir
        if ($TessDataDir) {
            Log-Success "Found tessdata at: $TessDataDir"
        } else {
            Log-Error "Tesseract tessdata directory not found after installation attempt."
        }
    }

    # Step 2 — Download chi_sim.traineddata
    if ($TessDataDir) {
        Log-Info "Attempting to download chi_sim.traineddata..."
        New-Item -ItemType Directory -Force -Path $TessDataDir | Out-Null
        $dest = Join-Path $TessDataDir "chi_sim.traineddata"

        # Check if already exists
        if (Test-Path $dest) {
            Log-Success "chi_sim.traineddata already exists at: $dest"
        } else {
            try {
                (New-Object System.Net.WebClient).DownloadFile(
                    "https://github.com/tesseract-ocr/tessdata_fast/raw/main/chi_sim.traineddata",
                    $dest
                )
                Log-Success "chi_sim.traineddata successfully downloaded to: $dest"
            } catch {
                Log-Error "chi_sim download failed: $_"
            }
        }

        # Final validation
        if (Test-Path $dest) {
            $size = (Get-Item $dest).Length / 1MB
            Log-Success "Tesseract setup complete. chi_sim.traineddata size: $([Math]::Round($size, 2)) MB"
        } else {
            Log-Error "chi_sim.traineddata not found after download attempt."
        }
    } else {
        Log-Error "Tesseract tessdata directory could not be located. Manual installation may be required."
        Log-Info "Install manually: https://github.com/UB-Mannheim/tesseract/wiki"
    }

} catch {
    Log-Error "Tesseract setup error (non-fatal): $_"
}

Log-Success "Tesseract installation script completed. Log: $LogPath"
$LogStream.Close()

exit 0
