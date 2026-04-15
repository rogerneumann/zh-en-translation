# Windows install helper for Python 3.14+
#
# argostranslate 1.9.6 pins sentencepiece==0.2.0, which has no pre-built wheel
# for Python 3.14 and fails to build from source (no MSVC/cmake in PATH).
# This script installs sentencepiece 0.2.1 (binary-only) first, then installs
# argostranslate without its locked sentencepiece dep.
#
# Usage (from repo root, inside an activated venv):
#   .\scripts\install-windows.ps1
#   .\scripts\install-windows.ps1 -Extras "ocr-windows"   # also install winsdk

param(
    [string]$Extras = "dev"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

Write-Host "==> Installing sentencepiece (binary-only, Python 3.14 compatible)..." -ForegroundColor Cyan
pip install "sentencepiece>=0.2.0" --only-binary :all:

Write-Host "==> Installing argostranslate runtime deps (ctranslate2, sacremoses, packaging)..." -ForegroundColor Cyan
pip install ctranslate2 sacremoses packaging

Write-Host "==> Installing argostranslate without its locked sentencepiece dep..." -ForegroundColor Cyan
pip install "argostranslate>=1.9.0,<1.10.0" --no-deps

Write-Host "==> Installing project + extras [$Extras] without re-resolving argostranslate deps..." -ForegroundColor Cyan
pip install -e ".[$Extras]" --no-deps

# Remaining direct deps (PyQt6, pynput, pyperclip, platformdirs already in pyproject.toml
# but --no-deps skips them above — install them normally since they have clean wheels)
Write-Host "==> Installing remaining project deps..." -ForegroundColor Cyan
pip install PyQt6 pynput pyperclip platformdirs

if ($Extras -ne "dev") {
    Write-Host "==> Installing dev extras (pytest, ruff)..." -ForegroundColor Cyan
    pip install pytest pytest-qt ruff
}

Write-Host ""
Write-Host "Done! Run the app with:" -ForegroundColor Green
Write-Host "  zh-en-translator" -ForegroundColor White
Write-Host ""
Write-Host "Run tests with:" -ForegroundColor Green
Write-Host "  pytest -x" -ForegroundColor White
