"""Chinese text segmentation with pluggable backends.

Supported backends (in priority order when auto-selecting):
  - jieba: fast, dictionary-based, good general accuracy (~81.6% F1)
  - pkuseg: statistical model, better on technical/domain text (~82.3% F1)
  - fallback: character-run grouping (no third-party dependency)

The active segmenter is chosen by calling ``set_segmenter(name)`` or by
passing a ``segmenter`` name to ``segment()``.  The module-level default is
``"jieba"`` for backwards compatibility.
"""

import logging
from pathlib import Path

try:
    import jieba

    jieba.setLogLevel(logging.WARNING)
    _JIEBA_AVAILABLE = True
except ImportError:
    _JIEBA_AVAILABLE = False

try:
    import spacy_pkuseg as _pkuseg_module

    _PKUSEG_AVAILABLE = True
except ImportError:
    _PKUSEG_AVAILABLE = False

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level segmenter state
# ---------------------------------------------------------------------------

# Name of the currently active segmenter backend ("jieba", "pkuseg", "fallback")
_active_segmenter: str = "jieba"

# Cached pkuseg instance (created lazily; creation is expensive ~0.5 s)
_pkuseg_instance = None


def set_segmenter(name: str) -> None:
    """Set the active segmenter backend for subsequent ``segment()`` calls.

    Args:
        name: One of ``"jieba"``, ``"pkuseg"``, or ``"fallback"``.
              If the requested backend is unavailable it falls back gracefully
              (pkuseg -> jieba -> fallback).

    Raises:
        ValueError: If *name* is not a recognised backend identifier.
    """
    global _active_segmenter
    valid = {"jieba", "pkuseg", "fallback"}
    if name not in valid:
        raise ValueError(f"Unknown segmenter '{name}'; choose one of {sorted(valid)}")

    if name == "pkuseg" and not _PKUSEG_AVAILABLE:
        logger.warning(
            "pkuseg requested but spacy-pkuseg is not installed; falling back to jieba"
        )
        name = "jieba" if _JIEBA_AVAILABLE else "fallback"

    if name == "jieba" and not _JIEBA_AVAILABLE:
        logger.warning("jieba requested but not installed; falling back to character-run segmenter")
        name = "fallback"

    _active_segmenter = name
    logger.info("Segmenter set to: %s", _active_segmenter)


def get_segmenter() -> str:
    """Return the name of the currently active segmenter backend."""
    return _active_segmenter


def _get_pkuseg() -> object:
    """Return (and lazily initialise) the shared pkuseg instance."""
    global _pkuseg_instance
    if _pkuseg_instance is None:
        if not _PKUSEG_AVAILABLE:
            raise RuntimeError("spacy-pkuseg is not installed")
        logger.debug("Initialising pkuseg segmenter (first use may be slow)")
        _pkuseg_instance = _pkuseg_module.pkuseg()
    return _pkuseg_instance


def load_user_dict(dict_path: str | Path) -> None:
    """Load a user dictionary into jieba for domain-specific terms.

    Args:
        dict_path: Path to user dictionary file. Expected format: one term per line,
                   optionally with frequency and POS tag (tab-separated).
                   Example: 激光模块\t10\tn
    """
    if not _JIEBA_AVAILABLE:
        logger.warning("jieba not available; user dictionary ignored")
        return

    dict_path = Path(dict_path)
    if not dict_path.exists():
        logger.warning("user dictionary not found: %s", dict_path)
        return

    try:
        jieba.load_userdict(str(dict_path))
        logger.info("loaded user dictionary from %s", dict_path)
    except Exception as e:
        logger.error("failed to load user dictionary: %s", e)


def add_custom_words(words: list[tuple[str, int, str]] | list[str]) -> None:
    """Add custom words to jieba vocabulary.

    Args:
        words: List of words (strings) or tuples of (word, frequency, pos_tag).
               Example: [('激光模块', 10, 'n'), ('手板样机', 8, 'n')]
    """
    if not _JIEBA_AVAILABLE:
        logger.warning("jieba not available; custom words ignored")
        return

    for word_data in words:
        if isinstance(word_data, str):
            jieba.add_word(word_data)
        elif isinstance(word_data, tuple) and len(word_data) >= 1:
            jieba.add_word(word_data[0], freq=word_data[1] if len(word_data) > 1 else None,
                          tag=word_data[2] if len(word_data) > 2 else None)


# ---------------------------------------------------------------------------
# Backend-specific segment helpers
# ---------------------------------------------------------------------------


def _segment_jieba(text: str) -> list[str]:
    """Segment using jieba (must be available)."""
    return [tok for tok in jieba.cut(text, cut_all=False) if tok]


def _segment_pkuseg(text: str) -> list[str]:
    """Segment Chinese text using pkuseg statistical model.

    For non-Chinese spans (ASCII, digits, punctuation) pkuseg sometimes merges
    them unexpectedly, so we pre-split on Chinese / non-Chinese boundaries,
    run pkuseg only on the Chinese portions, and reassemble.

    Args:
        text: Text to segment.

    Returns:
        List of tokens (empty strings filtered out).
    """
    seg = _get_pkuseg()

    # Split into Chinese and non-Chinese runs so ASCII words are preserved
    result: list[str] = []
    current_chinese: list[str] = []
    current_non_chinese: list[str] = []

    def _flush_chinese() -> None:
        if current_chinese:
            chunk = "".join(current_chinese)
            result.extend(tok for tok in seg.cut(chunk) if tok)
            current_chinese.clear()

    def _flush_non_chinese() -> None:
        if current_non_chinese:
            result.append("".join(current_non_chinese))
            current_non_chinese.clear()

    for char in text:
        cp = ord(char)
        is_chinese = (0x4E00 <= cp <= 0x9FFF) or (0x3400 <= cp <= 0x4DBF)
        if is_chinese:
            _flush_non_chinese()
            current_chinese.append(char)
        else:
            _flush_chinese()
            current_non_chinese.append(char)

    _flush_chinese()
    _flush_non_chinese()
    return result



def _segment_fallback(text: str) -> list[str]:
    """
    Segment Chinese text using greedy left-to-right character consumption.

    Groups consecutive Chinese characters into tokens, and groups non-Chinese
    characters (ASCII, punctuation, spaces) into their own tokens.

    This is the fallback used when jieba is not installed.

    Args:
        text: Text to segment.

    Returns:
        List of tokens.
    """
    if not text:
        return []

    # Chinese ranges: CJK Unified Ideographs (U+4E00-U+9FFF)
    # CJK Unified Ideographs Extension A (U+3400-U+4DBF)
    result = []
    current_chinese = []
    current_non_chinese = []

    for char in text:
        code_point = ord(char)
        is_chinese = (0x4E00 <= code_point <= 0x9FFF) or (0x3400 <= code_point <= 0x4DBF)

        if is_chinese:
            # Accumulate Chinese characters
            if current_non_chinese:
                # Flush non-Chinese before adding Chinese
                result.append("".join(current_non_chinese))
                current_non_chinese = []
            current_chinese.append(char)
        else:
            # Accumulate non-Chinese characters
            if current_chinese:
                # Flush Chinese before adding non-Chinese
                result.append("".join(current_chinese))
                current_chinese = []
            current_non_chinese.append(char)

    # Flush any remaining tokens
    if current_chinese:
        result.append("".join(current_chinese))
    if current_non_chinese:
        result.append("".join(current_non_chinese))

    return result


def segment(text: str, segmenter: str | None = None) -> list[str]:
    """Segment Chinese text into tokens using the configured backend.

    Uses the module-level active segmenter (set via ``set_segmenter()``) unless
    *segmenter* is given explicitly for this call.

    Backends:
    - ``"jieba"`` -- fast dictionary-based segmentation (default).
    - ``"pkuseg"`` -- statistical model; better on technical/domain text.
    - ``"fallback"`` -- character-run grouping; no third-party dependency.

    When a requested backend is unavailable the function degrades gracefully:
    pkuseg -> jieba -> fallback.

    Args:
        text: Text to segment.
        segmenter: Override the active backend for this call only.
                   One of ``"jieba"``, ``"pkuseg"``, or ``"fallback"``.

    Returns:
        List of tokens (empty strings filtered out).
    """
    if not text:
        return []

    backend = segmenter if segmenter is not None else _active_segmenter

    if backend == "pkuseg":
        if _PKUSEG_AVAILABLE:
            try:
                return _segment_pkuseg(text)
            except Exception as exc:
                logger.warning("pkuseg segmentation failed (%s); falling back to jieba", exc)
        else:
            logger.debug("pkuseg not available; falling back to jieba")
        backend = "jieba"  # fall through

    if backend == "jieba":
        if _JIEBA_AVAILABLE:
            return _segment_jieba(text)
        logger.debug("jieba not available; falling back to character-run segmenter")

    return _segment_fallback(text)
