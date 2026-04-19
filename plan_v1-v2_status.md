# Project Status: zh-en-translator (v1 & v2)

This document summarizes the completion status of the primary plan (v1) and the enhancement plan (v2) as of April 19, 2026.

## 🟢 v1 Primary Plan: Completed (10/10)
The core goal of a lightweight, offline-first Chinese → English popup translator is fully realized.

1.  **M1: Hello Popup** — Global hotkey, clipboard capture, frameless popup.
2.  **M2: Dictionary Lookup** — CC-CEDICT integration, jieba segmentation.
3.  **M3: Replace + Lookup** — Paste-back functionality, external dictionary links.
4.  **M4: Sentence Translation** — Offline neural MT via Argos Translate & ctranslate2.
5.  **M5: Sidebar Mode** — Dockable, animated "peek-tab" for persistent use.
6.  **M6: OCR** — Image-to-text via Windows OCR, Tesseract, or PaddleOCR.
7.  **M7: Preferences** — TOML-backed settings for fonts, hotkeys, and UI colors.
8.  **M8: Packaging** — Single-file Windows installer (`setup.exe`) with model downloader.
9.  **M9: A11y & Traditional** — OpenCC conversion, accessibility tree, and themes.
10. **M10: MS Cloud** — Opt-in Azure Translator support with privacy safeguards.

## 🔵 v2 Enhancement Plan: Completed (4/4)
Advanced features and maintenance hooks added in April 2026.

1.  **M1: Robustness** — Switched to `QClipboard`, added rotating logs, and loading animations.
2.  **M2: Sidebar History** — Persistence for the last 20 translations with CSV export capability.
3.  **M3: Intelligence** — Inline word-level lookup in translations and collapsible breakdown details.
4.  **M4: integrations** — DeepL engine support, GitHub update checker, and inline source editing.
5.  **UI Refresh** — Modernized look with Windows 11 fonts (Segoe UI Variable/Aptos) and pill buttons.

## 🚀 Future Roadmap (v3 Proposals)
- **Rust Core**: Rewrite performance-sensitive paths (hotkey, lookup) in Rust for minimal idle footprint.
- **History Sync**: Optional encrypted sync for translation history across multiple machines.
- **Advanced OCR**: Region-capture (drag-to-select) OCR mode similar to PowerToys Text Extractor.
- **DeepL Pro**: Add support for document-level translation and glossary features.

---
**Last Updated:** 2026-04-19
**Status:** All planned milestones for v1 and v2 are **VERIFIED**.
