"""PyInstaller entry point for zh-en-translator.

Patches sys.path so that the AppData overlay directory
(%APPDATA%\\zh-en-translator\\app\\) is checked before the bundled
zh_en_translator package.  If the overlay fails to import it is
removed and the bundled version is used instead (app-prev/ is promoted
back to app/ if it exists).

This module is the Analysis entry point in the PyInstaller spec.
"""

from __future__ import annotations

import importlib
import logging
import os
import pathlib
import shutil
import sys

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

def _appdata_base() -> pathlib.Path:
    if sys.platform == "win32":
        return pathlib.Path(os.environ.get("APPDATA", pathlib.Path.home())) / "zh-en-translator"
    try:
        from platformdirs import user_data_dir
        return pathlib.Path(user_data_dir("zh-en-translator"))
    except ImportError:
        return pathlib.Path.home() / ".local" / "share" / "zh-en-translator"


_BASE    = _appdata_base()
_OVERLAY = _BASE / "app"
_PREV    = _BASE / "app-prev"


# ---------------------------------------------------------------------------
# Bootstrap
# ---------------------------------------------------------------------------

def _bootstrap() -> None:
    """Prepend overlay to sys.path if it exists and is importable."""
    if not _OVERLAY.exists():
        return

    sys.path.insert(0, str(_OVERLAY))
    try:
        importlib.import_module("zh_en_translator")
        # Success — overlay is active
    except ImportError:
        # Corrupt overlay — pop it and auto-rollback to app-prev if available
        sys.path.pop(0)
        if _PREV.exists():
            try:
                shutil.rmtree(_OVERLAY, ignore_errors=True)
                _PREV.rename(_OVERLAY)
                sys.path.insert(0, str(_OVERLAY))
            except Exception:
                pass  # fall through to bundled version


_bootstrap()

# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

from zh_en_translator.app import main  # noqa: E402

if __name__ == "__main__":
    main()
