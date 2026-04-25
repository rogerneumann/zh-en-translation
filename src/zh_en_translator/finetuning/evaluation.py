"""Fine-tuning evaluation utilities.

Provides functions for measuring BLEU improvement of a fine-tuned model
versus the Argos baseline, using the metrics already implemented in
``zh_en_translator.evaluation.metrics``.

All functions in this module are CPU-only and do not require PyTorch or
OpenNMT-py.  They operate on pre-computed translation strings, so they
can be used both for the data-pipeline tests (no GPU) and for the GPU
training session's final evaluation pass.

Functions
---------
evaluate_finetuned_model(translations, corpus) -> EvalResult
    Compute BLEU + CER + glossary coverage for a set of translations
    against a reference corpus.

compute_bleu_improvement(baseline, finetuned) -> float
    Compute the absolute BLEU improvement: finetuned.bleu - baseline.bleu.

compare_models(baseline_translations, finetuned_translations, corpus)
    Side-by-side comparison of two model outputs.

Usage::

    from zh_en_translator.finetuning.evaluation import (
        evaluate_finetuned_model, compute_bleu_improvement,
    )

    # After generating translations with both models:
    baseline_result = evaluate_finetuned_model(baseline_translations, test_corpus)
    finetuned_result = evaluate_finetuned_model(finetuned_translations, test_corpus)
    improvement = compute_bleu_improvement(baseline_result, finetuned_result)
    print(f"BLEU improvement: +{improvement:.4f} ({improvement * 100:.1f} BLEU pts)")
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from zh_en_translator.evaluation.metrics import bleu_approx, cer

if TYPE_CHECKING:
    from zh_en_translator.corpus.corpus_manager import CorpusEntry

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# EvalResult dataclass
# ---------------------------------------------------------------------------


@dataclass
class EvalResult:
    """Aggregated evaluation metrics for one model on one test corpus.

    Attributes
    ----------
    bleu:
        Mean sentence-level BLEU on 0-1 scale across all test pairs.
        Multiply by 100 for the conventional BLEU score.
    cer:
        Mean Character Error Rate (lower is better).
    glossary_coverage:
        Fraction of expected manufacturing terms appearing correctly
        in the translations.  Computed only if a glossary is provided.
    n_sentences:
        Number of sentences evaluated.
    model_name:
        Identifier for the model that produced these translations.
    sentence_bleus:
        Per-sentence BLEU scores (same order as input).
    """

    bleu: float = 0.0
    cer: float = 0.0
    glossary_coverage: float = 0.0
    n_sentences: int = 0
    model_name: str = ""
    sentence_bleus: list[float] = field(default_factory=list)

    def summary(self) -> str:
        return (
            f"[{self.model_name or 'model'}] "
            f"BLEU={self.bleu:.4f} ({self.bleu * 100:.1f}), "
            f"CER={self.cer:.4f}, "
            f"GlossaryCov={self.glossary_coverage:.2%}, "
            f"n={self.n_sentences}"
        )


# ---------------------------------------------------------------------------
# evaluate_finetuned_model
# ---------------------------------------------------------------------------


def evaluate_finetuned_model(
    translations: list[str],
    corpus: list["CorpusEntry"],
    model_name: str = "",
    glossary: dict[str, str] | None = None,
) -> EvalResult:
    """Compute evaluation metrics for *translations* against *corpus*.

    Args:
        translations: List of hypothesis translations produced by the model,
                      one per entry in *corpus*.  Must be the same length.
        corpus:       List of ``CorpusEntry`` objects providing reference
                      translations (``entry.english``).
        model_name:   Label for the model (used in summary output).
        glossary:     Optional ``{chinese: english}`` dict of manufacturing
                      terms.  Used for glossary coverage metric.

    Returns:
        ``EvalResult`` with aggregated metrics.

    Raises:
        ValueError: If ``len(translations) != len(corpus)`` or either is empty.

    Example::

        result = evaluate_finetuned_model(
            translations=["Hardness after heat treatment meets GB/T"],
            corpus=[entry],        # CorpusEntry with .english reference
            model_name="argos_base",
        )
        print(result.summary())
    """
    if len(translations) != len(corpus):
        raise ValueError(
            f"translations ({len(translations)}) and corpus ({len(corpus)}) "
            f"must have the same length"
        )
    if not translations:
        raise ValueError("translations list is empty")

    sentence_bleus: list[float] = []
    sentence_cers: list[float] = []
    glossary_hits = 0
    glossary_total = 0

    for hyp, entry in zip(translations, corpus):
        ref = entry.english
        b = bleu_approx(hyp, ref)
        c = cer(hyp, ref)
        sentence_bleus.append(b)
        sentence_cers.append(c)

        # Glossary coverage: check that English values appear in hypothesis
        if glossary:
            for zh_term, en_term in glossary.items():
                if zh_term in entry.chinese:
                    glossary_total += 1
                    if en_term.lower() in hyp.lower():
                        glossary_hits += 1

    mean_bleu = sum(sentence_bleus) / len(sentence_bleus)
    mean_cer = sum(sentence_cers) / len(sentence_cers)
    g_coverage = (glossary_hits / glossary_total) if glossary_total > 0 else 0.0

    result = EvalResult(
        bleu=mean_bleu,
        cer=mean_cer,
        glossary_coverage=g_coverage,
        n_sentences=len(translations),
        model_name=model_name,
        sentence_bleus=sentence_bleus,
    )
    logger.info("evaluate_finetuned_model: %s", result.summary())
    return result


# ---------------------------------------------------------------------------
# compute_bleu_improvement
# ---------------------------------------------------------------------------


def compute_bleu_improvement(
    baseline: EvalResult,
    finetuned: EvalResult,
) -> float:
    """Compute absolute BLEU improvement of fine-tuned vs. baseline.

    Args:
        baseline:  ``EvalResult`` from the base (pre-fine-tuned) model.
        finetuned: ``EvalResult`` from the fine-tuned model.

    Returns:
        Absolute BLEU improvement on the 0-1 scale.  Multiply by 100
        for conventional BLEU points.  Positive = improvement.

    Example::

        delta = compute_bleu_improvement(baseline_result, finetuned_result)
        print(f"+{delta * 100:.1f} BLEU points")
    """
    improvement = finetuned.bleu - baseline.bleu
    logger.info(
        "BLEU improvement: %.4f -> %.4f = %+.4f (%+.1f pts)",
        baseline.bleu, finetuned.bleu, improvement, improvement * 100,
    )
    return improvement


# ---------------------------------------------------------------------------
# compare_models
# ---------------------------------------------------------------------------


def compare_models(
    baseline_translations: list[str],
    finetuned_translations: list[str],
    corpus: list["CorpusEntry"],
    baseline_name: str = "baseline",
    finetuned_name: str = "finetuned",
    glossary: dict[str, str] | None = None,
) -> dict[str, EvalResult]:
    """Evaluate and compare two model outputs side by side.

    Args:
        baseline_translations:  Translations from the base model.
        finetuned_translations: Translations from the fine-tuned model.
        corpus:                 Reference corpus.
        baseline_name:          Label for the baseline model.
        finetuned_name:         Label for the fine-tuned model.
        glossary:               Optional glossary for coverage metric.

    Returns:
        Dict with keys ``baseline`` and ``finetuned``, each an ``EvalResult``.

    Example::

        results = compare_models(base_hyps, ft_hyps, test_corpus)
        delta = compute_bleu_improvement(results["baseline"], results["finetuned"])
        print(f"Improvement: +{delta * 100:.1f} BLEU pts")
    """
    baseline_result = evaluate_finetuned_model(
        baseline_translations, corpus, model_name=baseline_name, glossary=glossary
    )
    finetuned_result = evaluate_finetuned_model(
        finetuned_translations, corpus, model_name=finetuned_name, glossary=glossary
    )

    delta = compute_bleu_improvement(baseline_result, finetuned_result)
    logger.info(
        "compare_models: %s vs %s | BLEU delta: %+.4f (%+.1f pts)",
        baseline_name, finetuned_name, delta, delta * 100,
    )
    return {"baseline": baseline_result, "finetuned": finetuned_result}
