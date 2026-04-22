"""Post-processing validation and recovery for translation completeness.

This module detects missing content in MT-generated translations and recovers it
using word-by-word dictionary lookup and POS tagging.
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Stop words: common particles and grammar markers that don't carry content meaning
_STOP_WORDS = {
    "的", "了", "和", "是", "在", "有", "被", "把", "给", "向", "跟", "比",
    "对", "于", "从", "到", "为", "因为", "所以", "如果", "但是", "或", "及",
    "不", "没", "无", "很", "太", "非常", "特别", "这", "那", "这个", "那个",
    "我", "你", "他", "她", "它", "们", "一", "二", "三", "四", "五", "六",
    "七", "八", "九", "十", "百", "千", "万", "亿"
}


def extract_content_tokens(text: str, dictionary) -> list[str]:
    """Extract meaningful content tokens from Chinese text using POS tagging.

    Filters out stop words (particles, grammar markers) and returns only content
    words (nouns, verbs, adjectives, key terms).

    Args:
        text: Chinese text to extract tokens from.
        dictionary: Dictionary instance for lookups (used for validation).

    Returns:
        List of content token strings (non-empty, meaningful tokens).
    """
    if not text or not text.strip():
        return []

    try:
        import jieba.posseg as pseg
    except ImportError:
        logger.warning("jieba.posseg not available; using fallback token extraction")
        # Fallback: use basic jieba segmentation and filter stop words
        from zh_en_translator.engines.segmentation import segment
        tokens = segment(text)
        return [t for t in tokens if t not in _STOP_WORDS and len(t) > 0]

    # Use POS tagging to filter for content words
    # Roughly: n=noun, v=verb, a=adjective, ad=adverbial, an=numeral, etc.
    content_pos = {"n", "v", "a", "ad", "an", "d"}  # Content-bearing POS tags

    content_tokens = []
    for word, pos in pseg.cut(text):
        # Skip stop words, empty tokens, and grammar particles
        if (
            word.strip()  # Non-empty after strip
            and word not in _STOP_WORDS
            and pos[0] in content_pos  # First char of POS tag indicates content
            and len(word) > 0
        ):
            content_tokens.append(word)

    return content_tokens


def is_translation_complete(
    source_tokens: list[str],
    translation: str,
    dictionary,
) -> bool:
    """Check if all content tokens from source appear (in English) in translation.

    Uses dictionary lookup to get English glosses for each source token and
    checks if those glosses appear in the translation. Returns True if >= 70%
    of source content tokens have English equivalents in the translation.

    Args:
        source_tokens: Content tokens extracted from source Chinese.
        translation: English translation output to validate.
        dictionary: Dictionary instance for lookups.

    Returns:
        True if >= 70% of source tokens are covered in translation, else False.
    """
    if not source_tokens:
        return True  # No content to check; consider complete

    if not translation or not translation.strip():
        return False  # Empty translation; not complete

    translation_lower = translation.lower()
    found_count = 0

    for token in source_tokens:
        # Lookup token in dictionary to get English glosses
        entries = dictionary.lookup(token)
        if not entries:
            continue

        # Check if any gloss appears in the translation
        found = False
        for entry in entries:
            if not entry.glosses:
                continue
            for gloss in entry.glosses:
                gloss_lower = gloss.lower()
                # Check if gloss (or a substring) appears in translation
                if gloss_lower in translation_lower:
                    found_count += 1
                    found = True
                    break  # Count this token as found (once per token)
            if found:
                break

    completeness_ratio = found_count / len(source_tokens) if source_tokens else 0.0
    logger.debug(
        "Translation completeness check: %d/%d tokens found (%.1f%%)",
        found_count,
        len(source_tokens),
        completeness_ratio * 100,
    )
    return completeness_ratio >= 0.7


def recover_missing_content(
    source: str,
    translation: str,
    missing_tokens: Optional[list[str]] = None,
    dictionary=None,
) -> str:
    """Recover missing content from source and insert into translation intelligently.

    If missing_tokens is not provided, extracts content tokens from source and
    identifies which ones are missing from the translation. Then looks up their
    English equivalents and inserts them into the translation (preferably at
    sentence end or before punctuation).

    Args:
        source: Original Chinese text.
        translation: Current English translation.
        missing_tokens: Optional list of tokens known to be missing. If None,
                       they will be detected automatically.
        dictionary: Dictionary instance for lookups.

    Returns:
        Enhanced translation string with recovered content inserted.
    """
    if not dictionary:
        logger.warning("No dictionary provided for recovery")
        return translation

    if not translation or not translation.strip():
        return translation  # No translation to enhance

    # Determine which tokens are missing
    if missing_tokens is None:
        source_tokens = extract_content_tokens(source, dictionary)
        if not source_tokens:
            return translation  # No content tokens to check

        translation_lower = translation.lower()
        missing_tokens = []
        for token in source_tokens:
            entries = dictionary.lookup(token)
            # Check if any gloss appears in translation
            found = False
            for entry in entries:
                if entry.glosses:
                    for gloss in entry.glosses:
                        if gloss.lower() in translation_lower:
                            found = True
                            break
                if found:
                    break
            if not found:
                missing_tokens.append(token)

    if not missing_tokens:
        return translation  # Nothing to recover

    # Recover English translations for missing tokens
    recovered_glosses = []
    for token in missing_tokens:
        entries = dictionary.lookup(token)
        if entries and entries[0].glosses:
            # Use first gloss from first entry
            recovered_glosses.append(entries[0].glosses[0])

    if not recovered_glosses:
        return translation  # No glosses to insert

    # Insert recovered content into translation
    recovered_text = ", ".join(recovered_glosses)

    # Try to insert at the end of the translation before final punctuation
    translation_stripped = translation.rstrip()
    final_char_idx = len(translation_stripped) - 1

    # Check if ends with punctuation
    if final_char_idx >= 0 and translation_stripped[final_char_idx] in ".!?;:":
        # Insert before final punctuation
        enhanced = (
            translation_stripped[:final_char_idx]
            + " "
            + recovered_text
            + translation_stripped[final_char_idx:]
        )
    else:
        # Append at end
        enhanced = translation_stripped + ". " + recovered_text + "."

    logger.debug("Recovered missing content: %s", recovered_text)
    return enhanced
