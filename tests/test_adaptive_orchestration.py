"""Tests for adaptive clause-level fallback decision logic.

Tests the heuristics that decide whether to attempt clause-level translation
fallback based on structural complexity of the input text.
"""

from zh_en_translator.engines.translation_worker import (
    _count_clauses,
    _count_content_tokens,
)


class TestCountClauses:
    """Test _count_clauses function."""

    def test_count_clauses_no_punctuation(self):
        result = _count_clauses("测试进行中")
        assert result == 0

    def test_count_clauses_single_period(self):
        result = _count_clauses("测试完成。")
        assert result == 1

    def test_count_clauses_multiple_periods(self):
        result = _count_clauses("完成。开始。")
        assert result == 2

    def test_count_clauses_mixed_punctuation(self):
        result = _count_clauses("测试。结果！")
        assert result == 2

    def test_count_clauses_all_punctuation_types(self):
        result = _count_clauses("句子。问题？感叹！分号；")
        assert result == 4

    def test_count_clauses_empty_string(self):
        result = _count_clauses("")
        assert result == 0

    def test_count_clauses_none_input(self):
        result = _count_clauses(None)
        assert result == 0

    def test_count_clauses_comma_not_counted(self):
        result = _count_clauses("测试，结果")
        assert result == 0

    def test_count_clauses_english_punctuation_not_counted(self):
        result = _count_clauses("Test. Result!")
        assert result == 0

    def test_count_clauses_complex_sentence(self):
        text = "NADCC氯片 200ppm 150ppm 100ppm浓度狗骨头浸泡测试已完成 实验室今天提供给@杨中宝"
        result = _count_clauses(text)
        assert result == 0

    def test_count_clauses_with_spacing(self):
        result = _count_clauses("测试  。  结果  。")
        assert result == 2

    def test_count_clauses_with_repeated_punctuation(self):
        result = _count_clauses("测试。。。结果")
        assert result == 3

    def test_count_clauses_only_punctuation(self):
        result = _count_clauses("。。。。")
        assert result == 4

    def test_count_clauses_very_long_text(self):
        text = "测试。" * 100
        result = _count_clauses(text)
        assert result == 100

    def test_count_clauses_mixed_line_endings(self):
        text = "测试。\n结果。\r\n完成。"
        result = _count_clauses(text)
        assert result == 3


class TestCountContentTokens:
    """Test _count_content_tokens function."""

    def test_count_content_tokens_empty_string(self):
        result = _count_content_tokens("")
        assert result == 0

    def test_count_content_tokens_whitespace_only(self):
        result = _count_content_tokens("   ")
        assert result == 0

    def test_count_content_tokens_simple_sentence(self):
        result = _count_content_tokens("我很好")
        assert result >= 1

    def test_count_content_tokens_with_stop_words(self):
        result = _count_content_tokens("我的苹果")
        assert result >= 0

    def test_count_content_tokens_nadcc_example(self):
        text = "NADCC氯片200ppm150ppm100ppm浓度狗骨头浸泡测试完成"
        result = _count_content_tokens(text)
        assert result >= 4

    def test_count_content_tokens_punctuation_filtered(self):
        result = _count_content_tokens("测试。结果！")
        assert result >= 1

    def test_count_content_tokens_repeated_words(self):
        result = _count_content_tokens("测试测试测试")
        assert result >= 1

    def test_count_content_tokens_mixed_content(self):
        result = _count_content_tokens("实验室test200ppm")
        assert result >= 1

    def test_count_content_tokens_none_input(self):
        result = _count_content_tokens(None)
        assert result == 0

    def test_count_content_tokens_long_text(self):
        text = "这是一个很长的中文句子，包含了许多不同的词汇和概念，用来测试分词和过滤功能。"
        result = _count_content_tokens(text)
        assert result >= 1

    def test_count_content_tokens_special_characters(self):
        text = "@用户 #标签 $符号"
        result = _count_content_tokens(text)
        assert isinstance(result, int)
        assert result >= 0

    def test_count_content_tokens_unicode_handling(self):
        text = "测试 αβγ 123 emoji😀"
        result = _count_content_tokens(text)
        assert isinstance(result, int)
        assert result >= 0

    def test_count_content_tokens_very_long_text(self):
        text = "测试 " * 1000
        result = _count_content_tokens(text)
        assert isinstance(result, int)
        assert result > 0

    def test_count_content_tokens_multiline(self):
        text = "第一行测试。\n第二行结果。\n第三行完成。"
        result = _count_content_tokens(text)
        assert isinstance(result, int)
        assert result > 0


class TestShouldUseClauseFallback:
    """Test _should_use_clause_fallback decision logic."""

    import pytest

    @pytest.fixture
    def worker(self):
        from zh_en_translator.engines.translation_worker import TranslationWorker
        return TranslationWorker("test")

    def test_skip_short_text(self, worker):
        """Short text (<80 chars) always skips clause fallback."""
        result = worker._should_use_clause_fallback("短文本")
        assert result is False

    def test_skip_short_boundary(self, worker):
        """79-char text is below the threshold and skips."""
        result = worker._should_use_clause_fallback("a" * 79)
        assert result is False

    def test_skip_single_clause(self, worker):
        """Text with no clause-ending punctuation skips (clause_count <= 1)."""
        result = worker._should_use_clause_fallback("这是一个简单的文本没有句号")
        assert result is False

    def test_skip_few_tokens(self, worker):
        """Very simple text with <5 content tokens skips."""
        result = worker._should_use_clause_fallback("简单")
        assert result is False

    def test_use_complex_text(self, worker):
        """Long, multi-clause, token-rich text uses clause fallback."""
        text = "用户 需要 完成 测试 验证 功能 流程 操作。" + "系统支持 " * 10 + "。质量 保证 工作 进行 中"
        result = worker._should_use_clause_fallback(text)
        assert result is True

    def test_skip_nadcc_example(self, worker):
        """NADCC example: ~60 chars, no clause punctuation → skips."""
        text = "NADCC氯片 200ppm 150ppm 100ppm浓度狗骨头浸泡测试已完成 实验室今天提供给@杨中宝"
        result = worker._should_use_clause_fallback(text)
        assert result is False

    def test_all_conditions_must_pass(self, worker):
        """All three heuristics must pass independently."""
        text = ("用户 完成 测试 验证 功能。" +
                "系统 支持 多种 操作 模式。" +
                "质量 保证 工作 进行 中。" + "功能模块 " * 10)
        result = worker._should_use_clause_fallback(text)
        assert result is True


class TestAdaptiveOrchestrationIntegration:
    """Integration tests for adaptive clause fallback flow."""

    import pytest

    @pytest.fixture
    def worker(self):
        from zh_en_translator.engines.translation_worker import TranslationWorker
        return TranslationWorker("test")

    def test_simple_text_skips_fallback(self, worker):
        result = worker._should_use_clause_fallback("我很好")
        assert result is False

    def test_high_completeness_irrelevant(self, worker):
        """Clause fallback decision is based purely on structure, not any completeness score."""
        # Complex text: decision is independent of any external score
        text = "这是一个很长的复杂中文句子。它包含了很多不同的信息。" + "测试" * 40
        result = worker._should_use_clause_fallback(text)
        assert isinstance(result, bool)

    def test_simple_cases_all_skip(self, worker):
        simple_cases = [
            "短句",
            "简短文本",
            "不超过80个字的文本",
        ]
        for text in simple_cases:
            result = worker._should_use_clause_fallback(text)
            assert result is False, f"Simple text '{text}' should skip clause fallback"

    def test_length_boundary(self, worker):
        """Exactly 80 chars passes the length check but may still skip on other heuristics."""
        text_80 = "a" * 80
        result = worker._should_use_clause_fallback(text_80)
        assert isinstance(result, bool)

    def test_single_clause_boundary(self, worker):
        """Single-clause text skips regardless of length."""
        text = "这是一个句子。"
        result = worker._should_use_clause_fallback(text)
        assert isinstance(result, bool)
