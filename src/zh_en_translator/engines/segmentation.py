"""Chinese text segmentation using jieba (preferred) with character-run fallback."""

import logging

try:
    import jieba

    jieba.setLogLevel(logging.WARNING)
    _JIEBA_AVAILABLE = True
except ImportError:
    _JIEBA_AVAILABLE = False


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


def segment(text: str) -> list[str]:
    """
    Segment Chinese text into tokens.

    Uses jieba for accurate word segmentation when available; falls back to
    character-run grouping when jieba is not installed.

    Args:
        text: Text to segment.

    Returns:
        List of tokens (empty strings filtered out).
    """
    if not text:
        return []

    if _JIEBA_AVAILABLE:
        return [tok for tok in jieba.cut(text, cut_all=False) if tok]

    return _segment_fallback(text)
