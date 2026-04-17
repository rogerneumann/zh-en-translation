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
#   - Argos model pack is NOT included — downloaded post-install (~50-100 MB)
#   - PyQt6 entire directory copied as datas (brute-force, handles any 6.x layout)
#   - runtime_hooks/set_qt_path.py adds all PyQt6 subdirs to DLL search path

import os
import sys
from pathlib import Path
from PyInstaller.utils.hooks import collect_all, collect_submodules

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
repo_root  = Path(SPECPATH).parent
src_root   = repo_root / "src"
hooks_dir  = Path(SPECPATH) / "runtime_hooks"

# ---------------------------------------------------------------------------
# Locate PyQt6 in the active Python environment and copy it wholesale.
# This is the most reliable approach for PyQt6 6.x where collect_all()
# may miss DLLs due to changed package layout between minor versions.
# ---------------------------------------------------------------------------
import PyQt6 as _pyqt6_pkg
_pyqt6_root = Path(_pyqt6_pkg.__file__).parent
print(f"[spec] PyQt6 root: {_pyqt6_root}")
print(f"[spec] PyQt6 version: {_pyqt6_pkg.QtCore.PYQT_VERSION_STR if hasattr(_pyqt6_pkg, 'QtCore') else 'unknown'}")

# Walk PyQt6 tree: collect every file as a (src, dest_dir) tuple for datas.
# This guarantees .pyd files, Qt DLLs, plugins, and translations all arrive.
_pyqt6_datas = []
for _root, _dirs, _files in os.walk(_pyqt6_root):
    for _f in _files:
        _src = os.path.join(_root, _f)
        _rel = os.path.relpath(_root, _pyqt6_root.parent)
        _pyqt6_datas.append((_src, _rel))

print(f"[spec] Collected {len(_pyqt6_datas)} PyQt6 files via directory walk")

# ---------------------------------------------------------------------------
# Hidden imports
# ---------------------------------------------------------------------------
hidden_imports = [
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
hidden_imports += collect_submodules("PyQt6")

# ---------------------------------------------------------------------------
# Data files and binaries from other packages
# ---------------------------------------------------------------------------
datas = list(_pyqt6_datas)  # start with the full PyQt6 tree

zh_en_data, zh_en_bins, zh_en_hidden = collect_all("zh_en_translator")
datas          += zh_en_data
hidden_imports += zh_en_hidden

ct2_data, ct2_bins, ct2_hidden = collect_all("ctranslate2")
datas          += ct2_data
hidden_imports += ct2_hidden

argos_data, argos_bins, argos_hidden = collect_all("argostranslate")
datas          += argos_data
hidden_imports += argos_hidden

# PyQt6 binaries from collect_all as belt-and-suspenders (may add extra DLLs)
_, pyqt6_bins, pyqt6_hidden = collect_all("PyQt6")
hidden_imports += pyqt6_hidden

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
    runtime_hooks=[str(hooks_dir / "set_qt_path.py")],
    excludes=[
        "stanza", "torch", "spacy",
        "paddleocr", "paddle", "tensorflow",
        "matplotlib", "scipy", "numpy.testing",
        "IPython", "notebook",
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
    exclude_binaries=True,
    name="zh-en-translator",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

# ---------------------------------------------------------------------------
# COLLECT
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
