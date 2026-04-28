#Requires -Version 5.1
<#
.SYNOPSIS
    Download and install the Argos Translate zh->en language pack.

.DESCRIPTION
    Called automatically after install by the Inno Setup [Run] section.
    Can also be run manually from an elevated or user PowerShell prompt.

    The script:
    1. Locates the bundled Python interpreter inside the install directory.
    2. Calls argostranslate.package to update the package index and install
       the zh->en translation pack (~50-100 MB download).
    3. Reports success or failure.

.PARAMETER InstallDir
    Path to the zh-en-translator install directory (where zh-en-translator.exe lives).
    Defaults to the directory containing this script.

.EXAMPLE
    # Run from the install directory:
    .\download_packs.ps1

    # Run from anywhere with explicit path:
    .\download_packs.ps1 -InstallDir "C:\Program Files\zh-en-translator"
#>

[CmdletBinding()]
param(
    [string] $InstallDir = ""
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Continue"   # don't abort on non-fatal errors

# ---------------------------------------------------------------------------
# Resolve install directory
# ---------------------------------------------------------------------------
if (-not $InstallDir -or $InstallDir -eq "") {
    # Default: the directory that contains this script
    $InstallDir = $PSScriptRoot
}

if (-not (Test-Path $InstallDir)) {
    Write-Host "ERROR: Install directory not found: $InstallDir" -ForegroundColor Red
    exit 1
}

Write-Host "zh-en-translator: Downloading translation model pack..." -ForegroundColor Cyan
Write-Host "Install directory: $InstallDir"

# ---------------------------------------------------------------------------
# Locate bundled Python
# ---------------------------------------------------------------------------
# PyInstaller bundles python3XX.dll but no python.exe; however the main .exe
# can be used to run Python code via the -c flag when frozen with onedir.
# The cleaner approach for post-install tasks: use the system Python if
# argostranslate is installed there, or use the bundled executable.

$BundledExe = Join-Path $InstallDir "zh-en-translator.exe"
$PythonExe  = $null

# Prefer a system Python with argostranslate already installed
$SystemPython = $null
@("python", "python3", "python3.11") | ForEach-Object {
    if (-not $SystemPython) {
        try {
            $p = (Get-Command $_ -ErrorAction Stop).Source
            # Check if argostranslate is importable
            $check = & $p -c "import argostranslate" 2>&1
            if ($LASTEXITCODE -eq 0) {
                $SystemPython = $p
            }
        } catch { }
    }
}

if ($SystemPython) {
    $PythonExe = $SystemPython
    Write-Host "Using system Python: $PythonExe"
} elseif (Test-Path $BundledExe) {
    # The bundled exe can run Python snippets via a special internal path.
    # We write a small wrapper .py to the temp directory and call the bundled exe
    # indirectly -- but since it's a windowed exe this won't work well for
    # stdout capture. Instead, look for _pyi_bootloader or similar.
    # Best fallback: print instructions and exit gracefully.
    Write-Host "WARNING: System Python with argostranslate not found." -ForegroundColor Yellow
    Write-Host "         The bundled exe cannot run post-install scripts directly."
    Write-Host ""
    Write-Host "To download the translation pack manually, open a command prompt and run:"
    Write-Host ""
    Write-Host "  pip install argostranslate"
    Write-Host "  python -c `"import argostranslate.package; argostranslate.package.update_package_index(); pkgs = argostranslate.package.get_available_packages(); pkg = next((p for p in pkgs if p.from_code=='zh' and p.to_code=='en'), None); pkg and pkg.install()`""
    Write-Host ""
    exit 0
} else {
    Write-Host "ERROR: Neither system Python nor bundled exe found." -ForegroundColor Red
    Write-Host "       Install argostranslate manually: pip install argostranslate"
    exit 1
}

# ---------------------------------------------------------------------------
# Download and install the zh->en Argos pack
# ---------------------------------------------------------------------------
$DownloadScript = @'
import sys
import logging

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("download_packs")

try:
    import argostranslate.package as pkg

    logger.info("Updating Argos package index...")
    pkg.update_package_index()

    available = pkg.get_available_packages()
    zh_en = next(
        (p for p in available if p.from_code == "zh" and p.to_code == "en"),
        None
    )

    if zh_en is None:
        logger.error("zh->en package not found in the Argos package index.")
        logger.info("You can install it manually:")
        logger.info("  import argostranslate.package as p")
        logger.info("  p.update_package_index()")
        logger.info("  pkgs = p.get_available_packages()")
        logger.info("  zh_en = next(x for x in pkgs if x.from_code=='zh' and x.to_code=='en')")
        logger.info("  zh_en.install()")
        sys.exit(1)

    logger.info("Found package: %s -> %s (version %s)", zh_en.from_code, zh_en.to_code, zh_en.package_version)
    logger.info("Downloading and installing... (this may take a few minutes)")
    zh_en.install()
    logger.info("SUCCESS: zh->en translation pack installed.")
    sys.exit(0)

except ImportError as e:
    print(f"ERROR: Could not import argostranslate: {e}", file=sys.stderr)
    print("Install with: pip install argostranslate", file=sys.stderr)
    sys.exit(1)
except Exception as e:
    print(f"ERROR: {e}", file=sys.stderr)
    sys.exit(1)
'@

# Write script to a temp file
$TempScript = Join-Path $env:TEMP "zh_en_download_packs.py"
$DownloadScript | Set-Content -Path $TempScript -Encoding UTF8

Write-Host ""
Write-Host "Running download script..." -ForegroundColor Cyan

try {
    $proc = Start-Process -FilePath $PythonExe `
        -ArgumentList @("-u", $TempScript) `
        -Wait -PassThru -NoNewWindow

    if ($proc.ExitCode -eq 0) {
        Write-Host ""
        Write-Host "Translation model pack installed successfully." -ForegroundColor Green
        Write-Host "zh-en-translator is ready for offline use."
    } else {
        Write-Host ""
        Write-Host "WARNING: Download script exited with code $($proc.ExitCode)." -ForegroundColor Yellow
        Write-Host ""
        Write-Host "To install the translation pack manually, run:" -ForegroundColor Yellow
        Write-Host "  python -c `"import argostranslate.package as p; p.update_package_index(); zh=next(x for x in p.get_available_packages() if x.from_code=='zh' and x.to_code=='en'); zh.install()`"" -ForegroundColor Yellow
    }
} catch {
    Write-Host "ERROR: Failed to run download script: $_" -ForegroundColor Red
    Write-Host ""
    Write-Host "Manual install instructions:" -ForegroundColor Yellow
    Write-Host "1. Open a command prompt"
    Write-Host "2. Run: pip install argostranslate"
    Write-Host "3. Run: python -c `"import argostranslate.package as p; p.update_package_index(); zh=next(x for x in p.get_available_packages() if x.from_code=='zh' and x.to_code=='en'); zh.install()`""
} finally {
    # Clean up temp script
    if (Test-Path $TempScript) {
        Remove-Item $TempScript -Force -ErrorAction SilentlyContinue
    }
}
