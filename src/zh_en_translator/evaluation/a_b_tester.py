"""A/B testing harness for comparing translation configurations.

Usage::

    from zh_en_translator.evaluation import ABTestConfig, ABTestRunner, ABTestEvaluator

    sentences = [
        ("镀锌钢板和表面处理工艺", "galvanized steel sheet and surface treatment process"),
        ("热处理后的硬度和精度公差", "hardness and dimensional tolerances after heat treatment"),
    ]

    config_a = ABTestConfig(
        name="jieba_no_glossary",
        segmenter="jieba",
        use_glossary=False,
    )
    config_b = ABTestConfig(
        name="jieba_with_glossary",
        segmenter="jieba",
        use_glossary=True,
    )

    runner = ABTestRunner(sentences)
    results = runner.run([config_a, config_b])

    evaluator = ABTestEvaluator(results)
    print(evaluator.summary_table())
    best = evaluator.best_config(metric="bleu")
    print(f"Best config: {best}")
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Callable

from zh_en_translator.evaluation.metrics import TranslationMetrics, score_translation

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


@dataclass
class ABTestConfig:
    """Defines a single translation configuration to test.

    Attributes:
        name:         Human-readable identifier for this configuration.
        segmenter:    Segmenter backend: ``"jieba"``, ``"pkuseg"``, or ``"fallback"``.
        use_glossary: Whether to load the manufacturing glossary.
        glossary:     Optional explicit glossary dict; overrides use_glossary if provided.
        extra_params: Free-form dict for future engine parameters.
        description:  Optional longer description for reports.
    """

    name: str
    segmenter: str = "jieba"
    use_glossary: bool = True
    glossary: dict[str, str] = field(default_factory=dict)
    extra_params: dict = field(default_factory=dict)
    description: str = ""

    def __post_init__(self):
        valid_segmenters = {"jieba", "pkuseg", "fallback"}
        if self.segmenter not in valid_segmenters:
            raise ValueError(
                f"Invalid segmenter '{self.segmenter}'; choose from {sorted(valid_segmenters)}"
            )


# ---------------------------------------------------------------------------
# Per-sentence result
# ---------------------------------------------------------------------------


@dataclass
class ABTestResult:
    """Result of translating a single sentence with a single configuration."""

    config_name: str
    chinese: str
    hypothesis: str          # translation produced
    reference: str = ""      # reference translation (if available)
    metrics: TranslationMetrics | None = None
    elapsed_ms: float = 0.0  # wall-clock time for this translation
    error: str = ""          # non-empty if the translation raised an exception


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

# Sentence = (chinese, reference_english) OR just chinese string
_Sentence = str | tuple[str, str]


def _parse_sentence(s: _Sentence) -> tuple[str, str]:
    """Return (chinese, reference) from a sentence or (chinese, reference) tuple."""
    if isinstance(s, str):
        return s, ""
    return s[0], s[1]


class ABTestRunner:
    """Run a set of test sentences through multiple translation configurations.

    The runner uses the pipeline-level ``translate`` function internally.  It
    switches the segmenter and glossary according to each :class:`ABTestConfig`.

    Args:
        sentences: List of Chinese sentences or (Chinese, reference) tuples.
        translate_fn: Optional custom translation callable with signature
                      ``(chinese: str, glossary: dict) -> str``.  If omitted,
                      the pipeline's ``translate_to_string`` is used.
    """

    def __init__(
        self,
        sentences: list[_Sentence],
        translate_fn: Callable[[str, dict], str] | None = None,
    ) -> None:
        self._sentences = [_parse_sentence(s) for s in sentences]
        self._translate_fn = translate_fn or self._default_translate

    @staticmethod
    def _default_translate(chinese: str, glossary: dict[str, str]) -> str:
        """Use the pipeline's translate_to_string with the given glossary."""
        from zh_en_translator.engines.pipeline import translate_to_string
        return translate_to_string(chinese, glossary=glossary)

    def run(
        self,
        configs: list[ABTestConfig],
    ) -> dict[str, list[ABTestResult]]:
        """Translate all sentences with all configs.

        Args:
            configs: List of :class:`ABTestConfig` instances to compare.

        Returns:
            Dict ``{config_name: [ABTestResult, ...]}``, preserving sentence order.
        """
        results: dict[str, list[ABTestResult]] = {cfg.name: [] for cfg in configs}

        for cfg in configs:
            logger.info("Running A/B config: %s (segmenter=%s, glossary=%s)",
                        cfg.name, cfg.segmenter, cfg.use_glossary)

            # Prepare glossary for this config
            glossary = self._resolve_glossary(cfg)

            # Set segmenter
            try:
                from zh_en_translator.engines.segmentation import set_segmenter
                set_segmenter(cfg.segmenter)
            except Exception as exc:
                logger.warning("Could not set segmenter '%s': %s", cfg.segmenter, exc)

            for chinese, reference in self._sentences:
                result = self._run_single(cfg.name, chinese, reference, glossary)
                results[cfg.name].append(result)

        return results

    def _resolve_glossary(self, cfg: ABTestConfig) -> dict[str, str]:
        """Return the glossary dict for a config."""
        if cfg.glossary:
            return cfg.glossary
        if cfg.use_glossary:
            try:
                from zh_en_translator.engines.glossary import load_all_glossaries
                return load_all_glossaries()
            except Exception as exc:
                logger.warning("Failed to load glossary: %s", exc)
                return {}
        return {}

    def _run_single(
        self,
        config_name: str,
        chinese: str,
        reference: str,
        glossary: dict[str, str],
    ) -> ABTestResult:
        """Translate one sentence and compute metrics."""
        t0 = time.perf_counter()
        hypothesis = ""
        error = ""

        try:
            hypothesis = self._translate_fn(chinese, glossary)
        except Exception as exc:
            error = str(exc)
            logger.warning("Translation failed for config '%s', input '%s': %s",
                           config_name, chinese, exc)

        elapsed_ms = (time.perf_counter() - t0) * 1000

        # Compute metrics
        metrics = score_translation(
            hypothesis=hypothesis,
            reference=reference,
            glossary=glossary,
        )

        return ABTestResult(
            config_name=config_name,
            chinese=chinese,
            hypothesis=hypothesis,
            reference=reference,
            metrics=metrics,
            elapsed_ms=elapsed_ms,
            error=error,
        )


# ---------------------------------------------------------------------------
# Evaluator
# ---------------------------------------------------------------------------


class ABTestEvaluator:
    """Analyse and compare A/B test results.

    Args:
        results: Output from :meth:`ABTestRunner.run`.
    """

    _METRICS = ("bleu", "cer", "token_overlap", "glossary_coverage")

    def __init__(self, results: dict[str, list[ABTestResult]]) -> None:
        self._results = results

    # ------------------------------------------------------------------
    # Aggregate statistics
    # ------------------------------------------------------------------

    def aggregate(self, config_name: str) -> dict[str, float]:
        """Return average metric values for *config_name*.

        Returns:
            Dict with keys: ``bleu``, ``cer``, ``token_overlap``,
            ``glossary_coverage``, ``avg_elapsed_ms``, ``error_count``.
        """
        entries = self._results.get(config_name, [])
        if not entries:
            return {}

        totals: dict[str, float] = {k: 0.0 for k in self._METRICS}
        totals["avg_elapsed_ms"] = 0.0
        errors = 0

        for r in entries:
            if r.metrics:
                totals["bleu"] += r.metrics.bleu
                totals["cer"] += r.metrics.cer_score
                totals["token_overlap"] += r.metrics.token_overlap_score
                totals["glossary_coverage"] += r.metrics.glossary_coverage_score
            totals["avg_elapsed_ms"] += r.elapsed_ms
            if r.error:
                errors += 1

        n = len(entries)
        return {k: v / n for k, v in totals.items()} | {"error_count": errors}

    def all_aggregates(self) -> dict[str, dict[str, float]]:
        """Return aggregate statistics for all configs."""
        return {name: self.aggregate(name) for name in self._results}

    # ------------------------------------------------------------------
    # Best config selection
    # ------------------------------------------------------------------

    def best_config(self, metric: str = "bleu") -> str | None:
        """Return the config name with the best average value for *metric*.

        For ``"cer"`` lower is better; for all others higher is better.

        Args:
            metric: One of ``"bleu"``, ``"cer"``, ``"token_overlap"``,
                    ``"glossary_coverage"``.

        Returns:
            Config name string, or None if no results.
        """
        if not self._results:
            return None

        aggregates = self.all_aggregates()
        lower_is_better = metric == "cer"

        best_name = None
        best_val = float("inf") if lower_is_better else float("-inf")

        for name, agg in aggregates.items():
            val = agg.get(metric, float("nan"))
            if lower_is_better:
                if val < best_val:
                    best_val = val
                    best_name = name
            else:
                if val > best_val:
                    best_val = val
                    best_name = name

        return best_name

    # ------------------------------------------------------------------
    # Diff / comparison helpers
    # ------------------------------------------------------------------

    def compare_pair(
        self, config_a: str, config_b: str
    ) -> list[dict]:
        """Compare two configs sentence by sentence.

        Returns a list of dicts, one per sentence, with fields:
        ``chinese``, ``hypothesis_a``, ``hypothesis_b``, ``reference``,
        ``bleu_a``, ``bleu_b``, ``bleu_delta`` (B - A).
        """
        rows_a = self._results.get(config_a, [])
        rows_b = self._results.get(config_b, [])
        comparisons = []

        for ra, rb in zip(rows_a, rows_b):
            bleu_a = ra.metrics.bleu if ra.metrics else 0.0
            bleu_b = rb.metrics.bleu if rb.metrics else 0.0
            comparisons.append({
                "chinese": ra.chinese,
                "hypothesis_a": ra.hypothesis,
                "hypothesis_b": rb.hypothesis,
                "reference": ra.reference,
                "bleu_a": round(bleu_a, 4),
                "bleu_b": round(bleu_b, 4),
                "bleu_delta": round(bleu_b - bleu_a, 4),
            })

        return comparisons

    # ------------------------------------------------------------------
    # Reporting
    # ------------------------------------------------------------------

    def summary_table(self) -> str:
        """Return a plain-text summary table of all configs."""
        aggs = self.all_aggregates()
        if not aggs:
            return "(no results)"

        col_w = max(len(n) for n in aggs) + 2
        header = (
            f"{'Config':<{col_w}} {'BLEU':>8} {'CER':>8} "
            f"{'TokOv':>8} {'GlsCov':>8} {'ms':>8} {'Errors':>7}"
        )
        sep = "-" * len(header)
        lines = [header, sep]

        for name, agg in sorted(aggs.items()):
            lines.append(
                f"{name:<{col_w}} "
                f"{agg.get('bleu', 0):.4f}   "
                f"{agg.get('cer', 0):.4f}   "
                f"{agg.get('token_overlap', 0):.4f}   "
                f"{agg.get('glossary_coverage', 0):.4f}   "
                f"{agg.get('avg_elapsed_ms', 0):6.1f}   "
                f"{int(agg.get('error_count', 0)):4d}"
            )

        return "\n".join(lines)

    def diff_report(self, config_a: str, config_b: str) -> str:
        """Return a human-readable diff between two configs."""
        agg_a = self.aggregate(config_a)
        agg_b = self.aggregate(config_b)
        comparisons = self.compare_pair(config_a, config_b)

        lines = [
            f"A/B Comparison: '{config_a}' vs '{config_b}'",
            "=" * 60,
            f"Metric         {config_a:>20} {config_b:>20}  Delta",
            "-" * 60,
        ]
        for metric in ("bleu", "cer", "token_overlap", "glossary_coverage"):
            va = agg_a.get(metric, 0)
            vb = agg_b.get(metric, 0)
            delta = vb - va
            sign = "+" if delta >= 0 else ""
            lines.append(f"{metric:<15}{va:>20.4f}{vb:>20.4f}  {sign}{delta:.4f}")

        lines.append("")
        lines.append("Sentence-level diff (showing BLEU changes):")
        for i, cmp in enumerate(comparisons, 1):
            sign = "+" if cmp["bleu_delta"] >= 0 else ""
            lines.append(
                f"  [{i}] {cmp['chinese'][:30]:<30}  "
                f"A={cmp['bleu_a']:.3f}  B={cmp['bleu_b']:.3f}  "
                f"delta={sign}{cmp['bleu_delta']:.3f}"
            )

        return "\n".join(lines)
