# zh-en-translator — Developer Reference

## Critical: PowerShell Script Encoding

Windows PowerShell 5.1 reads `.ps1` files **without a UTF-8 BOM using CP1252 encoding**. UTF-8
em-dashes (`—`, bytes `0xE2 0x80 0x94`) decode to three CP1252 chars; the third becomes `"` (RIGHT
DOUBLE QUOTATION MARK), which PowerShell treats as a string terminator, corrupting the parse tree
for the rest of the file.

**Rules for any `.ps1` file in this repo:**
1. Use only ASCII: `—` → `--`, `→` → `->`, no smart quotes or copyright symbols.
2. Save with UTF-8 BOM (`0xEF 0xBB 0xBF`) so PowerShell forces UTF-8 decoding.
3. `.gitattributes` rule order matters — **general rules first, specific rules after** (last match wins):
   ```
   * text=auto
   *.ps1 text eol=crlf
   *.bat text eol=crlf
   *.cmd text eol=crlf
   ```

**Syntax check without running:**
```powershell
powershell -NoProfile -Command "& { [System.Management.Automation.Language.Parser]::ParseFile('installer\build.ps1', [ref]$null, [ref]$null) }"
```

Files that have the BOM and ASCII-only content: `installer/build.ps1`, `installer/install_tesseract.ps1`.

---

## Build System

Run on a Windows dev machine with Python 3.11, PyInstaller, and Inno Setup 6 installed:

```powershell
.\installer\build.ps1
```

Outputs:
- `installer/Output/zh-en-translator-setup.exe` — full installer (~350–400 MB, Tesseract + CC-CEDICT + Argos bundled)
- `installer/Output/zh-en-translator-portable.zip` — portable ZIP (~80–120 MB)

Build steps in order:
1. Verify Python 3.11 + PyInstaller
2. `pip install -e .`
3. PyInstaller → `dist/zh-en-translator/`
4. Bundle Tesseract portable (~150 MB) into `installer/tesseract-bundle/`
5. Bundle CC-CEDICT (~6 MB) into `installer/cedict-bundle/`
6. Bundle Argos zh→en model (~100 MB) into `installer/argos-bundle/`
7. Locate `iscc.exe` (Inno Setup compiler)
8. Compile installer → `installer/Output/zh-en-translator-setup.exe`
9. Create portable ZIP → `installer/Output/zh-en-translator-portable.zip`

Bundle dirs are gitignored — generated at build time, not committed.

---

## Project State

Everything through **Priority 4** is complete and on `main`.

| Layer | What shipped |
|---|---|
| v1 | Hotkey popup, CC-CEDICT, jieba, Argos MT, OCR, sidebar, preferences, installer, OpenCC, Azure opt-in |
| v2 | QClipboard, rotating logs, translation history (20 items + CSV export), inline word lookup, DeepL, update checker, inline source editing, high-contrast theme, Fluent-lite UI |
| v3 | jieba user dict, full CC-CEDICT auto-download, Tesseract reliability (UAC fallback, log, path probe), Tesseract + CC-CEDICT + Argos bundled in installer, user glossary CSV editor, portable ZIP |
| v4 | Clause-level translation fallback, adaptive orchestration (structural heuristics: length + clause count + token count). Note: post-processing validation was removed — it produced garbled output by appending raw dictionary glosses to good MT translations. |
| P1 | PKUSEG segmenter (`segmenter = "pkuseg"` in config), manufacturing glossary (149 terms, 13 categories) |
| P2 | SQLite multi-domain glossary backend (`glossary_db.py`), corpus framework (`corpus_manager.py`), A/B testing harness (`a_b_tester.py`), 100-sentence manufacturing corpus |
| P3 | Fine-tuning scaffold: config, data pipeline, evaluation — all implemented and tested (71 tests). `FineTuneTrainer.train()` **not yet implemented** (requires GPU). |
| P4 | Domain glossaries: Medical (504 terms), Legal (409), Electronics (452). Combined with Manufacturing: 1,514 terms across 4 domains. Domain priority order: user → manufacturing → medical → legal → electronics. |

---

## Outstanding Work

### Priority 3: GPU Fine-tuning (one method left)

**What:** Implement `FineTuneTrainer.train()` in `src/zh_en_translator/finetuning/trainer.py`.

Everything else is scaffolded and tested. This is the only unimplemented method.

**Requires:** GPU with 8+ GB VRAM (RTX 3090 or better), CUDA 11.8+.

**Quick start:**
```bash
pip install -e ".[finetuning]"          # installs opennmt-py, ctranslate2, sentencepiece, torch
python -c "import torch; print(torch.cuda.is_available())"  # verify GPU
pytest tests/test_finetuning_prep.py -v  # 71 tests, no GPU needed
```

**Corpus:** `src/zh_en_translator/corpus/examples/manufacturing_samples.jsonl` (100 sentences, 99 verified)

**Expected gain:** +4–8 BLEU on manufacturing domain (baseline ~0.23, target ~0.31)

**After training**, add config toggle `use_finetuned_model = true` and model selection in `argos.py`:
```python
model_path = finetuned_path if finetuned_path.exists() else base_path
```

Full implementation guide: `GPU_TRAINING_IMPLEMENTATION.md`  
Architecture design: `FINETUNING_PLAN.md`  
Prerequisites + quick-start: `FINETUNING_SETUP.md`

---

### Deferred v3 Items (Low Priority)

Infrastructure partially exists; no UI wired up:
- **Traditional↔Simplified UI toggle** — config flag `traditional_to_simplified` exists, no toggle in Preferences
- **Cantonese support** — needs Argos Cantonese model + jieba with Cantonese vocab
- **Pinyin romanization options** — Wade-Giles, tone variants (currently Hanyu Pinyin with tones only)

---

### Long-Term (Deliberate Decision Required)

- **Back-translation augmentation** — use fine-tuned model to generate 3–5× synthetic corpus pairs, then re-train for another +2–4 BLEU
- **Code signing** — requires purchasing a cert
- **Region-capture OCR** — drag-to-select on-screen translation (PowerToys-style)
- **Auto-update mechanism** — signed manifest check from configurable URL (off by default in v1)
- **Rust rewrite** — only if Python proves insufficient for idle CPU target (<0.5%)

---

## Architecture Quick Reference

### Tech Stack

| Layer | Choice |
|---|---|
| Language | Python 3.11 |
| UI | PyQt6 |
| Dictionary | CC-CEDICT + SQLite |
| Segmentation | jieba (default) / PKUSEG (`segmenter = "pkuseg"` in config) |
| Traditional→Simplified | OpenCC |
| Sentence MT | Argos Translate / ctranslate2 |
| MT enhancement | Clause-level splitting + adaptive orchestration |
| OCR | Windows.Media.Ocr → Tesseract → PaddleOCR (waterfall) |
| Hotkeys | pynput / Win32 low-level hook |
| Packaging | PyInstaller → Inno Setup (installer) + portable ZIP |
| Config | TOML at `%APPDATA%\zh-en-translator\config.toml` |

### Key Files

```
src/zh_en_translator/
├── app.py                      ← entry point, tray, background update checker
├── config.py                   ← config loader; keys: segmenter, clause_fallback_enabled
├── engines/
│   ├── argos.py                ← sentence MT, split_into_clauses(), translate_with_clause_fallback()
│   ├── translation_worker.py   ← pipeline orchestration, _should_use_clause_fallback()
│   ├── dictionary.py           ← CC-CEDICT + SQLite, ensure_cedict()
│   ├── segmentation.py         ← jieba + PKUSEG wrapper, load_user_dict()
│   ├── glossary.py             ← TOML glossary loader (user + domain)
│   ├── glossary_db.py          ← SQLite multi-domain glossary backend
│   ├── pipeline.py             ← glossary → dict → MT pipeline
│   ├── history.py              ← last 20 translations, JSON storage
│   ├── deepl.py                ← DeepL API (opt-in)
│   ├── updates.py              ← GitHub releases version check
│   └── ocr/
│       ├── windows_ocr.py
│       ├── tesseract_ocr.py    ← bundled path detection, TESSDATA_PREFIX
│       └── paddle_ocr.py
├── ui/
│   ├── popup.py                ← frameless popup, editable source, Retranslate button
│   ├── sidebar.py              ← peek-tab, history list, export/clear
│   ├── preferences.py          ← settings dialog (glossary tab, Tesseract status, DeepL)
│   └── themes.py               ← system / dark / light / sepia / high-contrast
├── finetuning/                 ← Priority 3 GPU training
│   ├── config.py               (implemented)
│   ├── data_preparation.py     (implemented)
│   ├── evaluation.py           (implemented)
│   └── trainer.py              (scaffold — train() needs GPU implementation)
├── corpus/
│   ├── corpus_manager.py
│   └── examples/manufacturing_samples.jsonl   ← 100 sentences, 99 verified
├── evaluation/
│   ├── metrics.py
│   └── a_b_tester.py
└── resources/
    ├── glossary_manufacturing.toml   ← 149 terms, 13 categories
    ├── glossary_medical.toml         ← 504 terms
    ├── glossary_legal.toml           ← 409 terms
    ├── glossary_electronics.toml     ← 452 terms
    └── user_dict_technical.toml      ← 40+ terms for jieba

installer/
├── build.ps1                   ← UTF-8 BOM + ASCII-only (see encoding note above)
├── zh-en-translator.iss
└── install_tesseract.ps1       ← UAC fallback, logging to %TEMP%
```

### Translation Pipeline (runtime order)

1. User glossary exact match → use glossary translation (highest precedence)
2. Domain glossaries (manufacturing → medical → legal → electronics)
3. CC-CEDICT dictionary lookup + jieba segmentation
4. Argos MT (with adaptive clause-level fallback for complex sentences)
5. DeepL / Azure as opt-in overrides

---

## A/B Test Baselines (2026-04-24)

30 manufacturing sentences, jieba segmenter:

| Config | CER | Glossary Coverage |
|--------|-----|-------------------|
| No glossary | 0.849 | 0.5% |
| Manufacturing glossary (149 terms) | 0.757 | 2.2% |

BLEU is 0.000 in the test harness (stub translation engine). With live Argos + CC-CEDICT, expected baseline BLEU ~0.23–0.35. Priority 3 GPU fine-tuning targets BLEU ~0.31–0.43.

Full results: `ab_test_results.md`, `ab_multi_domain_results.md`
