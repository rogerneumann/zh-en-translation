"""Unified OCR interface — waterfall: Windows OCR → Tesseract → PaddleOCR."""

from __future__ import annotations

from zh_en_translator.engines.ocr import paddle_ocr, windows_ocr, tesseract_ocr


def is_any_engine_available() -> bool:
    """Return True if at least one OCR engine is available."""
    return (
        windows_ocr.is_available()
        or tesseract_ocr.is_available()
        or paddle_ocr.is_available()
    )


def ocr_image(image_bytes: bytes, lang: str = "zh") -> str | None:
    """
    Run OCR on raw image bytes (PNG/BMP/JPEG).

    lang: "zh" for Chinese (Simplified+Traditional), "en" for English.
    Returns extracted text, or None if all engines fail/unavailable.

    Waterfall order: Windows OCR (native) → Tesseract → PaddleOCR
    """
    if windows_ocr.is_available():
        result = windows_ocr.ocr_image(image_bytes, lang=lang)
        if result:
            return result

    if tesseract_ocr.is_available():
        result = tesseract_ocr.ocr_image(image_bytes, lang=lang)
        if result:
            return result

    if paddle_ocr.is_available():
        result = paddle_ocr.ocr_image(image_bytes, lang=lang)
        if result:
            return result

    return None
