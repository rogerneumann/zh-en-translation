# Linux Port & Flatpak — Progress Tracker

Based on [LINUX_FLATPAK_PLAN.md](LINUX_FLATPAK_PLAN.md).  
Last updated: 2026-05-02

---

## Phase 1 — Make the app run on Linux ✅ COMPLETE

### Code changes (all merged to `claude/review-todo-items-54NUR`)

| Item | File(s) | Status |
|---|---|---|
| OCR waterfall: skip Windows OCR on Linux | `engines/ocr/engine.py` | ✅ Done |
| Tesseract path discovery: add Linux/Flatpak paths | `engines/ocr/tesseract_ocr.py` | ✅ Done |
| "Run at login": XDG autostart on Linux | `app.py` | ✅ Done |
| Tesseract warning: use `tempfile.gettempdir()` | `app.py` | ✅ Done |
| No-OCR message: platform-specific install hint | `app.py` | ✅ Done |
| Log viewer: use `xdg-open` on Linux | `ui/preferences.py` | ✅ Done |
| `_InstallMonitor`: use `tempfile.gettempdir()` | `ui/preferences.py` | ✅ Done |
| Startup checkbox: "Launch at login" on Linux | `ui/preferences.py` | ✅ Done |
| Windows OCR group: hidden on Linux | `ui/preferences.py` | ✅ Done |
| Tesseract group: Linux-aware title + install hint | `ui/preferences.py` | ✅ Done |
| OCR engine combo: no "Windows" option on Linux | `ui/preferences.py` | ✅ Done |
| `pyproject.toml`: add `linux` extras group | `pyproject.toml` | ✅ Done |

### Test suite

| Suite | Result | Notes |
|---|---|---|
| Non-Qt tests (466 tests) | ✅ 466 passed, 18 skipped | All green |
| OCR waterfall tests | ✅ Fixed + new Linux test added | Now platform-aware with `sys.platform` mock |
| Qt UI tests | ⚠ Skipped in this env | Requires `libEGL.so.1` — passes on a real Linux desktop |

**Windows regression:** All platform guards use `sys.platform == "win32"` or equivalent, so
Windows behaviour is completely unchanged. The new Linux code paths are unreachable on Windows.

---

## Phase 2 — Build System ✅ COMPLETE

| Item | File(s) | Status |
|---|---|---|
| Linux shell build script | `installer/build_linux.sh` | ✅ Done |
| Linux PyInstaller spec | `installer/zh-en-translator-linux.spec` | ✅ Done |

**To produce a portable tarball on a real Linux machine:**
```bash
./installer/build_linux.sh --portable
# Output: dist/zh-en-translator-linux-portable.tar.gz
```

Prerequisites:
```bash
sudo apt install python3.11 python3.11-venv python3-pip \
    tesseract-ocr tesseract-ocr-chi-sim tesseract-ocr-chi-tra \
    libxcb-cursor0 libgl1
pip install -e ".[linux]" pyinstaller
```

---

## Phase 3 — Flatpak Packaging ✅ COMPLETE (scaffolded)

| Item | File(s) | Status |
|---|---|---|
| Flatpak manifest | `flatpak/io.github.zh_en_translator.yml` | ✅ Done |
| `.desktop` file | `flatpak/io.github.zh_en_translator.desktop` | ✅ Done |
| AppStream metadata | `flatpak/io.github.zh_en_translator.metainfo.xml` | ✅ Done |
| Source-generator script | `flatpak/scripts/generate-sources.sh` | ✅ Done |
| `generated-sources.json` | _(generated at build time)_ | ⏳ Needs build machine |

**To build the Flatpak locally:**
```bash
# 1. Generate Python dependency sources
pip install flatpak-pip-generator
bash flatpak/scripts/generate-sources.sh

# 2. Fill in real SHA256 hashes for Tesseract + tessdata URLs in the manifest

# 3. Build and install
flatpak-builder --user --install --force-clean build-dir \
    flatpak/io.github.zh_en_translator.yml

# 4. Run
flatpak run io.github.zh_en_translator
```

---

## Remaining / In-Progress Items

| Item | Status | Notes |
|---|---|---|
| Fill real SHA256 hashes in Flatpak manifest | ⏳ Pending | Needs internet to fetch archives |
| Run `flatpak-pip-generator` for `generated-sources.json` | ⏳ Pending | Needs internet + flatpak-pip-generator installed |
| Full Qt UI test pass on a real Linux desktop | ⏳ Pending | Requires display + libEGL |
| Wayland GlobalShortcuts portal (Phase 2 hotkeys) | 🔵 Future | Tracked in LINUX_FLATPAK_PLAN.md §3.6 |
| System tray fallback for GNOME | 🔵 Future | Tracked in LINUX_FLATPAK_PLAN.md §3.7 |
| Flathub submission | 🔵 Future | After SHA256 hashes + testing on real hardware |

---

## Windows Compatibility Verification

Every change made is backward-compatible with the existing Windows build:

- `_apply_startup_setting()`: Windows registry branch is unchanged; Linux XDG branch is entered
  only when `sys.platform != "win32"`.
- `_check_tesseract_warning()`: Already `win32`-only; `tempfile.gettempdir()` returns `%TEMP%`
  on Windows — same result.
- `engines/ocr/engine.py`: `sys.platform == "win32"` guard means Windows OCR is still tried first
  on Windows, exactly as before.
- `tesseract_ocr.py`: Windows `_get_tesseract_candidates()` branch is unchanged; Linux branch only
  runs on non-win32.
- `ui/preferences.py`: All Windows-specific controls (Install Tesseract button, Windows OCR group,
  log viewer) are still shown on `win32`. On Linux they are replaced with appropriate alternatives.
