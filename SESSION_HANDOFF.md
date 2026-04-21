# Session Handoff — 2026-04-21

**Status: v3 COMPLETE** (M1–M5 all done, minus 3 deferred M4 items)

## What's Done (this session)
- M1 ✅ Translation quality: jieba user dict, CC-CEDICT, technical dictionary
- M2 ✅ Tesseract reliability: UAC fallback, warning UI, log surfacing
- M3 ✅ Offline bundling: Tesseract + CC-CEDICT + Argos pre-bundled in installer
- M4 ✅ User glossary: CSV editor in Preferences, pipeline override
- M5 ✅ Portable distribution: standalone ZIP + network-free installer

## Deferred (M4 partial — low priority)
- Traditional↔Simplified UI toggle (config flag exists, no UI switch yet)
- Cantonese support
- Pinyin romanization variants (Wade-Giles, tone options)

## To build a release
```bash
# On Windows dev machine:
.\installer\build.ps1
# Produces:
#   installer/Output/zh-en-translator-setup.exe   (full installer, ~350-400 MB)
#   installer/Output/zh-en-translator-portable.zip (portable ZIP, ~80-120 MB)
```

## Branch: main (all merged)
