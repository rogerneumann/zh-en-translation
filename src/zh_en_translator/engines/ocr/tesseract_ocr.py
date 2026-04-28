"""Tesseract OCR engine via pytesseract (cross-platform fallback)."""

from __future__ import annotations
import logging
import sys
from pathlib import Path

logger = logging.getLogger(__name__)


def _get_tesseract_candidates() -> list[Path]:
    """Return candidate Tesseract paths, checking bundled path first in frozen builds."""
    candidates = []
    # Check bundled Tesseract first (for frozen/installed app)
    if getattr(sys, "frozen", False):
        bundled = Path(sys.executable).parent / "tesseract" / "tesseract.exe"
        candidates.append(bundled)
    # Standard Windows install locations
    candidates += [
        Path.home() / "AppData" / "Local" / "Programs" / "Tesseract-OCR" / "tesseract.exe",
        Path.home() / "AppData" / "Local" / "Tesseract-OCR" / "tesseract.exe",
        Path("C:\\Program Files\\Tesseract-OCR\\tesseract.exe"),
        Path("C:\\Program Files (x86)\\Tesseract-OCR\\tesseract.exe"),
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


def is_available() -> bool:
    """Return True if pytesseract and the tesseract binary are found."""
    try:
        import pytesseract

        # Try to configure the path if not already configured
        _configure_pytesseract_cmd()

        pytesseract.get_tesseract_version()
        return True
    except Exception as e:
        logger.debug("Tesseract not available: %s", e)
        return False


def _available_zh_lang() -> str:
    """Return the best available Tesseract language string for Chinese.

    Tries chi_sim+chi_tra first (both scripts), falls back to whichever single
    traineddata file is present. Returns empty string if neither is found.
    """
    import pytesseract

    try:
        available = pytesseract.get_languages()
    except Exception:
        available = []

    has_sim = "chi_sim" in available
    has_tra = "chi_tra" in available

    if has_sim and has_tra:
        return "chi_sim+chi_tra"
    if has_sim:
        return "chi_sim"
    if has_tra:
        return "chi_tra"
    return ""


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
    except Exception:
        return None
