# zh-en-translator Development Notes

## Critical: PowerShell Script Encoding Issue

### The Problem
Windows PowerShell 5.1 reads `.ps1` files **without a UTF-8 BOM using CP1252 encoding** (not UTF-8). This causes UTF-8 special characters to be misinterpreted:

- **em-dashes** (`—`, UTF-8: `0xE2 0x80 0x94`) are decoded as three CP1252 characters, where the third byte becomes `"` (RIGHT DOUBLE QUOTATION MARK)
- PowerShell 5.1 treats this `"` as a **string terminator**, breaking the parser state for the entire rest of the file
- The cascade of parse errors appears to start at random line numbers (not where the em-dash actually is)

**Example:** A line like:
```powershell
Write-Ok "tesseract-bundle already exists — skipping download"
```
Gets parsed as if it ended at the em-dash, leaving `skipping download"` as bare tokens, corrupting the entire file's parse state.

### Solution
**For any `.ps1` file in this repo:**
1. **Replace all Unicode special characters with ASCII equivalents:**
   - `—` (em-dash) → `--` (double hyphen)
   - `→` (right arrow) → `->` or appropriate ASCII
   - Avoid: smart quotes, em-dashes, copyright symbols, etc.

2. **Add UTF-8 BOM to the file** so PowerShell recognizes the encoding even if Unicode is reintroduced:
   - BOM bytes: `0xEF 0xBB 0xBF` at the start of the file
   - This forces PowerShell to read as UTF-8, not CP1252

3. **Ensure `.gitattributes` is correct:**
   ```
   # General rule FIRST
   * text=auto
   
   # Specific rules AFTER (they override)
   *.ps1 text eol=crlf
   *.bat text eol=crlf
   *.cmd text eol=crlf
   ```
   Order matters: last matching rule wins. General `text=auto` must come before specific rules.

### Testing
When editing `.ps1` files:
```powershell
# Syntax check without running
powershell -NoProfile -Command "&amp; { [System.Management.Automation.Language.Parser]::ParseFile('installer\build.ps1', [ref]$null, [ref]$null) }"
```

### Files Affected
- `installer/build.ps1` — Has UTF-8 BOM and ASCII-only special characters

### Why This Matters
This issue caused **4+ hours of debugging** with multiple false leads (line endings, git attributes, string syntax). The root cause was character encoding, not PowerShell syntax.

---

## Build System

### build.ps1
- Bundles PyInstaller output with Tesseract OCR, CC-CEDICT, and Argos translation model
- Compiles Inno Setup installer
- Creates portable ZIP archive
- **Requires:** Python 3.11, PyInstaller, Inno Setup 6, PowerShell 5.1+
- **Line endings:** CRLF (enforced by `.gitattributes`)
- **Encoding:** UTF-8 with BOM

### Key Steps
1. Step 0: Verify Python 3.11
2. Step 1: Verify PyInstaller
3. Step 1.5: Install dependencies (`pip install -e .`)
4. Step 2: Run PyInstaller → `dist/zh-en-translator/`
5. Step 2.5: Bundle Tesseract (~150 MB)
6. Step 2.6: Bundle CC-CEDICT (~6 MB)
7. Step 2.7: Bundle Argos zh→en model (~100 MB)
8. Step 3: Locate Inno Setup (`iscc.exe`)
9. Step 4: Compile installer → `installer/Output/zh-en-translator-setup.exe`
10. Step 5.1: Create portable ZIP → `installer/Output/zh-en-translator-portable.zip`

---

## Git Configuration

### .gitattributes
Ensures proper line ending handling across platforms:
- PowerShell/batch files: CRLF (Windows native)
- Everything else: LF in repo, native on checkout (`text=auto`)

### Notes
- The order of rules in `.gitattributes` matters: **last matching rule wins**
- Changes to `.gitattributes` only apply to new checkouts or after `git add --renormalize`

---

## v2 & v3 Milestones

See `plan-v2.md` and `plan-v3.md` for full roadmaps.

### v2 Complete (April 2026)
- DeepL support, Update Checker, Inline Source Editing, History persistence, etc.

### v3 Complete (April 2026)
- M1: Translation quality (jieba user dict, CC-CEDICT, technical dictionary)
- M2: Tesseract reliability (logging, path detection, validation)
- M3: Offline robustness (bundled Tesseract, CC-CEDICT, Argos model)
- M4: User glossary management (CSV editor, pipeline override)
- M5: Standalone portable ZIP build
