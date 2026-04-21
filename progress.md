# Progress Tracker

Running log of what has been built, what deviated from the plan, and what still
needs verification. Update this file at the end of every milestone.

Source of truth for plan/scope: `PLAN.md` and `plan-v2.md`.

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
