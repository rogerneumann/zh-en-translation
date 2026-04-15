# Progress Tracker

Running log of what has been built, what deviated from the plan, and what still
needs verification. Update this file at the end of every milestone.

Source of truth for plan/scope: `PLAN.md`.

---

## Status at a glance

| Milestone | Status | Commit | Verified on Windows? |
|---|---|---|---|
| M0 — Plan | Done | `be0570e` | n/a |
| M1 — Hello Popup | Done | `4c2b154`, `218209c` | ❌ Not yet |
| M2 — Dictionary Lookup | Done (engine only) | `6cd58ad` | ❌ Not yet |
| M3 — Replace + External Lookup | Skipped for now | — | — |
| M4 — Sentence Translation | Done | `claude/fix-windows-testing-issues-E6tHq` | ❌ Not yet |
| M5 — Sidebar Mode | Pending | — | — |
| M6 — OCR | Pending | — | — |
| M7 — Preferences | Pending | — | — |
| M8 — Packaging (MSI) | Pending | — | — |
| M9 — Accessibility + Traditional | Pending | — | — |
| M10 — Optional MS Cloud | Pending | — | — |

Branch: `claude/popup-translator-app-7bQp3`

---

## M1 — Hello Popup

**Scope**: Tray app, global hotkey, selected-text capture, frameless popup, dismiss behaviors.

**Delivered**:
- `src/zh_en_translator/app.py` — `QSystemTrayIcon` with Translate / Pause / Quit menu
- `src/zh_en_translator/hotkey.py` — `pynput.GlobalHotKeys` wrapper, default `Ctrl+Shift+T`
- `src/zh_en_translator/capture.py` — clipboard save → simulate Ctrl+C → restore
- `src/zh_en_translator/ui/popup.py` — frameless rounded-corner popup, drop shadow, cursor positioning, Esc / click-outside / focus-loss dismiss
- 25 unit tests across `tests/test_app_smoke.py`, `test_capture.py`, `test_hotkey.py`
- `pyproject.toml`, `conftest.py`, `.gitignore`
- README Development section

**Fixes applied post-agent-exit**:
- `QGraphicsDropShadowEffect.setOpacity()` doesn't exist in PyQt6 — replaced with `QColor(0, 0, 0, 76)` alpha (commit `218209c`)
- Ruff cleanup (unused imports, unused locals) rolled into scaffold commit

**Deviations from PLAN.md**: None.

**Not verifiable in Linux sandbox**:
- Global hotkey (no X server)
- PyQt6 rendering (no libEGL)
- Clipboard save/restore against real apps

**Manual test checklist for Windows 11**:
- [ ] Tray icon appears (blue square).
- [ ] `Ctrl+Shift+T` with text selected in Notepad → popup at cursor.
- [ ] Esc closes popup; original clipboard is restored.
- [ ] Click outside popup → closes.
- [ ] Alt-Tab away → popup closes.
- [ ] Popup repositions near screen edges.
- [ ] Multi-monitor: popup appears on correct screen.
- [ ] Works in Word, a browser, and a Save-As filename field.
- [ ] Right-click tray → Pause → hotkey does nothing → Resume → works again.

---

## M2 — Dictionary Lookup

**Scope**: CC-CEDICT + segmentation + word-by-word popup with pinyin.

**Delivered**:
- `src/zh_en_translator/engines/dictionary.py` — CC-CEDICT parser, SQLite schema (simplified + traditional indexed), pinyin tone-number to tone-mark converter, `Dictionary.build_from_cedict()` / `lookup()`
- `src/zh_en_translator/engines/segmentation.py` — character-run segmentation (Chinese vs. non-Chinese)
- `src/zh_en_translator/engines/pipeline.py` — segment + greedy longest-match dictionary lookup, returns `TokenResult` records
- `src/zh_en_translator/resources/cedict_sample.txt` — ~50 starter entries
- `src/zh_en_translator/app.py` — builds DB at `platformdirs` user data dir on first run; adds "Rebuild Dictionary" tray action
- `src/zh_en_translator/ui/popup.py` — `QTableWidget` word-by-word view (Token / Pinyin / English); unknown Chinese tokens highlighted pale yellow and remain selectable for copy/paste
- 22 new tests (`test_dictionary.py`, `test_segmentation.py`, `test_pipeline.py`)
- Adds `platformdirs` dep

**Fixes applied post-agent-exit**:
- **Pinyin tone-mark placement bug**: original agent code didn't mark the last vowel when no `a`/`e`/`o` was present (so `ni3` rendered as `ni` instead of `nǐ`, `lü3` as `lü` instead of `lǚ`). Rewrote the placement to follow the canonical rule: `a` > `e` > `ou` > last vowel. Regression tests for all tones 1-5 + ü-umlaut pass.
- `test_popup_long_text_sizing` asserted `width <= 600` (M1 bound); M2 widened popup to 700 for the table. Relaxed assertion.

**Deviations from PLAN.md**:
- **Dropped `jieba`** in favor of character-run segmentation + longest-match dictionary lookup. Reason: `jieba` wheel build failed in the Linux sandbox. Consequence: unknown multi-character compounds (not in dict) will split into individual chars rather than grouped unknown words. Acceptable for the 50-entry sample dictionary; tolerable for full CC-CEDICT (~120k entries); worth revisiting as an opt-in in M7.

**Not verifiable in Linux sandbox**:
- `jieba`-dependent tests (not installed). 39/39 other tests pass, including all 14 dictionary tests.
- Visual quality of the word-by-word table

**Manual test checklist for Windows 11**:
- [ ] Select `你好世界` in any app, hotkey → popup shows: `你好` / `nǐ hǎo` / `hello; hi` and `世界` / `shì jiè` / `world`.
- [ ] Unknown Chinese chars show pale yellow background, empty English column, still selectable.
- [ ] Pinyin tone marks (ā á ǎ à) render correctly in the system font.
- [ ] DPI scaling 125% / 150%: table columns remain readable, no clipping.
- [ ] Tray → Rebuild Dictionary → DB regenerates without crash.

---

## M4 — Sentence Translation

**Scope**: Argos Translate integration; popup shows readable English sentence.

**Delivered**:
- `src/zh_en_translator/engines/argos.py` — `is_available()`, `ensure_pack()` (downloads zh→en model ~100 MB on first use), `translate_sentence()`
- `src/zh_en_translator/ui/popup.py` — redesigned: source text (small, muted) + English sentence (large, selectable). `_TranslationWorker` (QThread) runs translation in background; popup appears instantly and fills in when ready.
- `src/zh_en_translator/app.py` — stripped dictionary wiring; popup is self-contained.
- `pyproject.toml` — added `argostranslate>=1.9.0` dependency.

**Deviations from PLAN.md**:
- M2 word-by-word table removed from popup UI (user preference — readable sentence is the primary output). Dictionary engine code remains; word-by-word can be added back as a collapsible section in M7.
- M3 (Replace + External Lookup) skipped for now; will revisit after M4 is verified on Windows.

**First-run behaviour**:
- If the zh→en Argos pack is not installed, `_TranslationWorker` calls `ensure_pack()` which downloads it automatically (~100 MB, requires internet, one-time only). The popup shows "Translating…" during download.

**Manual test checklist for Windows 11**:
- [ ] `pip install -e .` picks up `argostranslate`.
- [ ] First hotkey trigger → "Translating…" appears, then pack downloads, then English sentence fills in.
- [ ] Subsequent triggers → translation appears within ~2 s (no re-download).
- [ ] Translated text is selectable and copyable.
- [ ] Popup dismisses correctly (Esc / click-outside / focus loss).

## M3 — Replace + External Lookup  (deferred)

Skipped in favour of shipping M4 first. See `next_prompt.md` for context.

---

## Open questions / risks

- **Full CC-CEDICT distribution** — currently bundled sample is only 50 entries. Decide whether to bundle full ~2 MB text file or download on first run (download violates offline-first unless user opts in).
- **jieba re-introduction** — should we add it back as an opt-in in M7?
- **Global hotkey conflicts** — `Ctrl+Shift+T` may clash with browser "reopen closed tab". Revisit default in M7.
- **MSI code signing** — deferred; will show SmartScreen warning until we have a cert.
