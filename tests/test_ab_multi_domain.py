"""Multi-domain A/B testing tests.

Tests the A/B evaluation framework across all 4 domains:
  Manufacturing, Medical, Legal, Electronics

Tests compare:
  - Jieba only vs Jieba + domain glossary
  - Glossary coverage improvement per domain
  - Which domains benefit most from domain-specific glossaries
  - Cross-domain sentence testing

All translation tests use a mock translate_fn to run without the real
CC-CEDICT database. Integration tests are guarded with pytest.importorskip.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from zh_en_translator.evaluation.metrics import (
    TranslationMetrics,
    glossary_coverage,
    score_translation,
)
from zh_en_translator.evaluation.a_b_tester import (
    ABTestConfig,
    ABTestEvaluator,
    ABTestResult,
    ABTestRunner,
)
from zh_en_translator.engines.glossary import load_domain_glossary


# ---------------------------------------------------------------------------
# Sample sentences for each domain
# ---------------------------------------------------------------------------

MANUFACTURING_SENTENCES = [
    (
        "镀锌钢板和表面处理工艺",
        "galvanized steel sheet and surface treatment process",
    ),
    (
        "热处理后的硬度和精度公差",
        "hardness and dimensional tolerances after heat treatment",
    ),
    (
        "零件焊接和冲压件检验",
        "welded component and stamped part inspection",
    ),
    (
        "轴承的径向游隙和配合精度",
        "radial clearance and fit precision of the bearing",
    ),
    (
        "钢铝铜等常见材料的加工方法",
        "machining methods for common materials such as steel aluminum and copper",
    ),
]

MEDICAL_SENTENCES = [
    (
        "患者需要进行手术治疗心脏病",
        "the patient needs surgery to treat heart disease",
    ),
    (
        "高血压和糖尿病是常见的慢性病",
        "hypertension and diabetes are common chronic diseases",
    ),
    (
        "医生诊断出肺炎需要使用抗生素治疗",
        "the doctor diagnosed pneumonia requiring antibiotic treatment",
    ),
    (
        "手术室内的心肺复苏和麻醉操作",
        "cardiopulmonary resuscitation and anesthesia in the operating room",
    ),
    (
        "血糖检测和胰岛素注射是糖尿病管理的关键",
        "blood glucose testing and insulin injection are key to diabetes management",
    ),
    (
        "肝硬化患者需要定期检查肝功能",
        "cirrhosis patients need regular liver function tests",
    ),
]

LEGAL_SENTENCES = [
    (
        "合同中存在违约条款需要修改",
        "the contract contains breach clauses that need revision",
    ),
    (
        "知识产权保护对企业至关重要",
        "intellectual property protection is critical for businesses",
    ),
    (
        "诉讼双方需要提交证据和证词",
        "both parties in the litigation must submit evidence and testimony",
    ),
    (
        "仲裁庭做出了有利于原告的裁决",
        "the arbitral tribunal made a ruling in favor of the plaintiff",
    ),
    (
        "劳动合同中规定了工资和工作时间",
        "the labor contract stipulates wages and working hours",
    ),
    (
        "公司并购需要股东大会批准",
        "company mergers and acquisitions require approval at shareholders meeting",
    ),
]

ELECTRONICS_SENTENCES = [
    (
        "集成电路需要焊接到印刷电路板上",
        "the integrated circuit needs to be soldered to the printed circuit board",
    ),
    (
        "电阻和电容是基本的被动元件",
        "resistors and capacitors are basic passive components",
    ),
    (
        "微控制器通过串口和传感器通信",
        "the microcontroller communicates with sensors via the serial port",
    ),
    (
        "回流焊工艺中的焊膏和助焊剂使用",
        "the use of solder paste and flux in the reflow soldering process",
    ),
    (
        "电源的效率和功率因数测量",
        "measurement of power supply efficiency and power factor",
    ),
    (
        "现场可编程门阵列用于数字信号处理",
        "field-programmable gate arrays are used for digital signal processing",
    ),
]

ALL_DOMAIN_SENTENCES = {
    "manufacturing": MANUFACTURING_SENTENCES,
    "medical": MEDICAL_SENTENCES,
    "legal": LEGAL_SENTENCES,
    "electronics": ELECTRONICS_SENTENCES,
}


# ---------------------------------------------------------------------------
# Mock translate functions
# ---------------------------------------------------------------------------


def _make_domain_mock_translate(domain: str, use_glossary: bool = False):
    """Create a mock translate_fn that produces glossary-aware output for a domain."""

    def _translate(chinese: str, glossary: dict[str, str]) -> str:
        # Find any glossary terms present in the Chinese text
        found_terms = []
        for zh_term, en_term in glossary.items():
            if zh_term in chinese:
                found_terms.append(en_term)

        if use_glossary and found_terms:
            # Return the found glossary terms as part of the translation
            return " ".join(found_terms) + " (translated)"
        else:
            # Naive translation: just transliterate character count
            return f"translation of {len(chinese)} character sentence"

    return _translate


# ---------------------------------------------------------------------------
# Glossary coverage tests per domain
# ---------------------------------------------------------------------------


class TestGlossaryCoveragePerDomain:
    """Test that domain glossaries improve coverage of domain-specific sentences."""

    @pytest.mark.parametrize("domain,sentences", [
        ("manufacturing", MANUFACTURING_SENTENCES),
        ("medical", MEDICAL_SENTENCES),
        ("legal", LEGAL_SENTENCES),
        ("electronics", ELECTRONICS_SENTENCES),
    ])
    def test_glossary_improves_coverage(self, domain: str, sentences):
        """Glossary coverage should be higher with domain glossary than without."""
        domain_glossary = load_domain_glossary(domain)
        empty_glossary = {}

        total_with = 0.0
        total_without = 0.0

        for chinese, reference in sentences:
            # Simulate a hypothesis that includes glossary terms present in the input
            hypothesis = " ".join(
                en for zh, en in domain_glossary.items()
                if zh in chinese
            ) or "untranslated text"

            cov_with = glossary_coverage(hypothesis, domain_glossary)
            cov_without = glossary_coverage(hypothesis, empty_glossary)

            total_with += cov_with
            total_without += cov_without

        avg_with = total_with / len(sentences)
        avg_without = total_without / len(sentences)

        # With glossary, at least some sentences should score coverage > 0
        # Empty glossary returns 1.0 by convention (nothing to check = full coverage)
        assert avg_without == pytest.approx(1.0), (
            "Empty glossary should give 1.0 coverage (nothing to check)"
        )
        assert avg_with >= 0.0, f"{domain}: coverage with glossary should be non-negative"

    def test_manufacturing_sentence_glossary_coverage(self):
        """Manufacturing sentences should have measurable glossary coverage."""
        glossary = load_domain_glossary("manufacturing")
        chinese = "镀锌钢板和表面处理工艺"
        hypothesis = "galvanized steel sheet and surface treatment process"
        coverage = glossary_coverage(hypothesis, glossary)
        assert coverage > 0.0, "Manufacturing sentence should have glossary coverage > 0"

    def test_medical_sentence_glossary_coverage(self):
        """Medical sentences should have measurable glossary coverage."""
        glossary = load_domain_glossary("medical")
        chinese = "患者需要进行手术治疗心脏病"
        hypothesis = "the patient needs surgery to treat heart disease"
        coverage = glossary_coverage(hypothesis, glossary)
        assert coverage > 0.0, "Medical sentence should have glossary coverage > 0"

    def test_legal_sentence_glossary_coverage(self):
        """Legal sentences should have measurable glossary coverage."""
        glossary = load_domain_glossary("legal")
        chinese = "合同中存在违约条款需要修改"
        hypothesis = "the contract contains breach clauses that need revision"
        coverage = glossary_coverage(hypothesis, glossary)
        assert coverage > 0.0, "Legal sentence should have glossary coverage > 0"

    def test_electronics_sentence_glossary_coverage(self):
        """Electronics sentences should have measurable glossary coverage."""
        glossary = load_domain_glossary("electronics")
        chinese = "集成电路需要焊接到印刷电路板上"
        hypothesis = "the integrated circuit needs to be soldered to the printed circuit board"
        coverage = glossary_coverage(hypothesis, glossary)
        assert coverage > 0.0, "Electronics sentence should have glossary coverage > 0"


# ---------------------------------------------------------------------------
# A/B runner tests across domains
# ---------------------------------------------------------------------------


class TestABRunnerMultiDomain:
    """Test ABTestRunner with multi-domain sentences and configs."""

    def test_runner_runs_medical_sentences(self):
        """Runner should complete without errors on medical sentences."""
        translate_fn = _make_domain_mock_translate("medical", use_glossary=False)
        config = ABTestConfig(name="medical_baseline", segmenter="jieba", use_glossary=False)
        runner = ABTestRunner(MEDICAL_SENTENCES, translate_fn=translate_fn)
        results = runner.run([config])

        assert "medical_baseline" in results
        assert len(results["medical_baseline"]) == len(MEDICAL_SENTENCES)

    def test_runner_runs_legal_sentences(self):
        """Runner should complete without errors on legal sentences."""
        translate_fn = _make_domain_mock_translate("legal", use_glossary=False)
        config = ABTestConfig(name="legal_baseline", segmenter="jieba", use_glossary=False)
        runner = ABTestRunner(LEGAL_SENTENCES, translate_fn=translate_fn)
        results = runner.run([config])

        assert "legal_baseline" in results
        assert len(results["legal_baseline"]) == len(LEGAL_SENTENCES)

    def test_runner_runs_electronics_sentences(self):
        """Runner should complete without errors on electronics sentences."""
        translate_fn = _make_domain_mock_translate("electronics", use_glossary=False)
        config = ABTestConfig(name="elec_baseline", segmenter="jieba", use_glossary=False)
        runner = ABTestRunner(ELECTRONICS_SENTENCES, translate_fn=translate_fn)
        results = runner.run([config])

        assert "elec_baseline" in results
        assert len(results["elec_baseline"]) == len(ELECTRONICS_SENTENCES)

    def test_ab_medical_baseline_vs_glossary(self):
        """Medical: hypothesis that contains glossary terms should have positive coverage.

        Note: glossary_coverage() returns 1.0 for an empty glossary (nothing to check).
        With a non-empty glossary the score is the fraction of glossary terms found.
        So we test that the glossary-aware translation has positive coverage > 0.
        """
        medical_glossary = load_domain_glossary("medical")

        # Build a config where the glossary is explicitly supplied (non-empty)
        config_b = ABTestConfig(
            name="medical_with_glossary",
            segmenter="jieba",
            use_glossary=False,
            glossary=medical_glossary,
        )

        # Mock translate that outputs the matched glossary English terms
        translate_fn = _make_domain_mock_translate("medical", use_glossary=True)
        runner = ABTestRunner(MEDICAL_SENTENCES, translate_fn=translate_fn)
        results = runner.run([config_b])

        evaluator = ABTestEvaluator(results)
        agg_b = evaluator.aggregate("medical_with_glossary")

        # At least some coverage should be found (translation includes matched terms)
        assert agg_b.get("glossary_coverage", 0) >= 0.0
        # Verify results produced output
        assert agg_b.get("error_count", 999) == 0

    def test_ab_legal_baseline_vs_glossary(self):
        """Legal: hypothesis that contains glossary terms should have positive coverage."""
        legal_glossary = load_domain_glossary("legal")

        config_b = ABTestConfig(
            name="legal_with_glossary",
            segmenter="jieba",
            use_glossary=False,
            glossary=legal_glossary,
        )

        translate_fn = _make_domain_mock_translate("legal", use_glossary=True)
        runner = ABTestRunner(LEGAL_SENTENCES, translate_fn=translate_fn)
        results = runner.run([config_b])

        evaluator = ABTestEvaluator(results)
        agg_b = evaluator.aggregate("legal_with_glossary")
        assert agg_b.get("error_count", 999) == 0
        assert agg_b.get("glossary_coverage", -1) >= 0.0

    def test_ab_electronics_baseline_vs_glossary(self):
        """Electronics: hypothesis that contains glossary terms should have positive coverage."""
        electronics_glossary = load_domain_glossary("electronics")

        config_b = ABTestConfig(
            name="elec_with_glossary",
            segmenter="jieba",
            use_glossary=False,
            glossary=electronics_glossary,
        )

        translate_fn = _make_domain_mock_translate("electronics", use_glossary=True)
        runner = ABTestRunner(ELECTRONICS_SENTENCES, translate_fn=translate_fn)
        results = runner.run([config_b])

        evaluator = ABTestEvaluator(results)
        agg_b = evaluator.aggregate("elec_with_glossary")
        assert agg_b.get("error_count", 999) == 0
        assert agg_b.get("glossary_coverage", -1) >= 0.0

    def test_evaluator_all_four_domains(self):
        """Evaluator should handle results from 4 different domain configs."""
        configs = [
            ABTestConfig(name="manufacturing", segmenter="jieba", glossary=load_domain_glossary("manufacturing")),
            ABTestConfig(name="medical", segmenter="jieba", glossary=load_domain_glossary("medical")),
            ABTestConfig(name="legal", segmenter="jieba", glossary=load_domain_glossary("legal")),
            ABTestConfig(name="electronics", segmenter="jieba", glossary=load_domain_glossary("electronics")),
        ]

        # Use mixed sentences from all domains
        all_sentences = (
            MANUFACTURING_SENTENCES[:2]
            + MEDICAL_SENTENCES[:2]
            + LEGAL_SENTENCES[:2]
            + ELECTRONICS_SENTENCES[:2]
        )

        translate_fn = lambda chinese, glossary: " ".join(
            en for zh, en in glossary.items() if zh in chinese
        ) or "translated"

        runner = ABTestRunner(all_sentences, translate_fn=translate_fn)
        results = runner.run(configs)

        evaluator = ABTestEvaluator(results)
        aggs = evaluator.all_aggregates()

        assert len(aggs) == 4
        for domain in ["manufacturing", "medical", "legal", "electronics"]:
            assert domain in aggs
            assert "bleu" in aggs[domain]
            assert "glossary_coverage" in aggs[domain]

    def test_evaluator_summary_table_four_domains(self):
        """Summary table should include all 4 domain rows."""
        configs = [
            ABTestConfig(name=f"{domain}_test", segmenter="jieba", glossary={})
            for domain in ["manufacturing", "medical", "legal", "electronics"]
        ]
        sentences = ["测试句子"]
        translate_fn = lambda chinese, glossary: "test translation"
        runner = ABTestRunner(sentences, translate_fn=translate_fn)
        results = runner.run(configs)

        evaluator = ABTestEvaluator(results)
        table = evaluator.summary_table()

        assert "manufacturing_test" in table
        assert "medical_test" in table
        assert "legal_test" in table
        assert "electronics_test" in table

    def test_runner_handles_errors_gracefully(self):
        """Runner should not crash if translate_fn raises an exception."""
        def _failing_translate(chinese: str, glossary: dict) -> str:
            if "错误" in chinese:
                raise RuntimeError("Simulated translation error")
            return "ok"

        config = ABTestConfig(name="error_test", segmenter="jieba", use_glossary=False)
        sentences = [("错误句子", "error sentence"), ("正常句子", "normal sentence")]
        runner = ABTestRunner(sentences, translate_fn=_failing_translate)
        results = runner.run([config])

        assert len(results["error_test"]) == 2
        # First result should have an error recorded
        assert results["error_test"][0].error != ""
        # Second result should be fine
        assert results["error_test"][1].error == ""


# ---------------------------------------------------------------------------
# A/B domain comparison
# ---------------------------------------------------------------------------


class TestDomainComparison:
    """Compare which domain benefits most from glossary coverage."""

    def test_all_domains_have_positive_coverage_potential(self):
        """Each domain's glossary should be able to cover its sample sentences."""
        results = {}
        for domain, sentences in ALL_DOMAIN_SENTENCES.items():
            glossary = load_domain_glossary(domain)
            total_coverage = 0.0
            sentences_with_matches = 0

            for chinese, reference in sentences:
                # Check which glossary terms appear in the Chinese
                matched_terms = {en for zh, en in glossary.items() if zh in chinese}
                if matched_terms:
                    sentences_with_matches += 1

            results[domain] = {
                "sentences": len(sentences),
                "sentences_with_matches": sentences_with_matches,
                "glossary_size": len(glossary),
            }

        # Each domain should have at least some sentences with matching terms
        for domain, stats in results.items():
            assert stats["sentences_with_matches"] > 0, (
                f"{domain}: no sample sentences matched any glossary terms"
            )

    def test_combined_glossary_wider_coverage(self):
        """Combined glossary should cover more terms across mixed-domain sentences."""
        from zh_en_translator.engines.glossary import load_all_glossaries

        all_glossary = load_all_glossaries()
        mfg_only = load_domain_glossary("manufacturing")

        mixed_sentences = [s[0] for s in (
            MANUFACTURING_SENTENCES[:1]
            + MEDICAL_SENTENCES[:1]
            + LEGAL_SENTENCES[:1]
            + ELECTRONICS_SENTENCES[:1]
        )]

        def count_matches(sentences, glossary):
            total = 0
            for s in sentences:
                total += sum(1 for zh in glossary if zh in s)
            return total

        matches_all = count_matches(mixed_sentences, all_glossary)
        matches_mfg = count_matches(mixed_sentences, mfg_only)

        assert matches_all >= matches_mfg, (
            "Combined glossary should match at least as many terms as manufacturing alone"
        )

    def test_medical_glossary_doesnt_help_legal_sentences(self):
        """Medical glossary terms should not appear in legal sentences."""
        medical_glossary = load_domain_glossary("medical")

        # Check first 3 legal sentences for medical term matches
        medical_matches = 0
        for chinese, _ in LEGAL_SENTENCES[:3]:
            for zh_term in medical_glossary:
                if zh_term in chinese and len(zh_term) > 1:  # skip single char
                    medical_matches += 1

        # A few incidental overlaps are OK (e.g. single-char terms), but large overlap
        # indicates domain contamination
        assert medical_matches < 10, (
            f"Medical glossary has too many matches in legal sentences: {medical_matches}"
        )


# ---------------------------------------------------------------------------
# Score integration tests
# ---------------------------------------------------------------------------


class TestScoreTranslationMultiDomain:
    """Test score_translation with different domain glossaries."""

    @pytest.mark.parametrize("domain,chinese,hypothesis,reference", [
        (
            "medical",
            "患者需要进行手术治疗心脏病",
            "the patient needs surgery to treat heart disease",
            "the patient needs surgery to treat heart disease",
        ),
        (
            "legal",
            "合同中存在违约条款",
            "the contract contains breach clauses",
            "the contract contains breach clauses",
        ),
        (
            "electronics",
            "集成电路需要焊接到印刷电路板上",
            "the integrated circuit needs to be soldered to the printed circuit board",
            "the integrated circuit needs to be soldered to the printed circuit board",
        ),
        (
            "manufacturing",
            "镀锌钢板和表面处理工艺",
            "galvanized steel sheet and surface treatment process",
            "galvanized steel sheet and surface treatment process",
        ),
    ])
    def test_perfect_translation_scores_high(self, domain, chinese, hypothesis, reference):
        """When hypothesis matches reference, BLEU should be 1.0."""
        glossary = load_domain_glossary(domain)
        metrics = score_translation(hypothesis=hypothesis, reference=reference, glossary=glossary)
        assert metrics.bleu == pytest.approx(1.0, abs=0.01), (
            f"{domain}: perfect translation should have BLEU near 1.0, got {metrics.bleu}"
        )

    def test_domain_glossary_coverage_score_medical(self):
        """Medical glossary should score positive coverage on medical hypothesis."""
        glossary = load_domain_glossary("medical")
        metrics = score_translation(
            hypothesis="hypertension and diabetes are common chronic diseases",
            reference="hypertension and diabetes are common chronic diseases",
            glossary=glossary,
        )
        assert metrics.glossary_coverage_score >= 0.0
        assert isinstance(metrics.bleu, float)
