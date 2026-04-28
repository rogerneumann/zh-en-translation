"""Windows.Media.Ocr engine — tries winrt namespace packages first, then winsdk."""

from __future__ import annotations


def _imports():
    """
    Return (OcrEngine, Language, SoftwareBitmap, BitmapPixelFormat,
            BitmapAlphaMode, BitmapDecoder, DataWriter, InMemoryRandomAccessStream)
    trying winrt namespace packages (pywinrt, pre-built wheels) first,
    then winsdk (requires C compiler to build from source).

    Raises ImportError if neither is available.
    """
    try:
        from winrt.windows.media.ocr import OcrEngine
        from winrt.windows.globalization import Language
        from winrt.windows.graphics.imaging import (
            SoftwareBitmap,
            BitmapPixelFormat,
            BitmapAlphaMode,
            BitmapDecoder,
        )
        from winrt.windows.storage.streams import DataWriter, InMemoryRandomAccessStream
        return (OcrEngine, Language, SoftwareBitmap, BitmapPixelFormat,
                BitmapAlphaMode, BitmapDecoder, DataWriter, InMemoryRandomAccessStream)
    except ImportError:
        pass

    # Fallback: winsdk (older, requires build from source on Python 3.14)
    from winsdk.windows.media.ocr import OcrEngine
    from winsdk.windows.globalization import Language
    from winsdk.windows.graphics.imaging import (
        SoftwareBitmap,
        BitmapPixelFormat,
        BitmapAlphaMode,
        BitmapDecoder,
    )
    from winsdk.windows.storage.streams import DataWriter, InMemoryRandomAccessStream
    return (OcrEngine, Language, SoftwareBitmap, BitmapPixelFormat,
            BitmapAlphaMode, BitmapDecoder, DataWriter, InMemoryRandomAccessStream)


def is_available() -> bool:
    """Return True if winrt/winsdk is accessible AND a Chinese OCR recogniser is installed.

    Both conditions must hold for this engine to be useful in the zh->en pipeline.
    """
    try:
        _imports()
        return has_chinese_language()
    except ImportError:
        return False


def ocr_status() -> dict:
    """Return a dict describing Windows OCR availability for Chinese.

    Keys:
        api       (bool) -- winrt or winsdk package is importable
        chinese   (bool) -- at least one zh-* OCR recogniser is installed
    """
    try:
        _imports()
        api = True
    except ImportError:
        return {"api": False, "chinese": False}
    return {"api": api, "chinese": has_chinese_language()}


def has_chinese_language() -> bool:
    """Return True if a Chinese OCR language pack is available in Windows."""
    try:
        (OcrEngine, Language, *_) = _imports()
        available = list(OcrEngine.get_available_recognizer_languages())
        return any(lang.language_tag.startswith("zh") for lang in available)
    except Exception:
        return False


def ocr_image(image_bytes: bytes, lang: str = "zh") -> str | None:
    """
    Run Windows.Media.Ocr on the given image bytes.

    Uses asyncio.run() to execute the async WinRT API synchronously.
    lang "zh" tries "zh-Hans-CN" then "zh-Hant-TW" then any zh-* language.
    Returns the concatenated recognized text lines, or None on failure.
    """
    try:
        import asyncio
        (OcrEngine, Language, SoftwareBitmap, BitmapPixelFormat,
         BitmapAlphaMode, BitmapDecoder, DataWriter, InMemoryRandomAccessStream) = _imports()

        async def _run_ocr() -> str | None:
            engine = None
            if lang == "zh":
                for lang_tag in ("zh-Hans-CN", "zh-Hant-TW"):
                    candidate = Language(lang_tag)
                    if OcrEngine.is_language_supported(candidate):
                        engine = OcrEngine.try_create_from_language(candidate)
                        if engine:
                            break

                if engine is None:
                    for avail_lang in OcrEngine.get_available_recognizer_languages():
                        if avail_lang.language_tag.startswith("zh"):
                            engine = OcrEngine.try_create_from_language(avail_lang)
                            if engine:
                                break
            else:
                candidate = Language(lang)
                if OcrEngine.is_language_supported(candidate):
                    engine = OcrEngine.try_create_from_language(candidate)

            if engine is None:
                return None

            stream = InMemoryRandomAccessStream()
            writer = DataWriter(stream)
            writer.write_bytes(image_bytes)
            await writer.store_async()
            await writer.flush_async()
            stream.seek(0)

            decoder = await BitmapDecoder.create_async(stream)
            software_bitmap = await decoder.get_software_bitmap_async(
                BitmapPixelFormat.BGRA8,
                BitmapAlphaMode.PREMULTIPLIED,
            )

            result = await engine.recognize_async(software_bitmap)
            if result is None:
                return None

            lines = [line.text for line in result.lines]
            return "\n".join(lines).strip() or None

        return asyncio.run(_run_ocr())
    except Exception:
        return None
