# zh-en-translator

A lightweight, **offline-first** Chinese → English popup translator for
Windows 11 (cross-platform intent). Press a global hotkey on any selected
Chinese text and a frameless popup appears at the cursor with the full-sentence
English translation, pinyin, action buttons, and an optional persistent sidebar.

No text leaves the machine by default — translation runs locally via
[Argos Translate](https://github.com/argosopentech/argostranslate) +
[ctranslate2](https://github.com/OpenNMT/CTranslate2). Microsoft Azure
Translator can be opted into explicitly (see [Cloud translation](#cloud-translation-optional)).

---

## Features

| Feature | Notes |
|---|---|
| Global hotkey | Default `Ctrl+Shift+T`, fully configurable |
| Popup mode | Frameless rounded popup at cursor, dismisses on Esc / click-outside / focus loss |
| Sidebar mode | Persistent 6 px peek-tab at screen edge; slides out on click |
| Sentence translation | Argos Translate + ctranslate2 — fully offline after one-time model download |
| Pinyin | Shown above source text; auto-hidden for long inputs |
| Dictionary lookup | CC-CEDICT (~120 k entries) downloaded on first run |
| Replace in-place | Pastes translation back into the source field (Word, browsers, IDEs, etc.) |
| OCR | Translate Chinese text in clipboard images via Windows OCR / Tesseract / PaddleOCR |
| Traditional Chinese | Auto-converts Traditional → Simplified via OpenCC before translation |
| Themes | System / Light / Dark / Sepia |
| Preferences | In-app dialog — hotkey, font, colours, OCR engine, cloud key, and more |
| Accessibility | Screen-reader names/descriptions, logical tab order |
| Cloud (opt-in) | Azure Translator with explicit privacy warning; zero egress when disabled |

---

## Install

### Windows (Python 3.11 or 3.12 recommended)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
.\scripts\install-windows.ps1
```

To also install Windows OCR support (pre-built `winrt-*` wheels — no compiler needed):

```powershell
.\scripts\install-windows.ps1 -OCR
```

> **Python 3.14 note:** `argostranslate 1.9.x` pins `sentencepiece==0.2.0` which
> has no pre-built wheel for Python 3.14. The install script handles this by
> installing `sentencepiece>=0.2.0 --only-binary :all:` first (picks up 0.2.1),
> then argostranslate with `--no-deps`.

### Linux / macOS

```bash
pip install -e ".[dev]"
```

---

## OCR (optional)

| Engine | Install | Notes |
|---|---|---|
| **Windows OCR** (recommended) | `.\scripts\install-windows.ps1 -OCR` | Offline, ships with Windows; needs Chinese language pack |
| **Tesseract** | Install [Tesseract binary](https://github.com/UB-Mannheim/tesseract/wiki) + `chi_sim` pack, then `pip install pytesseract Pillow` | Offline |
| **PaddleOCR** | `pip install "zh-en-translator[ocr-paddle]"` | Best quality; heavy download |

If Windows OCR is installed but the Chinese language pack is missing, the
popup shows an "Open Language Settings" button that takes you directly to the
Windows language settings to add **Chinese (Simplified, China)**.

---

## Traditional Chinese

Install the OpenCC converter to enable automatic Traditional → Simplified
conversion before translation:

```powershell
pip install "zh-en-translator[traditional]"
```

Toggle the setting in **Preferences → General → Traditional Chinese**.

---

## Cloud translation (optional)

By default the app is fully offline. To use Microsoft Azure Translator:

1. Get an API key from the [Azure portal](https://portal.azure.com) (Cognitive Services → Translator). The **Free tier (F0)** allows 2 million characters/month.
2. Open **Preferences → Cloud** tab.
3. Tick **Enable cloud translation**, paste your key, and optionally enter your region (e.g. `eastus`).
4. Click **Apply**.

> **Privacy:** enabling this option sends every translated text segment to
> Microsoft Azure servers. The API key is stored in plain text in
> `config.toml` — secure that file if the machine is shared.
>
> When disabled (the default), zero outbound network traffic is generated
> during translation.

Cloud translation uses Azure as the primary engine and falls back to local
Argos automatically on any network or API failure.

---

## Run

```powershell
zh-en-translator
```

The app appears as a system-tray icon (blue rounded square with "中"). Right-click
the tray icon for the context menu.

---

## Configuration

Settings are stored in `%APPDATA%\zh-en-translator\config.toml` (Windows) or
`~/.config/zh-en-translator/config.toml` (Linux/macOS). Edit in the **Preferences** dialog
(tray → Preferences…) or directly in the file:

```toml
[general]
hotkey = "<ctrl>+<shift>+t"
mode = "popup"           # popup | sidebar

[display]
theme = "system"         # system | dark | light | sepia
font_family = ""         # empty = system default
font_size = 13

[sidebar]
side = "right"           # left | right
sidebar_y = 200
color_fresh = "#00C9CC"
color_idle = "#9E8080"

[lookup]
external_lookup_url = "https://www.mdbg.net/chinese/dictionary?wdqb={query}"

[ocr]
ocr_engine = "auto"      # auto | windows | tesseract | paddle

[pinyin]
show_pinyin = true
pinyin_max_chars = 80

[translation]
traditional_to_simplified = true

[cloud]
ms_translator_enabled = false
ms_translator_api_key = ""
ms_translator_region = ""
```

---

## Development

### Tests

```bash
# Headless (Linux / CI)
QT_QPA_PLATFORM=offscreen pytest -v

# Windows (offscreen is set automatically by the test suite)
pytest -v
```

### Lint

```bash
ruff check src/ tests/
```

### Dev setup (first clone)

Activate the pre-commit secret scanner (requires [gitleaks](https://github.com/gitleaks/gitleaks)):

```bash
git config core.hooksPath .githooks
winget install gitleaks   # Windows
# brew install gitleaks   # macOS
```

The hook runs `gitleaks protect --staged` on every commit and blocks anything that looks like a secret. It warns and skips gracefully if gitleaks is not installed.

### Architecture

```
zh-en-translation/
├─ src/zh_en_translator/
│  ├─ app.py                  ← tray app + hotkey entry point
│  ├─ hotkey.py               ← pynput global hotkey wrapper
│  ├─ capture.py              ← clipboard-based text capture + replace
│  ├─ config.py               ← TOML config loader/writer
│  ├─ engines/
│  │  ├─ argos.py             ← offline sentence MT (ctranslate2)
│  │  ├─ ms_cloud.py          ← Azure Translator (opt-in)
│  │  ├─ dictionary.py        ← CC-CEDICT + SQLite
│  │  ├─ segmentation.py      ← jieba word segmenter
│  │  ├─ converter.py         ← OpenCC Traditional→Simplified
│  │  ├─ themes.py            ← theme palette definitions
│  │  ├─ translation_worker.py← QThread wrapper (cloud → argos fallback)
│  │  └─ ocr/                 ← Windows / Tesseract / PaddleOCR engines
│  └─ ui/
│     ├─ popup.py             ← frameless translation popup
│     ├─ sidebar.py           ← peek-tab sidebar
│     └─ preferences.py       ← tabbed preferences dialog
└─ tests/                     ← 152 tests
```

---

## License

Released under the [GNU General Public License v3 or later](LICENSE).

---

## Milestones

| # | Milestone | Status |
|---|---|---|
| M1 | Hello Popup — tray, hotkey, frameless popup | ✅ |
| M2 | Dictionary Lookup — CC-CEDICT + jieba + pinyin | ✅ |
| M3 | Replace + Copy + External Lookup | ✅ |
| M4 | Sentence Translation — Argos / ctranslate2 (offline) | ✅ |
| M5 | Sidebar Mode — peek-tab, animations, indicator colours | ✅ |
| M6 | OCR — Windows / Tesseract / PaddleOCR waterfall | ✅ |
| M7 | Preferences — TOML config + in-app dialog | ✅ |
| M8 | Packaging (MSI) | ⏳ |
| M9 | Accessibility + Traditional Chinese — OpenCC, Qt a11y tree | ✅ |
| M10 | Optional MS Cloud — Azure Translator opt-in | ✅ |
