"""Windows.Media.Ocr engine via winsdk."""

from __future__ import annotations


def is_available() -> bool:
    """Return True if winsdk is installed and Windows OCR is accessible."""
    try:
        from winsdk.windows.media.ocr import OcrEngine  # noqa: F401
        from winsdk.windows.globalization import Language  # noqa: F401
        return True
    except ImportError:
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
        from winsdk.windows.media.ocr import OcrEngine
        from winsdk.windows.globalization import Language
        from winsdk.windows.graphics.imaging import (
            SoftwareBitmap,
            BitmapPixelFormat,
            BitmapAlphaMode,
            BitmapDecoder,
        )
        from winsdk.windows.storage.streams import (
            DataWriter,
            InMemoryRandomAccessStream,
        )

        async def _run_ocr() -> str | None:
            # Determine language
            engine = None
            if lang == "zh":
                for lang_tag in ("zh-Hans-CN", "zh-Hant-TW"):
                    candidate = Language(lang_tag)
                    if OcrEngine.is_language_supported(candidate):
                        engine = OcrEngine.try_create_from_language(candidate)
                        if engine:
                            break

                if engine is None:
                    # Try any available zh-* language
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

            # Load image bytes into an InMemoryRandomAccessStream
            stream = InMemoryRandomAccessStream()
            writer = DataWriter(stream)
            writer.write_bytes(image_bytes)
            await writer.store_async()
            await writer.flush_async()
            stream.seek(0)

            # Decode to SoftwareBitmap
            decoder = await BitmapDecoder.create_async(stream)
            software_bitmap = await decoder.get_software_bitmap_async(
                BitmapPixelFormat.BGRA8,
                BitmapAlphaMode.PREMULTIPLIED,
            )

            # Run OCR
            result = await engine.recognize_async(software_bitmap)
            if result is None:
                return None

            lines = [line.text for line in result.lines]
            return "\n".join(lines).strip() or None

        return asyncio.run(_run_ocr())
    except Exception:
        return None
