"""Tests for Priority 2 Phase 2: expanded corpus and A/B test execution.

Verifies:
- Corpus has 100+ entries, no duplicates, valid format
- A/B test runs without errors and computes metrics
- Glossary-aware config scores higher glossary_coverage than baseline
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from zh_en_translator.corpus.corpus_manager import CorpusManager, CorpusEntry
from zh_en_translator.evaluation.metrics import score_translation, glossary_coverage


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

CORPUS_FILE = (
    Path(__file__).parent.parent
    / "src/zh_en_translator/corpus/examples/manufacturing_samples.jsonl"
)


# ---------------------------------------------------------------------------
# Helper: small manufacturing glossary for tests
# ---------------------------------------------------------------------------

SAMPLE_GLOSSARY = {
    "镀锌": "galvanized",
    "表面处理": "surface treatment",
    "热处理": "heat treatment",
    "硬度": "hardness",
    "公差": "tolerance",
    "焊接": "welding",
    "轴承": "bearing",
    "齿轮": "gear",
    "螺栓": "bolt",
    "铸铁": "cast iron",
    "铝合金": "aluminum alloy",
    "不锈钢": "stainless steel",
    "检验": "inspection",
    "质量控制": "quality control",
    "装配": "assembly",
    "零件": "component",
    "淬火": "quenching",
    "退火": "annealing",
    "冲压": "stamping",
    "铣削": "milling",
}


# ===========================================================================
# Part I: Corpus Validation Tests
# ===========================================================================


class TestCorpusExpanded:
    """Verify the expanded manufacturing corpus meets quality requirements."""

    def test_corpus_file_exists(self):
        assert CORPUS_FILE.exists(), f"Corpus file not found: {CORPUS_FILE}"

    def test_corpus_has_100_or_more_entries(self):
        mgr = CorpusManager()
        count = mgr.load_file(CORPUS_FILE)
        assert count >= 100, f"Expected >= 100 entries, got {count}"

    def test_corpus_no_duplicate_chinese(self):
        seen = set()
        duplicates = []
        for line in CORPUS_FILE.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            d = json.loads(line)
            zh = d.get("chinese", "")
            if zh in seen:
                duplicates.append(zh[:40])
            seen.add(zh)
        assert not duplicates, f"Duplicate Chinese sentences found: {duplicates[:3]}"

    def test_corpus_all_entries_valid_json(self):
        lines = CORPUS_FILE.read_text(encoding="utf-8").splitlines()
        for i, line in enumerate(lines, 1):
            line = line.strip()
            if not line:
                continue
            try:
                json.loads(line)
            except json.JSONDecodeError as e:
                pytest.fail(f"Line {i} is not valid JSON: {e}")

    def test_corpus_required_fields_present(self):
        required = {"source", "chinese", "english", "domain", "verified"}
        missing_field_lines = []
        for i, line in enumerate(CORPUS_FILE.read_text(encoding="utf-8").splitlines(), 1):
            line = line.strip()
            if not line:
                continue
            d = json.loads(line)
            missing = required - d.keys()
            if missing:
                missing_field_lines.append(f"Line {i}: missing {missing}")
        assert not missing_field_lines, f"Entries with missing fields: {missing_field_lines[:5]}"

    def test_corpus_no_empty_chinese_or_english(self):
        for i, line in enumerate(CORPUS_FILE.read_text(encoding="utf-8").splitlines(), 1):
            line = line.strip()
            if not line:
                continue
            d = json.loads(line)
            assert d.get("chinese", "").strip(), f"Line {i}: empty 'chinese' field"
            assert d.get("english", "").strip(), f"Line {i}: empty 'english' field"

    def test_corpus_domains_are_manufacturing_or_materials(self):
        valid_domains = {"manufacturing", "materials"}
        bad_domains = []
        for i, line in enumerate(CORPUS_FILE.read_text(encoding="utf-8").splitlines(), 1):
            line = line.strip()
            if not line:
                continue
            d = json.loads(line)
            dom = d.get("domain", "")
            if dom not in valid_domains:
                bad_domains.append(f"Line {i}: domain='{dom}'")
        assert not bad_domains, f"Unexpected domain values: {bad_domains[:5]}"

    def test_corpus_manager_loads_all_entries(self):
        mgr = CorpusManager()
        mgr.load_file(CORPUS_FILE)
        stats = mgr.stats()
        assert stats["total"] >= 100
        assert "manufacturing" in stats["domains"]

    def test_corpus_mostly_verified(self):
        """At least 95% of entries should be verified=True."""
        entries = []
        for line in CORPUS_FILE.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            entries.append(json.loads(line))
        verified = sum(1 for e in entries if e.get("verified", False))
        ratio = verified / len(entries)
        assert ratio >= 0.95, f"Only {verified}/{len(entries)} entries verified ({ratio:.1%})"

    def test_corpus_iter_entries_by_domain(self):
        mgr = CorpusManager()
        mgr.load_file(CORPUS_FILE)
        mfg_entries = list(mgr.iter_entries(domain="manufacturing"))
        mat_entries = list(mgr.iter_entries(domain="materials"))
        assert len(mfg_entries) > 0
        assert len(mat_entries) > 0
        assert len(mfg_entries) + len(mat_entries) == mgr.count()


# ===========================================================================
# Part II: A/B Test Execution Tests
# ===========================================================================


class TestABTestExecution:
    """Verify the A/B test runs without errors and produces valid metrics."""

    def _naive_translate(self, chinese: str, glossary: dict) -> str:
        """Simulate baseline translation without glossary lookup."""
        generic = {
            "的": "of", "和": "and", "需要": "requires",
            "处理": "processing", "零件": "parts", "标准": "standard",
        }
        tokens = [en for zh, en in generic.items() if zh in chinese]
        return " ".join(tokens) if tokens else "standard manufacturing process"

    def _glossary_translate(self, chinese: str, glossary: dict) -> str:
        """Simulate glossary-aware translation with domain term substitution."""
        found = []
        for zh_key in sorted(glossary.keys(), key=len, reverse=True):
            if zh_key in chinese:
                found.append(glossary[zh_key].split("/")[0].strip())
        return " ".join(found) if found else "component processing"

    def test_ab_metrics_computed_for_all_sentences(self):
        """A/B test should compute metrics for each sentence without errors."""
        sentences = [
            ("镀锌钢板的表面处理工艺", "galvanized steel sheet surface treatment process"),
            ("热处理后的硬度和精度公差", "hardness and dimensional tolerances after heat treatment"),
            ("零件焊接和冲压件检验", "welded component and stamped part inspection"),
        ]
        for chinese, reference in sentences:
            hyp_a = self._naive_translate(chinese, {})
            hyp_b = self._glossary_translate(chinese, SAMPLE_GLOSSARY)
            m_a = score_translation(hyp_a, reference, glossary=SAMPLE_GLOSSARY)
            m_b = score_translation(hyp_b, reference, glossary=SAMPLE_GLOSSARY)
            assert m_a is not None
            assert m_b is not None
            assert 0.0 <= m_a.bleu <= 1.0
            assert 0.0 <= m_b.bleu <= 1.0

    def test_glossary_aware_has_higher_coverage_than_naive(self):
        """Glossary-aware translation should produce higher glossary_coverage."""
        sentences = [
            "镀锌钢板的表面处理工艺需要严格控制温度和时间。",
            "热处理后的硬度和精度公差必须符合GB/T标准要求。",
            "零件焊接和冲压件检验需要专业的质量控制流程。",
            "轴承的径向游隙应符合JB/T 10235规定的C3级别要求。",
            "齿轮加工完成后需进行渗碳淬火处理，表面硬度要求HRC58-62。",
        ]

        naive_covs = []
        glossary_covs = []

        for chinese in sentences:
            hyp_a = self._naive_translate(chinese, {})
            hyp_b = self._glossary_translate(chinese, SAMPLE_GLOSSARY)
            cov_a = glossary_coverage(hyp_a, SAMPLE_GLOSSARY)
            cov_b = glossary_coverage(hyp_b, SAMPLE_GLOSSARY)
            naive_covs.append(cov_a)
            glossary_covs.append(cov_b)

        mean_naive = sum(naive_covs) / len(naive_covs)
        mean_glossary = sum(glossary_covs) / len(glossary_covs)
        assert mean_glossary > mean_naive, (
            f"Expected glossary config to have higher mean coverage "
            f"({mean_glossary:.3f}) than naive ({mean_naive:.3f})"
        )

    def test_ab_runs_on_30_sentence_subset(self):
        """A/B test should complete on 30-sentence subset without exceptions."""
        mgr = CorpusManager()
        mgr.load_file(CORPUS_FILE)
        sentences = [(e.chinese, e.english) for e in mgr.iter_entries()][:30]
        assert len(sentences) == 30

        all_passed = True
        for chinese, reference in sentences:
            try:
                hyp_a = self._naive_translate(chinese, {})
                hyp_b = self._glossary_translate(chinese, SAMPLE_GLOSSARY)
                m_a = score_translation(hyp_a, reference, glossary=SAMPLE_GLOSSARY)
                m_b = score_translation(hyp_b, reference, glossary=SAMPLE_GLOSSARY)
                assert 0.0 <= m_a.glossary_coverage_score <= 1.0
                assert 0.0 <= m_b.glossary_coverage_score <= 1.0
            except Exception as e:
                all_passed = False
                pytest.fail(f"Error on sentence '{chinese[:40]}': {e}")

        assert all_passed

    def test_aggregated_metrics_in_valid_range(self):
        """Mean metrics over 30 sentences should be in [0, 1]."""
        mgr = CorpusManager()
        mgr.load_file(CORPUS_FILE)
        sentences = [(e.chinese, e.english) for e in mgr.iter_entries()][:30]

        bleus_a, bleus_b = [], []
        covs_a, covs_b = [], []

        for chinese, reference in sentences:
            hyp_a = self._naive_translate(chinese, {})
            hyp_b = self._glossary_translate(chinese, SAMPLE_GLOSSARY)
            m_a = score_translation(hyp_a, reference, glossary=SAMPLE_GLOSSARY)
            m_b = score_translation(hyp_b, reference, glossary=SAMPLE_GLOSSARY)
            bleus_a.append(m_a.bleu)
            bleus_b.append(m_b.bleu)
            covs_a.append(m_a.glossary_coverage_score)
            covs_b.append(m_b.glossary_coverage_score)

        for metric_name, values in [
            ("BLEU_A", bleus_a), ("BLEU_B", bleus_b),
            ("Cov_A", covs_a), ("Cov_B", covs_b),
        ]:
            mean = sum(values) / len(values)
            assert 0.0 <= mean <= 1.0, f"Mean {metric_name} out of range: {mean}"

    def test_ab_tester_framework_works_with_corpus(self):
        """ABTestRunner and ABTestEvaluator should work with corpus sentences."""
        from zh_en_translator.evaluation.a_b_tester import (
            ABTestConfig, ABTestRunner, ABTestEvaluator,
        )

        mgr = CorpusManager()
        mgr.load_file(CORPUS_FILE)
        sentences = [(e.chinese, e.english) for e in mgr.iter_entries()][:5]

        cfg_a = ABTestConfig(name="baseline", segmenter="jieba", use_glossary=False)
        cfg_b = ABTestConfig(
            name="with_glossary",
            segmenter="jieba",
            use_glossary=True,
            glossary=SAMPLE_GLOSSARY,
        )

        def mock_translate(chinese, glossary):
            if glossary:
                return self._glossary_translate(chinese, glossary)
            return self._naive_translate(chinese, {})

        runner = ABTestRunner(sentences, translate_fn=mock_translate)
        results = runner.run([cfg_a, cfg_b])
        evaluator = ABTestEvaluator(results)

        agg_a = evaluator.aggregate("baseline")
        agg_b = evaluator.aggregate("with_glossary")

        assert "bleu" in agg_a
        assert "glossary_coverage" in agg_b
        assert agg_b["glossary_coverage"] >= 0.0

        table = evaluator.summary_table()
        assert "baseline" in table
        assert "with_glossary" in table
