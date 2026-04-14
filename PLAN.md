# Popup Translator (Chinese → English) — Primary Plan

A lightweight, **offline-first**, modern popup translator for Windows 11 (with
cross-platform intent). Triggered by a global hotkey on selected text in any
application, it shows word-by-word and full-sentence translation in a
frameless popup or a dockable sidebar, with optional OCR from clipboard
images. No data leaves the machine unless the user explicitly opts in.

---

## Goals

- **Offline-first, zero data leakage** — all translation runs locally by default.
- **Low idle overhead** — no polling, no clipboard watchers; only acts on hotkey.
- **Dead-simple dismiss** — Esc, click-outside, or focus-loss closes the popup.
- **Replace selected text in-place** — works in Word, browsers, Save-As dialogs,
  IDEs, anywhere a normal paste works.
- **Modern but functional UI** — frameless popup, system-DPI aware, themable
  (system / dark / light / sepia), user-selectable fonts.
- **Accessibility-friendly** — screen readers, DPI scaling, high contrast.
- **Single MSI installer** with Lean / Full download options.

## Non-Goals (v1)

- Live OCR / screen-watching (manual hotkey only).
- Real-time streaming translation of video/audio.
- Languages other than zh → en.
- Automatic "send unknown terms to Google" (v1 = manual copy/paste).

---

## Target Audience

Technical users in a multinational company handling mostly **Simplified
Chinese** (Guangzhou) with a minority of **Traditional Chinese**. Data
sensitivity is high — the tool must not phone home.

---

## Tech Stack

| Layer | Choice | Rationale |
|---|---|---|
| Language | Python 3.11 | Fastest to iterate; mature libraries for Chinese NLP & Qt bindings |
| UI | PyQt6 | Native look, accessibility, DPI aware, cross-platform |
| Dictionary | CC-CEDICT + SQLite index | ~120k entries, MIT-style license, instant lookup |
| Segmentation | jieba | De-facto standard for Chinese word segmentation |
| Trad → Simp | OpenCC | Robust, widely used |
| Sentence MT | Argos Translate (default) / MarianMT via CTranslate2 (Full install) | True offline neural MT |
| OCR (Windows) | `Windows.Media.Ocr` via `winrt` | Truly offline, zero download |
| OCR (cross-platform) | Tesseract + `chi_sim`/`chi_tra` | Offline, mature |
| OCR (opt-in "Full") | PaddleOCR | Best Chinese OCR quality |
| Hotkeys | `pynput` / Win32 low-level keyboard hook | Reliable global hotkey |
| Packaging | PyInstaller → Inno Setup MSI | Single-file install |
| Config | TOML at `%APPDATA%\zh-en-translator\config.toml` | Human-readable text file |

**Future (post-v1):** Rust rewrite of hot paths (hotkey listener, lookup,
popup shell) using `egui` or `Slint`, keeping translation models as a
separate Python process.

### Engines explicitly rejected

- **Windows / MS Office built-in translation APIs** — phone home to Microsoft
  servers, violate offline-first. (Azure Translator is offered as *opt-in* with
  a warning banner, never default.)
- **Electron** — too heavy for a system-tray utility.

---

## Architecture

```
┌───────────────────────────────────────┐
│          System Tray App              │
│    (Python, PyQt6 QSystemTrayIcon)    │
└───────────────┬───────────────────────┘
                │
     ┌──────────▼──────────┐
     │ Global Hotkey Listener│
     │  Win32 / X11 / macOS │
     └──────────┬───────────┘
                │
     ┌──────────▼──────────┐
     │   Text Capture       │
     │ (clipboard save/     │
     │  simulate Ctrl+C /   │
     │  restore clipboard)  │
     └──────────┬───────────┘
                │
     ┌──────────▼──────────────────┐
     │    Translation Pipeline      │
     │ ┌─────────────────────────┐ │
     │ │ OpenCC (Trad → Simp)    │ │
     │ │ jieba segmentation      │ │
     │ │ CC-CEDICT lookup        │ │
     │ │   + user_dict override  │ │
     │ │ Argos/Marian sentence MT│ │
     │ └─────────────────────────┘ │
     └──────────┬──────────────────┘
                │
     ┌──────────▼──────────────────┐
     │  Renderer (PyQt6)            │
     │  - Popup mode (frameless)    │
     │  - Sidebar mode (peek tab)   │
     └──────────────────────────────┘
```

---

## UI Modes

### Popup Mode (default)

- Frameless, rounded-corner Qt window near cursor.
- Appears at cursor position, auto-repositions to stay on-screen.
- Dismisses on Esc, click-outside, focus loss, or second hotkey press.
- Pin button converts it into Sidebar Mode.

### Sidebar Mode

- Thin vertical **peek tab** anchored to screen edge.
- Indicator color: **red** (idle / no current selection) / **green** (fresh
  translation ready).
- Hover/click expands the panel to ~30-char width.
- Auto-refreshes when user hits hotkey on new selection.
- Close with `X` button or `Shift+Esc` — hotkey alone only toggles expand/collapse.

### Popup Content

1. Source text (selectable, editable).
2. **Pinyin** above characters (auto-collapses for text > ~80 chars; toggleable).
3. English full-sentence translation (Argos / Marian).
4. Word-by-word breakdown (collapsible).
5. Unknown tokens **highlighted** — selectable for copy/paste to external site.
6. Buttons: `Replace` · `Copy` · `Look up externally` · `Pin` · `Add to dictionary`.

---

## Settings (`config.toml`)

```toml
[general]
hotkey = "ctrl+shift+t"
sidebar_hotkey = "ctrl+shift+s"
startup = true
mode = "popup"           # popup | sidebar

[translation]
engine = "argos"         # dict | argos | marian | ms_cloud
fallback_to_dict = true
traditional_to_simplified = true

[display]
theme = "system"         # system | dark | light | sepia
font_family = ""         # empty = system default
font_size = 14
show_pinyin = true
pinyin_max_chars = 80

[ocr]
enabled = true
engine = "auto"          # auto | windows | tesseract | paddle

[cloud]
ms_translator_enabled = false
ms_translator_api_key = ""

[dictionary]
user_dict_path = "user_dict.toml"
external_lookup_url = "https://www.mdbg.net/chinese/dictionary?wdqb={query}"
```

---

## Milestones (Breadth-First)

Each milestone is **end-to-end runnable**. We ship a working build at every
step and iterate.

| # | Milestone | Deliverable |
|---|---|---|
| **M1** | Hello Popup | Tray app + global hotkey + selection capture + frameless Qt popup showing captured text. Esc/click-outside dismiss. No translation. |
| **M2** | Dictionary Lookup | CC-CEDICT + SQLite + jieba. Popup shows word-by-word English + pinyin. |
| **M3** | Replace + External Lookup | Replace-selected-text via clipboard-restore paste. Unknown tokens highlighted & selectable for copy. External-lookup button opens MDBG/configurable URL. |
| **M4** | Sentence Translation | Argos Translate integration. Full-sentence English shown above word-by-word. |
| **M5** | Sidebar Mode | Peek tab with red/green indicator. Pin-from-popup converts modes. Shift+Esc to fully close. |
| **M6** | OCR | Hotkey on clipboard image → Win OCR (Windows) / Tesseract (fallback) → translate. User can edit OCR result before translating. |
| **M7** | Preferences | `config.toml` hot-reload. Theme (system / dark / light / sepia). Font picker. Custom user dictionary. |
| **M8** | Packaging | PyInstaller → Inno Setup MSI. Lean (~90 MB) vs Full (~390 MB) install modes. Unsigned v1 (can sign later). |
| **M9** | Accessibility + Traditional | OpenCC Trad→Simp. Qt accessibility tree. NVDA screen reader tested. DPI scaling verified. |
| **M10** | Optional MS Cloud | Opt-in Azure Translator with explicit warning banner. Network-traffic test ensures zero egress when disabled. |

---

## Test Plan

### Core translation & dictionary

| # | Test |
|---|---|
| T1 | Load CC-CEDICT, look up `你好` → returns "hello; hi". |
| T2 | Unknown character → graceful "not found". |
| T3 | Segment `我喜欢吃苹果` → `["我","喜欢","吃","苹果"]`. |
| T4 | Mixed zh/en text `我love你` segments correctly. |
| T5 | Translate `今天天气很好` via Argos → reasonable English. |
| T6 | Empty string → no crash, no popup. |
| T7 | Very long text (>1000 chars) → completes within timeout or truncates. |

### Hotkey & capture

| # | Test |
|---|---|
| T8 | Hotkey with text selected in Notepad → popup near cursor. |
| T9 | Hotkey with no selection → no popup (or toast). |
| T36 | Select Chinese filename chars in Save-As dialog → Replace works. |

### Popup behavior

| # | Test |
|---|---|
| T10 | Esc closes popup. |
| T11 | Click outside closes popup. |
| T12 | Alt-Tab away closes popup. |
| T13 | Popup near screen edge → repositions on-screen. |
| T22 | Multi-monitor → popup appears on correct monitor. |

### Replace

| # | Test |
|---|---|
| T14 | Replace in Notepad → original selection replaced. |
| T15 | Replace in read-only field → graceful failure. |

### Sidebar

| # | Test |
|---|---|
| T25 | Enable sidebar, new selection + hotkey → sidebar refreshes without reopen. |
| T26 | Dismiss popup does not dismiss pinned sidebar. |

### OCR

| # | Test |
|---|---|
| T28 | Copy image with Chinese text, trigger translator → text extracted + translated. |
| T29 | Copy image with no text → "no text detected". |
| T30 | Blurry image → partial result with edit option. |

### Settings & customization

| # | Test |
|---|---|
| T31 | Add `镀锌 → galvanized` to user dict → overrides CC-CEDICT. |
| T32 | Change font in `config.toml` → live reload in open popup. |
| T33 | `theme = "sepia"` applied. |
| T24 | Look up `電腦` (traditional) → normalized to `电脑` → "computer". |

### Accessibility

| # | Test |
|---|---|
| T34 | NVDA reads all popup content correctly. |
| T35 | OS at 150% DPI → popup scales without clipping. |

### Security / offline

| # | Test |
|---|---|
| T17 | Network disconnected → identical behavior. |
| T23 | Inspect network traffic during translation → zero outbound. |
| T37 | MS Translator disabled → zero outbound even under load. |

### Performance

| # | Test |
|---|---|
| T18 | Dictionary lookup p95 < 50 ms. |
| T19 | Sentence translation p95 < 2 s (short sentences). |
| T39 | Idle CPU < 0.5 %. |

### Packaging

| # | Test |
|---|---|
| T21 | Run built MSI on clean Win11 VM → no runtime deps needed. |
| T39b | Lean install (~90 MB) → dict + pinyin works; sentence MT gated. |
| T40 | Full install (~390 MB) → all engines ready offline. |

### External lookup

| # | Test |
|---|---|
| T38 | Click "Look up externally" → opens default browser with prefilled query. |

---

## Directory Layout (proposed)

```
zh-en-translation/
├─ pyproject.toml
├─ README.md
├─ PLAN.md                    ← this file
├─ src/zh_en_translator/
│  ├─ __init__.py
│  ├─ app.py                  ← entry point + tray
│  ├─ hotkey.py               ← global hotkey listener
│  ├─ capture.py              ← selected-text capture & replace
│  ├─ config.py               ← TOML settings loader
│  ├─ engines/
│  │  ├─ dictionary.py        ← CC-CEDICT + SQLite
│  │  ├─ segmentation.py      ← jieba wrapper
│  │  ├─ converter.py         ← OpenCC wrapper
│  │  ├─ argos.py             ← sentence MT
│  │  └─ ocr/
│  │     ├─ windows_ocr.py
│  │     ├─ tesseract_ocr.py
│  │     └─ paddle_ocr.py
│  ├─ ui/
│  │  ├─ popup.py             ← frameless popup
│  │  ├─ sidebar.py           ← peek tab + panel
│  │  ├─ content.py           ← shared content renderer
│  │  └─ themes/
│  └─ resources/
│     ├─ cedict.sqlite        ← built at install time
│     └─ icons/
├─ tests/
│  ├─ test_dictionary.py
│  ├─ test_segmentation.py
│  ├─ test_translation.py
│  ├─ test_ocr.py
│  └─ test_ui_smoke.py
└─ installer/
   ├─ zh-en-translator.iss    ← Inno Setup script
   └─ build.ps1
```

---

## Open Items / Deferred Decisions

- **Code signing** — unsigned v1; revisit when a cert is available.
- **Auto-update** — off by default in v1; design TBD (signed-manifest check from a configurable URL, user opt-in).
- **Region-capture OCR** (Win+Shift+T style) — deferred past v1.
- **Automatic external lookup** — v1 is manual copy/paste; full automation deferred.
- **Rust rewrite** — post-v1, only if Python version proves insufficient.
