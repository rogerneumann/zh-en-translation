"""PaddleOCR engine (opt-in, best quality for Chinese)."""

from __future__ import annotations


def is_available() -> bool:
    """Return True if paddleocr is installed."""
    try:
        import paddleocr  # noqa: F401
        return True
    except ImportError:
        return False


def ocr_image(image_bytes: bytes, lang: str = "zh") -> str | None:
    """
    Run PaddleOCR on image bytes.

    Uses lang="ch" for Chinese (handles Simplified + Traditional).
    Returns concatenated text from all detected boxes, or None on failure.
    """
    try:
        from paddleocr import PaddleOCR
        import numpy as np
        from PIL import Image
        import io

        img = np.array(Image.open(io.BytesIO(image_bytes)))

        paddle_lang = "ch" if lang == "zh" else lang
        ocr = PaddleOCR(use_angle_cls=True, lang=paddle_lang, show_log=False)
        result = ocr.ocr(img, cls=True)

        if not result:
            return None

        text = " ".join(
            line[1][0] for block in result for line in block if line
        )
        return text.strip() or None
    except Exception:
        return None
