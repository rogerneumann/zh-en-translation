"""Translation quality evaluation and A/B testing framework.

Modules:
    metrics    -- BLEU approximation, CER, token overlap, glossary coverage
    a_b_tester -- A/B testing harness comparing translation configurations
"""

from zh_en_translator.evaluation.metrics import (
    bleu_approx,
    cer,
    token_overlap,
    glossary_coverage,
    TranslationMetrics,
    score_translation,
)
from zh_en_translator.evaluation.a_b_tester import (
    ABTestConfig,
    ABTestResult,
    ABTestRunner,
    ABTestEvaluator,
)

__all__ = [
    "bleu_approx",
    "cer",
    "token_overlap",
    "glossary_coverage",
    "TranslationMetrics",
    "score_translation",
    "ABTestConfig",
    "ABTestResult",
    "ABTestRunner",
    "ABTestEvaluator",
]
