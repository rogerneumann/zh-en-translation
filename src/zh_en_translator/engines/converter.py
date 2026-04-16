"""Traditional Chinese → Simplified Chinese conversion via OpenCC."""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

_converter = None  # cached OpenCC instance
_available: bool | None = None  # None = not yet probed


def _get_converter():
    """Return the cached OpenCC converter, probing on first call."""
    global _converter, _available

    if _available is not None:
        return _converter  # already probed

    # Try the official opencc package first
    try:
        import opencc  # type: ignore[import]
        _converter = opencc.OpenCC("t2s")
        _available = True
        logger.debug("OpenCC backend: opencc package")
        return _converter
    except Exception:
        pass

    # Try the pure-Python reimplementation
    try:
        import opencc_python_reimplemented as opencc  # type: ignore[import]
        _converter = opencc.OpenCC("t2s")
        _available = True
        logger.debug("OpenCC backend: opencc_python_reimplemented package")
        return _converter
    except Exception:
        pass

    _available = False
    logger.debug(
        "No OpenCC backend available (install opencc-python-reimplemented); "
        "Traditional Chinese will not be converted."
    )
    return None


def to_simplified(text: str) -> str:
    """Convert Traditional Chinese to Simplified Chinese.

    Returns *text* unchanged if OpenCC is not available or conversion fails.
    Never raises.
    """
    try:
        conv = _get_converter()
        if conv is None:
            return text
        return conv.convert(text)
    except Exception as exc:
        logger.debug("OpenCC conversion failed: %s", exc)
        return text


def is_available() -> bool:
    """Return True if an OpenCC backend is importable."""
    _get_converter()  # probe if not yet done
    return bool(_available)
