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
| M5 — Sidebar Mode (peek tab) | 🔄 In progress | Basic floating panel built; proper peek-tab being built |
| M6 — OCR | ✅ Done | Waterfall: PaddleOCR → winsdk → Tesseract; auto-detect clipboard |
| M7 — Preferences | ⏳ Pending | |
| M8 — Packaging (MSI) | ⏳ Pending | |
| M9 — Accessibility + Traditional | ⏳ Pending | |
| M10 — Optional MS Cloud | ⏳ Pending | |

Branch: `claude/fix-windows-testing-issues-E6tHq`

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
- `src/zh_en_translator/engines/ocr/engine.py` — unified waterfall: PaddleOCR → winsdk Windows.Media.Ocr → Tesseract
- `src/zh_en_translator/engines/ocr/windows_ocr.py` — async WinRT OCR via `winsdk`
- `src/zh_en_translator/engines/ocr/tesseract_ocr.py` — `pytesseract` fallback
- `src/zh_en_translator/engines/ocr/paddle_ocr.py` — PaddleOCR opt-in engine
- `src/zh_en_translator/app.py` — auto-detect flow: selected text → clipboard image (OCR) → clipboard text
- `src/zh_en_translator/ui/popup.py` — `is_ocr_pending` param + `set_ocr_result()` method
- `pyproject.toml` — optional deps: `[ocr-windows]`, `[ocr-tesseract]`, `[ocr-paddle]`
- 7 new tests (`tests/test_ocr.py`)

**First-run notes**:
- winsdk not yet installed on test Windows machine; install with `pip install winsdk`
- PaddleOCR is opt-in (heavy): `pip install "zh-en-translator[ocr-paddle]"`
- Tesseract needs separate binary install + chi_sim language pack

**Manual test checklist for Windows 11**:
- [ ] `pip install winsdk` → OCR engine available
- [ ] Copy image with Chinese text → `Ctrl+Shift+T` → popup shows OCR text + translation
- [ ] Copy image with no text → "No text detected"
- [ ] No selection, clipboard has Chinese text → translate clipboard text directly

---

## Open questions / risks

- **Full CC-CEDICT distribution** — sample is only 50 entries. Bundle full ~2 MB file or download on first run?
- **jieba re-introduction** — opt-in in M7?
- **Hotkey conflicts** — `Ctrl+Shift+T` clashes with "reopen closed tab" in browsers. Configurable in M7.
- **MSI code signing** — deferred; SmartScreen warning until cert available.
- **Indicator colours** — cyan/rose agreed; make user-configurable in M7.
- **Sidebar position persistence** — save Y position and left/right side across restarts (M7 config.toml).
- **Sidebar translation history** — currently shows only last translation; future: scrollable history.
- **winsdk OCR on Python 3.14** — needs testing; asyncio integration may need adjustment.
