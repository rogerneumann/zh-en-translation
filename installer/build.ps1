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

# ---------------------------------------------------------------------------
# Locate repo root (script lives in installer\, repo root is one level up)
# ---------------------------------------------------------------------------
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot
Write-Step "Working directory: $RepoRoot"

# ---------------------------------------------------------------------------
# Step 0 — Verify Python version is 3.11.x
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
# Step 1 — Verify PyInstaller is available via the active Python
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
# Step 1.5 — Install package dependencies
# ---------------------------------------------------------------------------
Write-Step "Step 1.5: Installing package dependencies (pip install -e .)"
Write-Host "    This ensures PyQt6, ctranslate2 etc. are present for PyInstaller to bundle." -ForegroundColor Gray

& pip install -e . --quiet
if ($LASTEXITCODE -ne 0) {
    Write-Fail "pip install -e . failed (exit code $LASTEXITCODE)"
    Write-Host "    Fix the install error above, then re-run this script." -ForegroundColor Yellow
    exit $LASTEXITCODE
}
Write-Ok "Dependencies installed"

# ---------------------------------------------------------------------------
# Step 2 — Run PyInstaller
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
# Step 2.5 — Download Tesseract portable for bundling
# ---------------------------------------------------------------------------
Write-Step "Step 2.5: Bundling Tesseract OCR (portable)"
$TessBundle = Join-Path $PSScriptRoot "tesseract-bundle"
if (Test-Path $TessBundle) {
    Write-Ok "tesseract-bundle already exists — skipping download"
} else {
    # Download installer
    $TessSetup = Join-Path $env:TEMP "tesseract-ocr-setup.exe"
    $TessUrl = "https://github.com/UB-Mannheim/tesseract/releases/download/v5.5.0.20241111/tesseract-ocr-w64-setup-5.5.0.20241111.exe"
    Write-Host "    Downloading Tesseract from $TessUrl" -ForegroundColor Gray
    (New-Object System.Net.WebClient).DownloadFile($TessUrl, $TessSetup)

    # Install silently to tesseract-bundle/
    Write-Host "    Installing Tesseract to tesseract-bundle\..." -ForegroundColor Gray
    $p = Start-Process $TessSetup -ArgumentList "/VERYSILENT /NORESTART /DIR=`"$TessBundle`"" -Wait -PassThru
    Remove-Item $TessSetup -Force -ErrorAction SilentlyContinue
    if ($p.ExitCode -ne 0) { Write-Fail "Tesseract install failed (exit $($p.ExitCode))"; exit 1 }

    # Download chi_sim.traineddata into tessdata/
    $TessData = Join-Path $TessBundle "tessdata"
    New-Item -ItemType Directory -Force -Path $TessData | Out-Null
    $ChiSim = Join-Path $TessData "chi_sim.traineddata"
    if (-not (Test-Path $ChiSim)) {
        Write-Host "    Downloading chi_sim.traineddata..." -ForegroundColor Gray
        (New-Object System.Net.WebClient).DownloadFile(
            "https://github.com/tesseract-ocr/tessdata_fast/raw/main/chi_sim.traineddata",
            $ChiSim
        )
    }
    Write-Ok "Tesseract bundle ready at: $TessBundle"
}

# ---------------------------------------------------------------------------
# Step 2.6 — Download CC-CEDICT for bundling
# ---------------------------------------------------------------------------
Write-Step "Step 2.6: Bundling CC-CEDICT"
$CedictBundle = Join-Path $PSScriptRoot "cedict-bundle"
$CedictFile = Join-Path $CedictBundle "cedict_ts.u8"
if (Test-Path $CedictFile) {
    Write-Ok "cedict-bundle already exists — skipping download"
} else {
    New-Item -ItemType Directory -Force -Path $CedictBundle | Out-Null
    Write-Host "    Downloading CC-CEDICT from mdbg.net..." -ForegroundColor Gray
    try {
        $ZipBytes = (New-Object System.Net.WebClient).DownloadData(
            "https://www.mdbg.net/chinese/export/cedict/cedict_1_0_ts_utf-8_mdbg.zip"
        )
        Add-Type -AssemblyName System.IO.Compression.FileSystem
        $zip = [System.IO.Compression.ZipArchive]::new([System.IO.MemoryStream]::new($ZipBytes))
        $entry = $zip.Entries | Where-Object { $_.Name -eq "cedict_ts.u8" } | Select-Object -First 1
        $stream = $entry.Open()
        $out = [System.IO.File]::Create($CedictFile)
        $stream.CopyTo($out); $out.Close(); $stream.Close()
        $zip.Dispose()
        Write-Ok "CC-CEDICT saved to: $CedictFile"
    } catch {
        Write-Host "    WARNING: CC-CEDICT download failed: $_" -ForegroundColor Yellow
        Write-Host "    The app will download it on first run instead." -ForegroundColor Yellow
    }
}

# ---------------------------------------------------------------------------
# Step 2.7 — Download Argos zh->en model for bundling
# ---------------------------------------------------------------------------
Write-Step "Step 2.7: Bundling Argos zh->en model (~100 MB)"
$ArgosBundle = Join-Path $PSScriptRoot "argos-bundle"
if ((Test-Path $ArgosBundle) -and (Get-ChildItem $ArgosBundle -Recurse -Filter "model.bin" | Select-Object -First 1)) {
    Write-Ok "argos-bundle already exists — skipping download"
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
# Step 3 — Locate Inno Setup compiler (iscc.exe)
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
# Step 4 — Run Inno Setup compiler
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
# Step 5 — Report output
# ---------------------------------------------------------------------------
Write-Step "Step 5: Build complete"

$OutputFile = Join-Path $PSScriptRoot "Output\zh-en-translator-setup.exe"
if (Test-Path $OutputFile) {
    $Size = (Get-Item $OutputFile).Length
    $SizeMB = [math]::Round($Size / 1MB, 1)
    Write-Ok "Installer produced: $OutputFile ($SizeMB MB)"
} else {
    Write-Host "    WARNING: Expected output file not found: $OutputFile" -ForegroundColor Yellow
    Write-Host "    Check Inno Setup output above for the actual output path." -ForegroundColor Yellow
}

# ---------------------------------------------------------------------------
# Step 5.1 — Create portable ZIP archive
# ---------------------------------------------------------------------------
Write-Step "Step 5.1: Creating portable ZIP archive"

$PortableDir  = Join-Path $env:TEMP "zh-en-translator-portable"
$PortableZip  = Join-Path $PSScriptRoot "Output\zh-en-translator-portable.zip"

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
    Write-Host "    tesseract-bundle not found — Tesseract not included in ZIP." -ForegroundColor Yellow
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
    $true   # includeBaseDirectory = true → zip contains zh-en-translator-portable\ subfolder
)

Remove-Item -Recurse -Force $PortableDir

if (Test-Path $PortableZip) {
    $ZipSize = [math]::Round((Get-Item $PortableZip).Length / 1MB, 1)
    Write-Ok "Portable ZIP: $PortableZip ($ZipSize MB)"
} else {
    Write-Host "    WARNING: Portable ZIP not created." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Done!" -ForegroundColor Green
