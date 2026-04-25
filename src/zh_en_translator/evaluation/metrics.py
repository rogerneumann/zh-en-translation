"""Translation quality metrics.

Provides lightweight, dependency-free metrics for evaluating Chinese-to-English
translation quality.  These are designed to run without NLTK, sacrebleu, or
any ML library -- just the Python standard library.

Metrics
-------
bleu_approx(hypothesis, reference)
    Simplified BLEU score (1-gram through 4-gram precision with brevity penalty).
    Not identical to sacrebleu, but correlates well for comparing configurations.

cer(hypothesis, reference)
    Character Error Rate: edit distance / len(reference).
    Lower is better; 0.0 is perfect.

token_overlap(hypothesis, source_terms)
    Fraction of ``source_terms`` that appear verbatim in ``hypothesis``.
    Useful for checking that glossary terms are preserved in the output.

glossary_coverage(hypothesis, glossary)
    For each (zh, en) pair in ``glossary``, check whether the English value
    appears in the hypothesis.  Returns fraction of glossary terms covered.

score_translation(hypothesis, reference, glossary, source_terms)
    Convenience wrapper: compute all metrics and return a TranslationMetrics
    dataclass.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Sequence


# ---------------------------------------------------------------------------
# Tokenisation helpers
# ---------------------------------------------------------------------------


def _tokenize(text: str) -> list[str]:
    """Simple whitespace + punctuation tokeniser."""
    # Lower-case, split on whitespace and common punctuation
    text = text.lower()
    tokens = re.findall(r"[a-z0-9]+", text)
    return tokens


def _ngrams(tokens: list[str], n: int) -> list[tuple[str, ...]]:
    return [tuple(tokens[i : i + n]) for i in range(len(tokens) - n + 1)]


# ---------------------------------------------------------------------------
# BLEU approximation
# ---------------------------------------------------------------------------


def bleu_approx(hypothesis: str, reference: str, max_n: int = 4) -> float:
    """Return an approximate BLEU score in [0, 1].

    This implementation follows the original Papineni et al. formulation:
    - Modified n-gram precision for n=1..max_n
    - Brevity penalty for short hypotheses
    - Geometric mean of precisions

    Args:
        hypothesis: The machine-translated output.
        reference:  The reference (human) translation.
        max_n:      Maximum n-gram order (default 4).

    Returns:
        Float in [0, 1]; 0 = no overlap, 1 = perfect match.
    """
    hyp_tokens = _tokenize(hypothesis)
    ref_tokens = _tokenize(reference)

    if not hyp_tokens or not ref_tokens:
        return 0.0

    log_sum = 0.0
    valid_orders = 0

    for n in range(1, max_n + 1):
        hyp_ngrams = _ngrams(hyp_tokens, n)
        ref_ngrams = _ngrams(ref_tokens, n)

        if not hyp_ngrams or not ref_ngrams:
            continue

        ref_counts = Counter(ref_ngrams)
        hyp_counts = Counter(hyp_ngrams)

        clipped = sum(min(cnt, ref_counts[ng]) for ng, cnt in hyp_counts.items())
        total = sum(hyp_counts.values())

        if total == 0 or clipped == 0:
            # Any zero precision kills BLEU; use a tiny floor to avoid -inf
            log_sum += -9999
        else:
            log_sum += math.log(clipped / total)
        valid_orders += 1

    if valid_orders == 0:
        return 0.0

    # Brevity penalty
    bp = 1.0 if len(hyp_tokens) >= len(ref_tokens) else math.exp(
        1 - len(ref_tokens) / len(hyp_tokens)
    )

    score = bp * math.exp(log_sum / valid_orders)
    return max(0.0, min(1.0, score))


# ---------------------------------------------------------------------------
# Character Error Rate
# ---------------------------------------------------------------------------


def cer(hypothesis: str, reference: str) -> float:
    """Return the Character Error Rate (CER).

    CER = edit_distance(hypothesis, reference) / len(reference)

    CER of 0.0 means perfect match.  CER > 1.0 is possible when the
    hypothesis is much longer than the reference.

    Args:
        hypothesis: The machine-translated output (lowercased internally).
        reference:  The reference translation.

    Returns:
        Float >= 0; lower is better.
    """
    h = hypothesis.lower().strip()
    r = reference.lower().strip()

    if not r:
        return 0.0 if not h else float(len(h))

    # Levenshtein distance (Wagner-Fischer DP)
    m, n = len(h), len(r)
    dp = list(range(n + 1))
    for i in range(1, m + 1):
        prev = dp[0]
        dp[0] = i
        for j in range(1, n + 1):
            temp = dp[j]
            if h[i - 1] == r[j - 1]:
                dp[j] = prev
            else:
                dp[j] = 1 + min(prev, dp[j], dp[j - 1])
            prev = temp

    return dp[n] / n


# ---------------------------------------------------------------------------
# Token overlap
# ---------------------------------------------------------------------------


def token_overlap(hypothesis: str, source_terms: Sequence[str]) -> float:
    """Fraction of ``source_terms`` that appear in ``hypothesis``.

    Used to check whether the output contains expected terms (e.g. glossary
    English equivalents).

    Args:
        hypothesis:   The machine-translated output.
        source_terms: Terms to look for (case-insensitive substring match).

    Returns:
        Float in [0, 1]; 1.0 = all terms found, 0.0 = none found.
        Returns 1.0 when ``source_terms`` is empty.
    """
    if not source_terms:
        return 1.0

    h_lower = hypothesis.lower()
    found = sum(1 for term in source_terms if term.lower() in h_lower)
    return found / len(source_terms)


# ---------------------------------------------------------------------------
# Glossary coverage
# ---------------------------------------------------------------------------


def glossary_coverage(hypothesis: str, glossary: dict[str, str]) -> float:
    """Fraction of glossary English translations appearing in ``hypothesis``.

    For each ``{chinese: english}`` pair in *glossary*, check whether the
    English value (or any slash-separated variant) appears in ``hypothesis``.

    Args:
        hypothesis: The machine-translated output.
        glossary:   Dict of ``{chinese: english}`` term mappings.

    Returns:
        Float in [0, 1].  1.0 = all glossary translations present.
        Returns 1.0 when *glossary* is empty.
    """
    if not glossary:
        return 1.0

    h_lower = hypothesis.lower()
    found = 0
    for english in glossary.values():
        # Handle "primary / alternative" style entries
        variants = [v.strip().lower() for v in english.split("/")]
        if any(v in h_lower for v in variants if v):
            found += 1

    return found / len(glossary)


# ---------------------------------------------------------------------------
# Composite score
# ---------------------------------------------------------------------------


@dataclass
class TranslationMetrics:
    """Aggregated quality metrics for a single translation."""

    hypothesis: str
    reference: str = ""

    bleu: float = 0.0          # BLEU approximation [0, 1]; higher is better
    cer_score: float = 0.0     # Character Error Rate; lower is better
    token_overlap_score: float = 0.0   # Term overlap [0, 1]; higher is better
    glossary_coverage_score: float = 0.0  # Glossary coverage [0, 1]

    # Tracking extras
    source_terms: list[str] = field(default_factory=list)
    glossary: dict[str, str] = field(default_factory=dict)

    def summary(self) -> str:
        """Return a human-readable one-line summary."""
        return (
            f"BLEU={self.bleu:.3f} | CER={self.cer_score:.3f} | "
            f"TermOverlap={self.token_overlap_score:.3f} | "
            f"GlossaryCov={self.glossary_coverage_score:.3f}"
        )

    def to_dict(self) -> dict:
        return {
            "hypothesis": self.hypothesis,
            "reference": self.reference,
            "bleu": round(self.bleu, 4),
            "cer": round(self.cer_score, 4),
            "token_overlap": round(self.token_overlap_score, 4),
            "glossary_coverage": round(self.glossary_coverage_score, 4),
        }


def score_translation(
    hypothesis: str,
    reference: str = "",
    glossary: dict[str, str] | None = None,
    source_terms: list[str] | None = None,
) -> TranslationMetrics:
    """Compute all available metrics for a single translation.

    Args:
        hypothesis:    The machine-translated output.
        reference:     Reference translation (if available; empty string skips
                       BLEU and CER computation).
        glossary:      Dict of ``{chinese: english}`` for glossary coverage.
        source_terms:  English terms expected in the output (for token overlap).

    Returns:
        A populated :class:`TranslationMetrics` dataclass.
    """
    if glossary is None:
        glossary = {}
    if source_terms is None:
        source_terms = []

    bleu_score = bleu_approx(hypothesis, reference) if reference else 0.0
    cer_score = cer(hypothesis, reference) if reference else 0.0
    tok_overlap = token_overlap(hypothesis, source_terms)
    gl_coverage = glossary_coverage(hypothesis, glossary)

    return TranslationMetrics(
        hypothesis=hypothesis,
        reference=reference,
        bleu=bleu_score,
        cer_score=cer_score,
        token_overlap_score=tok_overlap,
        glossary_coverage_score=gl_coverage,
        source_terms=list(source_terms),
        glossary=dict(glossary),
    )
