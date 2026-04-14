# zh-en-translation

A lightweight, offline-first Chinese→English popup translator for Windows 11 (with cross-platform intent). Triggered by a global hotkey (`Ctrl+Shift+T`) on selected text in any application, it displays a frameless popup with translation options.

## Development

### Install

```bash
# Clone the repository
git clone https://github.com/yourusername/zh-en-translation.git
cd zh-en-translation

# Install in development mode with dependencies
pip install -e ".[dev]"
```

### Run

```bash
# Start the translator app (tray icon)
zh-en-translator
```

### Test

```bash
# Run all tests with offscreen rendering (Linux/CI)
QT_QPA_PLATFORM=offscreen pytest -x

# Run tests with output
QT_QPA_PLATFORM=offscreen pytest -v

# Run specific test file
QT_QPA_PLATFORM=offscreen pytest tests/test_app_smoke.py -v
```

### Lint

```bash
ruff check src/ tests/
```

## Milestone 1 (M1) — "Hello Popup"

- System tray app with global hotkey listener
- Captures selected text via clipboard save/restore pattern
- Frameless popup with rounded corners and drop shadow
- Dismiss via Esc, click-outside, or focus loss
- No translation engine yet (scaffold only)
