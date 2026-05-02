# Windows 11 Manual Test Plan — zh-en-translator M1–M7

Branch: `claude/debug-windows-setup-pWclA`  
Last updated: covering commits through `906b37b` (M7)

This document is self-contained. Follow it top to bottom. Each section lists
preconditions, steps, and expected results. Mark each item `[x]` as you go.

---

## 0. Setup

### 0.1 Prerequisites
- [ ] Python 3.11 or 3.12 installed and on PATH (`python --version`)
- [ ] Git installed (`git --version`)
- [ ] Repo cloned: `git clone <repo-url> zh-en-translation`
- [ ] Branch checked out: `git checkout claude/debug-windows-setup-pWclA`

### 0.2 Install
```powershell
cd zh-en-translation
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
```
- [ ] `pip install` completes without error
- [ ] `pytest` runs and all tests pass:
  ```powershell
  pytest
  ```
  Expected: **119 passed** (or more if new tests added)

### 0.3 First launch
```powershell
zh-en-translator
```
- [ ] No traceback printed to console
- [ ] Blue square icon appears in the system tray (bottom-right near clock)
- [ ] Right-clicking tray icon shows a context menu

---

## 1. M1 — Hello Popup (tray, hotkey, capture, popup)

**Precondition**: App is running. No text selected anywhere.

### 1.1 Hotkey with no selection
- [ ] Press `Ctrl+Shift+T` with nothing selected → no popup appears, no crash

### 1.2 Basic popup trigger
- [ ] Open Notepad, type `Hello world`, select it
- [ ] Press `Ctrl+Shift+T`
- [ ] Popup appears near the cursor with title **"Captured Text"**
- [ ] The selected text is visible in the popup text area
- [ ] No crash, no traceback in console

### 1.3 Dismiss behaviours
With a popup open:
- [ ] Press `Esc` → popup closes
- [ ] Trigger again → click somewhere outside the popup → closes
- [ ] Trigger again → `Alt+Tab` to another window → popup closes
- [ ] After each close: clipboard still contains the original text (not mangled)

### 1.4 Cursor-edge positioning
- [ ] Select text in Notepad while the Notepad window is in the top-left corner of the screen → popup stays fully on-screen (does not go off the top or left edge)
- [ ] Move Notepad to the bottom-right corner → same test → popup flips to appear above/left of cursor, still fully on-screen
- [ ] Drag Notepad to each screen edge and repeat

### 1.5 Tray menu
- [ ] Right-click tray → **Translate Selection** with text selected → popup opens (same as hotkey)
- [ ] Right-click tray → **Pause** → hotkey does nothing → **Resume** → hotkey works again
- [ ] Pause label toggles to "Resume" when paused and back to "Pause" when resumed

### 1.6 Multi-monitor (if applicable)
- [ ] Move Notepad to the second monitor, select text, press hotkey → popup appears on the second monitor near the cursor (not on the primary monitor)

---

## 2. M2 — Dictionary Lookup (word-by-word, pinyin)

**Precondition**: App running. Dictionary built on first run (automatic).

### 2.1 Known Chinese phrase
- [ ] In Notepad type `你好世界`, select it, press hotkey
- [ ] Popup title is **"Translation"**
- [ ] Word table shows at minimum:
  - Row: `你好` | `nǐ hǎo` | `hello; hi`
  - Row: `世界` | `shì jiè` | `world`
- [ ] Pinyin uses proper tone marks (ǐ ǎ ì è) — not numbers

### 2.2 Unknown Chinese characters
- [ ] In Notepad type `龘龖`, select it, press hotkey
- [ ] Unknown tokens appear with **pale yellow background** in the English column
- [ ] English column shows "unknown" for those rows
- [ ] Rows are still selectable/copyable

### 2.3 Mixed Chinese / non-Chinese
- [ ] Select `Hello 你好 world` → popup shows table; non-Chinese tokens have empty pinyin/English
- [ ] No crash on mixed content

### 2.4 Pinyin tone marks
Verify each tone renders correctly in the system font:
- [ ] Tone 1: ā ē ī ō ū (macron)
- [ ] Tone 2: á é í ó ú (acute)
- [ ] Tone 3: ǎ ě ǐ ǒ ǚ (caron; check ǚ specifically for ü)
- [ ] Tone 4: à è ì ò ù (grave)
- [ ] Tone 5 / neutral: no mark

### 2.5 DPI scaling
- [ ] Set Windows display scaling to 125% or 150% (Settings → Display)
- [ ] Repeat test 2.1 → table columns are readable, no text clipping, no overlapping

### 2.6 Rebuild Dictionary
- [ ] Right-click tray → **Rebuild Dictionary** → no crash, "Dictionary rebuilt successfully" printed to console

---

## 3. M3 — Replace + External Lookup

**Precondition**: App running with dictionary.

### 3.1 Replace in Notepad
- [ ] In Notepad, type `你好`, select it
- [ ] Press hotkey → popup opens with word table
- [ ] Click **Replace** → popup closes, `你好` in Notepad is replaced with the English gloss (e.g. `hello; hi`)
- [ ] Clipboard is restored to what it was before the hotkey

### 3.2 Replace in a browser address bar
- [ ] Click a browser address bar, type some Chinese text, select it, press hotkey
- [ ] Click **Replace** → text is replaced in the address bar

### 3.3 Replace in a Save As dialog filename field
- [ ] Open a Save As dialog in any app, type Chinese in the filename field, select it, press hotkey
- [ ] Click **Replace** → text replaced in filename field

### 3.4 Copy translation
- [ ] Select `你好`, press hotkey
- [ ] Click **Copy translation** → a **"Copied!"** label appears briefly (≈2 seconds) then disappears
- [ ] Paste elsewhere (`Ctrl+V` in Notepad) → confirms the translation string was copied
- [ ] Popup remains open after Copy (does not close)

### 3.5 Unknown token selection + external lookup
- [ ] Select some Chinese text that contains unknown characters (pale yellow row)
- [ ] Click the unknown row in the table → label **"Unknown: <token>"** appears above the buttons
- [ ] Click **Look up externally** → default browser opens to `https://www.mdbg.net/chinese/dictionary?wdqb=<token>` (the selected unknown token, not the whole source)

### 3.6 External lookup without unknown selected
- [ ] Select `你好`, press hotkey, do NOT click any table row
- [ ] Click **Look up externally** → browser opens MDBG with the full source text `你好`

### 3.7 Close button
- [ ] Open any popup → click **Close** → popup closes, clipboard restored

---

## 4. M4 — Sentence Translation (Argos Translate)

**Precondition**: App running. Argos model may or may not be installed.

### 4.1 Model not installed (expected initial state)
- [ ] Select Chinese text, press hotkey
- [ ] Popup shows a grey label: **"Sentence translation not available — use tray menu to download model."**
- [ ] All other popup features still work (word table, buttons)

### 4.2 Download Recommended model
- [ ] Right-click tray → **Translation Model** → **Download Recommended (~100 MB)**
- [ ] Console shows download progress messages
- [ ] After completion, console shows "Model ready" or similar
- [ ] *Note: this requires internet. Skip if offline-only testing.*

### 4.3 Model installed
- [ ] Restart the app (quit + relaunch)
- [ ] Select `你好世界`, press hotkey
- [ ] Popup shows a **"Translation:"** section above the word table with an English sentence
- [ ] Translation text is selectable and copyable

### 4.4 Model Status
- [ ] Right-click tray → **Translation Model** → **Model Status** → console prints model availability

---

## 5. M5 — Sidebar Mode

**Precondition**: App running.

### 5.1 Toggle Sidebar
- [ ] Right-click tray → **Toggle Sidebar** → a **narrow coloured strip** (10 px wide) appears at the right edge of the screen
- [ ] Strip colour is **red** (no translation yet)
- [ ] The strip does NOT cover the OS scrollbar track in a maximised window; verify by maximising a browser and checking that its scrollbar is still clickable

### 5.2 Feeding content via hotkey
- [ ] Select `你好`, press `Ctrl+Shift+T` → sidebar strip turns **green**; popup does NOT open
- [ ] Click or hover the sidebar strip to expand it → translation content visible

### 5.3 Hover expand / mouse-leave collapse
- [ ] With sidebar collapsed (red or green), hover over the 10 px strip for >300 ms → sidebar auto-expands
- [ ] Move mouse completely away from the expanded sidebar → sidebar auto-collapses after ≈500 ms

### 5.4 Manual expand/collapse
- [ ] Click the strip → sidebar expands
- [ ] Click the **Collapse** button inside the expanded panel → sidebar collapses to strip
- [ ] Press `Shift+Esc` while sidebar is focused → sidebar collapses

### 5.5 Sidebar content
While expanded:
- [ ] Source text is shown and selectable
- [ ] Word table present (if dictionary loaded)
- [ ] MT translation section present (available or "not available" label)
- [ ] **Replace**, **Copy translation**, **Look up externally** buttons work the same as in the popup

### 5.6 Pin from popup
- [ ] Right-click tray → Toggle Sidebar to *close* the sidebar (click toggle again to hide it entirely if possible, or test when sidebar is not visible)
- [ ] Select `你好`, press hotkey → popup opens normally
- [ ] Click **Pin** in the popup → popup closes, sidebar appears green with that content

### 5.7 Width on different displays
- [ ] On a 1080p or 1366×768 laptop screen: sidebar expanded width ≈ 25% of screen = ~340–480 px, should look reasonable (not too narrow to read, not taking up half the screen)
- [ ] On a 2560×1440 docked display: expanded width ≈ 640 px, still readable

### 5.8 Multi-monitor (if applicable)
- [ ] Move cursor to secondary monitor, select text, press hotkey → sidebar anchors to right edge of secondary monitor, not primary

### 5.9 Content persistence
- [ ] Expand sidebar, note the displayed translation, collapse it
- [ ] Re-expand → same translation still shown (content not lost on collapse)

---

## 6. M6 — OCR from Clipboard Image

**Precondition**: App running. Windows 11 (winrt should be available).

### 6.1 Setup — copy an image with Chinese text
- [ ] Find or create a screenshot containing Chinese characters (e.g. screenshot a web page with Chinese text)
- [ ] Copy that image to clipboard (`Ctrl+C` on the screenshot)

### 6.2 OCR trigger
- [ ] Right-click tray → **OCR from Clipboard Image**
- [ ] Popup opens with title **"OCR Result — edit to correct"**
- [ ] Extracted Chinese text appears in the **editable** text area
- [ ] Word table shows below (if extraction succeeded and dictionary loaded)

### 6.3 Edit + Re-translate
- [ ] In the editable text area, change one character (simulate correcting an OCR mistake)
- [ ] Click **Re-translate**
- [ ] Word table refreshes to reflect the edited text
- [ ] No crash

### 6.4 No image in clipboard
- [ ] Copy plain text to clipboard (not an image)
- [ ] Right-click tray → **OCR from Clipboard Image**
- [ ] Console prints **"No image in clipboard."** — no popup opens

### 6.5 Image with no Chinese text
- [ ] Copy a screenshot containing only Latin text or a photo with no text
- [ ] Right-click tray → **OCR from Clipboard Image**
- [ ] Console prints **"OCR: no text detected."** — no popup opens

### 6.6 Engine fallback (if winrt not working)
- [ ] If OCR returns garbage or fails silently: check whether `winrt` is importable in the venv (`python -c "import winrt"`)
- [ ] If winrt missing: install tesseract and `chi_sim` language pack; the router falls back to Tesseract automatically

---

## 7. M7 — Preferences / config.toml

**Precondition**: App has been launched at least once (creates default config).

### 7.1 Locate config file
- [ ] Right-click tray → **Preferences** → **Open Config File**
- [ ] A text editor opens showing the default `config.toml`
- [ ] Confirm path is in `%APPDATA%\zh-en-translator\config.toml` (or equivalent)

### 7.2 Theme — dark
- [ ] In config.toml, set `theme = "dark"` under `[display]`, save the file
- [ ] Within ~1 second the app recolours: dark background, light text in popup/sidebar
- [ ] No restart needed
- [ ] Open a popup to confirm it uses the dark theme

### 7.3 Theme — sepia
- [ ] Set `theme = "sepia"`, save → warm beige/brown colours applied

### 7.4 Theme — light
- [ ] Set `theme = "light"`, save → white background, black text

### 7.5 Theme — system (reset)
- [ ] Set `theme = "system"`, save → app returns to OS default colours

### 7.6 Font customisation
- [ ] Set `font_family = "Consolas"` and `font_size = 16` under `[display]`, save
- [ ] Open a popup → text display uses Consolas 16pt
- [ ] Revert: set `font_family = ""` to restore system default

### 7.7 Hotkey change
- [ ] Set `hotkey = "<ctrl>+<shift>+z"` under `[general]`, save
- [ ] Old hotkey `Ctrl+Shift+T` no longer triggers the popup
- [ ] New hotkey `Ctrl+Shift+Z` triggers the popup
- [ ] Revert to `hotkey = "<ctrl>+<shift>+t"` when done

### 7.8 External lookup URL
- [ ] Set `external_lookup_url = "https://dict.cc/?s={query}"` under `[dictionary]`, save
- [ ] Open a popup, click **Look up externally** → browser opens dict.cc instead of MDBG

### 7.9 Sidebar width
- [ ] Set `sidebar_width_pct = 40` under `[display]`, save
- [ ] Toggle sidebar, expand it → noticeably wider than before
- [ ] Revert to `sidebar_width_pct = 25`

### 7.10 User dictionary override
- [ ] Create a file `user_dict.toml` alongside the config file with contents:
  ```toml
  你好 = ["howdy"]
  ```
- [ ] Set `user_dict_path = "C:\\path\\to\\user_dict.toml"` (full path) under `[dictionary]`, save
- [ ] Select `你好`, press hotkey → word table shows **"howdy"** instead of "hello; hi"

### 7.11 Manual reload
- [ ] Make a config change
- [ ] Right-click tray → **Preferences** → **Reload Config** → change applies immediately

### 7.12 Corrupt config recovery
- [ ] Open config.toml, introduce a syntax error (e.g. delete a closing quote), save
- [ ] App should NOT crash; console may print a warning; app continues running with previous or default config
- [ ] Fix the syntax error, save → normal operation resumes

---

## 8. Cross-Cutting / Regression

### 8.1 Rapid hotkey presses
- [ ] Press `Ctrl+Shift+T` 5 times in quick succession with text selected → no crash, at most one popup at a time

### 8.2 Very long text
- [ ] Select 500+ characters of Chinese text, press hotkey → popup appears (may truncate or scroll), no hang

### 8.3 Empty / whitespace selection
- [ ] Select only spaces or a newline, press hotkey → no popup (or graceful no-op)

### 8.4 Network disconnected
- [ ] Disable network adapter
- [ ] All features still work (dictionary, OCR, replace, sidebar) — zero outbound traffic
- [ ] External lookup button opens browser to cached/offline page (expected — browser handles it)

### 8.5 Quit
- [ ] Right-click tray → **Quit** → tray icon disappears, process exits cleanly (check Task Manager)

---

## 9. Known Not-Yet-Testable Items

These require additional setup not covered above:

| Item | Reason |
|---|---|
| Argos MT actual translation quality | Requires ~100 MB model download |
| Windows OCR on non-English Windows locale | Need to test with a non-English system language set |
| Traditional Chinese (`電腦` → `电脑` → "computer") | OpenCC not yet wired (M9) |
| NVDA screen reader compatibility | M9 milestone |
| MSI installer on clean VM | M8 milestone |
| Azure Translator opt-in | M10 milestone |

---

## 10. Reporting Issues

For each failure, note:
1. Which test step failed (e.g. "3.1 Replace in Notepad")
2. What actually happened vs. what was expected
3. Any console output / traceback
4. Windows version + DPI setting + Python version

File issues at `rogerneumann/zh-en-translation` or paste into the next Claude Code session with the step number.
