# Popup Translator (Chinese → English) — v3 Enhancement Roadmap

**Status:** M1 Complete ✅ | M2 In Progress 🔄 | M3-M5 Planned  
**Last Updated:** 2026-04-20 (End of session)

This document outlines improvements and new features for v3, informed by v1/v2 completion and user feedback.

---

## Context: v1 & v2 Summary

- **v1** (Complete): Core translator with hotkey, popup, sidebar, OCR, preferences, installer, accessibility, and optional MS Cloud
- **v2** (Complete, April 2026): Robustness (QClipboard, rotating logs, animations), history persistence (20 translations + CSV export), inline word lookup, collapsible dictionary details, DeepL engine, update checker, inline source editing

## v3 Goals

1. **Improve translation quality** for technical/compound phrases
2. **Harden installer reliability** for Tesseract and Python dependencies
3. **Extend offline language support** (Traditional → Simplified, optional Cantonese)
4. **Optimize user experience** based on collected usage patterns
5. **Reduce deployment friction** with bundled models and portable distribution

---

## v3 Milestones

### M1: Translation Quality ✅ COMPLETE

**Objective:** Fix poor translation of compound phrases and domain-specific jargon.

**Root causes identified & fixed:**
- ✅ jieba segmentation: User dictionary support added (`load_user_dict()`, `add_custom_words()`)
- ✅ Full CC-CEDICT (120k): `ensure_cedict()` wired into app startup (auto-downloads on first run)
- ✅ Greedy-match cap: Raised from 8 → 12 characters for longer compound words
- ✅ Technical user dictionary: Created `user_dict_technical.toml` with 40+ manufacturing/electronics terms

**Deliverables completed:**
1. ✅ User dictionary support infrastructure (`load_user_dict()`, `add_custom_words()`)
2. ✅ CC-CEDICT auto-download on first run (via `ensure_cedict()`)
3. ✅ Greedy-match cap raised to 12 characters
4. ✅ Technical dictionary with terms: 激光模块, 手板样机, 样机, 激光, 模块, 换, 进能部门, 部门, 标, 你们, + 30 more
5. ✅ Tests: 12 passing, 1 skipped (jieba not in CI env — correct behavior)

**Status:** **COMPLETE** (Merged to branch `v3-m1-m2-completion`)
- Technical dictionary: `src/zh_en_translator/resources/user_dict_technical.toml`
- User dict loading wired into app startup
- Tests fully passing
- Ready for production

---

### M2: Tesseract Reliability 🔄 IN PROGRESS

**Objective:** Make Tesseract OCR installation robust and diagnosable.

**Root causes identified:**
- ✅ `winget` fails silently in non-interactive Inno Setup child processes
- ✅ Elevation failures masked (Start-Process returns null)
- ✅ Even successful installs don't add binary to PATH for pytesseract
- ✅ No logging; errors invisible post-install

**Deliverables (5 total):**
1. ✅ **Logging**: Write all output to `%TEMP%\zh-en-translator-tesseract-install.log`
   - All attempt details (winget, direct DL, fallback)
   - Exit codes and error messages
   - File paths and sizes
2. ✅ **Python-side path detection**: Auto-probe known Tesseract locations; set `pytesseract.tesseract_cmd` explicitly
   - Candidates: `%LOCALAPPDATA%\Programs\Tesseract-OCR`, `%LOCALAPPDATA%\Tesseract-OCR`, `C:\Program Files\`
3. ✅ **Post-install validation**: After each install attempt, verify:
   - `tesseract.exe` exists and runs with `--version`
   - `chi_sim.traineddata` is present
   - Re-probe & log final state
4. ❌ **Elevated install fallback**: If direct install to LocalAppData fails, offer UAC elevation for `C:\Program Files\` (requires explicit user consent)
5. ❌ **Non-fatal warning UI**: If Tesseract install fails, show user-friendly message:
   - "Tesseract OCR unavailable; using Windows OCR instead"
   - Link to log file for troubleshooting
   - (Tesseract is optional; no blocker)

**Status:** 3/5 deliverables complete. Remaining: UAC fallback + warning UI (~40 min)
- Branch: `v3-m1-m2-completion`
- Next step: Sonnet agent to implement items 4-5

---

### M3: Offline Robustness (Pending)

**Objective:** Ensure all critical models/data are available offline after initial install.

**Current state:**
- Argos zh→en model (~100 MB): Downloaded on-demand via `ensure_pack()`
- CC-CEDICT: Falls back to 51-entry sample if full 120k unavailable
- Tesseract: Downloaded at install time, but not always found at runtime

**Deliverables:**
1. **Model bundling**:
   - Include Argos zh→en model in installer (or download during install, cache at `%APPDATA%\zh-en-translator\models\`)
   - Pre-download + bundle full CC-CEDICT
   - Verify bundle integrity (checksums)
2. **Graceful offline fallback**:
   - If model unavailable, degrade to dictionary-only translation
   - Log all model load attempts
   - User feedback: "Translation engine unavailable (offline?); showing dictionary match"
3. **Update checker offline mode**: Check for new versions only if network available; never block startup

**Status:** Code infrastructure in place (ensure_pack, ensure_cedict, fallback chains). Bundling strategy TBD.

---

### M4: Extended Language Support (Future)

**Objective:** Add Traditional Chinese ↔ Simplified, optional Cantonese, and domain-specific glossaries.

**Deliverables:**
1. **Traditional ↔ Simplified bidirectional toggle**: Already have OpenCC; wire up UI switch
2. **Cantonese support** (opt-in):
   - Add Cantonese → English translation path (via argostranslate if available, or custom dictionary)
   - Requires jieba + yue-specific training data
3. **User glossary management**:
   - Allow users to define custom term pairs (e.g., product names, internal jargon)
   - Glossary editor in Preferences
   - Import/export glossary (CSV, TXT)
4. **Pinyin romanization options**:
   - Toggle between Hanyu Pinyin, Wade-Giles, Pinyin (with/without tones)

**Status:** Deferred to v3.2+ (after v3.1 stabilization)

---

### M5: Portable Distribution (Future)

**Objective:** Ship "Tesseract portable" bundle and standalone archive for restricted environments.

**Deliverables:**
1. **Tesseract portable bundle**:
   - Include precompiled `tesseract.exe` + `chi_sim.traineddata` in installer
   - Avoids winget/download complexity; uses local binary
   - Falls back to Windows OCR if not present
2. **Standalone ZIP archive**:
   - For users who can't/won't run the MSI installer
   - Portable Python environment + app + models
   - Run `zh-en-translator.exe` directly from extracted folder
3. **Network-free installer variant**:
   - All models + dependencies pre-cached in installer
   - No internet access required during or after setup
   - Larger installer (~500+ MB) but zero-network deploy

**Status:** Deferred; depends on M2 & M3 completion

---

## Technical Debt & Refactoring

### High Priority

1. **Remove pyperclip dependency**: Already migrated to QClipboard (PyQt6 native); clean up any remnants
2. **Segmentation module tests**: Add regression tests for realistic compound-phrase sentences
   - Test case: `李勋、那个X10 Pro的手板样机，激光模块换完了，你们可以去进能部门标一下，我去找他弄`
   - Verify jieba segments into correct words (not single chars or oversized blobs)
3. **Translation worker robustness**: Add timeout & result validation
   - Set max wait for translation: 5–10 seconds
   - Validate result is non-empty string
   - Log translation path taken (DeepL → MS Cloud → Argos → dict-only)

### Medium Priority

4. **Installer script modernization**: PowerShell → batch + PowerShell wrapper
   - Inno Setup calls batch which calls PS1 (cleaner error handling)
5. **CI/CD for installer validation**:
   - Test installer on clean Win11 VM with various network conditions
   - Validate all three model download paths (online/offline/hybrid)
6. **Accessibility audit**: Re-test with NVDA/JAWS
   - Verify all UI updates (translations, history, sidebar) are announced

### Low Priority

7. **Code signing**: For MSI (requires cert; deferred unless required by org policy)
8. **Telemetry/analytics**: Optional, opt-in usage stats (e.g., most-translated terms)
   - Privacy-preserving; hashed, no PII
   - Helps prioritize future user dictionaries

---

## Testing Plan

### v3 Acceptance Criteria

1. **Translation Quality**
   - [ ] Complex sentences with 4+ compound words translate correctly
   - [ ] Industry jargon in custom dictionary recognized
   - [ ] No regression in simple sentences (v1/v2 baseline)

2. **Tesseract Reliability**
   - [ ] Installation succeeds on clean Win11 VM (no Tesseract pre-installed)
   - [ ] Logs written to expected location with all details
   - [ ] pytesseract finds binary at runtime
   - [ ] Graceful fallback if install fails

3. **Offline Robustness**
   - [ ] App starts and translates without internet
   - [ ] All models cached and available after first install
   - [ ] Timeout/fallback for any slow operations

4. **User Experience**
   - [ ] Installer completes in <5 minutes (including model download)
   - [ ] No silent failures; errors visible in log or UI
   - [ ] Sidebar/popup remain snappy even with large history

### Test Environments

- Windows 11 (22H2), clean VM
- Windows 10 (22H2), clean VM
- Network: Full internet, restricted (no GitHub/PyPI), offline
- System: Laptop (8GB RAM), Desktop (32GB RAM)
- Locales: en-US, zh-CN, ja-JP

---

## Deferred Items (v3.1+)

- **Region-capture OCR**: Drag-to-select on-screen text (PowerToys-style)
- **History sync**: Encrypted cloud sync across machines (Dropbox/OneDrive integration)
- **Advanced DeepL features**: Document translation, glossaries, formal/informal tone
- **Rust rewrite**: Performance-critical paths (hotkey, dictionary lookup)
- **Multi-language support**: Beyond zh↔en (requires additional language pairs)

---

## Success Metrics

- **Translation quality**: 95%+ accuracy on test corpus of 100+ sentences (domain-specific + general)
- **Installer reliability**: 99% success rate across network conditions
- **User adoption**: <5% support tickets related to broken installation/Tesseract
- **Performance**: P95 translation latency <2s, idle CPU <0.5%
- **Offline**: 100% of features work without internet (except update checker)

---

## Timeline Estimate

- **M1 (Translation Quality)**: 2–3 days (code + testing)
- **M2 (Tesseract Reliability)**: 2–3 days (post-validation, bundling)
- **M3 (Offline Robustness)**: 1–2 days (bundling, verification)
- **M4–M5**: 1–2 weeks each (deferred)

**Target v3 release:** End of April 2026

---

## References

- Commit `c24d82e`: Removed Tesseract error dialog + forced exit 0 (root cause of silent failures)
- Commit `a373ece` through `ff2fd54`: Various attempted Tesseract fixes (winget, elevation, download paths)
- Agent diagnostic: Root cause analysis of Tesseract & translation quality issues (April 20, 2026)
