"""Translation pipeline: segmentation + dictionary lookup."""

from dataclasses import dataclass

from zh_en_translator.engines.dictionary import Dictionary
from zh_en_translator.engines.segmentation import segment


def translate_to_string(
    text: str,
    glossary: dict[str, str] | None = None,
    dictionary: "Dictionary | None" = None,
    separator: str = " | ",
) -> str:
    """Translate *text* and return a flat English string.

    Convenience wrapper around :func:`translate` for A/B testing and
    evaluation.  Each token's best gloss is joined with *separator*.

    If no *dictionary* is provided the function attempts to load the bundled
    CC-CEDICT SQLite database (requires the ``cedict`` resource to be present).

    Args:
        text:       Chinese source text.
        glossary:   Optional ``{zh: en}`` override dict.
        dictionary: Pre-opened :class:`Dictionary` instance.  When ``None``
                    the bundled database is loaded on first call.
        separator:  String used to join per-token translations.

    Returns:
        English translation string, or an empty string on failure.
    """
    _dict = dictionary
    _owns_dict = False
    try:
        if _dict is None:
            from zh_en_translator.engines.dictionary import Dictionary, ensure_cedict
            cedict_path = ensure_cedict()
            db_path = cedict_path.with_suffix(".db")
            if not db_path.exists():
                Dictionary.build_from_cedict(cedict_path, db_path)
            _dict = Dictionary(db_path)
            _owns_dict = True

        results = translate(text, _dict, glossary=glossary)
        parts = []
        for r in results:
            if r.glosses:
                parts.append(r.glosses[0])
            elif not r.is_chinese:
                parts.append(r.token)
            # Unknown Chinese tokens are omitted (no English gloss)
        return separator.join(p for p in parts if p.strip())
    except Exception:
        return ""
    finally:
        if _owns_dict and _dict is not None:
            _dict.close()


@dataclass
class TokenResult:
    """Result for a single token after segmentation and lookup."""

    token: str
    pinyin: str | None  # None for non-Chinese tokens
    glosses: list[str]  # Empty list for unknown or non-Chinese tokens
    is_chinese: bool


def translate(
    text: str,
    dictionary: Dictionary,
    glossary: dict[str, str] | None = None,
) -> list[TokenResult]:
    """
    Segment text and look up each Chinese token in the dictionary.

    Uses greedy longest-match for multi-character words. If a glossary is
    provided, glossary entries take precedence over dictionary lookups for
    exact token matches.

    Args:
        text: Text to translate.
        dictionary: Dictionary instance for lookup.
        glossary: Optional {zh: en} dict of user-defined term overrides.

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

        # Glossary override: if the token matches a user-defined term, use it
        if glossary and token in glossary:
            results.append(TokenResult(token, None, [glossary[token]], True))
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
                for result in translate(remaining, dictionary, glossary):
                    results.append(result)
        else:
            # Unknown Chinese token
            results.append(TokenResult(token, None, [], True))

    return results
