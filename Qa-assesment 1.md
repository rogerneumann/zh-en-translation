# QA Assessment 1 — zh-en-translation

**Branch:** `claude/qa-testing-windows-Aa42E`
**Date:** 2026-04-15
**Build under test:** M1 + M2 (per `progress.md`)

> **Note on terminology:** there is no stand-alone `test cases.md` — the test
> plan lives in `PLAN.md` §Test Plan (T1–T40). This assessment runs that plan
> against the current M2 build. `progress.md` confirms only M1+M2 are built;
> the Windows checklists at the bottom of `progress.md` are still marked
> "❌ Not yet" verified on Windows.

---

## Automated test results

- `pytest`: **52/52 pass** (`QT_QPA_PLATFORM=offscreen python -m pytest -v`)
  once `libegl1 libxkbcommon0 libxcb-cursor0 libdbus-1-3 libfontconfig1` are
  installed for the headless Qt run.
- `ruff check src/ tests/`: clean.

---

## PLAN.md test-plan spot checks (what's actually verifiable against M2)

| #   | Result |
| --- | --- |
| T1 `你好` → "hello; hi", pinyin `nǐ hǎo` | ✅ |
| T2 unknown char → empty list | ✅ |
| T3 `我喜欢吃苹果` segments | ⚠️ returns a single Chinese run `['我喜欢吃苹果']`; pipeline then greedy-matches inside, but this *is* the jieba-dropped deviation noted in `progress.md` |
| T4 mixed `我love你` | ✅ `['我','love','你']` |
| T5 sentence MT | ⏭ M4 (not built) |
| T6 empty string | ✅ no crash |
| **T7 long text >1000 chars** | ❌ **FAIL — severe perf regression** (see bug #2) |
| T17/T23/T37 offline | ✅ no network code in M1/M2 |
| T18 lookup p95 < 50 ms | ✅ p95 ≈ 0.9 ms, p99 ≈ 2.0 ms |
| T24 `電腦` (traditional) → `电脑`/"computer" | ⚠️ `test_lookup_traditional` passes with a synthetic entry, but the *bundled* `cedict_sample.txt` has `电脑 电脑` (simp/simp), so live T24 returns nothing. Sample-data limitation. |
| T8–T15, T21, T22, T25–T40 | ⏭ require real Windows host |

---

## P0 bugs found

### Bug 1 — Popup crashes whenever a dictionary is attached

`src/zh_en_translator/ui/popup.py:180`

```python
num_rows = len(self.word_table) if hasattr(self, "word_table") else 0
```

`QTableWidget` has no `__len__`. Raises
`TypeError: object of type 'QTableWidget' has no len()`.

This fires on the real happy path: tray app boots → user hits hotkey →
`TranslatorApp._on_hotkey_pressed` → `TranslatorPopup(..., dictionary=self.dictionary)`
→ crash. Reproduced end-to-end.

**Fix:** `self.word_table.rowCount()`.

The existing tests miss this because every unit test calls
`TranslatorPopup(text, original_clipboard="")` with no `dictionary` argument,
so the `self.dictionary` branch is never exercised.

### Bug 2 — T7 long-text translation is O(n²) and hangs

`src/zh_en_translator/engines/pipeline.py:53`

Because the char-run segmenter emits one Chinese run for purely-Chinese input,
`translate()` does `lookup(token[:end])` for every prefix length of a 2000-char
blob — ~4 M SQLite queries.

Observed:

| Input size | Time |
| --- | --- |
| 50 ch   | 124 ms |
| 100 ch  | 560 ms |
| 200 ch  | 1.6 s |
| 500 ch  | 14.3 s |
| 2000 ch | did not finish within 30 s |

**Fix options:** cap max lookup length (e.g. 6 chars — CC-CEDICT's longest
entries), or reintroduce jieba for long text.

---

## Windows 11 readiness — code review

**Good news:** the code is deliberately portable. No `win32` / `ctypes` /
`winreg` imports, no hardcoded paths or separators (everything via `pathlib`),
file reads use explicit `encoding="utf-8"` (important on Windows where the
default is cp1252), and `platformdirs.user_data_dir("zh-en-translator")`
resolves to `%APPDATA%\zh-en-translator` as `PLAN.md` specifies.
`pynput.GlobalHotKeys`, `pyperclip`, PyQt6 `QSystemTrayIcon` /
`FramelessWindowHint | Tool | WindowStaysOnTopHint` are all supported on Win11.

### Windows-specific risks that will bite on a real Win11 host (beyond the P0 above)

- **Elevation mismatch** (`capture.py`): `pynput`'s low-level keyboard hook
  cannot inject `Ctrl+C` into processes running at a higher integrity level.
  If the translator is launched unelevated and the user tries to translate in
  an elevated app (e.g. admin cmd, elevated Notepad), `capture_selection()`
  will silently return the prior clipboard contents. Matches the T36 "Save-As
  dialog" case — may fail for system dialogs. No check / no toast.
- **SmartScreen:** PyInstaller + unsigned MSI (M8) will trigger Win11
  SmartScreen. Noted in `progress.md`, not a code bug.
- **`Ctrl+Shift+T` hotkey clash** with browser "reopen closed tab" — already
  flagged in `progress.md`.
- **`QSystemTrayIcon` availability** is not gated with
  `QSystemTrayIcon.isSystemTrayAvailable()`. Normal Win11 desktops have a tray
  so this is fine in practice, but on Server Core / stripped WinPE it would
  crash silently.
- **DPI scaling (T35):** `popup._resize_to_fit()` uses `longest_line * 8` raw
  pixels and fixed `40 + 100 + table_height`. PyQt6 enables high-DPI by
  default, but the *estimated* sizes aren't DPI-aware — the table itself
  handles DPI, but the popup envelope may clip at 150 %. Worth a manual check
  once the P0 popup crash is fixed.
- **Clipboard wait** (`CLIPBOARD_WAIT_MS = 0.08`): 80 ms is usually enough on
  Win11 but Word / OneNote have occasionally needed ~120 ms. If T14 fails
  intermittently, bump it.
- **Redundant dead code** in `app.py:112-122` (outer clipboard save that
  `TextCapture` already does). Harmless but noisy.

---

## Recommendations before anyone tries this on Windows

1. Fix the `len(self.word_table)` bug — single-line change, will unblock T8,
   T10–T15, T22, T25.
2. Cap the pipeline greedy-match window (e.g.
   `for end_pos in range(min(len(token), 8), 0, -1)`) so T7 doesn't hang.
3. Either swap `电脑 电脑` → `電腦 电脑` in the bundled sample or add a note to
   `progress.md` that T24 needs the real CC-CEDICT file.
4. Add at least one smoke test that instantiates
   `TranslatorPopup(text, "", dictionary=<real dict>)` so the dict-enabled
   code path stays green.

All of the above can be verified in this sandbox once fixed; the remaining
checklist items (global hotkey, clipboard paste, multi-monitor, DPI, NVDA,
MSI) genuinely require a Win11 host.
