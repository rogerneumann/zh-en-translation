# Next Session Prompt

Copy-paste the block below into a fresh Claude Code session on the repo to
continue work. Works on any machine that has the repo cloned.

---

## Before you run the prompt

1. **Verify M1 + M2 on Windows 11 first.** Run through the manual test
   checklists in `progress.md` under "M1" and "M2". If anything fails, fix
   those before adding M3 on top.
2. Make sure you're on branch `claude/popup-translator-app-7bQp3` and
   `git pull` is clean.
3. `pip install -e ".[dev]"` (this time with `jieba` installable — the
   previous sandbox had a build issue).

---

## Prompt for next agent (M3 — Replace + External Lookup)

> Read `PLAN.md`, `progress.md`, and the existing code in
> `src/zh_en_translator/` before writing anything.
>
> Implement **Milestone 3 (M3) "Replace + External Lookup"** only. Do NOT
> implement sentence MT, OCR, sidebar, config file, or any later milestone.
>
> **Deliverables**:
>
> 1. **Replace-selected-text action**:
>    - New module `src/zh_en_translator/replace.py` with a `replace_selection(new_text: str, original_clipboard: str) -> bool` function.
>    - Implementation: set clipboard to `new_text`, simulate `Ctrl+V` via
>      `pynput.keyboard.Controller`, wait ~80 ms, restore clipboard to
>      `original_clipboard`. Return `True` on success, `False` on exception.
>    - Must work in any app that accepts paste (Word, Notepad, browsers,
>      Save-As dialogs, IDEs).
>
> 2. **Popup UI additions**:
>    - Add a row of buttons at the bottom of the popup: `Replace`, `Copy
>      translation`, `Look up externally`, `Close`.
>    - `Replace` calls `replace_selection()` with the concatenated English
>      glosses joined by `; `. Closes popup on success.
>    - `Copy translation` writes the same string to the clipboard WITHOUT
>      restoring it (user explicitly asked for it). Show a brief toast /
>      status label confirming.
>    - `Look up externally`: opens default browser to MDBG (hardcoded for
>      M3; configurable URL is M7). URL template:
>      `https://www.mdbg.net/chinese/dictionary?wdqb={query}` with `{query}`
>      URL-encoded. The "query" is the current source text OR, if the user
>      has highlighted an unknown token in the table, just that token.
>
> 3. **Unknown-token interaction**:
>    - Clicking an unknown (pale-yellow) token in the table selects it and
>      auto-populates a small "Unknown: <token>" label above the button row.
>    - That label's presence changes what `Look up externally` queries
>      (the selected unknown token instead of the whole source text).
>
> 4. **Tests** (in `tests/`):
>    - `test_replace.py` — unit test `replace_selection` with mocked
>      `pyperclip` and `pynput.Controller`. Verify clipboard set, paste
>      simulated, clipboard restored, and `False` returned on exception.
>    - `test_popup_m3.py` — smoke tests for the new popup buttons. Use
>      `QT_QPA_PLATFORM=offscreen`. Verify buttons exist, `Copy` updates a
>      mocked clipboard, clicking an unknown token sets the label.
>
> 5. **Do NOT** add new runtime deps. All M3 work uses existing deps
>    (`pyperclip`, `pynput`, `PyQt6`, stdlib `urllib.parse`, `webbrowser`).
>
> 6. **Lint**: `ruff check src/ tests/` must pass.
>
> 7. **Git workflow — IMPORTANT**:
>    - You are on branch `claude/popup-translator-app-7bQp3`. Stay on it.
>    - **You MUST `git commit` and `git push` before exiting.** Previous
>      agents forgot and the parent had to clean up.
>    - Commit message: `M3: replace selected text, copy, external lookup`.
>    - Do NOT open a PR.
>
> 8. **Update `progress.md`**:
>    - Mark M3 as Done with the commit hash.
>    - List files changed, any deviations, and a Windows manual-test
>      checklist (try Replace in Word, Notepad, a Save-As dialog filename
>      field, a browser address bar; try external lookup; try unknown-token
>      click-to-select).
>
> Reply with a concise summary (under 300 words): files changed, test
> results, lint status, commit hash, one thing for the user to eyeball on
> Windows.
>
> Use Haiku. Do NOT escalate to a stronger model unless you hit a blocker
> that can't be solved in 2-3 attempts.

---

## Use this checklist when the agent returns

- [ ] Commit hash is on `origin/claude/popup-translator-app-7bQp3`.
- [ ] `progress.md` updated with M3 row + checklist.
- [ ] Ruff passes.
- [ ] All tests pass (should be > 50 tests now).
- [ ] No new runtime dependencies added to `pyproject.toml`.
- [ ] MDBG URL is hardcoded (config file is M7; don't let the agent
      pre-implement it).

---

## If the agent goes off-rails

Common failure modes to watch for, based on M1 and M2:

- **Forgets to commit/push** — check `git status` when it returns. If
  files are uncommitted, stage them yourself: `git add -A && git commit`
  and verify the work before pushing.
- **Adds unrequested deps** — review the pyproject.toml diff.
- **Implements future milestones** — if you see code referencing
  `config.toml` or sidebar or OCR, stop and tell it to remove that scope.
- **Linux-specific hacks** — if it adds `xdotool` or `xsel` instead of
  using the existing pynput/pyperclip, that's wrong.
