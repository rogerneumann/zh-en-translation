"""Chinese text segmentation using max-length matching."""


def segment(text: str) -> list[str]:
    """
    Segment Chinese text using greedy left-to-right character consumption.

    Groups consecutive Chinese characters into tokens, and groups non-Chinese
    characters (ASCII, punctuation, spaces) into their own tokens.

    Note: This is a simple fallback when jieba is unavailable. For better
    multi-character word segmentation, install jieba and use jieba.cut().

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
