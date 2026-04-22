# Progress Tracker

Running log of what has been built, what deviated from the plan, and what still
needs verification. Update this file at the end of every milestone.

Source of truth for plan/scope: `PLAN.md`, `plan-v2.md`, `plan-v3.md`, and **`v4_completeness.md`** (NEW).

---

## Current Initiative: Translation Completeness (v4) — 2026-04-22

**Issue Identified:** Sentence-level translation (Argos/ctranslate2) drops clauses and details on complex Chinese sentences.

**Example:**
```
Original:  "NADCC氯片... 狗骨头浸泡测试已完成 实验室今天提供给@杨中宝"
Current:   "NADCC chlorine tablets... test completed."
Missing:   "The laboratory provided the results to @YangZhongbao today."
Completeness: ~60%
```

**Root Cause:** Neural MT models compress content on complex run-on sentences lacking explicit structural markers.

**Solution:** Three-phase hybrid approach (see `v4_completeness.md` for full plan):
- **Phase 1:** Post-processing validation & recovery (1.2x speed, +30-50% completeness)
- **Phase 2:** Clause-level translation fallback (3-5x on complex, +20-30% total gain)
- **Phase 3:** Adaptive orchestration (1.5x average, final optimization)

**Effort:** ~7-9 hours total | **Expected outcome:** 95% completeness (up from 60%)

**Status:** 
- ✅ Problem analysis complete
- ✅ Solution designed (agent-assisted)
- ⏳ Phase 1 implementation in progress
- 📅 Phase 2 pending
- 📅 Phase 3 pending

---

## Latest: Build System Fixes (2026-04-21)

**Issue:** `installer/build.ps1` had PowerShell parse errors on Windows.

**Root Cause:** Windows PowerShell 5.1 reads `.ps1` files without UTF-8 BOM using CP1252 encoding, causing UTF-8 em-dashes (`—`) to be misinterpreted as string terminators.

**Resolution:**
- ✅ Replaced all em-dashes with ASCII double-hyphens (`--`)
- ✅ Added UTF-8 BOM to build.ps1
- ✅ Corrected `.gitattributes` rule order (general rules first, specific rules override)
- ✅ Replaced here-string with array-join for README generation (line-ending independent)
- ✅ Created **CLAUDE.md** with permanent knowledge base for PowerShell encoding issues

**Status:** build.ps1 now parses and runs successfully on Windows PowerShell 5.1.

---

## Status at a glance (v1 Plan)

| Milestone | Status | Notes |
|---|---|---|
| M1 — Hello Popup | ✅ Done | |
| M2 — Dictionary Lookup | ✅ Done | jieba + full CC-CEDICT download |
| M3 — Replace + Copy + External Lookup | ✅ Done | |
| M4 — Sentence Translation | ✅ Done | Argos Translate / ctranslate2 |
| M5 — Sidebar Mode | ✅ Done | Peek-tab design with animations |
| M6 — OCR | ✅ Done | Waterfall: PaddleOCR → Windows → Tesseract |
| M7 — Preferences | ✅ Done | TOML config + UI |
| M8 — Packaging | ✅ Done | Inno Setup installer |
| M9 — Accessibility + Traditional | ✅ Done | OpenCC + Qt A11y |
| M10 — Optional MS Cloud | ✅ Done | Azure Translator opt-in |

## Status at a glance (v2 Enhancements)

| Milestone | Status | Notes |
|---|---|---|
| M1 — Core Infrastructure | ✅ Done | QClipboard, Rotating logs, Loading indicators |
| M2 — Sidebar History | ✅ Done | JSON-based history, scrollable list, export/clear |
| M3 — Intelligence & A11y | ✅ Done | Inline lookup, Collapsible breakdown, High Contrast theme |
| M4 — External Integrations | ✅ Done | DeepL support, Update Checker, Inline source editing |
| UI Refresh | ✅ Done | Fluent-lite: Segoe UI Variable/Aptos fonts, pill buttons, soft fills |

---

## UI Refresh (Fluent-lite)

**Scope**: Modernize the "standard Qt" look with Windows 11-native aesthetics.

**Delivered**:
- **Modern Typography**: Integrated `Segoe UI Variable Display` and `Aptos` font stack.
- **Pill-Shaped Buttons**: Updated all buttons to 14px-16px border-radius with soft `btn_bg` fills.
- **Spacing & Layout**: Increased margins and padding for a cleaner, more spacious "Fluent" feel.
- **Palette Refinement**: Shifted to pure `#FFFFFF` light and `#202020` dark backgrounds.
- **Theme Engine**: Added `btn_bg` to `ThemePalette` in `themes.py` for consistent soft-fill styling.

---

## v2 Milestone 4 — External Integrations & Lifecycle

**Scope**: DeepL engine, Update checker, Inline source editing.

**Delivered**:
- `src/zh_en_translator/engines/deepl.py` — DeepL API integration via `urllib.request`.
- `src/zh_en_translator/engines/updates.py` — GitHub Releases check logic.
- `src/zh_en_translator/engines/translation_worker.py` — Priority: DeepL > MS Cloud > Argos.
- `src/zh_en_translator/ui/preferences.py` — Added DeepL config, Update check toggle/button.
- `src/zh_en_translator/app.py` — Background update worker, manual/auto check logic.
- `src/zh_en_translator/ui/popup.py` — Source text is now editable with a Retranslate (↺) button and `Ctrl+Enter` shortcut.

---

## v2 Milestone 3 — Intelligence & Accessibility

**Scope**: Inline lookup, collapsible details, High Contrast.

**Delivered**:
- **Inline Lookup**: English words in translation are now clickable <a> tags that show a CC-CEDICT tooltip.
- **Collapsible Details**: Added "▼ Details" button to popup showing word-by-word pipeline breakdown.
- **High Contrast**: Added "High Contrast" palette to `themes.py`.

---

## v2 Milestone 2 — Sidebar History & Management

**Scope**: History storage, Sidebar list, Export/Clear.

**Delivered**:
- `src/zh_en_translator/engines/history.py` — JSON storage for last 20 translations.
- `src/zh_en_translator/ui/sidebar.py` — Added scrollable history list; clicking items restores them.
- **Actions**: "Export to CSV" and "Clear History" buttons added to sidebar.

---

## v1 Milestones (Summary)
*See historical sections in previous versions of this file for full details.*
- **M1-M4**: Core popup, local dictionary, and offline sentence translation.
- **M5-M6**: Sidebar "peek" mode and multi-engine OCR waterfall.
- **M7-M8**: Configuration system and Windows installer (setup.exe).
- **M9-M10**: OpenCC Traditional conversion, themes, and Azure Cloud support.

---

## Status at a glance (v3 Enhancements)

| Milestone | Status | Notes |
|---|---|---|
| M1 — Translation Quality | ✅ Done | jieba user dict, CC-CEDICT 120k, technical dictionary (40+ terms) |
| M2 — Tesseract Reliability | ✅ Done | UAC elevation fallback, warning UI, install log surfaced |
| M3 — Offline Bundling | ✅ Done | Tesseract + CC-CEDICT + Argos pre-bundled at build time |
| M4 — User Glossary | ✅ Done (partial) | CSV editor in Preferences, pipeline override; UI toggle/Cantonese/Pinyin deferred |
| M5 — Portable Distribution | ✅ Done | Standalone ZIP + network-free installer via bundling |
| Tech Debt | ✅ Done | pyperclip removed, segmentation regression tests, worker timeout+validation |

---

## v3 Milestone 1 — Translation Quality

**Scope**: Fix poor translation of compound phrases and domain-specific jargon.

**Delivered**:
- `src/zh_en_translator/resources/user_dict_technical.toml` — 40+ manufacturing/electronics terms.
- `src/zh_en_translator/resources/user_dict_technical.txt` — jieba-format user dictionary.
- `src/zh_en_translator/engines/segmentation.py` — `load_user_dict()` wired in; greedy-match cap raised 8→12 chars.
- `src/zh_en_translator/engines/dictionary.py` — `ensure_cedict()` wired into startup; full 120k CC-CEDICT auto-downloaded.
- `src/zh_en_translator/engines/pipeline.py` — greedy-match cap + glossary override hook.
- `tests/test_user_dict.py` — 12 passing tests (1 skipped for jieba in CI).

---

## v3 Milestone 2 — Tesseract Reliability

**Scope**: Make Tesseract OCR installation robust and diagnosable.

**Delivered**:
- `installer/install_tesseract.ps1` — Full logging to `%TEMP%\zh-en-translator-tesseract-install.log`; Attempt A (winget) → B (LocalAppData) → C (UAC elevated `C:\Program Files\`); post-install validation.
- `src/zh_en_translator/engines/ocr/tesseract_ocr.py` — Auto-probe known paths; set `pytesseract.tesseract_cmd` explicitly; set `TESSDATA_PREFIX`.
- `src/zh_en_translator/app.py` — `_check_tesseract_warning()`: tray balloon on startup if Tesseract missing.
- `src/zh_en_translator/ui/preferences.py` — Tesseract status + "Open Log" button in Lookup & OCR tab.

---

## v3 Milestone 3 — Offline Bundling

**Scope**: All critical models/data bundled in installer; zero network required after install.

**Delivered**:
- `installer/build.ps1` — Steps 2.5–2.7: download Tesseract portable, CC-CEDICT, and Argos zh→en model at build time into `installer/*-bundle/` dirs (gitignored).
- `installer/zh-en-translator.iss` — Bundle files included via `Check:` guards; Tesseract download task removed (always bundled); Argos download skipped if bundle present.
- `src/zh_en_translator/engines/ocr/tesseract_ocr.py` — Checks `{app}\tesseract\tesseract.exe` first in frozen builds.
- CC-CEDICT pre-populated to `%APPDATA%\zh-en-translator\` at install time.
- Argos pack pre-populated to `%APPDATA%\argos-translate\packages\` at install time.

---

## v3 Milestone 4 — User Glossary

**Scope**: Custom Chinese→English term pairs that override the translation pipeline.

**Delivered**:
- `src/zh_en_translator/engines/glossary.py` — `load_glossary()` / `save_glossary()` for `%APPDATA%\zh-en-translator\glossary.csv`.
- `src/zh_en_translator/engines/pipeline.py` — Glossary checked before dictionary lookup for exact token matches.
- `src/zh_en_translator/engines/translation_worker.py` — Loads glossary and passes to pipeline.
- `src/zh_en_translator/ui/preferences.py` — "Glossary" tab: table editor with Add/Remove/Import CSV/Export CSV.

**Deferred** (low priority):
- Traditional↔Simplified UI toggle (config flag exists, no UI switch)
- Cantonese support
- Pinyin romanization variants

---

## v3 Milestone 5 — Portable Distribution

**Scope**: Ship Tesseract bundled and provide a standalone portable ZIP.

**Delivered**:
- M5.1: Tesseract portable bundled in installer (see M3).
- M5.2: `installer/build.ps1` Step 5.1 — produces `installer/Output/zh-en-translator-portable.zip` after Inno Setup; includes app bundle + bundled Tesseract + README-PORTABLE.txt.
- M5.3: Network-free installer achieved via M3 bundling (all models pre-packaged).

**Build outputs** (run `.\installer\build.ps1` on Windows dev machine):
- `installer/Output/zh-en-translator-setup.exe` — Full installer (~350–400 MB)
- `installer/Output/zh-en-translator-portable.zip` — Portable ZIP (~80–120 MB)

---

## v3 Tech Debt

**Delivered**:
- `pyproject.toml` — Removed `pyperclip` dependency (fully replaced by QClipboard).
- `tests/test_segmentation.py` — 12 new regression tests for compound phrase segmentation; jieba-gated tests use `skipif`.
- `src/zh_en_translator/engines/translation_worker.py` — Argos call wrapped in 8s `ThreadPoolExecutor` timeout; `_is_valid_translation()` rejects empty/echo-back results; translation path logged for all engines.

---

## Status at a glance (v4 Completeness)

| Milestone | Status | Notes |
|---|---|---|
| M1 — Post-Processing Validation | ⏳ In Progress | Extract, detect, recover missing content |
| M2 — Clause-Level Fallback | 📅 Pending | Split, translate, recombine clauses |
| M3 — Adaptive Orchestration | 📅 Pending | Heuristic-based fallback decisions |

---

## v4 Milestone 1 — Post-Processing Validation & Recovery (IN PROGRESS)

**Objective:** After Argos translates, detect missing content and recover it using word-by-word dictionary.

**Deliverables** (planned):
1. ✅ Plan complete (via agent design)
2. ⏳ `src/zh_en_translator/engines/validation.py` (NEW) — Core validation logic
3. ⏳ `src/zh_en_translator/engines/translation_worker.py` (MODIFY) — Integrate validation
4. ⏳ `src/zh_en_translator/config.py` (MODIFY) — Feature flags
5. ⏳ `tests/test_validation.py` (NEW) — Comprehensive tests

**Expected outcome:** 1.2x speed, +30-50% completeness gain

---

## v4 Milestone 2 — Clause-Level Translation (PENDING)

**Objective:** Split complex Chinese into clauses, translate each, recombine intelligently.

**Deliverables** (planned):
1. `src/zh_en_translator/engines/argos.py` (ENHANCE) — Clause splitting + fallback
2. `src/zh_en_translator/engines/translation_worker.py` (MODIFY) — Conditional fallback
3. `tests/test_clause_translation.py` (NEW) — Clause splitting & recombination tests

**Expected outcome:** +20-30% additional gain (total 50-70%), 3-5x on complex sentences

---

## v4 Milestone 3 — Adaptive Orchestration (PENDING)

**Objective:** Use heuristics to decide validation-only (fast) vs. clause-level (thorough).

**Deliverables** (planned):
1. `src/zh_en_translator/engines/translation_worker.py` (REFACTOR) — Adaptive decision logic
2. Integration tests for fallback decisions

**Expected outcome:** 1.5x average speed, 50-70% completeness (final)
