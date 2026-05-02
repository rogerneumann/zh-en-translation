#!/usr/bin/env bash
# Build a PyInstaller onedir bundle for Linux.
#
# Usage:
#   ./installer/build_linux.sh [--portable]
#
# Output:
#   dist/zh-en-translator/           -- onedir bundle
#   dist/zh-en-translator.tar.gz     -- portable archive (with --portable)
#
# Prerequisites (Debian/Ubuntu):
#   sudo apt install python3.11 python3.11-venv python3-pip \
#       tesseract-ocr tesseract-ocr-chi-sim tesseract-ocr-chi-tra \
#       libxcb-* libgl1
#   pip install pyinstaller
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
DIST="$REPO_ROOT/dist"
PORTABLE=false

for arg in "$@"; do
    [[ "$arg" == "--portable" ]] && PORTABLE=true
done

cd "$REPO_ROOT"

echo "==> Installing Python dependencies"
pip install -e ".[linux]" --quiet

echo "==> Verifying PyInstaller"
if ! command -v pyinstaller &>/dev/null; then
    echo "    pyinstaller not found — installing"
    pip install pyinstaller
fi

echo "==> Running PyInstaller"
pyinstaller installer/zh-en-translator-linux.spec --noconfirm

echo "==> Build complete: $DIST/zh-en-translator/"

if $PORTABLE; then
    ARCHIVE="$DIST/zh-en-translator-linux-portable.tar.gz"
    echo "==> Creating portable archive: $ARCHIVE"
    tar -czf "$ARCHIVE" -C "$DIST" zh-en-translator
    echo "    Written: $ARCHIVE"
fi
