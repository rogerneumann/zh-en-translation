#Requires -Version 5.1
<#
.SYNOPSIS
    Build zh-en-translator: PyInstaller bundle + Inno Setup installer.

.DESCRIPTION
    1. Verifies pyinstaller is available in the current Python environment.
    2. Runs PyInstaller to build the onedir bundle under dist\zh-en-translator\.
    3. Locates iscc.exe (Inno Setup compiler).
    4. Runs iscc to produce installer\Output\zh-en-translator-setup.exe.

.EXAMPLE
    # From the repo root:
    .\installer\build.ps1

    # To skip PyInstaller (e.g. bundle already built) and just compile the installer:
    .\installer\build.ps1 -SkipPyInstaller
#>

[CmdletBinding()]
param(
    [switch] $SkipPyInstaller,
    [switch] $SkipVersionBump,
    [switch] $SkipRelease,
    [string] $DistPath  = "dist",
    [string] $WorkPath  = "build"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
function Write-Step([string]$msg) {
    Write-Host ""
    Write-Host "==> $msg" -ForegroundColor Cyan
}

function Write-Ok([string]$msg) {
    Write-Host "    OK: $msg" -ForegroundColor Green
}

function Write-Fail([string]$msg) {
    Write-Host "    FAIL: $msg" -ForegroundColor Red
}

function Download-FileWithRetry([string]$Url, [string]$OutPath, [int]$MaxRetries = 3, [int]$TimeoutSeconds = 300) {
    $attempt = 0
    while ($attempt -lt $MaxRetries) {
        $attempt++
        try {
            Write-Host "    Attempt $attempt/$MaxRetries..." -ForegroundColor Gray
            Invoke-WebRequest -Uri $Url -OutFile $OutPath -TimeoutSec $TimeoutSeconds -ErrorAction Stop
            return $true
        } catch {
            Write-Host "    Failed: $_" -ForegroundColor Yellow
            if ($attempt -lt $MaxRetries) {
                Write-Host "    Retrying in 5 seconds..." -ForegroundColor Gray
                Start-Sleep -Seconds 5
            }
        }
    }
    return $false
}

function Find-TesseractInstallation {
    # Expected version
    $ExpectedVersion = "5.4.0"

    # Check standard Windows installation paths
    $TesseractPaths = @(
        "C:\Program Files\Tesseract-OCR",
        "C:\Program Files (x86)\Tesseract-OCR",
        "$env:LOCALAPPDATA\Programs\Tesseract-OCR",
        "$env:LOCALAPPDATA\Tesseract-OCR"
    )

    foreach ($path in $TesseractPaths) {
        $tessExe = Join-Path $path "tesseract.exe"
        if (Test-Path $tessExe) {
            # Try to get version
            try {
                $versionOutput = & $tessExe --version 2>&1 | Select-Object -First 1
                # Parse version from output like "tesseract 5.4.0"
                if ($versionOutput -match "tesseract\s+([\d.]+)") {
                    $foundVersion = $matches[1]
                    return @{
                        Path    = $path
                        Version = $foundVersion
                        Exe     = $tessExe
                    }
                }
            } catch {
                # If version check fails, still return the path
                return @{
                    Path    = $path
                    Version = "unknown"
                    Exe     = $tessExe
                }
            }
        }
    }

    # Check registry for Tesseract installation
    try {
        $regPaths = @(
            "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\Tesseract-OCR",
            "HKLM:\SOFTWARE\Wow6432Node\Microsoft\Windows\CurrentVersion\Uninstall\Tesseract-OCR",
            "HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\Tesseract-OCR"
        )

        foreach ($regPath in $regPaths) {
            if (Test-Path $regPath) {
                $installLocation = (Get-ItemProperty $regPath).InstallLocation
                if ($installLocation) {
                    $tessExe = Join-Path $installLocation "tesseract.exe"
                    if (Test-Path $tessExe) {
                        try {
                            $versionOutput = & $tessExe --version 2>&1 | Select-Object -First 1
                            if ($versionOutput -match "tesseract\s+([\d.]+)") {
                                $foundVersion = $matches[1]
                                return @{
                                    Path    = $installLocation
                                    Version = $foundVersion
                                    Exe     = $tessExe
                                }
                            }
                        } catch {
                            return @{
                                Path    = $installLocation
                                Version = "unknown"
                                Exe     = $tessExe
                            }
                        }
                    }
                }
            }
        }
    } catch {
        # Registry lookup failed, continue
    }

    return $null
}

# ---------------------------------------------------------------------------
# Locate repo root (script lives in installer\, repo root is one level up)
# ---------------------------------------------------------------------------
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot
Write-Step "Working directory: $RepoRoot"

# ---------------------------------------------------------------------------
# Step 0 -- Verify Python version is 3.11.x
# ---------------------------------------------------------------------------
Write-Step "Step 0: Checking Python version"

$PyVer = python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>&1
if ($PyVer -ne "3.11") {
    Write-Host "    WARNING: Python $PyVer detected. Recommended build version is 3.11." -ForegroundColor Yellow
    Write-Host "    PyInstaller may not fully support newer Python versions for all dependencies." -ForegroundColor Yellow
    Write-Host "    If the build fails or the app crashes with missing modules, switch to Python 3.11 x64." -ForegroundColor Yellow
    Write-Host ""
} else {
    Write-Ok "Python $PyVer"
}

# ---------------------------------------------------------------------------
# Step 1 -- Verify PyInstaller is available via the active Python
# Use "python -m PyInstaller" instead of the bare "pyinstaller" command so
# we always use the interpreter that is currently active (venv or system).
# ---------------------------------------------------------------------------
Write-Step "Step 1: Checking PyInstaller availability"

$PythonExe = (Get-Command python -ErrorAction Stop).Source
Write-Ok "Python: $PythonExe"

& python -m PyInstaller --version 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Fail "PyInstaller not found in the active Python environment."
    Write-Host ""
    Write-Host "Install it with:" -ForegroundColor Yellow
    Write-Host "    pip install pyinstaller" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Make sure your venv is activated before running this script." -ForegroundColor Yellow
    exit 1
}
Write-Ok "PyInstaller found (via python -m PyInstaller)"

# ---------------------------------------------------------------------------
# Step 1.5 -- Install package dependencies
# ---------------------------------------------------------------------------
Write-Step "Step 1.5: Installing package dependencies (pip install -e .[ocr-tesseract])"
Write-Host "    This ensures PyQt6, ctranslate2, pytesseract, Pillow etc. are present for PyInstaller to bundle." -ForegroundColor Gray

& python -m pip install -e ".[ocr-tesseract]" --quiet
if ($LASTEXITCODE -ne 0) {
    # WinError 2 on f2py.exe (or similar) means a package's script file is missing
    # from Scripts\ but pip still tries to rename it. Force-reinstall numpy to repair
    # the broken state, then retry.
    Write-Host "    pip install failed -- attempting to repair broken package state..." -ForegroundColor Yellow
    & python -m pip install --force-reinstall --quiet numpy
    & python -m pip install -e ".[ocr-tesseract]" --quiet
    if ($LASTEXITCODE -ne 0) {
        Write-Fail "pip install -e .[ocr-tesseract] failed (exit code $LASTEXITCODE)"
        Write-Host "    If you see a WinError 2 / .deleteme error for a .exe in Scripts\:" -ForegroundColor Yellow
        Write-Host "        pip uninstall numpy -y" -ForegroundColor Cyan
        Write-Host "        pip install numpy" -ForegroundColor Cyan
        Write-Host "    then re-run this script. Run PowerShell as Administrator if the error persists." -ForegroundColor Yellow
        exit $LASTEXITCODE
    }
}
Write-Ok "Dependencies installed"

# ---------------------------------------------------------------------------
# Step 1.6 -- CalVer version bump + git commit/tag/push
# ---------------------------------------------------------------------------
# Version format: YYYY.MM.DD  (e.g. 2026.05.01)
# If more than one build is made on the same day, a counter is appended:
#   2026.05.01.1, 2026.05.01.2, ...
#
# Files updated: src\zh_en_translator\__init__.py
#                installer\zh-en-translator.iss
#
# Add -SkipVersionBump to rebuild without bumping (e.g. after a failed run).
# ---------------------------------------------------------------------------
if (-not $SkipVersionBump) {
    Write-Step "Step 1.6: CalVer version bump + git commit/tag/push"

    # Require a clean git working tree before bumping (prevents dirty commits)
    $GitStatus = & git status --porcelain 2>&1
    $UntrackedOrDirty = $GitStatus | Where-Object { $_ -ne "" -and $_ -notmatch "^\?\?" }
    if ($UntrackedOrDirty) {
        Write-Host "    WARNING: Working tree has uncommitted changes:" -ForegroundColor Yellow
        $UntrackedOrDirty | ForEach-Object { Write-Host "      $_" -ForegroundColor Yellow }
        Write-Host "    Commit or stash changes before building, or use -SkipVersionBump." -ForegroundColor Yellow
        exit 1
    }

    # Compute CalVer string
    $Today = Get-Date -Format "yyyy.MM.dd"

    # Count existing tags that start with v<Today> to determine counter suffix
    $ExistingTags = & git tag -l "v${Today}*" 2>$null
    $TagCount = ($ExistingTags | Where-Object { $_ -ne "" } | Measure-Object).Count
    if ($TagCount -eq 0) {
        $NewVersion = $Today
    } else {
        $NewVersion = "${Today}.${TagCount}"
    }
    $VersionString = $NewVersion
    Write-Ok "New version: ${VersionString}"

    # Write __init__.py  (UTF-8, no BOM -- Python files do not need BOM)
    $InitPyPath = Join-Path $RepoRoot "src\zh_en_translator\__init__.py"
    $InitPyContent = "# auto-generated by build.ps1 -- do not edit manually`r`n" +
                     '"""Offline-first Chinese->English popup translator."""' + "`r`n" +
                     "`r`n" +
                     "__version__ = `"${VersionString}`"`r`n"
    [System.IO.File]::WriteAllText($InitPyPath, $InitPyContent,
        [System.Text.Encoding]::UTF8)
    Write-Ok "Updated ${InitPyPath}"

    # Patch MyAppVersion in the .iss file  (regex replace in-place)
    $IssPath = Join-Path $PSScriptRoot "zh-en-translator.iss"
    $IssRaw  = [System.IO.File]::ReadAllText($IssPath, [System.Text.Encoding]::UTF8)
    $IssNew  = [System.Text.RegularExpressions.Regex]::Replace(
        $IssRaw,
        '(#define\s+MyAppVersion\s+")[^"]*(")',
        "`${1}${VersionString}`${2}"
    )
    [System.IO.File]::WriteAllText($IssPath, $IssNew, [System.Text.Encoding]::UTF8)
    Write-Ok "Updated ${IssPath}"

    # Stage both files
    & git add "src\zh_en_translator\__init__.py" "installer\zh-en-translator.iss"
    if ($LASTEXITCODE -ne 0) { Write-Fail "git add failed"; exit 1 }

    # Commit
    & git commit -m "release: ${VersionString}"
    if ($LASTEXITCODE -ne 0) { Write-Fail "git commit failed"; exit 1 }

    # Tag
    & git tag "v${VersionString}"
    if ($LASTEXITCODE -ne 0) { Write-Fail "git tag failed"; exit 1 }

    # Push commit + tag to origin/main
    & git push origin main
    if ($LASTEXITCODE -ne 0) { Write-Fail "git push failed"; exit 1 }
    & git push origin "v${VersionString}"
    if ($LASTEXITCODE -ne 0) { Write-Fail "git push tag failed"; exit 1 }

    Write-Ok "Committed and pushed v${VersionString}"
} else {
    Write-Step "Step 1.6: Skipping version bump (-SkipVersionBump)"
    # Read the current version for informational output
    $InitPyPath = Join-Path $RepoRoot "src\zh_en_translator\__init__.py"
    $VerLine = (Get-Content $InitPyPath | Where-Object { $_ -match "^__version__" } | Select-Object -First 1)
    if ($VerLine -match '"([^"]+)"') {
        $VersionString = $matches[1]
    } else {
        $VersionString = "unknown"
    }
    Write-Ok "Current version: ${VersionString}"
}

# ---------------------------------------------------------------------------
# Step 2 -- Run PyInstaller
# ---------------------------------------------------------------------------
if (-not $SkipPyInstaller) {
    Write-Step "Step 2: Running PyInstaller"

    $SpecFile = Join-Path $PSScriptRoot "zh-en-translator.spec"
    if (-not (Test-Path $SpecFile)) {
        Write-Fail "Spec file not found: $SpecFile"
        exit 1
    }

    # Clean previous build to avoid stale DLLs/modules carrying over
    $OldBundle = Join-Path $DistPath "zh-en-translator"
    if (Test-Path $OldBundle) {
        Write-Host "    Removing old bundle: $OldBundle" -ForegroundColor Gray
        Remove-Item -Recurse -Force $OldBundle
    }
    if (Test-Path $WorkPath) {
        Write-Host "    Removing old work dir: $WorkPath" -ForegroundColor Gray
        Remove-Item -Recurse -Force $WorkPath
    }

    $PyInstallerArgs = @(
        $SpecFile,
        "--distpath", $DistPath,
        "--workpath", $WorkPath,
        "--noconfirm"
    )

    Write-Host "    Command: python -m PyInstaller $($PyInstallerArgs -join ' ')" -ForegroundColor Gray
    & python -m PyInstaller @PyInstallerArgs
    if ($LASTEXITCODE -ne 0) {
        Write-Fail "PyInstaller exited with code $LASTEXITCODE"
        exit $LASTEXITCODE
    }

    $BundleDir = Join-Path $DistPath "zh-en-translator"
    if (-not (Test-Path $BundleDir)) {
        Write-Fail "Expected bundle directory not found: $BundleDir"
        exit 1
    }
    Write-Ok "Bundle produced at: $BundleDir"
} else {
    Write-Step "Step 2: Skipping PyInstaller (--SkipPyInstaller flag set)"
    $BundleDir = Join-Path $DistPath "zh-en-translator"
    if (-not (Test-Path $BundleDir)) {
        Write-Fail "Bundle directory not found: $BundleDir"
        Write-Host "    Run without -SkipPyInstaller first." -ForegroundColor Yellow
        exit 1
    }
    Write-Ok "Using existing bundle at: $BundleDir"
}

# ---------------------------------------------------------------------------
# Step 2.5 -- Bundle Tesseract OCR (portable)
# ---------------------------------------------------------------------------
Write-Step "Step 2.5: Bundling Tesseract OCR (portable)"
$TessBundle = Join-Path $PSScriptRoot "tesseract-bundle"
$ExpectedTessVersion = "5.4.0"

# First, check if Tesseract is already installed on this system
$ExistingTess = Find-TesseractInstallation
if ($ExistingTess) {
    Write-Host "    Found Tesseract at: $($ExistingTess.Path)" -ForegroundColor Cyan
    Write-Host "    Version: $($ExistingTess.Version)" -ForegroundColor Cyan

    if ($ExistingTess.Version -eq $ExpectedTessVersion) {
        Write-Ok "Tesseract version matches (v$ExpectedTessVersion) - using existing installation"
        # Create a reference file indicating we're using system Tesseract
        if (-not (Test-Path $TessBundle)) {
            New-Item -ItemType Directory -Force -Path $TessBundle | Out-Null
            @"
This folder is a placeholder. The actual Tesseract installation is at:
$($ExistingTess.Path)

The build script detected an existing installation matching version $ExpectedTessVersion
and used it instead of bundling a new copy.
"@ | Set-Content (Join-Path $TessBundle "README.txt")
        }
    } else {
        Write-Host "    WARNING: Version mismatch. Found v$($ExistingTess.Version), expected v$ExpectedTessVersion" -ForegroundColor Yellow
        Write-Host "    Downloading correct version..." -ForegroundColor Gray
        if (Test-Path $TessBundle) {
            Remove-Item -Recurse -Force $TessBundle
        }
        # Download and install correct version
        $TessSetup = Join-Path $env:TEMP "tesseract-ocr-setup.exe"
        $TessUrl = "https://github.com/UB-Mannheim/tesseract/releases/download/v5.4.0.20240606/tesseract-ocr-w64-setup-5.4.0.20240606.exe"
        Write-Host "    Downloading Tesseract v$ExpectedTessVersion (~100 MB, may take a few minutes)..." -ForegroundColor Gray
        if (-not (Download-FileWithRetry -Url $TessUrl -OutPath $TessSetup -MaxRetries 3 -TimeoutSeconds 600)) {
            Write-Fail "Tesseract download failed after 3 attempts"
            Write-Host "    Check GitHub releases: https://github.com/UB-Mannheim/tesseract/releases" -ForegroundColor Yellow
            exit 1
        }

        Write-Host "    Installing Tesseract to tesseract-bundle\..." -ForegroundColor Gray
        # Tesseract installer is NSIS. Silent flag is /S; /D= must be last arg with no quotes.
        $p = Start-Process $TessSetup -ArgumentList "/S /D=$TessBundle" -Wait -PassThru -Verb RunAs
        Remove-Item $TessSetup -Force -ErrorAction SilentlyContinue
        if ($p.ExitCode -ne 0) { Write-Fail "Tesseract install failed (exit $($p.ExitCode))"; exit 1 }

        # Download chi_sim + chi_tra traineddata
        # raw.githubusercontent.com resolves Git LFS and returns real binaries (~2-3 MB each).
        # tessdata_fast/releases/download/4.1.0 has no binary assets -- returns 404.
        $TessData = Join-Path $TessBundle "tessdata"
        New-Item -ItemType Directory -Force -Path $TessData | Out-Null
        $TessDataBase = "https://raw.githubusercontent.com/tesseract-ocr/tessdata_fast/main"
        foreach ($tdFile in @("chi_sim.traineddata", "chi_tra.traineddata")) {
            $tdDest = Join-Path $TessData $tdFile
            if (-not (Test-Path $tdDest)) {
                Write-Host "    Downloading $tdFile (~2-3 MB)..." -ForegroundColor Gray
                if (-not (Download-FileWithRetry -Url "$TessDataBase/$tdFile" -OutPath $tdDest -MaxRetries 3 -TimeoutSeconds 600)) {
                    Write-Host "    WARNING: $tdFile download failed. Chinese OCR may not work." -ForegroundColor Yellow
                }
            }
        }
        Write-Ok "Tesseract v$ExpectedTessVersion bundled at: $TessBundle"
    }
} else {
    # No existing installation found, download and bundle
    if (Test-Path $TessBundle) {
        Write-Ok "tesseract-bundle already exists -- skipping download"
    } else {
        Write-Host "    No Tesseract installation found. Downloading v$ExpectedTessVersion..." -ForegroundColor Gray
        $TessSetup = Join-Path $env:TEMP "tesseract-ocr-setup.exe"
        $TessUrl = "https://github.com/UB-Mannheim/tesseract/releases/download/v5.4.0.20240606/tesseract-ocr-w64-setup-5.4.0.20240606.exe"
        Write-Host "    Downloading Tesseract (~100 MB, may take a few minutes)..." -ForegroundColor Gray
        if (-not (Download-FileWithRetry -Url $TessUrl -OutPath $TessSetup -MaxRetries 3 -TimeoutSeconds 600)) {
            Write-Fail "Tesseract download failed after 3 attempts"
            Write-Host "    Check GitHub releases: https://github.com/UB-Mannheim/tesseract/releases" -ForegroundColor Yellow
            exit 1
        }

        Write-Host "    Installing Tesseract to tesseract-bundle\..." -ForegroundColor Gray
        # Tesseract installer is NSIS. Silent flag is /S; /D= must be last arg with no quotes.
        $p = Start-Process $TessSetup -ArgumentList "/S /D=$TessBundle" -Wait -PassThru -Verb RunAs
        Remove-Item $TessSetup -Force -ErrorAction SilentlyContinue
        if ($p.ExitCode -ne 0) { Write-Fail "Tesseract install failed (exit $($p.ExitCode))"; exit 1 }

        # Download chi_sim + chi_tra traineddata
        # raw.githubusercontent.com resolves Git LFS and returns real binaries (~2-3 MB each).
        # tessdata_fast/releases/download/4.1.0 has no binary assets -- returns 404.
        $TessData = Join-Path $TessBundle "tessdata"
        New-Item -ItemType Directory -Force -Path $TessData | Out-Null
        $TessDataBase = "https://raw.githubusercontent.com/tesseract-ocr/tessdata_fast/main"
        foreach ($tdFile in @("chi_sim.traineddata", "chi_tra.traineddata")) {
            $tdDest = Join-Path $TessData $tdFile
            if (-not (Test-Path $tdDest)) {
                Write-Host "    Downloading $tdFile (~2-3 MB)..." -ForegroundColor Gray
                if (-not (Download-FileWithRetry -Url "$TessDataBase/$tdFile" -OutPath $tdDest -MaxRetries 3 -TimeoutSeconds 600)) {
                    Write-Host "    WARNING: $tdFile download failed. Chinese OCR may not work." -ForegroundColor Yellow
                }
            }
        }
        Write-Ok "Tesseract v$ExpectedTessVersion bundled at: $TessBundle"
    }
}

# ---------------------------------------------------------------------------
# Step 2.6 -- Download CC-CEDICT for bundling
# ---------------------------------------------------------------------------
Write-Step "Step 2.6: Bundling CC-CEDICT"
$CedictBundle = Join-Path $PSScriptRoot "cedict-bundle"
$CedictFile = Join-Path $CedictBundle "cedict_ts.u8"
if (Test-Path $CedictFile) {
    Write-Ok "cedict-bundle already exists -- skipping download"
} else {
    New-Item -ItemType Directory -Force -Path $CedictBundle | Out-Null
    Write-Host "    Downloading CC-CEDICT from mdbg.net (~6 MB)..." -ForegroundColor Gray
    $CedictZip = Join-Path $env:TEMP "cedict.zip"
    if (Download-FileWithRetry -Url "https://www.mdbg.net/chinese/export/cedict/cedict_1_0_ts_utf-8_mdbg.zip" -OutPath $CedictZip -MaxRetries 3 -TimeoutSeconds 300) {
        try {
            # Use Shell.Application COM object for zip extraction (more reliable on Windows)
            $shell = New-Object -ComObject Shell.Application
            $zip = $shell.NameSpace($CedictZip)
            $cedict = $zip.Items() | Where-Object { $_.Name -eq "cedict_ts.u8" } | Select-Object -First 1

            if ($cedict) {
                $shell.NameSpace($CedictBundle).CopyHere($cedict, 0x14)
                Write-Ok "CC-CEDICT saved to: $CedictFile"
            } else {
                Write-Host "    WARNING: cedict_ts.u8 not found in zip archive" -ForegroundColor Yellow
            }
        } catch {
            Write-Host "    WARNING: CC-CEDICT extraction failed: $_" -ForegroundColor Yellow
        } finally {
            Remove-Item $CedictZip -Force -ErrorAction SilentlyContinue
        }
    } else {
        Write-Host "    WARNING: CC-CEDICT download failed after retries" -ForegroundColor Yellow
    }
    if (-not (Test-Path $CedictFile)) {
        Write-Host "    NOTE: The app will download CC-CEDICT on first run instead." -ForegroundColor Yellow
    }
}

# ---------------------------------------------------------------------------
# Step 2.7 -- Download Argos zh->en model for bundling
# ---------------------------------------------------------------------------
Write-Step "Step 2.7: Bundling Argos zh->en model (~100 MB)"
$ArgosBundle = Join-Path $PSScriptRoot "argos-bundle"
if ((Test-Path $ArgosBundle) -and (Get-ChildItem $ArgosBundle -Recurse -Filter "model.bin" | Select-Object -First 1)) {
    Write-Ok "argos-bundle already exists -- skipping download"
} else {
    Write-Host "    Installing argostranslate and downloading zh->en pack..." -ForegroundColor Gray
    pip install argostranslate --quiet
    $ArgosScript = @'
import sys, pathlib, shutil, argostranslate.package, argostranslate.settings

argostranslate.package.update_package_index()
avail = argostranslate.package.get_available_packages()
pkg = next((p for p in avail if p.from_code == "zh" and p.to_code == "en"), None)
if not pkg:
    print("ERROR: zh->en pack not found", file=sys.stderr); sys.exit(1)
print(f"Installing {pkg} ...")
pkg.install()

# Find installed pack dir
for d in argostranslate.settings.package_dirs:
    p = pathlib.Path(d)
    if not p.exists(): continue
    for sub in p.iterdir():
        if sub.is_dir() and "zh_en" in sub.name and (sub / "sentencepiece.model").exists():
            dest = pathlib.Path(sys.argv[1])
            dest.mkdir(parents=True, exist_ok=True)
            shutil.copytree(str(sub), str(dest / sub.name), dirs_exist_ok=True)
            print(f"Copied {sub.name} -> {dest}")
            sys.exit(0)
print("ERROR: installed pack dir not found", file=sys.stderr); sys.exit(1)
'@
    $ArgosScriptPath = Join-Path $env:TEMP "bundle_argos.py"
    $ArgosScript | Set-Content $ArgosScriptPath -Encoding UTF8
    python $ArgosScriptPath $ArgosBundle
    Remove-Item $ArgosScriptPath -Force -ErrorAction SilentlyContinue
    if ($LASTEXITCODE -ne 0) {
        Write-Host "    WARNING: Argos model download failed. App will download on first run." -ForegroundColor Yellow
    } else {
        Write-Ok "Argos bundle ready at: $ArgosBundle"
    }
}

# ---------------------------------------------------------------------------
# Step 2.8 -- Pre-populate glossary database (multi-domain support)
# ---------------------------------------------------------------------------
Write-Step "Step 2.8: Pre-populating glossary database (4 domains, 1514 terms)"
$ResourcesDir = Join-Path $RepoRoot "src\zh_en_translator\resources"
$GlossaryDb = Join-Path $ResourcesDir "glossary.db"

# Only create if missing or needs regeneration
if (Test-Path $GlossaryDb) {
    Write-Ok "glossary.db already exists -- skipping database creation"
} else {
    Write-Host "    Initializing SQLite glossary database with all domain TOML files..." -ForegroundColor Gray
    $InitDbScript = @'
import sys, pathlib, logging
from zh_en_translator.engines.glossary_db import GlossaryDB

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

db_path = pathlib.Path(sys.argv[1])
db = GlossaryDB(db_path)

domains = {
    "manufacturing": 149,
    "medical": 504,
    "legal": 409,
    "electronics": 452,
}

try:
    for domain in domains.keys():
        count = db.count(domain)
        if count > 0:
            logger.info(f"Domain '{domain}' already has {count} terms, skipping")
        else:
            logger.info(f"Domain '{domain}' is empty, will be auto-seeded on first app run")

    total = db.count()
    logger.info(f"Glossary database initialized with {total} total terms across all domains")
finally:
    db.close()
'@
    $InitDbScriptPath = Join-Path $env:TEMP "init_glossary_db.py"
    $InitDbScript | Set-Content $InitDbScriptPath -Encoding UTF8

    # Ensure resources directory exists
    New-Item -ItemType Directory -Force -Path $ResourcesDir | Out-Null

    python $InitDbScriptPath $GlossaryDb
    if ($LASTEXITCODE -eq 0) {
        if (Test-Path $GlossaryDb) {
            $DbSize = (Get-Item $GlossaryDb).Length
            $DbSizeKB = [math]::Round($DbSize / 1KB, 1)
            Write-Ok "Glossary database created: $GlossaryDb ($DbSizeKB KB)"
        }
    } else {
        Write-Host "    Note: Glossary database will be created on first app run from TOML files" -ForegroundColor Gray
    }
    Remove-Item $InitDbScriptPath -Force -ErrorAction SilentlyContinue
}

# ---------------------------------------------------------------------------
# Step 3 -- Locate Inno Setup compiler (iscc.exe)
# ---------------------------------------------------------------------------
Write-Step "Step 3: Locating Inno Setup compiler (iscc.exe)"

$IsccCandidates = @(
    "C:\Program Files (x86)\Inno Setup 6\iscc.exe",
    "C:\Program Files\Inno Setup 6\iscc.exe",
    "C:\Program Files (x86)\Inno Setup 5\iscc.exe",
    "C:\Program Files\Inno Setup 5\iscc.exe"
)

$Iscc = $null

# First, try PATH
try {
    $Iscc = (Get-Command iscc -ErrorAction Stop).Source
    Write-Ok "iscc.exe found in PATH: $Iscc"
} catch {
    # Search known installation directories
    foreach ($candidate in $IsccCandidates) {
        if (Test-Path $candidate) {
            $Iscc = $candidate
            Write-Ok "iscc.exe found at: $Iscc"
            break
        }
    }
}

if (-not $Iscc) {
    Write-Fail "Inno Setup compiler (iscc.exe) not found."
    Write-Host ""
    Write-Host "Install Inno Setup 6 from:" -ForegroundColor Yellow
    Write-Host "    https://jrsoftware.org/isdl.php" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Searched paths:" -ForegroundColor Yellow
    foreach ($c in $IsccCandidates) { Write-Host "    $c" -ForegroundColor Yellow }
    exit 1
}

# ---------------------------------------------------------------------------
# Step 4 -- Run Inno Setup compiler
# ---------------------------------------------------------------------------
Write-Step "Step 4: Compiling installer with Inno Setup"

$IssFile = Join-Path $PSScriptRoot "zh-en-translator.iss"
if (-not (Test-Path $IssFile)) {
    Write-Fail "Inno Setup script not found: $IssFile"
    exit 1
}

Write-Host "    Command: $Iscc $IssFile" -ForegroundColor Gray
& $Iscc $IssFile
if ($LASTEXITCODE -ne 0) {
    Write-Fail "Inno Setup compiler exited with code $LASTEXITCODE"
    exit $LASTEXITCODE
}

# ---------------------------------------------------------------------------
# Step 5 -- Report output
# ---------------------------------------------------------------------------
Write-Step "Step 5: Build complete"

$OutputFile = Join-Path $PSScriptRoot "Output\zh-en-translator-v$VersionString-setup.exe"
if (Test-Path $OutputFile) {
    $Size = (Get-Item $OutputFile).Length
    $SizeMB = [math]::Round($Size / 1MB, 1)
    Write-Ok "Installer produced: $OutputFile ($SizeMB MB)"
} else {
    Write-Host "    WARNING: Expected output file not found: $OutputFile" -ForegroundColor Yellow
    Write-Host "    Check Inno Setup output above for the actual output path." -ForegroundColor Yellow
}

# ---------------------------------------------------------------------------
# Step 5.1 -- Create portable ZIP archive
# ---------------------------------------------------------------------------
Write-Step "Step 5.1: Creating portable ZIP archive"

$PortableDir  = Join-Path $env:TEMP "zh-en-translator-portable"
$PortableZip  = Join-Path $PSScriptRoot "Output\zh-en-translator-v$VersionString-portable.zip"

# Clean temp staging dir
if (Test-Path $PortableDir) { Remove-Item -Recurse -Force $PortableDir }
New-Item -ItemType Directory -Force -Path $PortableDir | Out-Null

# Copy PyInstaller onedir bundle
Write-Host "    Copying app bundle..." -ForegroundColor Gray
Copy-Item -Recurse "$BundleDir\*" $PortableDir

# Copy bundled Tesseract if present
$TessBundle = Join-Path $PSScriptRoot "tesseract-bundle"
if (Test-Path $TessBundle) {
    Write-Host "    Including bundled Tesseract..." -ForegroundColor Gray
    Copy-Item -Recurse $TessBundle (Join-Path $PortableDir "tesseract")
} else {
    Write-Host "    tesseract-bundle not found -- Tesseract not included in ZIP." -ForegroundColor Yellow
}

# Write README
$ReadmePath = Join-Path $PortableDir "README-PORTABLE.txt"
$TessLine = if (Test-Path $TessBundle) { "Tesseract OCR is bundled in the tesseract\ subfolder." } else { "Tesseract OCR is NOT included. Install it from https://github.com/UB-Mannheim/tesseract/wiki" }
$ReadmeLines = @(
    "zh-en-translator - Portable Edition",
    "=====================================",
    "",
    "USAGE",
    "-----",
    "1. Extract this folder anywhere (Desktop, USB drive, etc.)",
    "2. Run zh-en-translator.exe",
    "3. On first run the app will download:",
    "   - Offline translation model (~100 MB, one time)",
    "   - CC-CEDICT dictionary (~6 MB, one time)",
    "   These are saved to %APPDATA%\zh-en-translator\ and reused on next run.",
    "",
    "DOMAIN-SPECIFIC GLOSSARIES",
    "-------------------------",
    "Multi-domain support for technical translation:",
    "  - Manufacturing: 149 terms (materials, machining, heat treatment, etc.)",
    "  - Medical: 504 terms (anatomy, treatments, medications, etc.)",
    "  - Legal: 409 terms (contracts, IP, commercial law, etc.)",
    "  - Electronics: 452 terms (components, PCB design, RF, etc.)",
    "",
    "Enable/disable domains in Preferences (right-click system tray icon).",
    "Glossaries are automatically loaded from the bundled database on startup.",
    "",
    "TESSERACT OCR",
    "-------------",
    $TessLine,
    "",
    "HOTKEY",
    "------",
    "Default: Ctrl+Shift+T -- select Chinese text then press the hotkey to translate.",
    "Change in the system tray icon -> Preferences.",
    "",
    "UNINSTALL",
    "---------",
    "Delete this folder. App data is in %APPDATA%\zh-en-translator\ (delete that too for a clean uninstall)."
)
$ReadmeContent = ($ReadmeLines -join [Environment]::NewLine) + [Environment]::NewLine
[System.IO.File]::WriteAllText($ReadmePath, $ReadmeContent, [System.Text.Encoding]::UTF8)

# Create ZIP
Write-Host "    Zipping to $PortableZip..." -ForegroundColor Gray
New-Item -ItemType Directory -Force -Path (Split-Path $PortableZip) | Out-Null
if (Test-Path $PortableZip) { Remove-Item $PortableZip -Force }

Add-Type -AssemblyName System.IO.Compression.FileSystem
[System.IO.Compression.ZipFile]::CreateFromDirectory(
    $PortableDir,
    $PortableZip,
    [System.IO.Compression.CompressionLevel]::Optimal,
    $true   # includeBaseDirectory = true -> zip contains zh-en-translator-portable\ subfolder
)

Remove-Item -Recurse -Force $PortableDir

if (Test-Path $PortableZip) {
    $ZipSize = [math]::Round((Get-Item $PortableZip).Length / 1MB, 1)
    Write-Ok "Portable ZIP: $PortableZip ($ZipSize MB)"
} else {
    Write-Host "    WARNING: Portable ZIP not created." -ForegroundColor Yellow
}

# ---------------------------------------------------------------------------
# Step 6 -- Upload release to GitHub (zh-en-translator-releases)
# ---------------------------------------------------------------------------
if (-not $SkipRelease) {
    Write-Step "Step 6: Uploading release to GitHub (rogerneumann/zh-en-translator-releases)"

    # Check gh CLI is available and authenticated
    $GhExe = $null
    try {
        $GhExe = (Get-Command gh -ErrorAction Stop).Source
        Write-Ok "GitHub CLI found: ${GhExe}"
    } catch {
        Write-Host "    WARNING: GitHub CLI (gh) not found -- skipping release upload." -ForegroundColor Yellow
        Write-Host "    Install from https://cli.github.com/ and authenticate with 'gh auth login'." -ForegroundColor Yellow
        Write-Host "    Then re-run with -SkipVersionBump -SkipPyInstaller to upload only." -ForegroundColor Yellow
    }

    if ($GhExe) {
        # Verify authentication before attempting upload
        & gh auth status 2>&1 | Out-Null
        if ($LASTEXITCODE -ne 0) {
            Write-Host "    WARNING: gh is not authenticated. Run 'gh auth login' first." -ForegroundColor Yellow
            $GhExe = $null
        }
    }

    if ($GhExe) {
        $ReleasesRepo = "rogerneumann/zh-en-translator-releases"
        $ReleaseTag   = "v${VersionString}"
        $ReleaseTitle = "v${VersionString}"

        # Collect assets that exist
        $Assets = [System.Collections.Generic.List[string]]::new()
        if (Test-Path $OutputFile)  { $Assets.Add($OutputFile) }
        if (Test-Path $PortableZip) { $Assets.Add($PortableZip) }

        if ($Assets.Count -eq 0) {
            Write-Host "    WARNING: No build artifacts found to upload -- skipping." -ForegroundColor Yellow
        } else {
            Write-Host "    Creating release ${ReleaseTag} on ${ReleasesRepo}..." -ForegroundColor Gray
            foreach ($a in $Assets) {
                Write-Host "    Asset: $(Split-Path -Leaf $a)" -ForegroundColor Gray
            }

            $GhArgs = @(
                "release", "create", $ReleaseTag,
                "--repo", $ReleasesRepo,
                "--title", $ReleaseTitle,
                "--notes", "Installer and portable ZIP for ${ReleaseTitle}."
            ) + $Assets.ToArray()

            & gh @GhArgs
            if ($LASTEXITCODE -ne 0) {
                Write-Host "    WARNING: GitHub release upload failed (exit $LASTEXITCODE)" -ForegroundColor Yellow
                Write-Host "    Check 'gh auth status' and 'gh release list --repo ${ReleasesRepo}' for details." -ForegroundColor Yellow
            } else {
                Write-Ok "Released ${ReleaseTag} on ${ReleasesRepo}"
                foreach ($a in $Assets) {
                    Write-Ok "  Uploaded: $(Split-Path -Leaf $a)"
                }
            }
        }
    }
} else {
    Write-Step "Step 6: Skipping GitHub release upload (-SkipRelease)"
}

Write-Host ""
Write-Host "Done!" -ForegroundColor Green
