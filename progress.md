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
