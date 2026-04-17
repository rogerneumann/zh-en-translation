# Progress Tracker

Running log of what has been built, what deviated from the plan, and what still
needs verification. Update this file at the end of every milestone.

Source of truth for plan/scope: `PLAN.md`.

---

## Status at a glance

| Milestone | Status | Notes |
|---|---|---|
| M0 — Plan | ✅ Done | |
| M1 — Hello Popup | ✅ Done | Bugs fixed on Windows (focus, hotkey format, drop-shadow crash) |
| M2 — Dictionary Lookup | ✅ Done (engine only) | Word-by-word UI removed at user request; engine + tests intact |
| M3 — Replace + Copy + External Lookup | ✅ Done | Replace, Copy, Look up buttons in popup |
| M4 — Sentence Translation | ✅ Done + ✅ Verified on Windows | ctranslate2 direct (bypassed stanza); translation working |
| M5 — Sidebar Mode (peek tab) | ✅ Done | Peek-tab with 6px strip, slide animation, drag, keep-pinned, indicator colours |
| M6 — OCR | ✅ Done | Waterfall: PaddleOCR → winsdk → Tesseract; auto-detect clipboard |
| M7 — Preferences | ✅ Done | In-app dialog + TOML config; font, colors, sidebar, hotkey, OCR engine |
| Windows testing fixes | ✅ Done | Black popup/sidebar, OCR routing, clipboard wipe, strip click, mode sync — see below |
| M8 — Packaging (MSI) | ✅ Done | PyInstaller onedir + Inno Setup 6; single setup.exe; startup-on-login |
| M9 — Accessibility + Traditional | ✅ Done | OpenCC converter, theme support, Qt accessibility (names, descriptions, tab order) |
| M10 — Optional MS Cloud | ✅ Done | Azure Translator opt-in; warning banner; fallback to Argos |

All fixes merged to `main`.

---

## M1 — Hello Popup

**Scope**: Tray app, global hotkey, selected-text capture, frameless popup, dismiss behaviors.

**Delivered**:
- `src/zh_en_translator/app.py` — `QSystemTrayIcon` with Translate / Pause / Quit menu
- `src/zh_en_translator/hotkey.py` — `pynput.GlobalHotKeys` wrapper, default `Ctrl+Shift+T`
- `src/zh_en_translator/capture.py` — clipboard save → simulate Ctrl+C → restore
- `src/zh_en_translator/ui/popup.py` — frameless rounded-corner popup, cursor positioning, Esc / click-outside / focus-loss dismiss
- 25 unit tests across `tests/test_app_smoke.py`, `test_capture.py`, `test_hotkey.py`
- `pyproject.toml`, `conftest.py`, `.gitignore`

**Fixes applied**:
- `QGraphicsDropShadowEffect` crashes Windows (`UpdateLayeredWindowIndirect`) — removed; border drawn in `paintEvent` instead
- `WA_TranslucentBackground` makes popup invisible on Windows — fixed with manual `paintEvent` fill
- Hotkey format `ctrl+shift+t` → `<ctrl>+<shift>+t` (pynput angle-bracket syntax)
- `QObject: Cannot create children in different thread` — fixed by making `TranslatorApp` a `QObject` with `pyqtSignal` to marshal pynput callbacks to Qt main thread
- `showEvent` now calls `activateWindow()` + `raise_()` so Esc and text selection work

**Manual test checklist for Windows 11**:
- [ ] Tray icon appears (blue square).
- [ ] `Ctrl+Shift+T` with text selected in Notepad → popup at cursor.
- [x] Esc closes popup; original clipboard is restored.
- [x] Click outside popup → closes (WindowDeactivate, 150ms delay).
- [ ] Alt-Tab away → popup closes.
- [ ] Popup repositions near screen edges.
- [ ] Multi-monitor: popup appears on correct screen.
- [ ] Works in Word, a browser, and a Save-As filename field.

---

## M2 — Dictionary Lookup

**Scope**: CC-CEDICT + segmentation + word-by-word popup with pinyin.

**Delivered**:
- `src/zh_en_translator/engines/dictionary.py` — CC-CEDICT parser, SQLite schema, pinyin tone converter
- `src/zh_en_translator/engines/segmentation.py` — character-run segmentation
- `src/zh_en_translator/engines/pipeline.py` — greedy longest-match lookup, capped at 8 chars (O(n²) fix)
- `src/zh_en_translator/resources/cedict_sample.txt` — ~50 starter entries
- 22 new tests (`test_dictionary.py`, `test_segmentation.py`, `test_pipeline.py`)

**Deviations from PLAN.md**:
- **Dropped `jieba`** — wheel build failed; using character-run + longest-match instead. Revisit in M7.
- **Word-by-word table removed from popup UI** — user preference; readable sentence is primary output.
  Dictionary engine code remains; can be added back as collapsible section in M7.

**Manual test checklist for Windows 11**:
- [ ] Select `你好世界` → popup shows word-by-word breakdown (engine only; UI deferred to M7).
- [ ] Traditional `電腦` normalises to `电脑` → "computer".

---

## M3 — Replace + Copy + External Lookup

**Scope**: Replace-in-place, copy to clipboard, external dictionary lookup.

**Delivered** (commit `c014309`):
- **Replace text** button — copies translation, closes popup, sends Ctrl+V after 120ms
- **Copy** button — copies translation to clipboard without dismissing popup; "Copied!" feedback for 1.5s
- **Look up** button — opens MDBG in default browser with URL-encoded source text
  (`https://www.mdbg.net/chinese/dictionary?wdqb={text}` via `QDesktopServices`)
- All three buttons disabled while translation is pending; enabled on result

**Deviations from PLAN.md**:
- "Add to dictionary" button deferred to M7 (needs user dict + preferences)
- External lookup URL hardcoded to MDBG; configurable URL in M7

**Manual test checklist for Windows 11**:
- [x] Replace text: select Chinese in Notepad → translate → Replace → English appears in Notepad
- [x] Copy button → "Copied!" feedback → clipboard has translation
- [x] Look up → browser opens MDBG with source text prefilled

---

## M4 — Sentence Translation

**Scope**: Argos Translate integration; popup shows readable English sentence.

**Delivered**:
- `src/zh_en_translator/engines/argos.py` — bypasses `argostranslate.translate` entirely (hard-imports stanza which needs HuggingFace download). Calls ctranslate2 + sentencepiece directly from the installed pack directory. Stanza-free, offline after first pack install.
- `src/zh_en_translator/ui/popup.py` — source text (muted) + English sentence (large, selectable). `_TranslationWorker` (QThread) runs in background; popup appears instantly.
- `pyproject.toml` — pinned `argostranslate>=1.9.0,<1.10.0` (1.11+ adds stanza runtime dep)

**Windows-specific fixes**:
- argostranslate 1.9.6 `translate.py` does hard `import stanza` at top — stanza requires downloading Chinese NLP models from HuggingFace (blocked on corporate SSL). Bypassed by calling ctranslate2 directly.
- sentencepiece 0.2.0 has no Python 3.14 wheel — installed 0.2.1 via `--only-binary` workaround.
- stanza/torch/spaCy (installed from earlier 1.11.0) uninstalled to remove 114MB+ of unnecessary deps.
- sentencepiece `▁` word-boundary markers stripped from decoded output.

**Manual test checklist for Windows 11**:
- [x] `pip install -e .` installs argostranslate 1.9.6 + sentencepiece 0.2.1
- [x] First hotkey trigger → "Translating…" → English sentence fills in (~2s)
- [x] Translated text is selectable
- [x] No network calls during translation (offline after pack install)

---

## M5 — Sidebar Mode (peek tab)

**Scope**: Persistent right/left-edge peek tab with collapse/expand, indicator colours, sidebar mode.

**Delivered so far** (basic floating panel only):
- `src/zh_en_translator/ui/sidebar.py` — simple floating panel; `set_translation()`, `update_translation()`
- Pin → button in popup sends translation to sidebar

**In progress — proper peek-tab design**:

Design spec agreed with user:
- **Collapsed**: 6px coloured strip anchored to screen edge (doesn't cover scrollbars)
- **Expanded**: 280px panel, slides in with 200ms `QPropertyAnimation`
- **Expand trigger**: click the strip; or hotkey when sidebar is active and nothing to translate (shows last translation)
- **Collapse trigger**: mouse leaves → 300ms delay → collapses (unless keep-pinned is on)
- **Keep-pinned toggle**: button in header; disables auto-collapse on mouse leave
- **Esc**: collapses to strip; **X**: reverts to popup mode entirely (hides sidebar, disables sidebar mode)
- **Indicator colours**: cyan `#00C9CC` = fresh translation; muted rose `#9E8080` = idle/stale
  (user noted colours should be configurable in M7)
- **Draggable** up/down along screen edge
- **Left/right**: toggled from tray menu ("Move sidebar to left/right")
- **Sidebar mode**: activated when user first pins a translation (or via tray toggle).
  In sidebar mode, hotkey captures text → translation goes directly to sidebar (no popup shown).
  Translation runs in background; sidebar shows "Translating…" then updates.

**Manual test checklist for Windows 11**:
- [ ] 6px strip visible at screen edge; doesn't cover scrollbar of maximised window
- [ ] Click strip → panel slides in (200ms); click away → slides back
- [ ] Keep-pinned: panel stays open when mouse leaves
- [ ] Esc collapses; X reverts to popup mode
- [ ] Drag strip up/down → Y position updates
- [ ] Tray → "Move sidebar to left" → strip moves to left edge
- [ ] In sidebar mode: hotkey → sidebar updates directly (no popup)
- [ ] Indicator: cyan when fresh translation arrives; rose when stale/idle

---

## M6 — OCR

**Scope**: Clipboard image → OCR → translate. Auto-detect in hotkey flow.

**Delivered** (commits `4803a95`, `8a0da4a`):
- `src/zh_en_translator/engines/ocr/engine.py` — unified waterfall: PaddleOCR → Windows.Media.Ocr → Tesseract
- `src/zh_en_translator/engines/ocr/windows_ocr.py` — async WinRT OCR; tries `winrt-*` packages first, falls back to `winsdk`
- `src/zh_en_translator/engines/ocr/tesseract_ocr.py` — `pytesseract` fallback
- `src/zh_en_translator/engines/ocr/paddle_ocr.py` — PaddleOCR opt-in engine
- `src/zh_en_translator/app.py` — auto-detect flow: selected text → clipboard image (OCR) → clipboard text
- `src/zh_en_translator/ui/popup.py` — `is_ocr_pending` param + `set_ocr_result()` method
- `pyproject.toml` — optional deps: `[ocr-windows]` (winrt-* wheels), `[ocr-windows-legacy]` (winsdk), `[ocr-tesseract]`, `[ocr-paddle]`
- 7 new tests (`tests/test_ocr.py`)

**First-run notes**:
- Install Windows OCR support (no C compiler needed): `.\scripts\install-windows.ps1 -OCR`
- PaddleOCR is opt-in (heavy): `pip install "zh-en-translator[ocr-paddle]"`
- Tesseract needs separate binary install + chi_sim language pack

**Manual test checklist for Windows 11**:
- [ ] Run `.\scripts\install-windows.ps1 -OCR` → `winrt-*` packages installed
- [ ] Copy image with Chinese text → `Ctrl+Shift+T` → popup/sidebar shows OCR text + translation
- [ ] Copy image with no text → "No text detected"
- [ ] No Chinese language pack installed → "Open Language Settings" button appears
- [ ] No selection, clipboard has Chinese text → translate clipboard text directly

---

## M7 — Preferences

**Scope**: In-app preferences dialog + TOML config system.

**Delivered**:
- `src/zh_en_translator/config.py` — `Config` dataclass with typed defaults; `load_config()` / `save_config()` using stdlib `tomllib` (read) + manual TOML formatting (write); config path via `platformdirs.user_config_dir("zh-en-translator")` → `config.toml`
- `src/zh_en_translator/ui/preferences.py` — `PreferencesDialog(QDialog)` with four tabs:
  - **General**: hotkey `QLineEdit` (pynput syntax hint), mode radio (Popup / Sidebar)
  - **Display**: `QFontComboBox` font family, `QSpinBox` font size (8–36 pt), background color swatch → `QColorDialog` with "Reset to default"
  - **Sidebar**: Left/Right radio, Y position spinbox (0–2000), fresh + idle indicator color swatches
  - **Lookup & OCR**: external lookup URL `QLineEdit`, OCR engine `QComboBox` (Auto / Windows / Tesseract / PaddleOCR)
  - Standard OK / Cancel / Apply buttons; `settings_applied = pyqtSignal(Config)` on Apply/OK
- `src/zh_en_translator/app.py` updates:
  - Loads config at startup; applies hotkey, sidebar side/Y, mode
  - "Preferences…" tray menu item (before Pause)
  - `_on_settings_applied(cfg)`: re-registers hotkey if changed, calls `sidebar.apply_config()`, updates tray labels
  - Passes `config=self.config` to all `TranslatorPopup` instances
- `src/zh_en_translator/ui/popup.py` — `config=None` parameter; applies font family, font size, bg color override
- `src/zh_en_translator/ui/sidebar.py` — `config=None` constructor parameter; `apply_config(cfg)` method for live updates
- `tests/test_config.py` — 8 tests: defaults, save/load, missing file, partial TOML, invalid TOML, dir creation, `get_config_path`, special chars roundtrip

**Config fields**:
```
[general]  hotkey, mode
[display]  font_family, font_size, bg_color
[sidebar]  side, sidebar_y, color_fresh, color_idle
[lookup]   external_lookup_url
[ocr]      ocr_engine
```

**Deviations from PLAN.md**:
- `theme` (system/dark/light/sepia) deferred — requires stylesheet overhaul; design TBD in M9

**Manual test checklist for Windows 11**:
- [ ] Right-click tray → "Preferences…" opens dialog
- [ ] Change font size → Apply → popup uses new font size
- [ ] Change hotkey → Apply → new hotkey works; old does not
- [ ] Change sidebar colors → Apply → strip color updates
- [ ] Change mode to Sidebar → Apply → sidebar shows; no popup on hotkey
- [ ] Config persists across restarts (config.toml written to %APPDATA%\zh-en-translator\)

---

## Windows testing fixes (post-M7)

Bugs found and fixed during first Windows 11 testing pass.

**Installation fixes**:
- `sentencepiece==0.2.0` has no Python 3.14 wheel — workaround: install `sentencepiece>=0.2.0 --only-binary :all:` first (picks up 0.2.1), then `argostranslate --no-deps`
- `winsdk` requires a C compiler (no MSVC on user's machine) — switched `[ocr-windows]` to `winrt-*` pre-built binary wheels; `winsdk` kept as `[ocr-windows-legacy]`
- Added `scripts/install-windows.ps1` with `-OCR` switch to automate the above

**Runtime bugs fixed**:

| Bug | Root cause | Fix |
|---|---|---|
| Black/invisible popup | `WA_TranslucentBackground` corrupts per-widget palette on Windows (DWM sets Window role to black); `palette(text)` in stylesheets resolves to invisible | `setPalette(QApplication.palette())` reset + replace all `palette()` tokens with explicit hex colors computed from `_effective_bg().lightness()` |
| Black sidebar panel | Same `WA_TranslucentBackground` issue; sidebar child widgets still had `palette(text)` / `palette(mid)` | Added `_effective_bg()` + `_apply_styling()` to sidebar; bakes explicit hex colors into all five child widget stylesheets |
| OCR clipboard wipe | `capture_selection()` calls `pyperclip.copy("")` which wipes image data from clipboard | Snapshot `clipboard.image()` before `capture_selection()`; use snapshot as fallback |
| OCR always opened popup | `_run_ocr_from_qimage()` always created `TranslatorPopup` even in sidebar mode | Check `self.sidebar_mode` and route to sidebar with `_on_sidebar_ocr_result()` |
| "No text detected" (missing Chinese pack) | Windows OCR available but Chinese language pack not installed | Added `has_chinese_language()` check; show actionable error + "Open Language Settings" button (`ms-settings:regionlanguage`) |
| Sidebar strip unclickable | Collapsed window pushed mostly off-screen; strip drawn/detected at wrong side | Inverted strip position and `_is_on_strip` hit-test for collapsed vs expanded state |
| Indicator colors not updating | `apply_config()` compared indicator colour against already-updated `COLOUR_FRESH`/`COLOUR_IDLE` values | Save `was_fresh`/`was_idle` booleans before updating the class-level colours |
| Preferences mode sync | Tray toggle updated `sidebar_mode` but not `config.mode`; preferences opened showing stale state | Keep `config.mode` in sync in all three places where `sidebar_mode` changes; build runtime snapshot in `_open_preferences` |
| Pin button no visual feedback | Qt stylesheets don't support `opacity` property | Replaced with real CSS: `background: rgba(0,160,255,0.15); border: 1px solid rgba(0,160,255,0.5)` for `:checked` state |

**Tests added**: 74 → 83 (new: `btn_lang_settings` visibility, `set_ocr_result` routing, `_effective_bg`, `has_chinese_language`, `windows_ocr.is_available` with winrt+winsdk both blocked)

---

## Cleanup / Refactor

- `next_prompt.md` removed (was stale — referenced an old branch)
- Debug `print()` calls replaced with `logging` module throughout (`argos.py`, `popup.py`, `app.py`, `config.py`); `logging.basicConfig()` added to `app.main()` so warnings surface by default
- `_TranslationWorker` (popup.py) and `_SidebarTranslationWorker` (app.py) deduplicated into `src/zh_en_translator/engines/translation_worker.py`

---

## M2 update — jieba + full CC-CEDICT

**Added in branch `claude/review-plan-implementation-C0Fix`**:

- **jieba segmentation** (`src/zh_en_translator/engines/segmentation.py`):
  - `try: import jieba` at module load; sets `_JIEBA_AVAILABLE = True/False`.
  - `jieba.setLogLevel(logging.WARNING)` silences noisy stderr output.
  - `segment()` uses `jieba.cut(text, cut_all=False)` when jieba is available; filters empty tokens.
  - Old character-run logic preserved as `_segment_fallback(text)` for no-jieba environments.
  - `jieba>=0.42.1` added to `pyproject.toml` main dependencies.

- **Full CC-CEDICT download on first run** (`src/zh_en_translator/engines/dictionary.py`):
  - `CEDICT_URL` constant pointing to the MDBG ZIP distribution.
  - `get_cedict_path()` returns `platformdirs.user_data_dir("zh-en-translator") / "cedict_ts.u8"`.
  - `ensure_cedict()` checks for existing file; downloads the ZIP via `urllib.request.urlopen`,
    extracts `cedict_ts.u8`, and saves it. On any failure logs a warning and returns the bundled
    sample so the app stays functional offline.

- **Background warm-up** (`src/zh_en_translator/app.py`):
  - `_ensure_cedict_background()` module-level helper calls `ensure_cedict()` and logs the result.
  - `TranslatorApp.__init__` launches it as a daemon thread immediately after `load_config()`,
    so the dictionary is ready before the first popup lookup.

- **Tests** (88 → 91):
  - `test_segmentation.py`: updated `test_segment_english_only` to allow jieba's word-level
    splitting of English text (was hardcoded to fallback single-token behaviour); added mock tests
    for jieba path, empty-token filtering, and fallback path.
  - `test_dictionary.py`: added `TestEnsureCedict` class with three tests —
    download-and-extract success path, returns-existing-file (no re-download), and
    fallback-to-bundled-sample on network failure.

**Deviations**: none — jieba wheel fails to build in the sandbox via pip but is pure Python;
copied the extracted source tree directly to site-packages as a workaround.

---

## M9 — Part 1: OpenCC Traditional→Simplified

**Scope**: Detect and convert Traditional Chinese input to Simplified before dictionary lookup and neural MT.

**Delivered**:
- `src/zh_en_translator/engines/converter.py` — `to_simplified(text)` / `is_available()` with dual-backend probe:
  - Tries `import opencc` (official package) first, then `import opencc_python_reimplemented` as fallback.
  - Caches the `OpenCC("t2s")` instance at module level (expensive to construct).
  - Graceful degradation: if neither backend is importable, logs a debug message and returns text unchanged.
  - Never raises — all exceptions are caught and the original text is returned.
- `pyproject.toml` — new optional dep group `[traditional]` → `opencc-python-reimplemented>=1.1.0`.
- `src/zh_en_translator/config.py` — new `[translation]` TOML section with `traditional_to_simplified: bool = True` (default on).
- `src/zh_en_translator/app.py` — conversion applied in four code paths (all before text enters the pipeline):
  - Popup mode: after text capture, before `TranslatorPopup`.
  - Sidebar mode: after text capture, before `_translate_for_sidebar`.
  - OCR popup path: in `_on_ocr_result`, skipped if text starts with `⚠`.
  - OCR sidebar path: in `_on_sidebar_ocr_result`, skipped if text starts with `⚠`.
- `src/zh_en_translator/ui/preferences.py` — "Traditional Chinese" group box in the General tab with `_trad_to_simp_check` (`QCheckBox`); wired in `_load_config_into_ui()` and `_collect_config()`.
- `tests/test_converter.py` — 7 tests: simplified passthrough, traditional conversion (conditional on `is_available()`), never-raises, empty string, ASCII passthrough, `is_available()` bool type, idempotent.
- `tests/test_config.py` — 3 new tests: `traditional_to_simplified` default, False round-trip, True round-trip.
- `tests/test_app_smoke.py` — 3 new preferences tests: checkbox exists, reflects False, `_collect_config()` reads state.

**OpenCC availability in sandbox**: `opencc-python-reimplemented` not installed; graceful fallback active (Traditional text passes through unchanged, tests adapted via `is_available()` guard).

**Config field**:
```
[translation]
traditional_to_simplified = true
```

---

## M9 — Part 2: Theme support

**Scope**: Add `theme` config field (system/dark/light/sepia) controlling the overall color palette of both the popup and sidebar.

**Delivered**:
- `src/zh_en_translator/engines/themes.py` — `ThemePalette` frozen dataclass + `THEMES` dict (light, dark, sepia palettes) + `resolve_palette(theme, system_is_dark)` helper.
- `src/zh_en_translator/config.py` — `theme: str = "system"` field added to `Config`; saved/loaded from `[display]` TOML section.
- `src/zh_en_translator/ui/popup.py` — `_apply_styling()` replaced with theme-aware version that calls `resolve_palette()`; `_effective_bg()` updated to respect non-system theme when no `bg_color` override is set.
- `src/zh_en_translator/ui/sidebar.py` — `_apply_styling()` and `_effective_bg()` updated similarly; indicator strip colors (`COLOUR_FRESH` / `COLOUR_IDLE`) unchanged.
- `src/zh_en_translator/ui/preferences.py` — "Theme" group box added above Font in the Display tab (`_theme_combo` QComboBox with System default / Light / Dark / Sepia); wired in `_load_config_into_ui()` and `_collect_config()`.
- `tests/test_themes.py` — 11 new tests covering `resolve_palette`, config roundtrip, and preferences combo.

**Behavior**: `bg_color` override still takes priority over theme background — when set, the palette is re-resolved based on the override color's lightness.

**Config field**:
```
[display]
theme = "system"   # "system" | "dark" | "light" | "sepia"
```

**Tests**: 112 → 123 (+11).

---

## M9 — Part 3: Qt Accessibility

**Scope**: Screen-reader support via Qt accessible names, descriptions, and logical tab order for the popup and sidebar.

**Delivered**:
- `src/zh_en_translator/ui/popup.py` — new `_setup_accessibility()` method called at the end of `_setup_ui()`:
  - `setAccessibleName()` on `_pinyin_label`, `text_display`, `translation_label`
  - `setAccessibleDescription()` on all five buttons (`btn_copy`, `btn_lookup`, `btn_replace`, `btn_pin`, `btn_lang_settings`) and all informational widgets
  - Logical tab order: source text → translation → Copy → Look up → Replace text → Pin
- `src/zh_en_translator/ui/sidebar.py` — new `_setup_accessibility()` method called in `__init__`:
  - `setAccessibleName("Translation sidebar")` on the sidebar itself
  - `setAccessibleName("Source text")` on `source_label`
  - `setAccessibleName("Translation")` on `translation_label`
  - `setAccessibleDescription()` on `btn_pin` and `_close_btn`
- `tests/test_accessibility.py` — 15 new tests covering popup and sidebar accessible names/descriptions; all use `qapp` fixture and `_cleanup` pattern

**Tests**: 123 → 138 (+15).

**Manual verification needed**: NVDA screen reader navigation, DPI scaling on 4K displays.

---

## Popup UI Refinements (Post-M9)

**Scope**: Improve popup UI with better affordances; add pin-to-keep-open and close buttons.

**Delivered**:
- `src/zh_en_translator/ui/popup.py`:
  - **Header row** (top of popup): Checkable pin button (📌) + close button (✕)
    - Pin button (📌) — checkable, keeps popup open when toggled; disabled while translating, enabled on result
    - Close button (✕) — always available, immediately dismisses popup
  - **Bottom action row**: Retains original buttons (Copy, Look up, Replace, Pin →)
    - "Pin →" button sends translation to sidebar and dismisses popup
  - `_pinned` state added to `__init__`; `changeEvent()` respects pinned state to prevent auto-dismiss on focus loss
  - `_on_pin_toggled(checked)` handler updates pin state for header pin button
  - `_pin_to_sidebar()` method handles "Pin →" button (send to sidebar + dismiss)
  - Button styling includes `:checked` pseudo-state with blue highlight for pin button
  - Accessibility: Pin button (top) has accessible name/description; Pin → (bottom) has description; tab order updated

- `src/zh_en_translator/ui/sidebar.py`:
  - **Context menu fix**: Added unified stylesheet for `QMenu` items to prevent black background on right-click menus
  - `_apply_styling()` now computes border color with fallback and creates unified CSS for entire sidebar (both widgets and context menus)
  - QMenu styled with theme background, correct text color, padding, and border
  - QMenu items get hover background color; separators get proper styling

**Layout**:
```
┌─────────────────────────┐
│ [Pin 📌] [Close ✕]      │  ← Header row (top controls)
├─────────────────────────┤
│ [Pinyin...]             │
│ Chinese text...         │
│ ─────────────────────   │
│ English translation...  │
│                         │
│ [Copy] [Look up] [...] │
│ [Replace] [Pin →]       │  ← Action row (bottom buttons)
└─────────────────────────┘
```

**Behavior**:
- **Popup pinning**: Toggle pin (📌 at top) to keep popup open; prevents auto-dismiss on focus loss. Esc still closes.
- **Close button**: Always available (✕ at top); gives non-keyboard users clear dismiss affordance.
- **Sidebar integration**: "Pin →" button at bottom sends translation to sidebar and dismisses popup (existing behavior preserved).
- **Context menus**: Sidebar context menus now respect theme (light/dark) instead of appearing with black background.

**Tests**: No new tests (UI-only changes); existing smoke tests remain passing.

**Manual test checklist for Windows 11**:
- [ ] Header buttons visible at top: Pin (📌) disabled while translating, Close (✕) always visible
- [ ] Pin button enabled once translation arrives
- [ ] Click pin button → blue highlight + popup stays open on focus loss
- [ ] Click pin button again → highlight disappears; popup auto-dismisses on next focus loss
- [ ] Close button (✕) immediately closes popup
- [ ] Esc still closes popup (pinned or not)
- [ ] "Pin →" button in action row sends to sidebar and closes popup
- [ ] Right-click on sidebar text → context menu appears with proper colors (not black background)

---

## M10 — Optional MS Cloud

**Scope**: Opt-in Azure Translator with explicit warning banner; zero egress when disabled.

**Delivered**:
- `src/zh_en_translator/engines/ms_cloud.py` — Azure Cognitive Services Translator (v3 REST API):
  - `is_configured(api_key)` — True only when a non-blank key is provided
  - `translate_sentence(text, api_key, region)` — POST to Azure endpoint with `urllib.request`; returns `None` on any failure (HTTP error, network error, malformed JSON); never raises
  - Zero network calls when key is empty or text is blank
- `src/zh_en_translator/config.py` — new `[cloud]` TOML section with three fields:
  - `ms_translator_enabled: bool = False` (default off — no egress)
  - `ms_translator_api_key: str = ""`
  - `ms_translator_region: str = ""`
- `src/zh_en_translator/engines/translation_worker.py` — `TranslationWorker` now accepts an optional `config` argument:
  - When `ms_translator_enabled=True` AND a key is configured, tries Azure first
  - Automatically falls back to local Argos engine on any cloud failure
  - When `ms_translator_enabled=False` (default), the cloud code path is never reached
- `src/zh_en_translator/ui/popup.py` — passes `config` to `TranslationWorker` so popup picks up engine choice
- `src/zh_en_translator/app.py`:
  - Sidebar `TranslationWorker` also receives `config`
  - `_open_preferences()` snapshot now includes the three cloud fields (prevents them resetting on every dialog open)
- `src/zh_en_translator/ui/preferences.py` — new **Cloud** tab (fifth tab):
  - Orange-bordered warning banner: data leaves the machine, API key stored plain-text
  - `ms_translator_enabled` checkbox (unchecked by default)
  - API key `QLineEdit` with `EchoMode.Password` + "Show/Hide" toggle button
  - Region `QLineEdit` (optional; blank = no region header sent)
  - Credentials group box is disabled until the checkbox is ticked
  - Hint text with pricing info (Azure Free tier: 2 M chars/month)
- `tests/test_ms_cloud.py` — 20 tests (14 run everywhere; 6 require PyQt6 and skip cleanly in headless CI):
  - `is_configured` edge cases
  - Zero-network guarantee when key is empty
  - Mocked HTTP success, region header forwarding, no-region-header path
  - Graceful failure: HTTP 401, URLError, malformed JSON
  - Config defaults + round-trip for all three cloud fields
  - `TranslationWorker` skips cloud when disabled; uses cloud when enabled (Qt-gated)
  - Preferences tab presence, default unchecked state, collect-config, masked key field (Qt-gated)

**User discoverability**:
- Right-click tray → **Preferences…** → **Cloud** tab (the tab is always visible; badge-free but clearly named)
- Warning banner inside the tab makes the opt-in nature immediately visible
- Credentials group box is greyed out until the user explicitly ticks the enable checkbox — prevents accidental key entry

**Config fields**:
```toml
[cloud]
ms_translator_enabled = false
ms_translator_api_key = ""
ms_translator_region = ""   # e.g. "eastus", "westeurope"; optional
```

**Tests**: 138 → 152 (+14 non-Qt, +6 Qt-gated skips in sandbox).

**Manual test checklist for Windows 11**:
- [ ] Tray → Preferences → Cloud tab visible (5th tab)
- [ ] Warning banner shown with orange border
- [ ] Credentials group disabled until checkbox ticked
- [ ] Enter valid Azure key + region → Apply → translate selection → result comes from Azure (check network monitor)
- [ ] Disable cloud → Apply → no outbound traffic during translation
- [ ] Invalid key → translation falls back to Argos silently (warning logged)
- [ ] Config.toml contains `[cloud]` section after Apply
- [ ] Restart app → cloud settings persist

---

## App icon + monitor warning fix (post-M10)

**Scope**: Replace placeholder icon; suppress spurious Qt monitor warning.

**Delivered**:
- `src/zh_en_translator/app.py`:
  - `_render_icon_pixmap(size)` — draws a blue (#2563EB) antialiased rounded square with a white "中" glyph at any requested pixel size; font fallback chain: Microsoft YaHei → SimHei → Arial Unicode MS → system default
  - `_create_icon()` now builds a multi-size `QIcon` (16, 24, 32, 48, 64, 128, 256 px) via `QIcon.addPixmap()`
  - `_setup_tray()` calls `QApplication.setWindowIcon(app_icon)` so popup and sidebar windows inherit the icon automatically (Windows taskbar, Alt-Tab switcher, Explorer title bar)
  - `main()` sets `QT_LOGGING_RULES=qt.qpa.screen.warning=false` **before** `QApplication` is created — suppresses the harmless `"Unable to open monitor interface to \\\\.\\DISPLAY2:"` warning (error `0xe0000225` = `ERROR_NOT_FOUND`) that Windows emits when a secondary display adapter detects no physical monitor on the port

---

## UI Overhaul (post-M10)

**Scope**: Compact popup, resizable sidebar with interactive drag, live preferences preview.

**Delivered**:

### Popup
- Header pin (📌) and close (✕) buttons shrunk from 32×32 to 22×22 px; styled as borderless icon buttons with subtle hover highlight.
- Layout margins reduced (18 → 14 px sides, 14 → 8 px top); inter-widget spacing 10 → 7 px.
- Initial size 400×160 (was 420×190); max height 520 px; height is fully content-driven.
- Action button "Replace text" shortened to "Replace"; buttons now pill-shaped (`border-radius: 10px`) with refined hover/disabled states.
- Removed duplicate `_on_pinyin_ready` method that was silently shadowing the real implementation.

### Sidebar
- **Resizable** — `_ResizeHandle` child widget (6 px, `SizeHorCursor`) sits at the inner edge of the expanded panel. Drag it to resize between 180 and 600 px. Right-docked: handle at left edge; left-docked: handle at right edge.
- **Free drag** — strip drag (Y repositioning) now works in **both** collapsed and expanded states. When expanded, a ⠿ grip icon in the header also initiates Y drag.
- **Auto-save** — width and Y position written to `config.toml` automatically on drag/resize release (no apply button needed).
- Panel width is now a per-instance variable (`self._width`, default 280 px); class constant `WIDTH` removed.
- New `sidebar_width: int = 280` field in `Config`, `load_config`, and `save_config`.
- Rounded corners 12 px (was 10); header buttons 22×22.

### Preferences
- **Sidebar tab**: Y-position spinbox removed; replaced with a hint explaining interactive drag/resize.
- **Display tab**: live **Preview** panel added below Pinyin settings — a mini styled frame that re-renders in real-time as theme, font family, font size, or background colour changes.
- **Unsaved-changes guard**: closing the dialog with unapplied edits shows a *Save / Discard / Cancel* message box. OK and Cancel buttons bypass the check (`_skip_close_check` flag). All settings widgets connected to `_mark_dirty`; flag cleared on Apply/OK.

**Config fields added**:
```toml
[sidebar]
sidebar_width = 280
```

**Tests**: no regressions (152 tests; PyQt6 UI-only changes not covered by sandbox tests).

**Manual test checklist for Windows 11**:
- [ ] Popup appears at ~400×160, grows to fit translation text (no fixed height)
- [ ] Pin and close buttons in header are small and unobtrusive; hover shows highlight
- [ ] Sidebar inner edge shows SizeHorCursor when expanded; drag resizes smoothly
- [ ] Drag indicator strip (collapsed or expanded) moves sidebar up/down; saves on release
- [ ] Drag ⠿ icon in expanded header also moves sidebar vertically
- [ ] Width and Y position survive app restart (written to config.toml)
- [ ] Preferences → Display: changing theme/font/size updates Preview panel instantly
- [ ] Close Preferences with unsaved changes → Save/Discard/Cancel dialog appears
- [ ] Cancel button closes without prompting; OK saves without prompting

---

## Post-overhaul fixes

### Popup header buttons not rendering on Windows (fix)

**Root cause**: `setObjectName("headerBtn")` was called *after* `setStyleSheet()`. Qt skips
stylesheet re-evaluation when the string is unchanged, so the `#headerBtn` CSS rules never
fired. Additionally, `min-height: 0` in the CSS can override `setFixedSize` on Windows and
collapse button height to 0 px.

**Fix**: removed the objectName approach entirely; call `setStyleSheet()` directly on
`btn_pin` and `btn_close` — the same pattern already used reliably in `sidebar.py`.

### Draggable popup

Users can now click-and-drag the popup to any position on screen:
- **`⠿` grip icon** added to the left of the header row — shows `SizeAllCursor` as a visible affordance.
- Drag starts from any non-interactive area that propagates mouse events to the parent:
  the grip, header stretch, margins, separator, pinyin label.
- Buttons and text fields (`QPushButton`, `QTextEdit`, selectable `QLabel`) absorb their
  own mouse events and are excluded automatically — no explicit blocklist needed.
- Cursor changes to `SizeAllCursor` during drag and is restored on release.

**Manual test checklist for Windows 11**:
- [ ] Pin (📌) and close (✕) icons visible in popup header immediately on open
- [ ] Hover over header buttons shows highlight; click works correctly
- [ ] Grab ⠿ grip or any margin area → cursor becomes move cursor → popup follows mouse
- [ ] Release → cursor restores; popup stays at new position
- [ ] Clicking buttons and selecting text still works normally (not intercepted by drag)

---

## Cloud tab disabled (post-M10)

Azure is the only wired-up cloud provider and requires an Azure account/API key.
The Cloud tab has been hidden from the Preferences dialog until a better provider
(e.g. DeepL free tier) is chosen and implemented. One line in `preferences.py`
`_setup_ui` is commented out to re-enable it; all backend code and config fields
are untouched.

---

## M8 — Packaging

**Scope**: Single-file Windows installer, startup-on-login, OCR fallback, post-install Argos model download.

**Delivered**:
- `installer/zh-en-translator.spec` — PyInstaller onedir spec; no UPX (breaks ctranslate2/sentencepiece DLLs); excludes stanza/torch/paddle; collects PyQt6, ctranslate2, argostranslate data files. Total bundle ~240–290 MB.
- `installer/zh-en-translator.iss` — Inno Setup 6 script producing a single `zh-en-translator-setup.exe`. Win 10/11 x64, user-level install (no admin). Tasks: desktop shortcut (unchecked), startup-on-login (checked). Post-install: Argos zh→en pack downloaded silently; Windows OCR checked — if unavailable, offers Tesseract download.
- `installer/build.ps1` — one-command build script: `pyinstaller → iscc`.
- `installer/download_packs.ps1` — post-install Argos model downloader (called by Inno Setup [Run]).
- `config.py` — `startup: bool = True` field added (load + save).
- `app.py` — `_apply_startup_setting()` writes/clears `HKCU\…\Run` on startup and on each preferences-apply; no-op in dev mode (`sys.frozen` guard).
- `preferences.py` — "Windows Startup" checkbox in General tab; wired to dirty flag.

**Deviations from PLAN.md**:
- Output is a single `.exe` (self-extracting via Inno Setup), not MSI. Equivalent UX; no WiX needed.
- Argos model pack is downloaded post-install (not bundled) — keeps installer ~240–290 MB instead of ~390 MB.
- Unsigned for v1; SmartScreen warning expected until a code-signing cert is obtained.

**Build instructions** (on a Windows machine):
```powershell
# Install build tools
pip install pyinstaller
# (Inno Setup 6 installed separately from https://jrsoftware.org/isdl.php)

# From repo root:
.\installer\build.ps1
# Output: installer\Output\zh-en-translator-setup.exe
```

**Manual test checklist for Windows 11**:
- [ ] `.\installer\build.ps1` completes without errors
- [ ] `installer\Output\zh-en-translator-setup.exe` produced (~240–290 MB)
- [ ] Installer runs on clean Win 11 VM; no runtime deps needed
- [ ] Post-install: Argos model download runs (or offers manual install)
- [ ] OCR: if no Chinese Windows OCR pack, Tesseract download is offered
- [ ] Startup checkbox in installer creates HKCU Run entry; app launches on next login
- [ ] Startup checkbox in Preferences updates Run entry live

---

## Open questions / risks

- **MSI code signing** — deferred; SmartScreen warning until cert available.
- **Sidebar translation history** — currently shows only last translation; future: scrollable history.
- **Cloud provider** — Azure requires account/CC; DeepL free tier (500K chars/month, no CC) is the leading candidate to replace or supplement it.

