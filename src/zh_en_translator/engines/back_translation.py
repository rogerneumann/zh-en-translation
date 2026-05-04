"""Back-translation quality validation worker.

After each zh->en translation, translates the English result back to Chinese
using the best available engine, then compares the back-translation against
the original Chinese using CER and content-word coverage to produce a
confidence score and human-readable label.

Engine priority for en->zh: DeepL > Google > Azure > LibreTranslate > Argos en->zh.
This is independent of which engine produced the forward translation.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from PyQt6.QtCore import QThread, pyqtSignal

from zh_en_translator.evaluation.metrics import cer as _cer

if TYPE_CHECKING:
    from zh_en_translator.config import Config

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Confidence thresholds
# ---------------------------------------------------------------------------

_CER_GREEN = 0.25    # CER below this qualifies for green (if coverage also OK)
_CER_RED   = 0.45    # CER above this always red
_COV_GREEN = 0.75    # content-word coverage required for green
_COV_AMBER = 0.50    # minimum coverage before forcing amber

# Stop words used to filter content tokens (mirrors translation_worker.py)
_STOP_WORDS: frozenset[str] = frozenset({
    "\u7684", "\u4e86", "\u548c", "\u662f", "\u5728", "\u6709", "\u88ab",
    "\u628a", "\u7ed9", "\u5411", "\u8ddf", "\u6bd4", "\u5bf9", "\u4e8e",
    "\u4ece", "\u5230", "\u4e3a", "\u56e0\u4e3a", "\u6240\u4ee5",
    "\u5982\u679c", "\u4f46\u662f", "\u6216", "\u53ca",
    "\u4e0d", "\u6ca1", "\u65e0", "\u5f88", "\u592a", "\u975e\u5e38",
    "\u7279\u522b", "\u8fd9", "\u90a3", "\u8fd9\u4e2a", "\u90a3\u4e2a",
    "\u6211", "\u4f60", "\u4ed6", "\u5979", "\u5b83", "\u4eec",
    "\u4e00", "\u4e8c", "\u4e09", "\u56db", "\u4e94", "\u516d",
    "\u4e03", "\u516b", "\u4e5d", "\u5341", "\u767e", "\u5343",
    "\u4e07", "\u4ebf",
    ",", ".", "\u3001", "\uff0c", "\u3002", "\uff1b", "\uff01", "\uff1f",
    ":", "\uff1a", '"', "'", "\u201c", "\u201d", "\u2018", "\u2019",
})


# ---------------------------------------------------------------------------
# Pure functions (testable without Qt)
# ---------------------------------------------------------------------------

def compute_confidence(cer_score: float, coverage: float) -> float:
    """Combine CER and content-word coverage into a 0-1 confidence score."""
    return max(0.0, min(1.0, (1.0 - cer_score) * 0.6 + coverage * 0.4))


def confidence_to_label(confidence: float) -> tuple[str, str]:
    """Return (hex_colour, tooltip_text) for a confidence value.

    confidence < 0 means the quality check was unavailable.
    """
    if confidence < 0:
        return "#9CA3AF", "Quality check unavailable"
    if confidence >= 0.75:
        return "#22C55E", "High confidence"
    if confidence >= 0.50:
        return "#F59E0B", "May be incomplete"
    return "#EF4444", "Low confidence \u2014 review recommended"


def content_word_coverage(zh_original: str, zh_back: str) -> float:
    """Fraction of content words from zh_original present in zh_back.

    Segments zh_original, filters stop words, then checks each content
    token as a substring of zh_back. Returns 1.0 if no content words found.
    """
    if not zh_original or not zh_back:
        return 0.0

    try:
        from zh_en_translator.engines.segmentation import segment
        tokens = segment(zh_original)
    except Exception:
        # Fallback: split into individual characters
        tokens = list(zh_original)

    content = [t for t in tokens if t.strip() and t not in _STOP_WORDS and len(t) > 1]
    if not content:
        return 1.0  # no content words to check -> neutral

    hits = sum(1 for t in content if t in zh_back)
    return hits / len(content)


# ---------------------------------------------------------------------------
# BackTranslationWorker
# ---------------------------------------------------------------------------

class BackTranslationWorker(QThread):
    """Translate English back to Chinese and emit a confidence result.

    Signals:
        back_translation_ready(zh_back, confidence, colour, tooltip):
            zh_back    -- back-translated Chinese string (empty if unavailable)
            confidence -- float 0-1, or -1.0 if no engine available
            colour     -- hex colour string for the quality badge
            tooltip    -- plain-language label for hover tooltip
            engine     -- name of engine used, or "" if none
    """

    back_translation_ready = pyqtSignal(str, float, str, str, str)

    def __init__(self, en_text: str, zh_original: str, config: "Config",
                 parent=None):
        super().__init__(parent)
        self._en_text = en_text
        self._zh_original = zh_original
        self._config = config

    def run(self) -> None:
        zh_back, engine = self._translate_en_to_zh(self._en_text)

        if zh_back is None:
            colour, tooltip = confidence_to_label(-1.0)
            self.back_translation_ready.emit("", -1.0, colour, tooltip, "")
            return

        cer_score = _cer(zh_back, self._zh_original)
        coverage  = content_word_coverage(self._zh_original, zh_back)
        confidence = compute_confidence(cer_score, coverage)
        colour, tooltip = confidence_to_label(confidence)

        logger.debug(
            "back-translation: CER=%.3f coverage=%.3f confidence=%.3f engine=%s",
            cer_score, coverage, confidence, engine,
        )
        self.back_translation_ready.emit(zh_back, confidence, colour, tooltip, engine)

    def _translate_en_to_zh(self, text: str) -> tuple[str | None, str]:
        """Try each engine in priority order. Returns (result, engine_name)."""
        cfg = self._config

        # 1. DeepL
        if cfg.deepl_enabled and cfg.deepl_api_key:
            try:
                from zh_en_translator.engines.deepl import translate_with_deepl
                result = translate_with_deepl(
                    text, cfg, source_lang="EN", target_lang="ZH"
                )
                if result and not result.startswith("\u26a0"):
                    return result, "DeepL"
            except Exception as exc:
                logger.debug("DeepL back-translation failed: %s", exc)

        # 2. Google
        if cfg.google_translate_enabled and cfg.google_translate_api_key:
            try:
                from zh_en_translator.engines.google_translate import translate_with_google
                result = translate_with_google(
                    text, cfg, source="en", target="zh-CN"
                )
                if result and not result.startswith("\u26a0"):
                    return result, "Google"
            except Exception as exc:
                logger.debug("Google back-translation failed: %s", exc)

        # 3. Azure
        if cfg.ms_translator_enabled and cfg.ms_translator_api_key:
            try:
                from zh_en_translator.engines.ms_cloud import translate_sentence
                result = translate_sentence(
                    text, cfg.ms_translator_api_key, cfg.ms_translator_region,
                    from_lang="en", to_lang="zh-Hans",
                )
                if result:
                    return result, "Azure"
            except Exception as exc:
                logger.debug("Azure back-translation failed: %s", exc)

        # 4. LibreTranslate
        if cfg.libretranslate_enabled:
            try:
                from zh_en_translator.engines.libretranslate import translate_with_libretranslate
                result = translate_with_libretranslate(
                    text, cfg, source="en", target="zh"
                )
                if result and not result.startswith("\u26a0"):
                    return result, "LibreTranslate"
            except Exception as exc:
                logger.debug("LibreTranslate back-translation failed: %s", exc)

        # 5. Argos en->zh (offline)
        try:
            from zh_en_translator.engines.argos import translate_en_to_zh, is_en_zh_available
            if is_en_zh_available():
                result = translate_en_to_zh(text)
                if result:
                    return result, "Argos"
        except Exception as exc:
            logger.debug("Argos en->zh back-translation failed: %s", exc)

        return None, ""
