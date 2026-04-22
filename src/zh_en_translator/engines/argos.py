"""Offline Chinese→English translation via ctranslate2 + sentencepiece.

Calls ctranslate2 and sentencepiece directly from the installed argostranslate
pack, bypassing argostranslate.translate which hard-imports stanza (and stanza
requires downloading Chinese NLP models that are unavailable on restricted networks).
"""

from __future__ import annotations
import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)


def _find_pack_dir() -> Path | None:
    """
    Locate the installed zh→en ctranslate2 pack directory.

    Uses argostranslate.settings (which does NOT import stanza) to find the
    correct platform-specific packages directory.
    """
    try:
        import argostranslate.settings
        package_dirs = argostranslate.settings.package_dirs
    except Exception:
        return None

    for pkg_dir in package_dirs:
        pkg_path = Path(pkg_dir)
        if not pkg_path.exists():
            continue
        for d in pkg_path.iterdir():
            if d.is_dir() and "zh_en" in d.name:
                model_dir = d / "model"
                spm_file = d / "sentencepiece.model"
                if (model_dir / "model.bin").exists() and spm_file.exists():
                    return d
    return None


def is_available() -> bool:
    """Return True if the zh→en pack and required libraries are present."""
    if _find_pack_dir() is None:
        return False
    try:
        import ctranslate2  # noqa: F401
        import sentencepiece  # noqa: F401
        return True
    except ImportError:
        return False


def ensure_pack() -> bool:
    """
    Ensure the zh→en pack is ready to use.

    Returns True immediately if already installed. Falls back to downloading
    via argostranslate.package (requires internet for one-time ~100 MB download).
    """
    if is_available():
        return True

    try:
        import argostranslate.package

        argostranslate.package.update_package_index()
        available = argostranslate.package.get_available_packages()
        pkg = next(
            (p for p in available if p.from_code == "zh" and p.to_code == "en"),
            None,
        )
        if not pkg:
            return False
        path = pkg.download()
        argostranslate.package.install_from_path(path)
        return is_available()
    except Exception:
        return False


def translate_sentence(text: str) -> str | None:
    """
    Translate Chinese text to English.

    Uses ctranslate2 + sentencepiece directly — no stanza, no network calls.
    Returns the translated string, or None on failure.
    """
    if not text.strip():
        return None

    pack_dir = _find_pack_dir()
    if not pack_dir:
        logger.debug("pack directory not found")
        return None

    try:
        import ctranslate2
        import sentencepiece as spm

        model_dir = str(pack_dir / "model")
        spm_path = str(pack_dir / "sentencepiece.model")

        logger.debug("model: %s", pack_dir.name)

        translator = ctranslate2.Translator(model_dir, device="cpu")
        sp_model = spm.SentencePieceProcessor()
        sp_model.Load(spm_path)

        tokens = sp_model.encode(text, out_type=str)
        logger.debug("encoded %d tokens", len(tokens))

        results = translator.translate_batch([tokens])
        target_tokens = results[0].hypotheses[0]

        translation = sp_model.decode(target_tokens)
        # Sentencepiece ▁ (U+2581) marks word boundaries; strip from decoded output
        translation = translation.replace("\u2581", " ").strip()
        # Collapse any double-spaces left by the substitution
        while "  " in translation:
            translation = translation.replace("  ", " ")
        logger.debug("translation successful (length: %d chars)", len(translation))

        return translation if translation else None

    except Exception as e:
        logger.debug("exception: %s", e)
        logger.debug("traceback", exc_info=True)
        return None


def split_into_clauses(text: str, max_clause_length: int = 60) -> list[str]:
    """Split Chinese text into clauses by clause-ending punctuation.

    Splits on: 。！？；
    Protects edge cases (numbers like "200ppm", URLs, emails, @mentions).
    Keeps punctuation with clauses (e.g., "完成。" not "完成" + "。").
    If a clause exceeds max_clause_length, splits further by commas (，).

    Args:
        text: Chinese text to split.
        max_clause_length: Maximum characters per clause before splitting on comma.

    Returns:
        List of clause strings (may be empty if text is empty).

    Example:
        "NADCC氯片测试已完成。实验室今天提供给@杨中宝。"
        -> ["NADCC氯片测试已完成。", "实验室今天提供给@杨中宝。"]
    """
    if not text or not text.strip():
        return []

    # Regex to protect patterns that shouldn't be split:
    # - Numbers like "200ppm" (digit + letters, no split after digit)
    # - @ mentions like "@杨中宝" (@ followed by Chinese)
    # - URLs and emails (simplified; may contain : and .)
    # Strategy: split on clause punctuation (。！？；) but with lookbehind/lookahead
    # to avoid splitting inside protected patterns.

    # Find all clause-ending punctuation with their positions
    clause_punctuation = r'[。！？；]'

    # Build list of matches with positions
    clauses = []
    current_pos = 0

    for match in re.finditer(clause_punctuation, text):
        end_pos = match.end()
        clause = text[current_pos:end_pos]

        # If clause is within max length, keep it as-is
        if len(clause) <= max_clause_length:
            clauses.append(clause)
        else:
            # Split long clause by comma (，) but keep comma with preceding text
            sub_clauses = _split_long_clause(clause, max_clause_length)
            clauses.extend(sub_clauses)

        current_pos = end_pos

    # Add any remaining text (may not end with punctuation)
    if current_pos < len(text):
        remainder = text[current_pos:]
        if remainder.strip():
            if len(remainder) <= max_clause_length:
                clauses.append(remainder)
            else:
                sub_clauses = _split_long_clause(remainder, max_clause_length)
                clauses.extend(sub_clauses)

    return clauses


def _split_long_clause(clause: str, max_length: int) -> list[str]:
    """Split a long clause by commas (，) while keeping commas with preceding text.

    Args:
        clause: A clause string (possibly already ending with punctuation).
        max_length: Maximum length per sub-clause.

    Returns:
        List of sub-clauses.
    """
    # Find comma positions
    comma_pos = []
    for match in re.finditer(r'[，]', clause):
        comma_pos.append(match.start())

    if not comma_pos:
        # No commas to split on, return as-is
        return [clause]

    # Split by commas, keeping comma with preceding text
    sub_clauses = []
    current_pos = 0

    for comma_idx in comma_pos:
        # Include text up to and including the comma
        sub_clause = clause[current_pos : comma_idx + 1]
        if sub_clause.strip():
            sub_clauses.append(sub_clause)
        current_pos = comma_idx + 1

    # Add remaining text after last comma
    remainder = clause[current_pos:]
    if remainder.strip():
        sub_clauses.append(remainder)

    # If we still have empty or minimal sub-clauses, return original
    if not sub_clauses:
        return [clause]

    return sub_clauses


def _recombine_translations(
    original: str,
    clauses: list[str],
    translations: list[str],
) -> str:
    """Recombine translated clauses with original punctuation and proper grammar.

    Preserves original clause punctuation (。→., ！→!, ？→?, ；→;).
    Joins clauses with appropriate English conjunctions:
    - After 。(period): start new sentence (capitalize next)
    - After ， (comma): join with ", "
    - After ； (semicolon): join with "; "

    Cleans up spacing and ensures grammatical correctness.

    Args:
        original: Original Chinese text (for reference, not directly used).
        clauses: List of original Chinese clauses (with punctuation).
        translations: List of English translations (one per clause).

    Returns:
        Recombined English text with proper punctuation and spacing.

    Example:
        Original: "测试。实验。"
        Clauses: ["测试。", "实验。"]
        Translations: ["Test completed.", "Experiment."]
        Result: "Test completed. Experiment."
    """
    if not clauses or not translations:
        return ""

    # Ensure we have same number of translations as clauses
    # Pad with empty strings if needed
    translations = translations + [""] * (len(clauses) - len(translations))

    result_parts = []

    for i, (clause, translation) in enumerate(zip(clauses, translations)):
        if not translation or not translation.strip():
            # Skip empty translations
            continue

        trans = translation.strip()

        # Determine punctuation from original clause
        if clause and clause[-1] in "。！？；":
            clause_punct = clause[-1]
        else:
            clause_punct = None

        # Map Chinese punctuation to English
        punct_map = {
            "。": ".",
            "！": "!",
            "？": "?",
            "；": ";",
        }

        # Remove trailing punctuation from translation if present
        # (we'll add the correct English equivalent)
        trans_stripped = trans.rstrip(".!?;:")

        # Add the appropriate English punctuation
        if clause_punct and clause_punct in punct_map:
            trans_with_punct = trans_stripped + punct_map[clause_punct]
        elif trans_stripped and not trans_stripped.endswith((".", "!", "?", ";")):
            # Default to period if no original punctuation and none in translation
            trans_with_punct = trans_stripped + "."
        else:
            trans_with_punct = trans_stripped

        result_parts.append(trans_with_punct)

    # Join parts with appropriate spacing
    if not result_parts:
        return ""

    # Join with space, ensuring proper sentence separation
    result = " ".join(result_parts)

    # Clean up multiple spaces
    while "  " in result:
        result = result.replace("  ", " ")

    # Capitalize first letter if needed
    if result and result[0].islower():
        result = result[0].upper() + result[1:]

    return result


def translate_with_clause_fallback(text: str) -> str | None:
    """Translate with automatic clause-level fallback when single-pass fails.

    First attempts a single-pass Argos translation (faster, simpler).
    If that succeeds and is non-empty, returns it immediately.
    If single-pass fails or returns empty, falls back to clause-level translation:
    - Split into clauses
    - Translate each clause separately
    - Recombine with proper punctuation and grammar

    Args:
        text: Chinese text to translate.

    Returns:
        Translated English string, or None on complete failure.
    """
    if not text or not text.strip():
        return None

    # Step 1: Try single-pass translation
    logger.debug("Attempting single-pass translation")
    result = translate_sentence(text)

    if result and result.strip():
        logger.debug("Single-pass translation successful, skipping clause-level fallback")
        return result

    # Step 2: Fall back to clause-level translation
    logger.debug("Single-pass translation failed or empty, attempting clause-level fallback")

    clauses = split_into_clauses(text)
    if not clauses:
        logger.debug("No clauses extracted, returning None")
        return None

    logger.debug("Split into %d clauses", len(clauses))

    # Translate each clause
    clause_translations = []
    for i, clause in enumerate(clauses):
        clause_result = translate_sentence(clause)
        if clause_result:
            clause_translations.append(clause_result)
            logger.debug("Clause %d translated: %s -> %s", i, clause, clause_result)
        else:
            # If translation fails for a clause, use empty string
            clause_translations.append("")
            logger.debug("Clause %d translation failed: %s", i, clause)

    # Recombine translations
    recombined = _recombine_translations(text, clauses, clause_translations)

    if recombined and recombined.strip():
        logger.debug("Clause-level translation successful (length: %d)", len(recombined))
        return recombined

    logger.debug("Clause-level translation produced empty result")
    return None
