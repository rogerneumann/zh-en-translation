# Linux Desktop Port & Flatpak Packaging Plan

**Date:** 2026-05-01  
**Scope:** Make zh-en-translator run natively on Linux desktops; distribute via Flatpak.

---

## Overview

The application core is already mostly cross-platform — PyQt6, pynput, argostranslate, jieba, and
Tesseract all run on Linux without changes. The work falls into four areas:

1. **Code changes** — remove or adapt Windows-specific code paths
2. **Linux packaging** — replace Inno Setup / PowerShell with a Flatpak manifest + build script
3. **Runtime & distribution** — AppStream metadata, `.desktop` file, Flathub submission prep
4. **Known hard problems** — global hotkeys under Wayland, system-tray compatibility

Estimated effort: **~3–4 days** of focused work to a working Flatpak build, plus another day for
Flathub submission prep.

---

## Part 1 — Code Changes Required

### 1.1 Windows OCR removal (`engines/ocr/windows_ocr.py`)

`windows_ocr.py` wraps the WinRT `Windows.Media.Ocr` API, which does not exist on Linux.

**Action:** The OCR waterfall in `engines/ocr/engine.py` already has Tesseract and PaddleOCR as
fallbacks. On Linux simply never register Windows OCR as a candidate.

```python
# engines/ocr/engine.py — change the candidate list to be platform-aware
import sys

def _build_candidates():
    candidates = []
    if sys.platform == "win32":
        candidates.append(WindowsOcrEngine())
    candidates.append(TesseractOcrEngine())
    candidates.append(PaddleOcrEngine())
    return candidates
```

No other file needs to change for OCR.

---

### 1.2 Tesseract path discovery (`engines/ocr/tesseract_ocr.py` lines 11–25)

Current code only looks in Windows paths. Add Linux paths:

```python
def _get_tesseract_candidates() -> list[Path]:
    paths = []

    # Frozen / Flatpak bundled binary
    if getattr(sys, "frozen", False):
        paths.append(Path(sys.executable).parent / "tesseract" / "tesseract")
    flatpak_path = Path("/app/bin/tesseract")
    if flatpak_path.exists():
        paths.append(flatpak_path)

    if sys.platform == "win32":
        appdata = os.environ.get("LOCALAPPDATA", "")
        paths += [
            Path(appdata) / "Programs" / "Tesseract-OCR" / "tesseract.exe",
            Path("C:/Program Files/Tesseract-OCR/tesseract.exe"),
            Path("C:/Program Files (x86)/Tesseract-OCR/tesseract.exe"),
        ]
    else:
        # Linux / macOS — check PATH first, then common prefixes
        from shutil import which
        system_tess = which("tesseract")
        if system_tess:
            paths.append(Path(system_tess))
        paths += [
            Path("/usr/bin/tesseract"),
            Path("/usr/local/bin/tesseract"),
            Path("/opt/homebrew/bin/tesseract"),  # macOS Homebrew
        ]

    return paths
```

---

### 1.3 "Run at login" — replace registry with XDG autostart (`app.py` lines 114–142)

Current code writes `HKCU\...\Run` on Windows.  
On Linux the equivalent is a `.desktop` file in `~/.config/autostart/`.

```python
def _apply_startup_setting(self, enable: bool) -> None:
    if sys.platform == "win32":
        # existing registry code unchanged
        ...
    else:
        autostart_dir = Path.home() / ".config" / "autostart"
        desktop_file = autostart_dir / "zh-en-translator.desktop"
        if enable:
            autostart_dir.mkdir(parents=True, exist_ok=True)
            exe = _get_frozen_exe_path() or shutil.which("zh-en-translator") or ""
            desktop_file.write_text(
                "[Desktop Entry]\n"
                "Type=Application\n"
                "Name=zh-en-translator\n"
                f"Exec={exe}\n"
                "Hidden=false\n"
                "X-GNOME-Autostart-enabled=true\n"
            )
        else:
            desktop_file.unlink(missing_ok=True)
```

---

### 1.4 Log viewer — replace `notepad.exe` with `xdg-open` (`ui/preferences.py` lines 598–615)

```python
def _open_tess_log(self) -> None:
    log_path = ...
    if sys.platform == "win32":
        subprocess.Popen(["notepad.exe", str(log_path)])
    else:
        subprocess.Popen(["xdg-open", str(log_path)])
```

---

### 1.5 Preferences dialog — hide Windows-only controls (`ui/preferences.py`)

Three controls are Windows-only and already have `sys.platform == "win32"` guards:

- Line 333: "Launch at Windows login" checkbox — rename to "Launch at login" and keep for Linux
  (the XDG autostart backend from 1.3 handles it).
- Line 546: "Reinstall Chinese OCR" button — hide on Linux (no Windows OCR).
- Lines 587–615: "Install Tesseract" / open log buttons — replace with a status label pointing
  users to `sudo apt install tesseract-ocr tesseract-ocr-chi-sim` or equivalent.

No structural changes needed; just update the platform guard and label text.

---

### 1.6 TEMP directory reference (`app.py` line 643, `ui/preferences.py` line 601)

Replace `os.environ.get("TEMP", "")` with `tempfile.gettempdir()` — works on all platforms.

---

### 1.7 Summary of files to edit

| File | Lines | Change |
|---|---|---|
| `engines/ocr/engine.py` | candidate list | Skip Windows OCR on non-win32 |
| `engines/ocr/tesseract_ocr.py` | 11–25 | Add Linux/Flatpak paths |
| `app.py` | 114–142 | XDG autostart for Linux |
| `app.py` | 643 | Use `tempfile.gettempdir()` |
| `ui/preferences.py` | 333, 546–615 | Update labels + platform guards |
| `pyproject.toml` | optional-deps | Add `linux` extra (see §2.3) |

No changes needed to: translation logic, dictionary, segmentation, sidebar, popup, history,
clipboard, themes, finetuning, or corpus code.

---

## Part 2 — Build System

### 2.1 Replace PowerShell build script with a shell script

Create `installer/build_linux.sh` to produce a PyInstaller onedir bundle:

```bash
#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$REPO_ROOT"

# 1. Install dependencies
pip install -e ".[ocr-tesseract,traditional]"
pip install pyinstaller

# 2. Run PyInstaller
pyinstaller installer/zh-en-translator-linux.spec

# 3. Output: dist/zh-en-translator/
echo "Build complete: dist/zh-en-translator/"
```

### 2.2 PyInstaller spec for Linux

Create `installer/zh-en-translator-linux.spec` — similar to the Windows spec but:

- Remove `winreg`, `winrt.*`, `winsdk` from hidden imports
- Remove `set_qt_path.py` runtime hook (DLL path fixup is Windows-only)
- Keep all translation, jieba, argostranslate, PyQt6 hidden imports
- Set `console=False` and include the SVG icon

```python
# installer/zh-en-translator-linux.spec  (abbreviated)
a = Analysis(
    ["../src/zh_en_translator/app.py"],
    hiddenimports=[
        "PyQt6.sip",
        "pytesseract", "PIL",
        "argostranslate", "jieba",
        "opencc",                    # if traditional extra installed
    ],
    datas=[
        ("../src/zh_en_translator/resources", "zh_en_translator/resources"),
    ],
    excludes=["paddle", "torch", "tensorflow", "winrt", "winsdk", "winreg"],
)
exe = EXE(a.pure, a.scripts, name="zh-en-translator", console=False)
coll = COLLECT(exe, a.binaries, a.datas, name="zh-en-translator")
```

### 2.3 `pyproject.toml` — add Linux extra

```toml
[project.optional-dependencies]
linux = [
    "pytesseract",
    "Pillow",
    "opencc-python-reimplemented>=1.1.0",
]
```

---

## Part 3 — Flatpak Packaging

### 3.1 Flatpak runtime choice

| Option | Runtime | Reason |
|---|---|---|
| **Recommended** | `org.freedesktop.Platform//24.08` | Smallest, widely available |
| Alternative | `org.kde.Platform//6.7` | Includes Qt 6 libs; larger |

Use `org.freedesktop.Platform//24.08` with the Python 3.11 SDK extension:

```
org.freedesktop.Sdk.Extension.python311//24.08
```

This provides CPython 3.11 at `/usr/lib/sdk/python311/` without bundling a full Python interpreter
from scratch.

### 3.2 Directory layout

```
flatpak/
├── io.github.zh_en_translator.yml          ← Flatpak manifest (main)
├── io.github.zh_en_translator.metainfo.xml ← AppStream metadata
├── io.github.zh_en_translator.desktop      ← .desktop file
├── icon.svg                                ← app icon (already exists: translation_icn.svg)
├── python-modules/                         ← pip-generated module sources
│   ├── requirements-flatpak.txt
│   └── generated-sources.json             ← flatpak-pip-generator output
└── shared-modules/                         ← git submodule (tesseract, leptonica)
```

### 3.3 Flatpak manifest (`io.github.zh_en_translator.yml`)

```yaml
app-id: io.github.zh_en_translator
runtime: org.freedesktop.Platform
runtime-version: "24.08"
sdk: org.freedesktop.Sdk
sdk-extensions:
  - org.freedesktop.Sdk.Extension.python311
command: zh-en-translator

finish-args:
  # Display
  - --socket=fallback-x11       # X11 fallback when Wayland not available
  - --socket=wayland            # Wayland display
  - --share=ipc                 # required for X11 shared memory
  - --device=dri                # GPU acceleration for rendering
  # Clipboard
  - --talk-name=org.freedesktop.portal.Desktop
  # Global hotkeys — see §3.6 for the Wayland caveat
  - --device=all                # evdev input (needed for pynput on Wayland)
  # Network: only for optional DeepL / Azure / update-check
  - --share=network
  # Filesystem: config + data dirs
  - --filesystem=xdg-config/zh-en-translator:create
  - --filesystem=xdg-data/zh-en-translator:create
  # Autostart .desktop file (for "run at login" feature)
  - --filesystem=xdg-config/autostart:create

modules:
  # ── Leptonica (Tesseract dependency) ──────────────────────────────────────
  - name: leptonica
    buildsystem: cmake-ninja
    config-opts:
      - -DBUILD_SHARED_LIBS=ON
    sources:
      - type: archive
        url: https://github.com/DanBloomberg/leptonica/releases/download/1.84.1/leptonica-1.84.1.tar.gz
        sha256: <sha256>

  # ── Tesseract OCR ─────────────────────────────────────────────────────────
  - name: tesseract
    buildsystem: cmake-ninja
    config-opts:
      - -DBUILD_TRAINING_TOOLS=OFF
    sources:
      - type: archive
        url: https://github.com/tesseract-ocr/tesseract/archive/refs/tags/5.3.4.tar.gz
        sha256: <sha256>

  # ── Tesseract Chinese traineddata ─────────────────────────────────────────
  - name: tesseract-chi-sim
    buildsystem: simple
    build-commands:
      - install -Dm644 chi_sim.traineddata /app/share/tessdata/chi_sim.traineddata
      - install -Dm644 chi_tra.traineddata /app/share/tessdata/chi_tra.traineddata
    sources:
      - type: file
        url: https://github.com/tesseract-ocr/tessdata_best/raw/main/chi_sim.traineddata
        sha256: <sha256>
      - type: file
        url: https://github.com/tesseract-ocr/tessdata_best/raw/main/chi_tra.traineddata
        sha256: <sha256>

  # ── Python packages (generated by flatpak-pip-generator) ──────────────────
  - name: python-deps
    buildsystem: simple
    build-commands:
      - pip3 install --prefix=/app --no-index --find-links=. PyQt6 pynput platformdirs
          argostranslate jieba opencc-python-reimplemented pytesseract Pillow
    sources:
      - generated-sources.json   # produced by flatpak-pip-generator

  # ── zh-en-translator application ──────────────────────────────────────────
  - name: zh-en-translator
    buildsystem: simple
    build-commands:
      - pip3 install --prefix=/app --no-build-isolation .
      - install -Dm644 flatpak/io.github.zh_en_translator.desktop
            /app/share/applications/io.github.zh_en_translator.desktop
      - install -Dm644 translation_icn.svg
            /app/share/icons/hicolor/scalable/apps/io.github.zh_en_translator.svg
      - install -Dm644 flatpak/io.github.zh_en_translator.metainfo.xml
            /app/share/metainfo/io.github.zh_en_translator.metainfo.xml
    sources:
      - type: dir
        path: ..
```

### 3.4 `.desktop` file

```ini
[Desktop Entry]
Version=1.0
Type=Application
Name=zh-en Translator
GenericName=Chinese–English Translator
Comment=Offline popup translator for Chinese text
Exec=zh-en-translator
Icon=io.github.zh_en_translator
Categories=Utility;Translation;
Keywords=Chinese;Mandarin;translation;OCR;
StartupNotify=false
```

### 3.5 AppStream metadata (`io.github.zh_en_translator.metainfo.xml`)

```xml
<?xml version="1.0" encoding="UTF-8"?>
<component type="desktop-application">
  <id>io.github.zh_en_translator</id>
  <name>zh-en Translator</name>
  <summary>Offline popup translator for Chinese text</summary>
  <description>
    <p>
      Offline-first Chinese to English translator with OCR support.
      Press a configurable hotkey to translate selected text or screen captures instantly.
    </p>
    <ul>
      <li>CC-CEDICT dictionary with inline word lookup</li>
      <li>Argos MT offline sentence translation</li>
      <li>Tesseract OCR for image text extraction</li>
      <li>Domain glossaries: manufacturing, medical, legal, electronics</li>
      <li>Translation history with CSV export</li>
    </ul>
  </description>
  <metadata_license>MIT</metadata_license>
  <project_license>MIT</project_license>
  <url type="homepage">https://github.com/rogerneumann/zh-en-translation</url>
  <releases>
    <release version="2.0.0" date="2026-05-01"/>
  </releases>
  <provides>
    <binary>zh-en-translator</binary>
  </provides>
  <content_rating type="oars-1.1"/>
</component>
```

### 3.6 Global hotkeys on Wayland — the hard problem

pynput uses `XGrabKey` on X11 (works everywhere) and `/dev/input` evdev on Wayland.

**Flatpak constraint:** evdev access requires `--device=all`, which is a broad permission that
Flathub reviewers flag. The XDG Global Shortcuts portal (`org.freedesktop.portal.GlobalShortcuts`,
available in KDE Plasma 5.27+ and GNOME 45+) is the correct long-term solution but requires a
custom implementation — pynput does not use it.

**Recommended approach (phased):**

| Phase | What | Trade-off |
|---|---|---|
| **Phase 1** | Ship with `--device=all` for full evdev access | Works everywhere; needs justification in Flathub submission |
| **Phase 2** | Implement portal-based hotkey registration via `dbus-python` | Wayland-native, no broad device permission; requires GNOME 45 / KDE 5.27+ |

For Phase 2, the hotkey module would call:
```
org.freedesktop.portal.GlobalShortcuts.CreateSession()
org.freedesktop.portal.GlobalShortcuts.BindShortcuts()
```
and listen to the `Activated` signal. Fall back to evdev if the portal is unavailable.

### 3.7 System tray on GNOME

GNOME Shell has removed the legacy StatusNotifierItem tray by default. Options:

1. **gnome-shell-extension-appindicator** — user must install; not ideal.
2. **`libayatana-appindicator`** — add as a Flatpak module; the more portable choice.
3. **Graceful degradation** — if the tray cannot register, show a persistent window instead of
   hiding to tray.

Recommended: add `libayatana-appindicator3` as a Flatpak module and set
`QT_QPA_PLATFORMTHEME=gtk3` in the manifest environment. Wrap `QSystemTrayIcon.show()` in a
try-except and fall back to a minimal always-on-top sidebar if tray registration fails.

---

## Part 4 — Step-by-Step Implementation Order

### Step 1 — Make the app run on Linux without Flatpak (1 day)

1. Apply all code changes from Part 1 (§1.1–1.6).
2. `pip install -e ".[ocr-tesseract,traditional]"` on a Linux machine.
3. `apt install tesseract-ocr tesseract-ocr-chi-sim` for OCR.
4. Run `zh-en-translator` and verify: hotkey, popup, sidebar, tray icon, OCR, preferences.
5. Run the test suite: `pytest tests/ -v` — all 644 tests should pass.

### Step 2 — PyInstaller bundle (half day)

1. Write `installer/zh-en-translator-linux.spec`.
2. Write `installer/build_linux.sh`.
3. Run the build and smoke-test the `dist/zh-en-translator/zh-en-translator` binary.

### Step 3 — Flatpak scaffolding (1 day)

1. Create `flatpak/` directory with the files from §3.2.
2. Run `flatpak-pip-generator` to produce `generated-sources.json` for all Python deps.
   ```bash
   pip install flatpak-pip-generator
   flatpak-pip-generator PyQt6 pynput platformdirs argostranslate jieba \
       opencc-python-reimplemented pytesseract Pillow > flatpak/generated-sources.json
   ```
3. Add Leptonica and Tesseract source archives with verified SHA256 hashes.
4. Build locally:
   ```bash
   flatpak-builder --user --install --force-clean build-dir \
       flatpak/io.github.zh_en_translator.yml
   flatpak run io.github.zh_en_translator
   ```

### Step 4 — Fix Wayland / tray issues found in Step 3 (half day)

1. Test under GNOME (Wayland) and KDE (Wayland + X11).
2. Implement tray fallback (§3.7) if needed.
3. Decide on hotkey strategy: `--device=all` for now, portal ticket filed for later.

### Step 5 — Flathub submission prep (1 day)

1. Verify AppStream metadata with `appstream-util validate`.
2. Verify `.desktop` file with `desktop-file-validate`.
3. Verify Flatpak with `flatpak run --command=flatpak-builder-lint org.flatpak.Builder`.
4. Pin all source URLs to exact versions with verified SHA256 hashes.
5. Review Flathub submission guidelines: https://docs.flathub.org/docs/for-app-authors/submission

---

## Part 5 — Dependency Compatibility Matrix

| Package | Linux support | Notes |
|---|---|---|
| PyQt6 | Full | pip wheel available; or use system package |
| pynput | Full (X11); Partial (Wayland) | Wayland needs evdev or portal |
| platformdirs | Full | XDG paths work correctly |
| argostranslate | Full | Pure Python + ctranslate2 |
| jieba | Full | Pure Python |
| opencc-python-reimplemented | Full | Pure Python |
| pytesseract | Full | Wrapper around system tesseract binary |
| Pillow | Full | pip wheel available |
| paddleocr | Full | Large optional dep; not included in Flatpak Phase 1 |
| winrt-* | None | Skip entirely on Linux |
| spacy-pkuseg | Full | Optional; pure Python |

---

## Part 6 — Files to Create

```
flatpak/
├── io.github.zh_en_translator.yml
├── io.github.zh_en_translator.metainfo.xml
├── io.github.zh_en_translator.desktop
└── generated-sources.json          ← produced at build time, gitignored

installer/
├── build_linux.sh                  ← new
└── zh-en-translator-linux.spec     ← new
```

New source code changes (no new files):
- `src/zh_en_translator/engines/ocr/engine.py`
- `src/zh_en_translator/engines/ocr/tesseract_ocr.py`
- `src/zh_en_translator/app.py`
- `src/zh_en_translator/ui/preferences.py`
- `pyproject.toml`

---

## Part 7 — Out of Scope for This Plan

- **GPU fine-tuning** — unrelated to Linux porting.
- **PaddleOCR in Flatpak** — large deps (~500 MB); defer to a separate optional Flatpak extension.
- **macOS `.app` bundle** — similar effort; most Linux changes benefit macOS too.
- **Wayland GlobalShortcuts portal** — Phase 2 item; tracked separately.
- **Cantonese / Wade-Giles** — existing deferred items; unaffected by Linux work.
- **Auto-update mechanism** — Flatpak handles updates via `flatpak update`; the in-app updater
  should be disabled when running inside a Flatpak sandbox (`FLATPAK_ID` env var is set).
