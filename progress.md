# zh-en-translator — Progress Log

## Session: Tesseract / OCR Fix (2026-04-29)

### Root causes found and fixed across three sessions

#### Bug 1 — Tesseract installer flags were wrong (never installed silently)
The Tesseract OCR Windows installer (UB-Mannheim distribution) is built with
**NSIS**, not Inno Setup. All three scripts (`install_tesseract.ps1`,
`setup_elevated.ps1`, `build.ps1`) were passing Inno Setup flags:

```
/VERYSILENT /NORESTART /DIR="<path>"
```

NSIS ignores these flags entirely and shows its interactive UI. Correct NSIS
silent install syntax:

```
/S /D=<path>          # /D= must be the LAST argument, no quotes needed
```

All three scripts updated.

#### Bug 2 — Pinned fallback URL returned HTTP 404
`install_tesseract.ps1` and `setup_elevated.ps1` pinned:

```
https://github.com/UB-Mannheim/tesseract/releases/download/v5.5.0.20241111/...
```

UB-Mannheim never released 5.5.0 — that version lives under
`tesseract-ocr/tesseract`, not UB-Mannheim. Their latest release is 5.4.0.
Fixed to pinned 5.4.0:

```
https://github.com/UB-Mannheim/tesseract/releases/download/v5.4.0.20240606/tesseract-ocr-w64-setup-5.4.0.20240606.exe
```

#### Bug 3 — tessdata download URL returned HTTP 404
All scripts were downloading language model files from:

```
https://github.com/tesseract-ocr/tessdata_fast/releases/download/4.1.0/chi_sim.traineddata
```

The `tessdata_fast` release tag 4.1.0 contains only auto-generated source
archives (zip/tar.gz) — no `.traineddata` binary assets. Every download was
silently failing with 404.

The correct URL is `raw.githubusercontent.com`, which resolves Git LFS
automatically and serves the real model binary (~2-3 MB per file):

```
https://raw.githubusercontent.com/tesseract-ocr/tessdata_fast/main/chi_sim.traineddata
https://raw.githubusercontent.com/tesseract-ocr/tessdata_fast/main/chi_tra.traineddata
```

#### Bug 4 — `chi_sim+chi_tra` required both files; only chi_sim was downloaded
`tesseract_ocr.py` hardcoded `"chi_sim+chi_tra"` as the Tesseract language
string. Tesseract fails if either file is missing. Now queries
`pytesseract.get_languages()` at runtime and uses the best available
combination (`chi_sim+chi_tra` > `chi_sim` > `chi_tra`). Both files are
now downloaded by all installer scripts.

#### Bug 5 — OCR waterfall order was wrong
`engine.py` tried PaddleOCR first (heavy GPU library), then Windows OCR, then
Tesseract. Fixed to: Windows OCR (native) → Tesseract → PaddleOCR.

#### Bug 6 — `--scope user` on winget is unreliable
Both `UB-Mannheim.TesseractOCR` and `tesseract-ocr.tesseract` are NSIS
machine-scope packages. Neither declares user scope in their winget manifest.
The `--scope user` flag was removed from the winget call.

#### Bug 7 — PS1 encoding: em-dashes and missing BOM
`install_tesseract.ps1` had 8 em-dashes (`—`, UTF-8: `E2 80 94`) and no
UTF-8 BOM. PowerShell 5.1 without BOM reads as CP1252; the em-dash becomes a
right double-quote (`"`), corrupting parse state. `download_packs.ps1` had the
same issue with em-dashes and right-arrows (`→`). All four PS1 files now have
UTF-8 BOM and ASCII-only content.

#### Bug 8 — No Windows OCR language pack detection or install path
Preferences showed Tesseract status but never showed Windows OCR status.
Windows OCR is the primary engine but requires the Chinese language capability
(`Language.OCR~~~~~zh-Hans-CN~0.0.1.0`) to be installed via
`Add-WindowsCapability`. Added:
- Windows OCR status group in Preferences (API available / Chinese language
  installed)
- "Install Chinese OCR (requires admin)" button triggering `setup_elevated.ps1`
- `setup_elevated.ps1`: new consolidated elevated script covering Windows OCR
  capability + Tesseract Program Files install in a single UAC prompt
- Installer now calls `setup_elevated.ps1` via `ShellExec('runas')` once
  post-install instead of triggering multiple separate UAC prompts

### Files changed
- `src/zh_en_translator/engines/ocr/engine.py` — waterfall order
- `src/zh_en_translator/engines/ocr/tesseract_ocr.py` — runtime lang probe
- `src/zh_en_translator/engines/ocr/windows_ocr.py` — `ocr_status()`, `is_available()` now checks Chinese language
- `src/zh_en_translator/ui/preferences.py` — Windows OCR + Tesseract status UI with install buttons
- `installer/install_tesseract.ps1` — NSIS flags, correct URL, both traineddata files, BOM, ASCII-only
- `installer/setup_elevated.ps1` — new; consolidated UAC elevation for Windows OCR + Tesseract
- `installer/build.ps1` — NSIS flags for bundle install, correct tessdata URLs
- `installer/download_packs.ps1` — BOM, ASCII-only (em-dashes and arrows replaced)
- `installer/zh-en-translator.iss` — single ShellExec runas for OCR setup post-install

### Current OCR status
Priority waterfall (first successful result wins):
1. **Windows OCR** — native Windows API, no extra install if Chinese language pack present
2. **Tesseract** — bundled in installer or user-installed; now installs correctly with NSIS flags
3. **PaddleOCR** — GPU-accelerated, optional heavy dependency

Both Windows OCR and Tesseract paths are now fully wired with correct install
logic. A fresh install should work without any manual intervention.
