# QA Assessment 1 -- zh-en-translation

**Date:** 2026-04-15
**Build under test:** M1 + M2

> **Historical note:** This assessment was conducted against the very first
> Windows-readiness review of the M1/M2 build. All P0 bugs identified here
> were fixed in subsequent sessions before M3 was shipped. The Windows
> readiness observations remain useful context.

---

## Automated test results (M1+M2 baseline)

- `pytest`: **52/52 pass** (`QT_QPA_PLATFORM=offscreen python -m pytest -v`)
- `ruff check src/ tests/`: clean.

---

## Test-plan spot checks

| #   | Result |
| --- | --- |
| T1 `你好` -> "hello; hi", pinyin `ni hao` | Pass |
| T2 unknown char -> empty list | Pass |
| T3 `我喜欢吃苹果` segments | Warn -- single run; jieba deviation noted in progress.md |
| T4 mixed `我love你` | Pass |
| T5 sentence MT | Skip -- M4 not built |
| T6 empty string | Pass -- no crash |
| T7 long text >1000 chars | FAIL -- O(n^2) perf (see Bug 2 below, fixed in pipeline.py) |
| T17/T23/T37 offline | Pass -- no network code in M1/M2 |
| T18 lookup p95 < 50 ms | Pass -- p95 ~0.9 ms, p99 ~2.0 ms |
| T24 `電腦` (traditional) | Warn -- sample CEDICT has simp/simp; fixed with full CC-CEDICT |
| T8-T15, T21, T22, T25-T40 | Skip -- require real Windows host |

---

## P0 bugs found (both fixed before M3)

### Bug 1 -- Popup crash with dictionary attached

`src/zh_en_translator/ui/popup.py` called `len(self.word_table)` on a
`QTableWidget`, which has no `__len__`. Fixed to `self.word_table.rowCount()`.

### Bug 2 -- Long-text translation O(n^2) hang

`pipeline.py` ran greedy prefix lookups on entire Chinese input with no length
cap, causing ~4M SQLite queries on 2000-char input. Fixed by capping max lookup
window to 8 chars (longest CC-CEDICT entry).

---

## Windows 11 readiness notes (still relevant)

- **Elevation mismatch:** `pynput` cannot inject `Ctrl+C` into elevated
  processes. Translating inside an admin cmd window silently returns stale
  clipboard. No user-visible error -- a known limitation.
- **SmartScreen:** unsigned installer triggers SmartScreen. Tracked in
  `signing_plan.md` (P7).
- **`Ctrl+Shift+T` hotkey clash** with browser "reopen closed tab". Configurable
  in Preferences.
- **DPI scaling:** popup envelope sizing used raw pixels; fixed in later UI work.
- **Clipboard wait:** 80 ms default; Word/OneNote may need 120 ms. Bumped in
  later config.
