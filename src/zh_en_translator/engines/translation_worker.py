"""Shared background workers for zh→en sentence translation and pinyin lookup."""

from __future__ import annotations
import logging

from PyQt6.QtCore import QThread, pyqtSignal

logger = logging.getLogger(__name__)


class TranslationWorker(QThread):
    """Background thread: translates text and emits the result.

    Uses Azure Translator (MS Cloud) when enabled and configured, with
    automatic fallback to the local Argos offline engine on any failure.
    """

    result_ready = pyqtSignal(str)

    def __init__(self, text: str, config=None):
        super().__init__()
        self.text = text
        self.config = config  # Config | None

    def run(self):
        logger.debug("input (%d chars): %r", len(self.text), self.text[:80])

        # Try MS Cloud first when the user has explicitly enabled it
        if self.config and self.config.ms_translator_enabled:
            from zh_en_translator.engines.ms_cloud import is_configured, translate_sentence as ms_translate
            if is_configured(self.config.ms_translator_api_key):
                result = ms_translate(
                    self.text,
                    self.config.ms_translator_api_key,
                    self.config.ms_translator_region,
                )
                if result:
                    logger.debug("ms_cloud result: %r", result[:80])
                    self.result_ready.emit(result)
                    return
                logger.warning("MS Cloud translation failed — falling back to Argos")

        # Offline fallback: local Argos / ctranslate2
        from zh_en_translator.engines.argos import ensure_pack, translate_sentence

        if not ensure_pack():
            logger.warning("ensure_pack() failed")
            self.result_ready.emit("⚠ Translation model not available.")
            return

        try:
            result = translate_sentence(self.text)
            logger.debug("result: %r", result)
        except Exception as e:
            logger.debug("exception: %s", e)
            result = None

        self.result_ready.emit(
            result if result else f"(no translation — input: {self.text[:60]!r})"
        )


class PinyinWorker(QThread):
    """Background thread: runs pipeline.translate() and emits a pinyin string."""

    result_ready = pyqtSignal(str)

    def __init__(self, text: str):
        super().__init__()
        self.text = text

    def run(self):
        try:
            from zh_en_translator.engines.dictionary import Dictionary, ensure_cedict
            from zh_en_translator.engines import pipeline

            cedict_path = ensure_cedict()
            db_path = cedict_path.with_suffix(".db")
            if not db_path.exists():
                Dictionary.build_from_cedict(cedict_path, db_path)
            dictionary = Dictionary(db_path)

            try:
                results = pipeline.translate(self.text, dictionary)
                pinyin_str = " ".join(
                    r.pinyin if r.pinyin else r.token for r in results
                )
            finally:
                dictionary.close()

            self.result_ready.emit(pinyin_str)
        except Exception as exc:
            logger.debug("PinyinWorker failed: %s", exc)
            self.result_ready.emit("")
