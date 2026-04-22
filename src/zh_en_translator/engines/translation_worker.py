"""Shared background workers for zh→en sentence translation and pinyin lookup."""

from __future__ import annotations
import logging
import concurrent.futures

from PyQt6.QtCore import QThread, pyqtSignal

logger = logging.getLogger(__name__)

_ARGOS_TIMEOUT_S = 8  # seconds before the Argos/MT call is considered hung


def _is_valid_translation(result: str, source: str) -> bool:
    """Return True if *result* is a usable translation.

    A result is considered invalid if it is empty or if it is identical to the
    source text (indicating the engine returned the input unchanged).
    """
    if not result or not result.strip():
        return False
    if result.strip() == source.strip():
        return False
    return True


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

    def _apply_validation(self, source: str, translation: str) -> tuple[str, float]:
        """Apply translation validation and recovery pipeline (Phase 1).

        Detects missing content from the source and recovers it using dictionary lookup.

        Args:
            source: Original Chinese text.
            translation: Current English translation from Argos.

        Returns:
            Tuple of (enhanced_translation, completeness_score) where completeness_score
            is between 0.0 and 1.0.
        """
        try:
            from zh_en_translator.engines.dictionary import Dictionary, ensure_cedict
            from zh_en_translator.engines.validation import (
                extract_content_tokens,
                get_translation_completeness_score,
                recover_missing_content,
            )

            # Load dictionary
            cedict_path = ensure_cedict()
            db_path = cedict_path.with_suffix(".db")
            if not db_path.exists():
                Dictionary.build_from_cedict(cedict_path, db_path)
            dictionary = Dictionary(db_path)

            try:
                # Extract content tokens and check completeness
                source_tokens = extract_content_tokens(source, dictionary)
                completeness = get_translation_completeness_score(
                    source_tokens,
                    translation,
                    dictionary,
                )

                if completeness < 0.7:
                    # Recover missing content
                    enhanced = recover_missing_content(
                        source,
                        translation,
                        missing_tokens=None,
                        dictionary=dictionary,
                    )
                    logger.debug(
                        "Phase 1 incomplete (%.1f%%), recovered content",
                        completeness * 100,
                    )
                    return enhanced, completeness
                else:
                    logger.debug("Phase 1 complete (%.1f%%)", completeness * 100)
                    return translation, completeness

            finally:
                dictionary.close()

        except Exception as e:
            logger.warning("Translation validation failed: %s (continuing with original)", e)
            return translation, 0.0

    def _apply_clause_fallback(self, source: str, translation: str) -> str:
        """Apply clause-level translation fallback (Phase 2).

        For incomplete translations, splits into clauses, translates each,
        and recombines intelligently.

        Args:
            source: Original Chinese text.
            translation: Current English translation from Phase 1.

        Returns:
            Enhanced translation with clause-level fallback applied, or original
            if fallback fails.
        """
        try:
            from zh_en_translator.engines.argos import translate_with_clause_fallback

            result = translate_with_clause_fallback(source)
            if result and _is_valid_translation(result, source):
                logger.debug("Phase 2 clause-level fallback succeeded")
                return result
            else:
                logger.debug("Phase 2 clause-level fallback failed or empty result")
                return translation

        except Exception as e:
            logger.warning("Phase 2 clause-level fallback failed: %s", e)
            return translation

    def run(self):
        logger.info("Translation started (input length: %d chars)", len(self.text))

        # 1. Try DeepL first if enabled
        if self.config and self.config.deepl_enabled:
            from zh_en_translator.engines.deepl import translate_with_deepl
            result = translate_with_deepl(self.text, self.config)
            if result and not result.startswith("⚠") and _is_valid_translation(result, self.text):
                logger.info("Translation path: DeepL")
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
                if result and _is_valid_translation(result, self.text):
                    logger.info("Translation path: MS Cloud")
                    self.result_ready.emit(result)
                    return
                logger.warning("MS Cloud translation failed or returned source unchanged — falling back to Argos")

        # 3. Offline fallback: local Argos / ctranslate2 (with timeout)
        from zh_en_translator.engines.argos import ensure_pack, translate_sentence

        if not ensure_pack():
            logger.warning("ensure_pack() failed")
            logger.info("Translation path: dict-only (model unavailable)")
            self.result_ready.emit("⚠ Translation model not available.")
            return

        result = None
        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(translate_sentence, self.text)
                try:
                    result = future.result(timeout=_ARGOS_TIMEOUT_S)
                except concurrent.futures.TimeoutError:
                    logger.warning(
                        "Argos translation timed out after %d s — falling back to dict-only",
                        _ARGOS_TIMEOUT_S,
                    )
                    result = None
        except Exception as e:
            logger.error("Argos translation failed: %s", e)
            result = None

        if result and _is_valid_translation(result, self.text):
            logger.info("Translation path: Argos")
            # Post-process with validation and recovery if enabled
            if self.config and self.config.validation_enabled:
                result, completeness = self._apply_validation(self.text, result)
                # If Phase 1 is still incomplete, try Phase 2 clause-level fallback
                if completeness < 0.7:
                    logger.info("Phase 1 incomplete (%.1f%%), attempting Phase 2", completeness * 100)
                    result = self._apply_clause_fallback(self.text, result)
            self.result_ready.emit(result)
            return

        if result:
            logger.warning(
                "Argos returned source text unchanged — falling back to dict-only result"
            )
        else:
            logger.warning("Argos translation returned empty/None result — falling back to dict-only")

        logger.info("Translation path: dict-only")
        self.result_ready.emit("(no translation found)")


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
