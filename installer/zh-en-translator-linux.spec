# PyInstaller spec for Linux onedir build.
# Run via: installer/build_linux.sh
# Or directly: pyinstaller installer/zh-en-translator-linux.spec

import sys
from pathlib import Path

repo_root = Path(SPECPATH).parent
src = repo_root / "src" / "zh_en_translator"

a = Analysis(
    [str(src / "app.py")],
    pathex=[str(repo_root / "src")],
    binaries=[],
    datas=[
        (str(src / "resources"), "zh_en_translator/resources"),
        (str(repo_root / "translation_icn.svg"), "."),
    ],
    hiddenimports=[
        # PyQt6
        "PyQt6.sip",
        "PyQt6.QtSvg",
        "PyQt6.QtWidgets",
        "PyQt6.QtCore",
        "PyQt6.QtGui",
        # OCR
        "pytesseract",
        "PIL",
        "PIL.Image",
        # Translation
        "argostranslate",
        "argostranslate.package",
        "argostranslate.translate",
        "jieba",
        "jieba.analyse",
        # Config / state
        "platformdirs",
        "toml",
        # Segmentation
        "zh_en_translator.engines.segmentation",
        # OpenCC (traditional Chinese, optional)
        "opencc",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Windows-only
        "winreg",
        "winrt",
        "winsdk",
        # Heavy optional ML deps not needed at runtime
        "paddle",
        "paddleocr",
        "torch",
        "torchvision",
        "tensorflow",
        "opennmt",
        "ctranslate2",
        "sentencepiece",
    ],
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data)

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
    console=False,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(repo_root / "translation_icn.svg"),
)

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
