# Windows install helper for Python 3.14+
#
# Two known issues with a plain `pip install -e ".[dev]"` on Python 3.14 Windows:
#
# 1. argostranslate 1.9.6 pins sentencepiece==0.2.0, which has no pre-built
#    wheel for Python 3.14 and fails to compile from source.
#    Fix: install sentencepiece>=0.2.0 binary-only first (picks up 0.2.1).
#
# 2. winsdk (Windows OCR) also requires a C compiler.
#    Fix: use winrt-* namespace packages instead (pre-built binary wheels).
#
# Usage (from repo root, inside an activated venv):
#   .\scripts\install-windows.ps1              # base + dev tools
#   .\scripts\install-windows.ps1 -OCR         # also install Windows OCR support

param(
    [switch]$OCR
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

Write-Host "==> Installing sentencepiece (binary-only, Python 3.14 compatible)..." -ForegroundColor Cyan
pip install "sentencepiece>=0.2.0" --only-binary :all:

Write-Host "==> Installing argostranslate runtime deps (ctranslate2, sacremoses, packaging)..." -ForegroundColor Cyan
pip install ctranslate2 sacremoses packaging

Write-Host "==> Installing argostranslate without its locked sentencepiece dep..." -ForegroundColor Cyan
pip install "argostranslate>=1.9.0,<1.10.0" --no-deps

Write-Host "==> Installing remaining project deps..." -ForegroundColor Cyan
pip install PyQt6 pynput pyperclip platformdirs

Write-Host "==> Installing dev extras (pytest, ruff)..." -ForegroundColor Cyan
pip install pytest pytest-qt ruff

Write-Host "==> Installing project (editable, no-deps)..." -ForegroundColor Cyan
pip install -e . --no-deps

if ($OCR) {
    Write-Host "==> Installing Windows OCR support (winrt namespace packages)..." -ForegroundColor Cyan
    # winrt-* packages have pre-built wheels; no C compiler needed.
    # Falls back to winsdk in windows_ocr.py if these are unavailable.
    pip install `
        winrt-runtime `
        "winrt-Windows.Media.Ocr" `
        "winrt-Windows.Graphics.Imaging" `
        "winrt-Windows.Storage.Streams" `
        "winrt-Windows.Globalization"

    if ($LASTEXITCODE -ne 0) {
        Write-Warning "winrt-* install failed (no Python 3.14 wheels yet?)."
        Write-Warning "OCR will fall back to Tesseract if installed."
        Write-Warning "To use Tesseract: install from https://github.com/UB-Mannheim/tesseract/wiki"
        Write-Warning "then: pip install pytesseract Pillow"
    }
}

Write-Host ""
Write-Host "Done! Run the app with:" -ForegroundColor Green
Write-Host "  zh-en-translator" -ForegroundColor White
Write-Host ""
Write-Host "Run tests with:" -ForegroundColor Green
Write-Host "  pytest -x" -ForegroundColor White
