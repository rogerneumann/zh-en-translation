# -*- mode: python ; coding: utf-8 -*-
#
# PyInstaller spec for zh-en-translator
#
# Build from repo root:
#   pyinstaller installer/zh-en-translator.spec --distpath dist --workpath build
#
# Notes:
#   - onedir mode so Inno Setup can bundle the whole dist\zh-en-translator\ folder
#   - UPX disabled: ctranslate2 / sentencepiece DLLs break under UPX compression
#   - strip disabled: breaks some compiled extensions on Windows
#   - Argos model pack is NOT included — it's downloaded post-install (~50-100 MB)

import sys
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files, collect_all

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
repo_root = Path(SPECPATH).parent  # SPECPATH = directory containing this file
src_root  = repo_root / "src"

# ---------------------------------------------------------------------------
# Hidden imports
# ---------------------------------------------------------------------------
hidden_imports = [
    "PyQt6.sip",
    "pynput.keyboard",
    "pynput.mouse",
    "pyperclip",
    "platformdirs",
    "tomllib",
    "jieba",
    "ctranslate2",
    "sentencepiece",
    "argostranslate",
    "argostranslate.translate",
    "argostranslate.package",
    # winreg is built-in on Windows; keep as fallback import guard
    "winreg",
]

# ---------------------------------------------------------------------------
# Data files
# ---------------------------------------------------------------------------
datas = []

# zh_en_translator package data (resources/cedict_sample.txt etc.)
zh_en_data, zh_en_bins, zh_en_hidden = collect_all("zh_en_translator")
datas   += zh_en_data
hidden_imports += zh_en_hidden

# PyQt6 — plugins, translations
pyqt6_data, pyqt6_bins, pyqt6_hidden = collect_all("PyQt6")
datas   += pyqt6_data
hidden_imports += pyqt6_hidden

# ctranslate2 — runtime DLLs and data
ct2_data, ct2_bins, ct2_hidden = collect_all("ctranslate2")
datas   += ct2_data
hidden_imports += ct2_hidden

# argostranslate — package metadata (not the model; models downloaded at runtime)
argos_data, argos_bins, argos_hidden = collect_all("argostranslate")
datas   += argos_data
hidden_imports += argos_hidden

# ---------------------------------------------------------------------------
# Analysis
# ---------------------------------------------------------------------------
a = Analysis(
    [str(src_root / "zh_en_translator" / "app.py")],
    pathex=[str(src_root)],
    binaries=zh_en_bins + pyqt6_bins + ct2_bins + argos_bins,
    datas=datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Explicitly excluded — not used, saves 100+ MB
        "stanza",
        "torch",
        "spacy",
        "paddleocr",
        "paddle",
        "tensorflow",
        "matplotlib",
        "scipy",
        "numpy.testing",
        "IPython",
        "notebook",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=None,
    noarchive=False,
)

# ---------------------------------------------------------------------------
# PYZ
# ---------------------------------------------------------------------------
pyz = PYZ(a.pure, a.zipped_data, cipher=None)

# ---------------------------------------------------------------------------
# EXE
# ---------------------------------------------------------------------------
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,   # onedir: binaries go into COLLECT
    name="zh-en-translator",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,             # strip=True breaks some Windows DLLs
    upx=False,               # UPX breaks ctranslate2 and sentencepiece DLLs
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,           # windowed app — no console window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,        # x64 (matches Python 3.11 x64)
    codesign_identity=None,
    entitlements_file=None,
    # icon=None,             # no custom .ico yet
)

# ---------------------------------------------------------------------------
# COLLECT  (produces dist\zh-en-translator\)
# ---------------------------------------------------------------------------
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="zh-en-translator",
)
