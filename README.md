# zh-en-translation

A lightweight, offline-first Chinese→English popup translator for Windows 11 (with cross-platform intent). Triggered by a global hotkey (`Ctrl+Shift+T`) on selected text in any application, it displays a frameless popup with translation options.

## Development

### Install

**Windows (Python 3.14+) — use the helper script** (works around a sentencepiece wheel issue):

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
.\scripts\install-windows.ps1
```

To also install Windows OCR support (pre-built `winrt-*` wheels, no compiler needed):

```powershell
.\scripts\install-windows.ps1 -OCR
```

If `winrt-*` wheels aren't yet available for your Python version, install
[Tesseract](https://github.com/UB-Mannheim/tesseract/wiki) (standalone binary,
no compiler required) and then:

```powershell
pip install pytesseract Pillow
```

**Linux / macOS:**

```bash
# Clone the repository
git clone https://github.com/yourusername/zh-en-translation.git
cd zh-en-translation

# Install in development mode with dependencies
pip install -e ".[dev]"
```

> **Why the Windows script?** `argostranslate 1.9.6` pins `sentencepiece==0.2.0` which
> has no pre-built wheel for Python 3.14. The script installs `sentencepiece>=0.2.0`
> binary-only first (picks up 0.2.1 which ships a 3.14 wheel), then installs
> argostranslate with `--no-deps` to avoid the locked constraint being re-applied.

### Run

```bash
# Start the translator app (tray icon)
zh-en-translator
```

### Test

```bash
# Run all tests with offscreen rendering (Linux/CI)
QT_QPA_PLATFORM=offscreen pytest -x

# Run tests with output
QT_QPA_PLATFORM=offscreen pytest -v

# Run specific test file
QT_QPA_PLATFORM=offscreen pytest tests/test_app_smoke.py -v
```

### Lint

```bash
ruff check src/ tests/
```

## Milestones

### Milestone 1 (M1) — "Hello Popup"

- System tray app with global hotkey listener
- Captures selected text via clipboard save/restore pattern
- Frameless popup with rounded corners and drop shadow
- Dismiss via Esc, click-outside, or focus loss
- No translation engine yet (scaffold only)

### Milestone 2 (M2) — "Dictionary Lookup"

- CC-CEDICT loader with SQLite indexing (~50 common words in bundled sample)
- Pinyin conversion from tone numbers (e.g., `chuan2 tong3` → `chuán tǒng`) with full tone-mark support (tones 1–5)
- Chinese text segmentation (character-by-character + greedy longest-match dictionary lookup)
- Word-by-word table in popup showing:
  - Token | Pinyin | English glosses
  - Unknown Chinese tokens highlighted with yellow background
  - All cells selectable for copy/paste
- Popup table scrolls vertically if content exceeds ~400 px
- M1 fallback: popup works without dictionary (shows only captured text)

#### Dictionary data

The bundled dictionary contains ~50 common Simplified Chinese words. For production use, replace `src/zh_en_translator/resources/cedict_sample.txt` with the full CC-CEDICT file from:

[CC-CEDICT](https://www.mdbg.net/chinese/dictionary?page=cc-cedict)

Format: one entry per line as `traditional simplified [pinyin] /gloss1/gloss2/.../`

Lines starting with `#` are treated as comments and skipped.
