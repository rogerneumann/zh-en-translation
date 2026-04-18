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

Write-Host ""
Write-Host "Done!" -ForegroundColor Green
