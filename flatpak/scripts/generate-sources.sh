#!/usr/bin/env bash
# Regenerate flatpak/generated-sources.json from the pinned requirements file.
# Run this whenever Python dependencies change.
#
# Prerequisites:
#   pip install flatpak-pip-generator
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FLATPAK_DIR="$(dirname "$SCRIPT_DIR")"

flatpak-pip-generator \
    --runtime org.freedesktop.Platform//24.08 \
    --output "$FLATPAK_DIR/generated-sources" \
    PyQt6 \
    PyQt6-Qt6 \
    PyQt6-sip \
    pynput \
    platformdirs \
    "argostranslate>=1.9.0,<1.10.0" \
    jieba \
    opencc-python-reimplemented \
    pytesseract \
    Pillow \
    toml

echo "generated-sources.json written to $FLATPAK_DIR/generated-sources.json"
