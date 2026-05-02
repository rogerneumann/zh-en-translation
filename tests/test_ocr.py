"""Tests for OCR engine modules and unified waterfall interface."""

from __future__ import annotations

import sys
import types
from unittest.mock import MagicMock


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_fake_paddleocr_module():
    """Return a minimal fake paddleocr module so imports succeed."""
    mod = types.ModuleType("paddleocr")
    ocr_instance = MagicMock()
    # result: list of blocks, each block is a list of lines; line = [bbox, (text, score)]
    ocr_instance.ocr.return_value = [[[[None, ("你好", 0.99)]]]]
    paddle_cls = MagicMock(return_value=ocr_instance)
    mod.PaddleOCR = paddle_cls
    return mod


def _make_fake_pytesseract_module(text: str = "你好"):
    mod = types.ModuleType("pytesseract")
    mod.get_tesseract_version = MagicMock(return_value="5.0.0")
    mod.image_to_string = MagicMock(return_value=text)
    return mod


def _make_fake_pil_module():
    pil = types.ModuleType("PIL")
    image_mod = types.ModuleType("PIL.Image")
    fake_img = MagicMock()
    image_mod.open = MagicMock(return_value=fake_img)
    pil.Image = image_mod
    sys.modules.setdefault("PIL", pil)
    sys.modules["PIL.Image"] = image_mod
    return pil, image_mod


def _make_fake_numpy_module():
    np = types.ModuleType("numpy")
    np.array = MagicMock(return_value=MagicMock())
    sys.modules["numpy"] = np
    return np


# ---------------------------------------------------------------------------
# engine.py — waterfall tests
# ---------------------------------------------------------------------------

def test_ocr_engine_waterfall_windows_first(monkeypatch):
    """Windows OCR is tried first on win32; if it returns text, others are not called."""
    windows_mod = MagicMock()
    windows_mod.is_available.return_value = True
    windows_mod.ocr_image.return_value = "extracted by windows"

    tesseract_mod = MagicMock()
    tesseract_mod.is_available.return_value = True
    tesseract_mod.ocr_image.return_value = "should not be reached"

    paddle_mod = MagicMock()
    paddle_mod.is_available.return_value = True
    paddle_mod.ocr_image.return_value = "should not be reached"

    monkeypatch.setattr("zh_en_translator.engines.ocr.engine.paddle_ocr", paddle_mod)
    monkeypatch.setattr("zh_en_translator.engines.ocr.engine.windows_ocr", windows_mod)
    monkeypatch.setattr("zh_en_translator.engines.ocr.engine.tesseract_ocr", tesseract_mod)
    monkeypatch.setattr("zh_en_translator.engines.ocr.engine.sys.platform", "win32")

    from zh_en_translator.engines.ocr.engine import ocr_image
    result = ocr_image(b"fake_image_bytes", lang="zh")

    assert result == "extracted by windows"
    windows_mod.ocr_image.assert_called_once()
    tesseract_mod.ocr_image.assert_not_called()
    paddle_mod.ocr_image.assert_not_called()


def test_ocr_engine_waterfall_windows_falls_back_to_tesseract(monkeypatch):
    """When Windows OCR returns None on win32, Tesseract is tried next."""
    windows_mod = MagicMock()
    windows_mod.is_available.return_value = True
    windows_mod.ocr_image.return_value = None  # windows found but returned nothing

    tesseract_mod = MagicMock()
    tesseract_mod.is_available.return_value = True
    tesseract_mod.ocr_image.return_value = "extracted by tesseract"

    paddle_mod = MagicMock()
    paddle_mod.is_available.return_value = True
    paddle_mod.ocr_image.return_value = "should not be reached"

    monkeypatch.setattr("zh_en_translator.engines.ocr.engine.paddle_ocr", paddle_mod)
    monkeypatch.setattr("zh_en_translator.engines.ocr.engine.windows_ocr", windows_mod)
    monkeypatch.setattr("zh_en_translator.engines.ocr.engine.tesseract_ocr", tesseract_mod)
    monkeypatch.setattr("zh_en_translator.engines.ocr.engine.sys.platform", "win32")

    from zh_en_translator.engines.ocr.engine import ocr_image
    result = ocr_image(b"fake_image_bytes", lang="zh")

    assert result == "extracted by tesseract"
    windows_mod.ocr_image.assert_called_once()
    tesseract_mod.ocr_image.assert_called_once()
    paddle_mod.ocr_image.assert_not_called()


def test_ocr_engine_waterfall_falls_back_to_tesseract(monkeypatch):
    """When Windows OCR returns None on win32, Tesseract is tried next."""
    paddle_mod = MagicMock()
    paddle_mod.is_available.return_value = False

    windows_mod = MagicMock()
    windows_mod.is_available.return_value = True
    windows_mod.ocr_image.return_value = None  # windows found but returned nothing

    tesseract_mod = MagicMock()
    tesseract_mod.is_available.return_value = True
    tesseract_mod.ocr_image.return_value = "extracted by tesseract"

    monkeypatch.setattr("zh_en_translator.engines.ocr.engine.paddle_ocr", paddle_mod)
    monkeypatch.setattr("zh_en_translator.engines.ocr.engine.windows_ocr", windows_mod)
    monkeypatch.setattr("zh_en_translator.engines.ocr.engine.tesseract_ocr", tesseract_mod)
    monkeypatch.setattr("zh_en_translator.engines.ocr.engine.sys.platform", "win32")

    from zh_en_translator.engines.ocr.engine import ocr_image
    result = ocr_image(b"fake_image_bytes", lang="zh")

    assert result == "extracted by tesseract"
    paddle_mod.ocr_image.assert_not_called()
    windows_mod.ocr_image.assert_called_once()
    tesseract_mod.ocr_image.assert_called_once()


def test_ocr_engine_waterfall_linux_skips_windows_ocr(monkeypatch):
    """On Linux, Windows OCR is never called even if is_available() returns True."""
    windows_mod = MagicMock()
    windows_mod.is_available.return_value = True
    windows_mod.ocr_image.return_value = "should not be reached"

    tesseract_mod = MagicMock()
    tesseract_mod.is_available.return_value = True
    tesseract_mod.ocr_image.return_value = "extracted by tesseract"

    paddle_mod = MagicMock()
    paddle_mod.is_available.return_value = False

    monkeypatch.setattr("zh_en_translator.engines.ocr.engine.paddle_ocr", paddle_mod)
    monkeypatch.setattr("zh_en_translator.engines.ocr.engine.windows_ocr", windows_mod)
    monkeypatch.setattr("zh_en_translator.engines.ocr.engine.tesseract_ocr", tesseract_mod)
    monkeypatch.setattr("zh_en_translator.engines.ocr.engine.sys.platform", "linux")

    from zh_en_translator.engines.ocr.engine import ocr_image
    result = ocr_image(b"fake_image_bytes", lang="zh")

    assert result == "extracted by tesseract"
    windows_mod.ocr_image.assert_not_called()
    tesseract_mod.ocr_image.assert_called_once()


def test_ocr_engine_none_available(monkeypatch):
    """When no engine is available, ocr_image returns None."""
    paddle_mod = MagicMock()
    paddle_mod.is_available.return_value = False

    windows_mod = MagicMock()
    windows_mod.is_available.return_value = False

    tesseract_mod = MagicMock()
    tesseract_mod.is_available.return_value = False

    monkeypatch.setattr("zh_en_translator.engines.ocr.engine.paddle_ocr", paddle_mod)
    monkeypatch.setattr("zh_en_translator.engines.ocr.engine.windows_ocr", windows_mod)
    monkeypatch.setattr("zh_en_translator.engines.ocr.engine.tesseract_ocr", tesseract_mod)

    from zh_en_translator.engines.ocr.engine import ocr_image, is_any_engine_available
    result = ocr_image(b"fake_image_bytes")
    assert result is None

    available = is_any_engine_available()
    assert available is False


# ---------------------------------------------------------------------------
# windows_ocr.py — availability test
# ---------------------------------------------------------------------------

def test_windows_ocr_not_available_without_winsdk(monkeypatch):
    """is_available() returns False when neither winrt nor winsdk is installed."""
    # Block both winrt-* and winsdk so _imports() raises ImportError for both
    for key in list(sys.modules.keys()):
        if key.startswith("winrt") or key.startswith("winsdk"):
            monkeypatch.setitem(sys.modules, key, None)
    for stub in (
        "winrt", "winrt.windows", "winrt.windows.media", "winrt.windows.media.ocr",
        "winrt.windows.globalization", "winrt.windows.graphics",
        "winrt.windows.graphics.imaging", "winrt.windows.storage",
        "winrt.windows.storage.streams",
        "winsdk", "winsdk.windows", "winsdk.windows.media",
        "winsdk.windows.media.ocr", "winsdk.windows.globalization",
        "winsdk.windows.graphics", "winsdk.windows.graphics.imaging",
        "winsdk.windows.storage", "winsdk.windows.storage.streams",
    ):
        monkeypatch.setitem(sys.modules, stub, None)

    import importlib
    import zh_en_translator.engines.ocr.windows_ocr as win_mod
    importlib.reload(win_mod)

    assert win_mod.is_available() is False


def test_has_chinese_language_returns_false_on_exception(monkeypatch):
    """has_chinese_language() returns False when _imports() raises."""
    import zh_en_translator.engines.ocr.windows_ocr as win_mod

    # Make _imports raise so has_chinese_language returns False gracefully
    monkeypatch.setattr(win_mod, "_imports", lambda: (_ for _ in ()).throw(ImportError("no winrt")))
    assert win_mod.has_chinese_language() is False


def test_has_chinese_language_true_when_zh_available(monkeypatch):
    """has_chinese_language() returns True when OcrEngine lists a zh-* language."""
    import zh_en_translator.engines.ocr.windows_ocr as win_mod

    fake_lang = MagicMock()
    fake_lang.language_tag = "zh-Hans-CN"
    fake_engine_cls = MagicMock()
    fake_engine_cls.get_available_recognizer_languages.return_value = [fake_lang]

    _extra = [MagicMock()] * 7
    monkeypatch.setattr(win_mod, "_imports", lambda: (fake_engine_cls, *_extra))
    assert win_mod.has_chinese_language() is True


def test_has_chinese_language_false_when_no_zh(monkeypatch):
    """has_chinese_language() returns False when no zh-* language is in the list."""
    import zh_en_translator.engines.ocr.windows_ocr as win_mod

    fake_lang = MagicMock()
    fake_lang.language_tag = "en-US"
    fake_engine_cls = MagicMock()
    fake_engine_cls.get_available_recognizer_languages.return_value = [fake_lang]

    _extra = [MagicMock()] * 7
    monkeypatch.setattr(win_mod, "_imports", lambda: (fake_engine_cls, *_extra))
    assert win_mod.has_chinese_language() is False


# ---------------------------------------------------------------------------
# tesseract_ocr.py — availability test
# ---------------------------------------------------------------------------

def test_tesseract_not_available_without_binary(monkeypatch):
    """is_available() returns False when the tesseract binary is not found."""
    fake_pytesseract = types.ModuleType("pytesseract")
    # Simulate the binary not being found
    fake_pytesseract.get_tesseract_version = MagicMock(
        side_effect=Exception("tesseract not found")
    )
    monkeypatch.setitem(sys.modules, "pytesseract", fake_pytesseract)

    import importlib
    import zh_en_translator.engines.ocr.tesseract_ocr as tess_mod
    importlib.reload(tess_mod)

    assert tess_mod.is_available() is False


# ---------------------------------------------------------------------------
# paddle_ocr.py — availability test
# ---------------------------------------------------------------------------

def test_paddle_not_available_without_package(monkeypatch):
    """is_available() returns False when paddleocr package is not installed."""
    monkeypatch.setitem(sys.modules, "paddleocr", None)

    import importlib
    import zh_en_translator.engines.ocr.paddle_ocr as paddle_mod
    importlib.reload(paddle_mod)

    assert paddle_mod.is_available() is False
