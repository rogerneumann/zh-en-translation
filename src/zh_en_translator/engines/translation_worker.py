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
        logger.info("Translation started (input length: %d chars)", len(self.text))

        # 1. Try DeepL first if enabled
        if self.config and self.config.deepl_enabled:
            from zh_en_translator.engines.deepl import translate_with_deepl
            result = translate_with_deepl(self.text, self.config)
            if result and not result.startswith("⚠"):
                logger.info("DeepL translation successful (result length: %d chars)", len(result))
                self.result_ready.emit(result)
                return
            logger.warning("DeepL translation failed or not configured correctly: %s", result)

        # 2. Try MS Cloud second
        if self.config and self.config.ms_translator_enabled:
            from zh_en_translator.engines.ms_cloud import is_configured, translate_sentence as ms_translate
            if is_configured(self.config.ms_translator_api_key):
                result = ms_translate(
                    self.text,
                    self.config.ms_translator_api_key,
                    self.config.ms_translator_region,
                )
                if result:
                    logger.info("ms_cloud translation successful (result length: %d chars)", len(result))
                    self.result_ready.emit(result)
                    return
                logger.warning("MS Cloud translation failed — falling back to Argos")

        # 3. Offline fallback: local Argos / ctranslate2
        from zh_en_translator.engines.argos import ensure_pack, translate_sentence

        if not ensure_pack():
            logger.warning("ensure_pack() failed")
            self.result_ready.emit("⚠ Translation model not available.")
            return

        try:
            result = translate_sentence(self.text)
            if result:
                logger.info("Argos translation successful (result length: %d chars)", len(result))
            else:
                logger.warning("Argos translation returned empty result")
        except Exception as e:
            logger.error("Argos translation failed: %s", e)
            result = None

        self.result_ready.emit(
            result if result else "(no translation found)"
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
            from zh_en_translator.engines.glossary import load_glossary

            cedict_path = ensure_cedict()
            db_path = cedict_path.with_suffix(".db")
            if not db_path.exists():
                Dictionary.build_from_cedict(cedict_path, db_path)
            dictionary = Dictionary(db_path)

            try:
                glossary = load_glossary()
                results = pipeline.translate(self.text, dictionary, glossary=glossary)
                pinyin_str = " ".join(
                    r.pinyin if r.pinyin else r.token for r in results
                )
            finally:
                dictionary.close()

            self.result_ready.emit(pinyin_str)
        except Exception as exc:
            logger.debug("PinyinWorker failed: %s", exc)
            self.result_ready.emit("")
