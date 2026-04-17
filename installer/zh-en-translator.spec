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
#   - runtime_hooks/set_qt_path.py adds PyQt6/Qt6/bin to the DLL search path
#     before first import, fixing "No module named PyQt6.QtCore" on Windows

import os
import sys
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files, collect_all, collect_submodules

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
repo_root  = Path(SPECPATH).parent  # SPECPATH = directory containing this file
src_root   = repo_root / "src"
hooks_dir  = Path(SPECPATH) / "runtime_hooks"

# ---------------------------------------------------------------------------
# Explicit PyQt6 binary collection
# Fallback: if collect_all misses the Qt6 DLLs (common with PyQt6 6.x),
# walk the Qt6/bin directory and add each DLL explicitly.
# ---------------------------------------------------------------------------
try:
    import PyQt6 as _pyqt6
    _qt6_bin = Path(_pyqt6.__file__).parent / "Qt6" / "bin"
    _extra_bins = []
    if _qt6_bin.is_dir():
        for _dll in _qt6_bin.glob("*.dll"):
            _extra_bins.append((str(_dll), "PyQt6/Qt6/bin"))
    print(f"[spec] found {len(_extra_bins)} Qt6 DLLs in {_qt6_bin}")
except Exception as _e:
    print(f"[spec] PyQt6 explicit DLL scan skipped: {_e}")
    _extra_bins = []

# ---------------------------------------------------------------------------
# Hidden imports
# ---------------------------------------------------------------------------
hidden_imports = [
    # PyQt6 — explicit core modules (collect_all alone sometimes misses these)
    "PyQt6.sip",
    "PyQt6.QtCore",
    "PyQt6.QtGui",
    "PyQt6.QtWidgets",
    "PyQt6.QtNetwork",
    "PyQt6.QtOpenGL",
    "PyQt6.QtOpenGLWidgets",
    "PyQt6.QtPrintSupport",
    "PyQt6.QtSvg",
    "PyQt6.QtXml",
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
    "winreg",
]

# Collect all PyQt6 submodules so no Qt binding is accidentally omitted
hidden_imports += collect_submodules("PyQt6")

# ---------------------------------------------------------------------------
# Data files
# ---------------------------------------------------------------------------
datas = []

# zh_en_translator package data (resources/cedict_sample.txt etc.)
zh_en_data, zh_en_bins, zh_en_hidden = collect_all("zh_en_translator")
datas          += zh_en_data
hidden_imports += zh_en_hidden

# PyQt6 — plugins, translations, and binaries
pyqt6_data, pyqt6_bins, pyqt6_hidden = collect_all("PyQt6")
datas          += pyqt6_data
hidden_imports += pyqt6_hidden

# ctranslate2 — runtime DLLs and data
ct2_data, ct2_bins, ct2_hidden = collect_all("ctranslate2")
datas          += ct2_data
hidden_imports += ct2_hidden

# argostranslate — package metadata (models downloaded at runtime)
argos_data, argos_bins, argos_hidden = collect_all("argostranslate")
datas          += argos_data
hidden_imports += argos_hidden

# Merge explicit Qt6 DLLs with what collect_all found (dedup by dest path)
all_bins = zh_en_bins + pyqt6_bins + ct2_bins + argos_bins + _extra_bins

# ---------------------------------------------------------------------------
# Analysis
# ---------------------------------------------------------------------------
a = Analysis(
    [str(src_root / "zh_en_translator" / "app.py")],
    pathex=[str(src_root)],
    binaries=all_bins,
    datas=datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    # Runtime hook extends the DLL search path before any Qt import
    runtime_hooks=[str(hooks_dir / "set_qt_path.py")],
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
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
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
