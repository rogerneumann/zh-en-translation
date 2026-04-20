"""Translation pipeline: segmentation + dictionary lookup."""

from dataclasses import dataclass

from zh_en_translator.engines.dictionary import Dictionary
from zh_en_translator.engines.segmentation import segment


@dataclass
class TokenResult:
    """Result for a single token after segmentation and lookup."""

    token: str
    pinyin: str | None  # None for non-Chinese tokens
    glosses: list[str]  # Empty list for unknown or non-Chinese tokens
    is_chinese: bool


def translate(text: str, dictionary: Dictionary) -> list[TokenResult]:
    """
    Segment text and look up each Chinese token in the dictionary.

    Uses greedy longest-match for multi-character words.

    Args:
        text: Text to translate.
        dictionary: Dictionary instance for lookup.

    Returns:
        List of TokenResult for each token.
    """
    tokens = segment(text)
    results = []

    for token in tokens:
        # Check if token is Chinese
        is_chinese = False
        for char in token:
            code_point = ord(char)
            if (0x4E00 <= code_point <= 0x9FFF) or (0x3400 <= code_point <= 0x4DBF):
                is_chinese = True
                break

        if not is_chinese:
            results.append(TokenResult(token, None, [], False))
            continue

        # For Chinese tokens, try greedy longest-match lookup
        # First try the whole token, then progressively shorter prefixes
        best_entries = None
        best_match = None

        for end_pos in range(min(len(token), 12), 0, -1):
            candidate = token[:end_pos]
            entries = dictionary.lookup(candidate)
            if entries:
                best_entries = entries
                best_match = candidate
                break

        if best_entries:
            # Concatenate glosses from all entries
            all_glosses = []
            pinyin = best_entries[0].pinyin  # Use pinyin from first entry
            for entry in best_entries:
                all_glosses.extend(entry.glosses)
            results.append(TokenResult(best_match, pinyin, all_glosses, True))

            # If we only matched part of the token, recursively process the rest
            if best_match and best_match != token:
                remaining = token[len(best_match):]
                for result in translate(remaining, dictionary):
                    results.append(result)
        else:
            # Unknown Chinese token
            results.append(TokenResult(token, None, [], True))

    return results
