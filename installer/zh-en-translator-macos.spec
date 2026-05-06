# PyInstaller spec for macOS (Apple Silicon) onedir + .app bundle build.
# Run via GitHub Actions: pyinstaller installer/zh-en-translator-macos.spec
# Bundles: Tesseract arm64 binary, CC-CEDICT, Argos zh<->en models, all resources.
# Tesseract binary and models must be staged to installer/tesseract-bundle-macos/
# before running PyInstaller (done by the CI workflow).

import sys
from pathlib import Path
from PyInstaller.utils.hooks import collect_all, collect_data_files

repo_root = Path(SPECPATH).parent
src = repo_root / "src" / "zh_en_translator"
tesseract_bundle = repo_root / "installer" / "tesseract-bundle-macos"
argos_bundle     = repo_root / "installer" / "argos-bundle"
argos_en_zh      = repo_root / "installer" / "argos-en-zh-bundle"
cedict_bundle    = repo_root / "installer" / "cedict-bundle"

# --- Argos / ctranslate2 / sentencepiece collect_all ---
argos_data, argos_bins, argos_hidden = collect_all("argostranslate")
ct2_data,   ct2_bins,   ct2_hidden   = collect_all("ctranslate2")
spm_data,   spm_bins,   spm_hidden   = collect_all("sentencepiece")

try:
    pyt_data, pyt_bins, pyt_hidden = collect_all("pytesseract")
except Exception as e:
    print(f"[spec] pytesseract not found, skipping: {e}")
    pyt_data, pyt_bins, pyt_hidden = [], [], []

a = Analysis(
    [str(src / "__main__.py")],
    pathex=[str(repo_root / "src")],
    binaries=[
        (str(tesseract_bundle / "tesseract"), "tesseract"),
    ] + argos_bins + ct2_bins + spm_bins + pyt_bins,
    datas=[
        (str(src / "resources"),                       "zh_en_translator/resources"),
        (str(tesseract_bundle / "tessdata"),            "tesseract/tessdata"),
        (str(cedict_bundle / "cedict_ts.u8"),           "zh_en_translator/resources"),
        (str(argos_bundle),                             "argos-bundle"),
        (str(argos_en_zh),                              "argos-en-zh-bundle"),
    ] + argos_data + ct2_data + spm_data + pyt_data,
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
        "ctranslate2",
        "sentencepiece",
        "jieba",
        "jieba.analyse",
        # Config / state
        "platformdirs",
        "toml",
        # Segmentation
        "zh_en_translator.engines.segmentation",
        # OpenCC (traditional Chinese)
        "opencc",
    ] + argos_hidden + ct2_hidden + spm_hidden + pyt_hidden,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[
        str(repo_root / "installer" / "runtime_hooks" / "macos_paths.py"),
    ],
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
        "stanza",
        "spacy",
        "matplotlib",
        "scipy",
        "IPython",
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
    target_arch="arm64",
    codesign_identity=None,
    entitlements_file=None,
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

app = BUNDLE(
    coll,
    name="Zh-En Translator.app",
    icon=str(repo_root / "installer" / "icon.icns"),
    bundle_identifier="com.rogerneumann.zh-en-translator",
    info_plist={
        "CFBundleDisplayName": "Zh-En Translator",
        "CFBundleShortVersionString": "1.0.0",
        "NSAccessibilityUsageDescription": (
            "Zh-En Translator needs Accessibility access to capture selected text "
            "with the global hotkey."
        ),
        "LSUIElement": True,
    },
)
