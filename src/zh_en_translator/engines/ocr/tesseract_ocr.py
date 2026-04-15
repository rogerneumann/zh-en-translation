"""Tesseract OCR engine via pytesseract (cross-platform fallback)."""

from __future__ import annotations


def is_available() -> bool:
    """Return True if pytesseract and the tesseract binary are found."""
    try:
        import pytesseract
        pytesseract.get_tesseract_version()
        return True
    except Exception:
        return False


def ocr_image(image_bytes: bytes, lang: str = "zh") -> str | None:
    """
    Run pytesseract on image bytes.

    lang "zh" → tesseract lang string "chi_sim+chi_tra"
    lang "en" → "eng"
    Returns extracted text or None on failure.
    """
    try:
        import pytesseract
        from PIL import Image
        import io

        tess_lang = "chi_sim+chi_tra" if lang == "zh" else "eng"
        img = Image.open(io.BytesIO(image_bytes))
        text = pytesseract.image_to_string(img, lang=tess_lang)
        return text.strip() or None
    except Exception:
        return None
