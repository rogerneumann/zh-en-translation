"""Tesseract OCR engine via pytesseract (cross-platform fallback)."""

from __future__ import annotations
import logging
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

# Session-level cache: True once a successful version check has passed.
# Avoids spawning a redundant get_tesseract_version() subprocess on every
# is_available() call (engine.py calls it once in is_any_engine_available and
# again inside ocr_image's waterfall check).
_version_ok: bool = False

# Session-level cache for the best available Chinese language string.
# None = not yet determined; "" = no Chinese data found; else the lang arg.
_zh_lang_cache: str | None = None


def _get_tesseract_candidates() -> list[Path]:
    """Return candidate Tesseract paths, checking bundled/system paths for the current platform."""
    import shutil

    candidates = []

    if sys.platform == "win32":
        # Frozen (PyInstaller) bundled binary on Windows
        if getattr(sys, "frozen", False):
            candidates.append(Path(sys.executable).parent / "tesseract" / "tesseract.exe")
        # System PATH first so user-chosen installs win over hardcoded dirs
        system_tess = shutil.which("tesseract")
        if system_tess:
            candidates.append(Path(system_tess))
        candidates += [
            Path.home() / "AppData" / "Local" / "Programs" / "Tesseract-OCR" / "tesseract.exe",
            Path.home() / "AppData" / "Local" / "Tesseract-OCR" / "tesseract.exe",
            Path("C:\\Program Files\\Tesseract-OCR\\tesseract.exe"),
            Path("C:\\Program Files (x86)\\Tesseract-OCR\\tesseract.exe"),
        ]
    else:
        # Flatpak bundled binary
        flatpak_bin = Path("/app/bin/tesseract")
        if flatpak_bin.exists():
            candidates.append(flatpak_bin)
        # Frozen (PyInstaller) bundled binary on Linux/macOS
        if getattr(sys, "frozen", False):
            candidates.append(Path(sys.executable).parent / "tesseract" / "tesseract")
        # System PATH — most reliable on Linux/macOS
        system_tess = shutil.which("tesseract")
        if system_tess:
            candidates.append(Path(system_tess))
        # Common install prefixes as final fallback
        candidates += [
            Path("/usr/bin/tesseract"),
            Path("/usr/local/bin/tesseract"),
            Path("/opt/homebrew/bin/tesseract"),  # macOS Homebrew
        ]

    return candidates


def _configure_pytesseract_cmd() -> bool:
    """Set pytesseract.tesseract_cmd to a known Tesseract location if found.

    Returns True if a valid tesseract.exe was found and configured.
    """
    try:
        import pytesseract
    except ImportError:
        return False

    import os

    # Suppress the brief console-window flash that Windows shows when
    # pytesseract spawns tesseract.exe as a subprocess.
    if sys.platform == "win32":
        import subprocess as _sp
        pytesseract.pytesseract.subprocess_args = {
            "creationflags": _sp.CREATE_NO_WINDOW
        }

    # Check each candidate path
    for candidate in _get_tesseract_candidates():
        if candidate.exists() and candidate.is_file():
            try:
                tessdata_dir = candidate.parent / "tessdata"
                if tessdata_dir.exists():
                    os.environ["TESSDATA_PREFIX"] = str(tessdata_dir)
                pytesseract.pytesseract.tesseract_cmd = str(candidate)
                logger.info("Configured pytesseract.tesseract_cmd to: %s", candidate)
                return True
            except Exception as e:
                logger.debug("Failed to set tesseract_cmd to %s: %s", candidate, e)
                continue

    return False


def get_found_path() -> str | None:
    """Return the path of the first found tesseract.exe, or None if not found."""
    for candidate in _get_tesseract_candidates():
        if candidate.exists() and candidate.is_file():
            return str(candidate)
    return None


def is_available() -> bool:
    """Return True if pytesseract and the tesseract binary are found."""
    global _version_ok
    if _version_ok:
        return True
    try:
        import pytesseract
        _configure_pytesseract_cmd()
        pytesseract.get_tesseract_version()
        _version_ok = True
        return True
    except Exception as e:
        logger.debug("Tesseract not available: %s", e)
        return False


def _available_zh_lang() -> str:
    """Return the best available Tesseract language string for Chinese.

    Tries chi_sim+chi_tra first (both scripts), falls back to whichever single
    traineddata file is present. Returns empty string if neither is found.
    Result is cached for the session to avoid a redundant subprocess spawn.
    """
    global _zh_lang_cache
    if _zh_lang_cache is not None:
        return _zh_lang_cache

    import pytesseract

    try:
        available = pytesseract.get_languages()
    except Exception:
        available = []

    has_sim = "chi_sim" in available
    has_tra = "chi_tra" in available

    if has_sim and has_tra:
        _zh_lang_cache = "chi_sim+chi_tra"
    elif has_sim:
        _zh_lang_cache = "chi_sim"
    elif has_tra:
        _zh_lang_cache = "chi_tra"
    else:
        _zh_lang_cache = ""
        logger.warning(
            "Tesseract found but no Chinese traineddata (chi_sim/chi_tra). "
            "Available languages: %s", available
        )

    return _zh_lang_cache


def ocr_image(image_bytes: bytes, lang: str = "zh") -> str | None:
    """
    Run pytesseract on image bytes.

    lang "zh" → best available Chinese tessdata (chi_sim+chi_tra, chi_sim, or chi_tra)
    lang "en" → "eng"
    Returns extracted text or None on failure.
    """
    try:
        import pytesseract
        from PIL import Image
        import io

        if lang == "zh":
            tess_lang = _available_zh_lang()
            if not tess_lang:
                logger.debug("No Chinese tessdata found; skipping Tesseract OCR")
                return None
        else:
            tess_lang = "eng"

        img = Image.open(io.BytesIO(image_bytes))
        text = pytesseract.image_to_string(img, lang=tess_lang)
        return text.strip() or None
    except Exception as e:
        logger.warning("Tesseract ocr_image failed: %s", e, exc_info=True)
        return None
