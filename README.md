# zh-en-translator

A lightweight, **offline-first** Chinese → English popup translator for
Windows 11 (cross-platform intent). Press a global hotkey on any selected
Chinese text and a frameless popup appears at the cursor with the full-sentence
English translation, pinyin, action buttons, and an optional persistent sidebar.

No text leaves the machine by default — translation runs locally via
[Argos Translate](https://github.com/argosopentech/argostranslate) +
[ctranslate2](https://github.com/OpenNMT/CTranslate2). Four cloud engines
can be opted into explicitly: DeepL, Google Translate, Azure Translator, and
LibreTranslate — including free options that require no account
(see [Cloud translation](#cloud-translation-optional)).

---

## Quick Start

1. **Copy** Chinese text with **Ctrl+C**.
   > **Tip:** copy rather than just highlight — some applications do not expose selected text to
   > other programs. Copying first ensures the text is available to the translator.
2. Press **Ctrl+Shift+T** (default hotkey) from anywhere on your desktop.
3. The translation popup appears at your cursor with the English translation, pinyin, and action buttons.

### Popup controls at a glance

| Control | Action |
|---|---|
| ↺ button | Edit source text inline, then ↺ or **Ctrl+Enter** to retranslate |
| **Copy** | Copy the English translation to clipboard |
| **Replace** | Paste the translation back over the original text in the source app |
| **Pin →** | Send translation to the persistent sidebar panel |
| **Look up** | Open source text in MDBG dictionary |
| **▼ Details** | Expand word-by-word dictionary breakdown |
| 📌 (header) | Keep popup open when clicking away |
| **✕ / Esc** | Dismiss |

> Full usage guide also available in the app at **Preferences → Help**.

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
| Cloud (opt-in) | DeepL, Google Translate, Azure Translator, LibreTranslate — all opt-in with privacy warning; zero egress when disabled |

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

By default the app is **fully offline** — no text leaves your machine. Four cloud
engines can be enabled on an opt-in basis in **Preferences → Cloud**. They run in
priority order, falling back to the next available engine on any failure:

| # | Engine | Cost | Account needed | Setup |
|---|---|---|---|---|
| 1 | **DeepL** | Free tier: 500 K chars/month | Yes (deepl.com) | API key |
| 2 | **Google Translate** | Free tier: 500 K chars/month | Yes (GCP project) | API key |
| 3 | **Azure Translator** | Free tier: 2 M chars/month | Yes (Azure portal) | API key + region |
| 4 | **LibreTranslate** | Free (public instances) | **No** | URL only |

If none of the cloud engines are enabled or succeed, the app falls back to the
local Argos offline model automatically.

### LibreTranslate — no account required

LibreTranslate is an open-source translation server. Several public instances
accept requests with no API key at all:

| Instance | API key required |
|---|---|
| `https://translate.argosopentech.com` | No |
| `https://libretranslate.de` | No |
| `https://libretranslate.com` | Yes (free tier available) |

To use a public instance: enable LibreTranslate in **Preferences → Cloud**,
set the URL to one of the above, and leave the API key blank.

You can also [self-host LibreTranslate](https://github.com/LibreTranslate/LibreTranslate)
for unlimited, fully private cloud-quality translation on your own machine or server.

### Setting up the paid/freemium engines

**DeepL:**
1. Create a free account at [deepl.com](https://www.deepl.com/pro-api)
2. Copy your API key from the account dashboard
3. Preferences → Cloud → DeepL → paste key → Apply

**Google Translate:**
1. Create a project in [Google Cloud Console](https://console.cloud.google.com)
2. Enable the **Cloud Translation API**
3. Create an API key under Credentials
4. Preferences → Cloud → Google Cloud Translation → paste key → Apply

**Azure Translator:**
1. Get an API key from the [Azure portal](https://portal.azure.com) (Cognitive Services → Translator)
2. Preferences → Cloud → Azure Translator → paste key + region → Apply

> **Privacy:** when any cloud engine is enabled, translated text is sent to that
> provider's servers. API keys are stored in plain text in `config.toml` — secure
> that file if the machine is shared. When all cloud engines are disabled (the
> default), zero outbound network traffic is generated during translation.

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
deepl_enabled = false
deepl_api_key = ""
deepl_pro = false
google_translate_enabled = false
google_translate_api_key = ""
ms_translator_enabled = false
ms_translator_api_key = ""
ms_translator_region = ""
libretranslate_enabled = false
libretranslate_url = "https://libretranslate.com"
libretranslate_api_key = ""
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
│  │  ├─ deepl.py             ← DeepL API (opt-in)
│  │  ├─ google_translate.py  ← Google Cloud Translation API (opt-in)
│  │  ├─ ms_cloud.py          ← Azure Translator (opt-in)
│  │  ├─ libretranslate.py    ← LibreTranslate / self-hosted (opt-in, free)
│  │  ├─ dictionary.py        ← CC-CEDICT + SQLite
│  │  ├─ segmentation.py      ← jieba word segmenter
│  │  ├─ converter.py         ← OpenCC Traditional→Simplified
│  │  ├─ themes.py            ← theme palette definitions
│  │  ├─ translation_worker.py← QThread: DeepL→Google→Azure→LibreTranslate→Argos
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
| M10 | Cloud translation — DeepL, Google Translate, Azure, LibreTranslate (all opt-in) | ✅ |
