"""A/B translation quality tests.

Tests the evaluation framework (metrics, ABTestConfig, ABTestRunner,
ABTestEvaluator) and validates end-to-end A/B comparisons across
four manufacturing-domain scenarios:

  Scenario 1: Jieba only vs Jieba + glossary
  Scenario 2: PKUSEG only vs PKUSEG + glossary
  Scenario 3: Jieba + glossary vs PKUSEG + glossary
  Scenario 4: No glossary baseline vs Full (Jieba + glossary)

The translation tests use a mock translate_fn so they run without the
real CC-CEDICT database.  Integration tests that use the live pipeline are
guarded with pytest.importorskip.
"""

from __future__ import annotations

import pytest
from unittest.mock import patch

from zh_en_translator.evaluation.metrics import (
    TranslationMetrics,
    bleu_approx,
    cer,
    glossary_coverage,
    score_translation,
    token_overlap,
)
from zh_en_translator.evaluation.a_b_tester import (
    ABTestConfig,
    ABTestEvaluator,
    ABTestResult,
    ABTestRunner,
)


# ---------------------------------------------------------------------------
# Sample manufacturing test sentences
# (Chinese + reference English translation)
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
        "machining methods for common materials such as steel, aluminum, and copper",
    ),
]


# ---------------------------------------------------------------------------
# Fixtures: mock translate functions
# ---------------------------------------------------------------------------


def _make_mock_translate(glossary_lookup: bool = False):
    """Create a mock translate_fn that returns deterministic results.

    With ``glossary_lookup=True`` the function 'finds' glossary terms in its
    output, producing higher glossary_coverage scores.
    """

    def _translate(chinese: str, glossary: dict[str, str]) -> str:
        # Simulate glossary-aware vs naive translation
        if glossary_lookup and glossary:
            # Return English values for any matching Chinese keys
            found = []
            for zh, en in glossary.items():
                if zh in chinese:
                    found.append(en.split("/")[0].strip())
            if found:
                return " ".join(found)
        # Naive: just echo a placeholder
        return f"translation of: {chinese}"

    return _translate


@pytest.fixture()
def mock_sentences():
    return MANUFACTURING_SENTENCES[:3]


@pytest.fixture()
def manufacturing_glossary():
    return {
        "镀锌": "galvanized",
        "表面处理": "surface treatment",
        "热处理": "heat treatment",
        "硬度": "hardness",
        "公差": "tolerance",
        "零件": "component",
        "焊接": "welding",
        "冲压件": "stamped part",
        "轴承": "bearing",
        "钢": "steel",
    }


# ===========================================================================
# Part I: Metrics Unit Tests
# ===========================================================================


class TestBLEUApprox:
    def test_identical_strings_score_one(self):
        score = bleu_approx("the cat sat on the mat", "the cat sat on the mat")
        assert score == pytest.approx(1.0, abs=0.001)

    def test_empty_hypothesis_returns_zero(self):
        assert bleu_approx("", "some reference text") == 0.0

    def test_empty_reference_returns_zero(self):
        assert bleu_approx("some hypothesis text", "") == 0.0

    def test_completely_different_returns_low_score(self):
        score = bleu_approx("xylophone banana cloud", "cat dog fish bird")
        assert score < 0.1

    def test_partial_overlap_between_zero_and_one(self):
        score = bleu_approx("the cat sat on a mat", "the cat sat on the mat")
        assert 0.0 < score < 1.0

    def test_longer_hypothesis_no_brevity_bonus(self):
        short = bleu_approx("heat treatment", "heat treatment process specifications")
        long_ = bleu_approx(
            "heat treatment process specifications and quality control",
            "heat treatment process specifications",
        )
        # Both have the reference tokens; longer hyp should not score > 1
        assert long_ <= 1.0

    def test_case_insensitive(self):
        s1 = bleu_approx("Heat Treatment", "heat treatment")
        s2 = bleu_approx("heat treatment", "heat treatment")
        assert abs(s1 - s2) < 0.001

    def test_manufacturing_terms_score_higher_when_present(self):
        # Use max_n=1 (unigram BLEU) which is robust for short test sentences
        with_terms = bleu_approx(
            "galvanized steel sheet surface treatment",
            "galvanized steel sheet and surface treatment process",
            max_n=1,
        )
        without_terms = bleu_approx(
            "cold chain traceability batch number expiration",
            "galvanized steel sheet and surface treatment process",
            max_n=1,
        )
        assert with_terms > without_terms

    def test_score_in_valid_range(self):
        for hyp, ref in MANUFACTURING_SENTENCES:
            score = bleu_approx(hyp, ref)
            assert 0.0 <= score <= 1.0


class TestCER:
    def test_identical_strings_returns_zero(self):
        assert cer("heat treatment", "heat treatment") == pytest.approx(0.0)

    def test_empty_reference_returns_zero(self):
        # When reference is empty, CER is 0 (no reference = no error to measure)
        assert cer("", "") == 0.0

    def test_completely_different_high_cer(self):
        score = cer("abc", "xyz")
        assert score > 0.5

    def test_one_char_difference(self):
        score = cer("heat tratment", "heat treatment")
        assert 0.0 < score < 0.5

    def test_cer_non_negative(self):
        assert cer("a", "bcd") >= 0.0

    def test_cer_case_insensitive(self):
        assert cer("HEAT TREATMENT", "heat treatment") == pytest.approx(0.0)


class TestTokenOverlap:
    def test_all_terms_present_returns_one(self):
        hyp = "galvanized steel surface treatment process"
        terms = ["galvanized", "steel", "surface treatment"]
        assert token_overlap(hyp, terms) == pytest.approx(1.0)

    def test_no_terms_present_returns_zero(self):
        hyp = "completely different text"
        terms = ["galvanized", "steel"]
        assert token_overlap(hyp, terms) == pytest.approx(0.0)

    def test_partial_overlap(self):
        hyp = "galvanized steel processing"
        terms = ["galvanized", "surface treatment"]
        score = token_overlap(hyp, terms)
        assert score == pytest.approx(0.5)

    def test_empty_terms_list_returns_one(self):
        assert token_overlap("any text", []) == pytest.approx(1.0)

    def test_case_insensitive_matching(self):
        score = token_overlap("GALVANIZED STEEL", ["galvanized", "steel"])
        assert score == pytest.approx(1.0)

    def test_substring_match_counts(self):
        # "surface treatment" is a substring of the longer text
        score = token_overlap("advanced surface treatment processes", ["surface treatment"])
        assert score == pytest.approx(1.0)


class TestGlossaryCoverage:
    def test_all_glossary_terms_present(self, manufacturing_glossary):
        # Make a hypothesis that contains all English values
        hyp = " ".join(manufacturing_glossary.values())
        score = glossary_coverage(hyp, manufacturing_glossary)
        assert score == pytest.approx(1.0)

    def test_no_glossary_terms_present(self, manufacturing_glossary):
        hyp = "random text with no domain terms whatsoever"
        score = glossary_coverage(hyp, manufacturing_glossary)
        assert score == pytest.approx(0.0)

    def test_empty_glossary_returns_one(self):
        assert glossary_coverage("any text", {}) == pytest.approx(1.0)

    def test_slash_variant_matching(self):
        # Glossary entry "galvanized / zinc-plated" should match on either variant
        glossary = {"镀锌": "galvanized / zinc-plated"}
        assert glossary_coverage("zinc-plated steel", glossary) == pytest.approx(1.0)
        assert glossary_coverage("galvanized steel", glossary) == pytest.approx(1.0)

    def test_partial_coverage(self, manufacturing_glossary):
        # Hypothesis contains only some of the glossary terms
        hyp = "galvanized steel component"
        score = glossary_coverage(hyp, manufacturing_glossary)
        assert 0.0 < score < 1.0


class TestScoreTranslation:
    def test_returns_translation_metrics(self):
        result = score_translation("heat treatment", "heat treatment")
        assert isinstance(result, TranslationMetrics)

    def test_perfect_match_high_bleu(self):
        result = score_translation("heat treatment", "heat treatment")
        assert result.bleu > 0.9

    def test_no_reference_bleu_is_zero(self):
        result = score_translation("heat treatment")
        assert result.bleu == 0.0

    def test_glossary_coverage_computed(self, manufacturing_glossary):
        hyp = "galvanized steel heat treatment process"
        result = score_translation(hyp, glossary=manufacturing_glossary)
        assert result.glossary_coverage_score > 0.0

    def test_token_overlap_computed(self):
        hyp = "galvanized steel sheet"
        terms = ["galvanized", "steel"]
        result = score_translation(hyp, source_terms=terms)
        assert result.token_overlap_score == pytest.approx(1.0)

    def test_to_dict_has_required_keys(self):
        result = score_translation("test", "test")
        d = result.to_dict()
        for key in ("hypothesis", "reference", "bleu", "cer", "token_overlap", "glossary_coverage"):
            assert key in d

    def test_summary_returns_string(self):
        result = score_translation("heat treatment", "heat treatment")
        s = result.summary()
        assert isinstance(s, str)
        assert "BLEU" in s


# ===========================================================================
# Part II: ABTestConfig
# ===========================================================================


class TestABTestConfig:
    def test_valid_config_creation(self):
        cfg = ABTestConfig(name="test", segmenter="jieba", use_glossary=True)
        assert cfg.name == "test"
        assert cfg.segmenter == "jieba"
        assert cfg.use_glossary is True

    def test_default_segmenter_is_jieba(self):
        cfg = ABTestConfig(name="x")
        assert cfg.segmenter == "jieba"

    def test_invalid_segmenter_raises(self):
        with pytest.raises(ValueError, match="Invalid segmenter"):
            ABTestConfig(name="bad", segmenter="unknown_backend")

    def test_pkuseg_is_valid(self):
        cfg = ABTestConfig(name="x", segmenter="pkuseg")
        assert cfg.segmenter == "pkuseg"

    def test_fallback_is_valid(self):
        cfg = ABTestConfig(name="x", segmenter="fallback")
        assert cfg.segmenter == "fallback"

    def test_explicit_glossary_dict(self, manufacturing_glossary):
        cfg = ABTestConfig(name="x", glossary=manufacturing_glossary)
        assert cfg.glossary == manufacturing_glossary


# ===========================================================================
# Part III: ABTestRunner (with mock translate_fn)
# ===========================================================================


class TestABTestRunner:
    def test_runner_returns_results_for_all_configs(self, mock_sentences):
        cfg_a = ABTestConfig(name="config_a")
        cfg_b = ABTestConfig(name="config_b")
        runner = ABTestRunner(
            mock_sentences,
            translate_fn=_make_mock_translate(False),
        )
        results = runner.run([cfg_a, cfg_b])
        assert "config_a" in results
        assert "config_b" in results

    def test_runner_result_count_matches_sentences(self, mock_sentences):
        cfg = ABTestConfig(name="test_cfg")
        runner = ABTestRunner(
            mock_sentences,
            translate_fn=_make_mock_translate(),
        )
        results = runner.run([cfg])
        assert len(results["test_cfg"]) == len(mock_sentences)

    def test_runner_stores_chinese_in_result(self, mock_sentences):
        cfg = ABTestConfig(name="c")
        runner = ABTestRunner(mock_sentences, translate_fn=_make_mock_translate())
        results = runner.run([cfg])
        for result, (zh, ref) in zip(results["c"], mock_sentences):
            assert result.chinese == zh

    def test_runner_stores_reference_in_result(self, mock_sentences):
        cfg = ABTestConfig(name="c")
        runner = ABTestRunner(mock_sentences, translate_fn=_make_mock_translate())
        results = runner.run([cfg])
        for result, (zh, ref) in zip(results["c"], mock_sentences):
            assert result.reference == ref

    def test_runner_computes_metrics(self, mock_sentences):
        cfg = ABTestConfig(name="c")
        runner = ABTestRunner(mock_sentences, translate_fn=_make_mock_translate())
        results = runner.run([cfg])
        for r in results["c"]:
            assert r.metrics is not None
            assert isinstance(r.metrics.bleu, float)

    def test_runner_records_elapsed_time(self, mock_sentences):
        cfg = ABTestConfig(name="c")
        runner = ABTestRunner(mock_sentences, translate_fn=_make_mock_translate())
        results = runner.run([cfg])
        for r in results["c"]:
            assert r.elapsed_ms >= 0.0

    def test_runner_handles_plain_string_sentences(self):
        sentences = ["镀锌钢板", "热处理"]
        cfg = ABTestConfig(name="c")
        runner = ABTestRunner(sentences, translate_fn=_make_mock_translate())
        results = runner.run([cfg])
        assert len(results["c"]) == 2
        for r in results["c"]:
            assert r.reference == ""

    def test_runner_handles_translation_exception(self):
        def failing_translate(chinese, glossary):
            raise RuntimeError("Simulated failure")

        cfg = ABTestConfig(name="fail_cfg")
        runner = ABTestRunner(["镀锌"], translate_fn=failing_translate)
        results = runner.run([cfg])
        assert results["fail_cfg"][0].error != ""

    def test_glossary_aware_translate_scores_higher(self, manufacturing_glossary):
        """Config with glossary-aware translation should find more glossary terms in output."""
        sentences = [
            ("镀锌钢板和表面处理工艺", "galvanized steel and surface treatment"),
            ("热处理后的公差", "tolerances after heat treatment"),
        ]

        cfg_naive = ABTestConfig(
            name="naive",
            use_glossary=True,
            glossary=manufacturing_glossary,
        )
        cfg_aware = ABTestConfig(
            name="aware",
            use_glossary=True,
            glossary=manufacturing_glossary,
        )

        # Naive translate: does NOT use glossary in output
        naive_fn = _make_mock_translate(glossary_lookup=False)
        aware_fn = _make_mock_translate(glossary_lookup=True)

        # Run separately to control translate_fn
        runner_naive = ABTestRunner(sentences, translate_fn=naive_fn)
        results_naive = runner_naive.run([cfg_naive])

        runner_aware = ABTestRunner(sentences, translate_fn=aware_fn)
        results_aware = runner_aware.run([cfg_aware])

        # Glossary-aware output should have higher glossary coverage
        naive_cov = [r.metrics.glossary_coverage_score for r in results_naive["naive"] if r.metrics]
        aware_cov = [r.metrics.glossary_coverage_score for r in results_aware["aware"] if r.metrics]
        assert sum(aware_cov) > sum(naive_cov)


# ===========================================================================
# Part IV: ABTestEvaluator
# ===========================================================================


@pytest.fixture()
def sample_results(mock_sentences, manufacturing_glossary):
    """Pre-computed results for two configs using mock translate."""
    cfg_a = ABTestConfig(name="baseline", use_glossary=False)
    cfg_b = ABTestConfig(
        name="with_glossary",
        use_glossary=True,
        glossary=manufacturing_glossary,
    )
    runner = ABTestRunner(
        mock_sentences,
        translate_fn=_make_mock_translate(glossary_lookup=True),
    )
    return runner.run([cfg_a, cfg_b])


class TestABTestEvaluator:
    def test_aggregate_returns_dict(self, sample_results):
        ev = ABTestEvaluator(sample_results)
        agg = ev.aggregate("baseline")
        assert isinstance(agg, dict)

    def test_aggregate_has_expected_keys(self, sample_results):
        ev = ABTestEvaluator(sample_results)
        agg = ev.aggregate("baseline")
        for key in ("bleu", "cer", "token_overlap", "glossary_coverage"):
            assert key in agg

    def test_aggregate_unknown_config_returns_empty(self, sample_results):
        ev = ABTestEvaluator(sample_results)
        assert ev.aggregate("nonexistent") == {}

    def test_all_aggregates_has_all_configs(self, sample_results):
        ev = ABTestEvaluator(sample_results)
        agg = ev.all_aggregates()
        assert "baseline" in agg
        assert "with_glossary" in agg

    def test_best_config_bleu_returns_string(self, sample_results):
        ev = ABTestEvaluator(sample_results)
        best = ev.best_config(metric="bleu")
        assert best in ("baseline", "with_glossary")

    def test_best_config_cer_lower_is_better(self, sample_results):
        ev = ABTestEvaluator(sample_results)
        best = ev.best_config(metric="cer")
        assert best in ("baseline", "with_glossary")

    def test_compare_pair_length_matches_sentences(self, sample_results, mock_sentences):
        ev = ABTestEvaluator(sample_results)
        comparisons = ev.compare_pair("baseline", "with_glossary")
        assert len(comparisons) == len(mock_sentences)

    def test_compare_pair_has_required_fields(self, sample_results):
        ev = ABTestEvaluator(sample_results)
        comparisons = ev.compare_pair("baseline", "with_glossary")
        for cmp in comparisons:
            for key in ("chinese", "hypothesis_a", "hypothesis_b", "bleu_a", "bleu_b", "bleu_delta"):
                assert key in cmp

    def test_summary_table_is_string(self, sample_results):
        ev = ABTestEvaluator(sample_results)
        table = ev.summary_table()
        assert isinstance(table, str)
        assert "baseline" in table
        assert "with_glossary" in table

    def test_diff_report_is_string(self, sample_results):
        ev = ABTestEvaluator(sample_results)
        report = ev.diff_report("baseline", "with_glossary")
        assert isinstance(report, str)
        assert "baseline" in report
        assert "with_glossary" in report

    def test_empty_evaluator_summary_table(self):
        ev = ABTestEvaluator({})
        assert ev.summary_table() == "(no results)"

    def test_best_config_empty_returns_none(self):
        ev = ABTestEvaluator({})
        assert ev.best_config() is None


# ===========================================================================
# Part V: Four A/B Scenarios (using mock translate for speed)
# ===========================================================================


class TestFourScenarios:
    """Verify the four required A/B test scenarios produce valid, comparable results."""

    def _run_scenario(self, config_a, config_b, sentences=None, translate_fn=None):
        if sentences is None:
            sentences = MANUFACTURING_SENTENCES[:3]
        if translate_fn is None:
            translate_fn = _make_mock_translate(glossary_lookup=True)
        runner = ABTestRunner(sentences, translate_fn=translate_fn)
        results = runner.run([config_a, config_b])
        evaluator = ABTestEvaluator(results)
        return results, evaluator

    def test_scenario_1_jieba_vs_jieba_glossary(self):
        """Scenario 1: Jieba only vs Jieba + glossary."""
        cfg_a = ABTestConfig(name="jieba_only", segmenter="jieba", use_glossary=False)
        cfg_b = ABTestConfig(name="jieba_glossary", segmenter="jieba", use_glossary=True)
        results, ev = self._run_scenario(cfg_a, cfg_b)

        assert len(results["jieba_only"]) == 3
        assert len(results["jieba_glossary"]) == 3

        agg_a = ev.aggregate("jieba_only")
        agg_b = ev.aggregate("jieba_glossary")
        assert "bleu" in agg_a and "bleu" in agg_b

    def test_scenario_2_pkuseg_vs_pkuseg_glossary(self):
        """Scenario 2: PKUSEG only vs PKUSEG + glossary."""
        cfg_a = ABTestConfig(name="pkuseg_only", segmenter="pkuseg", use_glossary=False)
        cfg_b = ABTestConfig(name="pkuseg_glossary", segmenter="pkuseg", use_glossary=True)
        results, ev = self._run_scenario(cfg_a, cfg_b)

        assert len(results["pkuseg_only"]) == 3
        assert len(results["pkuseg_glossary"]) == 3

    def test_scenario_3_jieba_glossary_vs_pkuseg_glossary(self):
        """Scenario 3: Jieba + glossary vs PKUSEG + glossary."""
        cfg_a = ABTestConfig(name="jieba_glossary", segmenter="jieba", use_glossary=True)
        cfg_b = ABTestConfig(name="pkuseg_glossary", segmenter="pkuseg", use_glossary=True)
        results, ev = self._run_scenario(cfg_a, cfg_b)

        assert len(results["jieba_glossary"]) == 3
        assert len(results["pkuseg_glossary"]) == 3

        # Both configs use glossary; evaluator should select a best config
        best = ev.best_config(metric="bleu")
        assert best in ("jieba_glossary", "pkuseg_glossary")

    def test_scenario_4_baseline_vs_full(self):
        """Scenario 4: Original baseline (no glossary) vs full (Jieba + glossary)."""
        cfg_a = ABTestConfig(name="baseline", segmenter="jieba", use_glossary=False)
        cfg_b = ABTestConfig(
            name="full",
            segmenter="jieba",
            use_glossary=True,
            description="Jieba segmenter + manufacturing glossary (Priority 1 state)",
        )
        results, ev = self._run_scenario(cfg_a, cfg_b)

        table = ev.summary_table()
        assert "baseline" in table
        assert "full" in table

        report = ev.diff_report("baseline", "full")
        assert "baseline" in report
        assert "full" in report

    def test_all_four_scenarios_produce_metrics(self):
        """All four scenarios should produce valid float metrics."""
        configs = [
            ABTestConfig(name="jieba_only", segmenter="jieba", use_glossary=False),
            ABTestConfig(name="jieba_glossary", segmenter="jieba", use_glossary=True),
            ABTestConfig(name="pkuseg_only", segmenter="pkuseg", use_glossary=False),
            ABTestConfig(name="pkuseg_glossary", segmenter="pkuseg", use_glossary=True),
        ]
        runner = ABTestRunner(
            MANUFACTURING_SENTENCES[:5],
            translate_fn=_make_mock_translate(glossary_lookup=True),
        )
        results = runner.run(configs)
        evaluator = ABTestEvaluator(results)

        aggs = evaluator.all_aggregates()
        assert len(aggs) == 4

        for name, agg in aggs.items():
            assert 0.0 <= agg["bleu"] <= 1.0, f"{name}: BLEU out of range"
            assert agg["cer"] >= 0.0, f"{name}: CER negative"
            assert 0.0 <= agg["token_overlap"] <= 1.0
            assert 0.0 <= agg["glossary_coverage"] <= 1.0


# ===========================================================================
# Part VI: Integration tests (require CC-CEDICT DB; skipped if unavailable)
# ===========================================================================


class TestIntegrationWithPipeline:
    """End-to-end A/B tests using the real translation pipeline.

    These are automatically skipped if the CC-CEDICT database is not present.
    """

    @pytest.fixture(autouse=True)
    def require_pipeline(self):
        try:
            from zh_en_translator.engines.dictionary import ensure_cedict
            from zh_en_translator.engines.pipeline import translate_to_string
            cedict_path = ensure_cedict()
            db_path = cedict_path.with_suffix(".db")
            if not db_path.exists():
                from zh_en_translator.engines.dictionary import Dictionary
                Dictionary.build_from_cedict(cedict_path, db_path)
        except Exception as e:
            pytest.skip(f"CC-CEDICT pipeline unavailable: {e}")

    def test_real_pipeline_returns_string(self):
        from zh_en_translator.engines.pipeline import translate_to_string
        result = translate_to_string("镀锌")
        assert isinstance(result, str)

    def test_real_pipeline_jieba_vs_glossary(self):
        """Live test: jieba without glossary vs with manufacturing glossary."""
        from zh_en_translator.engines.glossary import load_all_glossaries

        glossary = load_all_glossaries()
        sentences = [
            ("镀锌钢板和表面处理工艺", "galvanized steel and surface treatment"),
            ("热处理后的硬度和精度公差", "hardness and tolerance after heat treatment"),
        ]

        cfg_a = ABTestConfig(name="no_glossary", segmenter="jieba", use_glossary=False)
        cfg_b = ABTestConfig(
            name="with_glossary",
            segmenter="jieba",
            use_glossary=True,
            glossary=glossary,
        )

        runner = ABTestRunner(sentences)
        results = runner.run([cfg_a, cfg_b])
        ev = ABTestEvaluator(results)

        agg_a = ev.aggregate("no_glossary")
        agg_b = ev.aggregate("with_glossary")

        # Basic sanity: results are well-formed
        assert "bleu" in agg_a
        assert "bleu" in agg_b

        # Both configs produce valid coverage scores in [0, 1]
        assert 0.0 <= agg_a["glossary_coverage"] <= 1.0
        assert 0.0 <= agg_b["glossary_coverage"] <= 1.0
