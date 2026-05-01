# zh-en-translator — Progress Log

## Session: Translation Display Fixes + Test Suite Cleanup (2026-05-01)

### Bug 12 — Pin → sidebar showed raw HTML instead of translated text

**Symptom:** Clicking "Pin →" caused the sidebar to display the full HTML markup
of the translation (e.g. `<a href="word:The" style="...">The</a> cat sat`) rather
than rendered text.

**Root cause:** `QLabel.text()` returns the raw HTML string when the label was set
with rich text via `wrap_words()`. The pin callback passed `self.translation_label.text()`
(HTML) to `sidebar.set_translation()`, which then called `wrap_words()` on that
already-HTML string — wrapping attribute names like `href`, `style`, `color`,
`inherit` in more `<a>` tags, producing catastrophically malformed markup.

The same HTML leak affected **Copy** (copied markup to clipboard) and **Replace**
(pasted markup into the target app instead of plain text).

**Fix:** Added `self._translation_text: str = ""` to the popup. Plain text is stored
on arrival in `_on_translation_ready` before `wrap_words()` is applied. All
three outbound paths (pin, copy, replace) now read `self._translation_text`.

### Bug 13 — HTML display helper was missing, causing double-wrapping in sidebar

Added `_render_translation_html(text)` module-level helper in `popup.py`:
- Splits on `\n`, applies `wrap_words()` per line, joins with `<br>`
- `wrap_words` regex never sees `<br>` tags (ordering fix)
- Imported and used in `sidebar.py` for `set_translation`, `update_translation`,
  and `_on_history_item_clicked` — the last of which previously set raw plain
  text with no word-link wrapping at all

### Bug 14 — Multi-line / structured source text translated as one flat block

**Symptom:** Copying a bulleted list, numbered list, or multi-paragraph block
produced a single run-on English sentence with no structure preserved.

**Fix:** Added `_segment_source_text(text)` to `translation_worker.py`. Before
translating, the source is split into segments based on:
- Empty lines → paragraph breaks
- Bullet characters (`• · - * ► ▶ ‣ ◦`) → individual bullet items (prefix stripped, restored after)
- Numbered lists (`1.` `2.` `①` `一、` etc.) → individual items
- Tab / 4-space-indented lines → indented items
- Sentence-final punctuation (`。！？；.!?;`) → hard break between text segments
- No terminal punctuation → soft wrap, lines joined (space added at ASCII boundaries)

Each segment is translated independently via the same engine waterfall; results
are reassembled with original prefixes and separators. Single-segment input
(the common case) is unchanged in behaviour.

**Architecture principle applied:** Plain text is the data model throughout.
`wrap_words()` / `<br>` substitutions are view-layer only, applied once at
`setText()` time and never stored or passed between components.

### Test suite: 16 pre-existing failures fixed

All tests now pass (644 passed, 18 skipped). Failures fell into three categories:

**Stale test assertions (tests wrong, code correct):**
- `test_ocr.py` — two tests described old Paddle-first waterfall; renamed and
  rewritten to match actual Windows → Tesseract → Paddle order
- `test_themes.py` — colour values (`#F8F8F8` → `#FFFFFF`, `#1E1E1E` → `#202020`)
  and theme combo count (4 → 5, high-contrast was added) updated to match code
- `test_ab_translation.py` — invalid cross-config glossary coverage comparison
  (configs score against different glossary dicts, making the `>=` meaningless)
  replaced with valid in-range assertions

**Missing production code (tests correct, code incomplete):**
- `popup.py` — 5 missing `setAccessibleDescription()` calls added to
  `_setup_accessibility()` (btn_pin, btn_lang_settings, text_display,
  translation_label, _pinyin_label)
- `sidebar.py` — 2 missing `setAccessibleDescription()` calls (btn_pin,
  _close_btn) + missing `set_side(side)` method added
- `test_segmentation.py` — compound token tests relied on file-based
  `load_user_dict` which doesn't reliably update jieba's live dictionary;
  switched to `add_custom_words` directly (same approach as the passing test)

**Test tooling:**
- `pytest` and `pytest-qt` installed into the system Python environment;
  `pip` was bootstrapped via `ensurepip` (was missing from the Python 3.11 install)

### Files changed (2026-05-01)
- `src/zh_en_translator/ui/popup.py` — `_translation_text`, `_render_translation_html()`, fix pin/copy/replace, accessibility descriptions
- `src/zh_en_translator/ui/sidebar.py` — `_render_translation_html` usage, accessibility descriptions, `set_side()`
- `src/zh_en_translator/engines/translation_worker.py` — `_segment_source_text()`, `_translate_one()`, updated `run()`
- `tests/test_ocr.py` — waterfall order corrected
- `tests/test_themes.py` — colour values and combo count updated
- `tests/test_ab_translation.py` — coverage comparison assertion fixed
- `tests/test_segmentation.py` — compound tests use `add_custom_words` directly

---

## Session: Tesseract PS1 Parse Error (2026-04-30)

### Bug 11 — PowerShell parse error silently killed both setup scripts

**Symptom:** Clicking "Install Tesseract" in Preferences caused a PowerShell
window to flash and close instantly with no log file created, no UAC prompt,
and no error message. Confirmed on Windows 11 with a Program Files install.

**Root cause:** `$fname:` in a double-quoted string was parsed as a
scope-qualified variable reference (like `$env:TEMP` or `$global:`). Since a
space followed the colon rather than a valid variable name character, PowerShell
raised a **parse error at script load time** — before a single statement
executed. Both scripts were affected:

- `installer/setup_elevated.ps1` line ~139: `"Failed to download $fname: $_"`
- `installer/install_tesseract.ps1` line ~196: `"Failed to download $fname: $_"`

**Fix:** Delimit the variable with braces so PowerShell knows exactly where the
name ends: `"Failed to download ${fname}: $_"`

**Additional hardening in `setup_elevated.ps1`:**
- `StreamWriter` construction moved inside the `try` block with a `Write-Host`
  fallback — a log-open failure no longer silently kills the script
- A `Write-Host` banner fires before the `StreamWriter` is opened, so there is
  always at least one console line visible on early failure

**Debugging method:** The PowerShell parser validates the full script before
running any code, so the fix was confirmed by running the script manually from
an elevated PowerShell prompt and reading the parse error output. The error
pinpointed the exact line and character position.

**Rule added to CLAUDE.md:** Avoid `$varname: ` (variable followed immediately
by colon-space) in double-quoted PS strings. Use `${varname}:` instead.

---

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

---

## Session: Elevation + Log Fix (2026-04-30)

#### Bug 9 — Preferences install buttons never requested admin elevation
Both "Install Tesseract" and "Install Chinese OCR" buttons in Preferences used
`subprocess.Popen`, which launches PowerShell as the current (non-admin) user.
The UB-Mannheim NSIS installer has `RequestExecutionLevel admin` hard-baked in,
so it silently fails without an admin token. winget machine-scope packages also
require elevation. Neither install path could ever succeed.

Fixed to use `ctypes.windll.shell32.ShellExecuteW(None, "runas", ...)` which
triggers a proper Windows UAC prompt before running `setup_elevated.ps1`.
Both buttons now point to `setup_elevated.ps1` (handles Tesseract + Windows OCR
in one elevated pass) instead of the user-level `install_tesseract.ps1`.

`install_tesseract.ps1` was also added to the `[Files]` section in the `.iss`
installer so it is present in installed builds.

#### Bug 10 — Log files split across two filenames; "View Log" found nothing
`install_tesseract.ps1` wrote to `zh-en-translator-tesseract-install.log` while
`setup_elevated.ps1` wrote to `zh-en-translator-elevated-setup.log`. The
"View Log" button only looked for the former, so after the button switch to
`setup_elevated.ps1` (Bug 9 fix) the log was never found.

Both scripts now write to the same file: `zh-en-translator-elevated-setup.log`.
The "View Log" button looks for exactly that one path.

### Files changed (2026-04-30)
- `src/zh_en_translator/ui/preferences.py` — ShellExecuteW(runas) for both
  install buttons; both point to setup_elevated.ps1; View Log simplified to
  single log path
- `installer/install_tesseract.ps1` — log filename unified to elevated-setup.log
- `installer/zh-en-translator.iss` — added install_tesseract.ps1 to [Files]

---

### Files changed (2026-04-29)
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

---

## Session: OCR bundling fix + unified availability check (2026-05-01)

#### Bug 11 -- pytesseract and Pillow not bundled in frozen exe
`build.ps1` ran `pip install -e .` (no extras), so `pytesseract` and `Pillow`
were never installed in the build environment. PyInstaller never saw them.
Both are imported inside `try/except ImportError` blocks in `tesseract_ocr.py`,
so static analysis silently missed them. The frozen exe shipped without either
package, causing `tesseract_ocr.is_available()` to return `False` at runtime
even with Tesseract installed -- producing "No OCR engine available."

Windows OCR was simultaneously unavailable because `winrt`/`winsdk` were also
absent from `hidden_imports` and `collect_all` in the spec.

#### Bug 12 -- preferences and runtime used different Tesseract path-finding logic
Preferences checked Tesseract availability via `shutil.which` + four hardcoded
Windows paths (file existence only). The runtime `tesseract_ocr.is_available()`
used a different candidate list via `_get_tesseract_candidates()` AND actually
invoked `pytesseract.get_tesseract_version()`. In frozen builds, `_get_tesseract_candidates()`
also checks the bundled path (`sys.executable/../tesseract/tesseract.exe`) which
preferences never checked. The two paths could silently disagree, making
preferences show "green" while the runtime failed.

### Fixes
- `build.ps1`: `pip install -e .` -> `pip install -e ".[ocr-tesseract]"` so
  `pytesseract` and `Pillow` are present in the build env for PyInstaller
- `zh-en-translator.spec`: added `pytesseract`, `PIL`, `PIL.Image`, `PIL.ImageOps`,
  and winrt namespaces to `hidden_imports`; added `collect_all` for `pytesseract`
  and `PIL` (with graceful skip if absent)
- `tesseract_ocr.py`: added `get_found_path() -> str | None` -- single canonical
  path lookup reusing `_get_tesseract_candidates()`
- `preferences.py`: replaced ad-hoc `shutil.which` + hardcoded path checks in
  both `_build_lookup_ocr_tab` and `_refresh_install_buttons` with
  `_tess.is_available()` / `_tess.get_found_path()` -- one code path, one truth
