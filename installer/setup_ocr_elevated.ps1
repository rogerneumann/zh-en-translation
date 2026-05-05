#Requires -Version 5.1
<#
.SYNOPSIS
    Elevated one-shot Windows OCR Chinese capability install.
    Called by the installer (ShellExec runas) or from Preferences for OCR setup.
    Installs Language.OCR zh-Hans-CN and zh-Hant-TW via Add-WindowsCapability.
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

    # -- Windows OCR Chinese capability --
    Write-Log "Checking Windows OCR Chinese capabilities..." "Cyan"

    $chineseCaps = @()
    try {
        $chineseCaps = Get-WindowsCapability -Online -ErrorAction Stop |
            Where-Object { $_.Name -like "Language.OCR*zh*" }
    } catch {
        Write-Log "Get-WindowsCapability failed: $_ -- using known names" "Yellow"
    }

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

    Write-Log "" "White"
    Write-Log "=== Elevated OCR setup complete. Log saved to: $LogPath ===" "Green"
    Write-Log "SETUP_STATUS: SUCCESS" "Green"

} catch {
    Write-Host "[FATAL] $_" -ForegroundColor Red
    if ($LogStream) {
        try {
            $LogStream.WriteLine("[FATAL] $_")
            $LogStream.WriteLine("SETUP_STATUS: FAILED")
            $LogStream.Flush()
        } catch {}
    }
}

if ($LogStream) { $LogStream.Close() }
exit 0
