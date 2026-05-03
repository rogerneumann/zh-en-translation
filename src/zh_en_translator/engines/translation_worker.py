"""Shared background workers for zh→en sentence translation and pinyin lookup."""

from __future__ import annotations
import logging
import re
import concurrent.futures

from PyQt6.QtCore import QThread, pyqtSignal

logger = logging.getLogger(__name__)

_ARGOS_TIMEOUT_S = 8  # seconds before the Argos/MT call is considered hung

# Heuristic thresholds for clause-level fallback decision
_ADAPTIVE_LENGTH_THRESHOLD = 80  # chars: short text rarely needs clause-level
_ADAPTIVE_MIN_TOKENS = 5  # if source has fewer content tokens, skip clause fallback


def _count_clauses(text: str) -> int:
    """Count Chinese clause-ending punctuation markers.

    Counts occurrences of Chinese sentence-ending punctuation (。！？；)
    to estimate the number of clauses in the text.

    Args:
        text: Chinese text to analyze.

    Returns:
        Number of clause-ending punctuation marks (0 = no clauses, 1 = single clause,
        2+ = multi-clause).
    """
    if not text:
        return 0
    clause_marks = "。！？；"
    return sum(1 for char in text if char in clause_marks)


def _count_content_tokens(text: str) -> int:
    """Count content tokens in Chinese text using quick heuristic.

    Uses jieba basic segmentation and filters out stop words to count
    only meaningful tokens (nouns, verbs, key terms). This is a fast
    heuristic without full dictionary lookup.

    Args:
        text: Chinese text to analyze.

    Returns:
        Count of non-stop-word tokens (fast approximation).
    """
    if not text or not text.strip():
        return 0

    # Stop words: common particles and grammar markers with no content meaning
    stop_words = {
        "的", "了", "和", "是", "在", "有", "被", "把", "给", "向", "跟", "比",
        "对", "于", "从", "到", "为", "因为", "所以", "如果", "但是", "或", "及",
        "不", "没", "无", "很", "太", "非常", "特别", "这", "那", "这个", "那个",
        "我", "你", "他", "她", "它", "们", "一", "二", "三", "四", "五", "六",
        "七", "八", "九", "十", "百", "千", "万", "亿", ",", ".", "、", "，",
        "。", "；", "！", "？", ":", "：", '"', "'", """, """, "'", "'",
    }

    try:
        from zh_en_translator.engines.segmentation import segment
        tokens = segment(text)
        # Filter out stop words and empty tokens
        content_tokens = [t for t in tokens if t.strip() and t not in stop_words]
        return len(content_tokens)
    except Exception as e:
        logger.debug("Failed to count content tokens: %s (using fallback)", e)
        # Fallback: rough approximation based on text length
        # (Chinese characters are mostly content-bearing)
        return len([c for c in text if ord(c) >= 0x4E00 and ord(c) <= 0x9FFF])


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


_SENTENCE_FINAL = frozenset("。！？；.!?;")
_BULLET_CHARS = frozenset("•·*►▶‣◦")
_NUMBERED_RE = re.compile(
    r'^(\d+[.)）]|[①②③④⑤⑥⑦⑧⑨⑩]|[一二三四五六七八九十]+[、.]|\([一二三四五六七八九十\d]+\))\s*'
)
_TAB_RE = re.compile(r'^\t|^ {4}')


def _classify_line(line: str) -> str:
    stripped = line.lstrip()
    if not stripped:
        return "empty"
    if stripped[0] in _BULLET_CHARS or stripped[0] == '-':
        return "bullet"
    if _NUMBERED_RE.match(stripped):
        return "numbered"
    if _TAB_RE.match(line):
        return "indented"
    if stripped[0] == '>':
        return "quote"
    return "text"


def _ends_sentence(line: str) -> bool:
    stripped = line.rstrip()
    return bool(stripped) and stripped[-1] in _SENTENCE_FINAL


def _soft_join(a: str, b: str) -> str:
    """Join two soft-wrapped lines, adding a space only at ASCII boundaries."""
    if a and ord(a[-1]) < 128:
        return a + ' ' + b
    return a + b


def _segment_source_text(text: str) -> list:
    """Split source text into translatable segments preserving structure.

    Returns a list of dicts with keys:
      text      - content to translate (prefix stripped)
      type      - "text", "bullet", "numbered", "indented", "quote"
      prefix    - original prefix to restore (e.g. "• ", "1. ")
      separator - string to append after translated segment in output
    """
    lines = text.split('\n')
    segments = []
    current_lines = []
    pending_separator = ''

    def flush_text(sep=''):
        nonlocal pending_separator
        if current_lines:
            if len(current_lines) == 1:
                joined = current_lines[0]
            else:
                joined = current_lines[0]
                for i in range(1, len(current_lines)):
                    if current_lines[i - 1] and ord(current_lines[i - 1][-1]) < 128:
                        joined += ' ' + current_lines[i]
                    else:
                        joined += current_lines[i]
            segments.append({
                'text': joined,
                'type': 'text',
                'prefix': '',
                'separator': pending_separator or sep,
            })
            current_lines.clear()
        pending_separator = ''

    for line in lines:
        line_type = _classify_line(line)

        if line_type == 'empty':
            flush_text('\n\n')
            pending_separator = '\n\n'
            continue

        if line_type in ('bullet', 'numbered', 'indented', 'quote'):
            flush_text('\n')
            stripped = line.lstrip()
            prefix = ''
            content = stripped
            if line_type == 'bullet':
                prefix = stripped[0] + ' '
                content = stripped[1:].lstrip()
            elif line_type == 'numbered':
                m = _NUMBERED_RE.match(stripped)
                if m:
                    prefix = m.group(0)
                    content = stripped[m.end():]
            segments.append({
                'text': content,
                'type': line_type,
                'prefix': prefix,
                'separator': '\n',
            })
            continue

        # Regular text line
        if current_lines and _ends_sentence(current_lines[-1]):
            flush_text('\n')
        current_lines.append(line)

    flush_text('')
    # Fix last segment: strip trailing separator
    if segments:
        segments[-1]['separator'] = segments[-1]['separator'].rstrip('\n')

    return segments


class TranslationWorker(QThread):
    """Background thread: translates text and emits the result.

    Uses Azure Translator (MS Cloud) when enabled and configured, with
    automatic fallback to the local Argos offline engine on any failure.
    Includes adaptive orchestration (Phase 3) to optimize completeness vs. speed.
    """

    result_ready = pyqtSignal(str)

    def __init__(self, text: str, config=None):
        super().__init__()
        self.text = text
        self.config = config  # Config | None

    def _should_use_clause_fallback(self, text: str) -> bool:
        """Decide whether to attempt clause-level translation fallback.

        Uses structural heuristics on the source text to determine if clause-level
        splitting is likely to help:
        - Text length < 80 chars: short text rarely needs clause-level splitting
        - Clause count <= 1: no complex clause structure to split
        - Content token count < 5: too simple to benefit from splitting

        Args:
            text: Original Chinese text.

        Returns:
            True if clause-level fallback should be attempted, False otherwise.
        """
        # Short text rarely needs clause-level splitting
        if len(text) < _ADAPTIVE_LENGTH_THRESHOLD:
            logger.debug(
                "Skipping clause fallback (short: %d chars < %d)",
                len(text),
                _ADAPTIVE_LENGTH_THRESHOLD,
            )
            return False

        # No complex clause structure to split
        clause_count = _count_clauses(text)
        if clause_count <= 1:
            logger.debug(
                "Skipping clause fallback (single clause: %d)",
                clause_count,
            )
            return False

        # Too simple to benefit from splitting
        token_count = _count_content_tokens(text)
        if token_count < _ADAPTIVE_MIN_TOKENS:
            logger.debug(
                "Skipping clause fallback (few tokens: %d < %d)",
                token_count,
                _ADAPTIVE_MIN_TOKENS,
            )
            return False

        logger.debug(
            "Using clause fallback (complex: %d chars, %d clauses, %d tokens)",
            len(text),
            clause_count,
            token_count,
        )
        return True

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

    def _translate_one(self, text: str) -> str:
        # 1. Try DeepL first if enabled
        if self.config and self.config.deepl_enabled:
            from zh_en_translator.engines.deepl import translate_with_deepl
            result = translate_with_deepl(text, self.config)
            if result and not result.startswith("⚠") and _is_valid_translation(result, text):
                logger.info("Translation path: DeepL")
                return result
            logger.warning("DeepL translation failed or not configured correctly: %s", result)

        # 2. Try Google Translate second
        if self.config and self.config.google_translate_enabled:
            from zh_en_translator.engines.google_translate import translate_with_google
            result = translate_with_google(text, self.config)
            if result and not result.startswith("\u26a0") and _is_valid_translation(result, text):
                logger.info("Translation path: Google Translate")
                return result
            logger.warning("Google Translate failed or not configured correctly: %s", result)

        # 3. Try MS Cloud third
        if self.config and self.config.ms_translator_enabled:
            from zh_en_translator.engines.ms_cloud import (
                is_configured,
                translate_sentence as ms_translate,
            )
            if is_configured(self.config.ms_translator_api_key):
                result = ms_translate(
                    text,
                    self.config.ms_translator_api_key,
                    self.config.ms_translator_region,
                )
                if result and _is_valid_translation(result, text):
                    logger.info("Translation path: MS Cloud")
                    return result
                logger.warning(
                    "MS Cloud translation failed or returned source unchanged"
                    " -- falling back to Argos"
                )

        # 4. Offline fallback: local Argos / ctranslate2 (with timeout)
        from zh_en_translator.engines.argos import is_available, translate_sentence

        if not is_available():
            logger.info("Translation path: none (Argos model not installed)")
            return (
                "\u26a0 Offline translation model not installed. "
                "Enable cloud translation in Preferences \u203a Cloud, "
                "or re-run the installer and select Full install to download the model."
            )

        result = None
        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(translate_sentence, text)
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

        if result and _is_valid_translation(result, text):
            logger.info("Translation path: Argos")
            if self.config and self.config.clause_fallback_enabled:
                if self._should_use_clause_fallback(text):
                    logger.info("Complex input detected, attempting clause-level fallback")
                    result = self._apply_clause_fallback(text, result)
            return result

        if result:
            logger.warning(
                "Argos returned source text unchanged — falling back to dict-only result"
            )
        else:
            logger.warning(
                "Argos translation returned empty/None result -- falling back to dict-only"
            )

        logger.info("Translation path: dict-only")
        return "(no translation found)"

    def run(self):
        logger.info("Translation started (input length: %d chars)", len(self.text))
        segments = _segment_source_text(self.text)

        if len(segments) <= 1:
            result = self._translate_one(self.text)
            self.result_ready.emit(result)
            return

        parts = []
        for seg in segments:
            translated = self._translate_one(seg['text']) if seg['text'].strip() else ''
            parts.append(seg['prefix'] + translated + seg['separator'])

        result = ''.join(parts).rstrip('\n')
        self.result_ready.emit(result)


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
            from zh_en_translator.engines.glossary import load_all_glossaries

            cedict_path = ensure_cedict()
            db_path = cedict_path.with_suffix(".db")
            if not db_path.exists():
                Dictionary.build_from_cedict(cedict_path, db_path)
            dictionary = Dictionary(db_path)

            try:
                glossary = load_all_glossaries()
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
