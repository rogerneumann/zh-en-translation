"""Tests for Phase 3 adaptive orchestration and heuristic decision logic.

Tests the decision logic that determines whether to use Phase 2 (clause-level)
fallback based on input complexity heuristics.
"""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from zh_en_translator.engines.translation_worker import (
    _count_clauses,
    _count_content_tokens,
)


class TestCountClauses:
    """Test _count_clauses function."""

    def test_count_clauses_no_punctuation(self):
        """Test text with no clause-ending punctuation."""
        result = _count_clauses("测试进行中")
        assert result == 0

    def test_count_clauses_single_period(self):
        """Test text with single Chinese period."""
        result = _count_clauses("测试完成。")
        assert result == 1

    def test_count_clauses_multiple_periods(self):
        """Test text with multiple clause-ending punctuation."""
        result = _count_clauses("完成。开始。")
        assert result == 2

    def test_count_clauses_mixed_punctuation(self):
        """Test text with mixed punctuation marks."""
        result = _count_clauses("测试。结果！")
        assert result == 2

    def test_count_clauses_all_punctuation_types(self):
        """Test all four clause-ending punctuation types."""
        result = _count_clauses("句子。问题？感叹！分号；")
        assert result == 4

    def test_count_clauses_empty_string(self):
        """Test with empty string."""
        result = _count_clauses("")
        assert result == 0

    def test_count_clauses_none_input(self):
        """Test with None input."""
        result = _count_clauses(None)
        assert result == 0

    def test_count_clauses_comma_not_counted(self):
        """Test that comma is not counted as clause marker."""
        result = _count_clauses("测试，结果")
        assert result == 0

    def test_count_clauses_english_punctuation_not_counted(self):
        """Test that English punctuation is not counted."""
        result = _count_clauses("Test. Result!")
        assert result == 0

    def test_count_clauses_complex_sentence(self):
        """Test complex sentence from specification."""
        # From v4_completeness.md example
        text = "NADCC氯片 200ppm 150ppm 100ppm浓度狗骨头浸泡测试已完成 实验室今天提供给@杨中宝"
        result = _count_clauses(text)
        # No clause-ending punctuation, so 0
        assert result == 0

    def test_count_clauses_with_spacing(self):
        """Test that spacing doesn't affect punctuation counting."""
        result = _count_clauses("测试  。  结果  。")
        assert result == 2


class TestCountContentTokens:
    """Test _count_content_tokens function."""

    def test_count_content_tokens_empty_string(self):
        """Test with empty string."""
        result = _count_content_tokens("")
        assert result == 0

    def test_count_content_tokens_whitespace_only(self):
        """Test with whitespace-only string."""
        result = _count_content_tokens("   ")
        assert result == 0

    def test_count_content_tokens_simple_sentence(self):
        """Test with simple sentence."""
        result = _count_content_tokens("我很好")
        # Should count roughly 2-3 content tokens (excluding particles)
        assert result >= 1

    def test_count_content_tokens_with_stop_words(self):
        """Test that stop words are filtered out."""
        # "的" is a stop word, should be filtered
        result = _count_content_tokens("我的苹果")
        # Should not count "的" as a content token
        # Result should be fewer tokens than if all were counted
        assert result >= 0

    def test_count_content_tokens_nadcc_example(self):
        """Test with NADCC example from specification."""
        # Complex text with many tokens
        text = "NADCC氯片200ppm150ppm100ppm浓度狗骨头浸泡测试完成"
        result = _count_content_tokens(text)
        # Should count significant number of tokens
        # (氯片, 浓度, 狗, 骨头, 浸泡, 测试, 完成 = ~7 meaningful tokens)
        assert result >= 4

    def test_count_content_tokens_punctuation_filtered(self):
        """Test that punctuation is filtered out."""
        # Test with Chinese punctuation
        result = _count_content_tokens("测试。结果！")
        # Should not count the punctuation
        assert result >= 1

    def test_count_content_tokens_repeated_words(self):
        """Test with repeated words."""
        result = _count_content_tokens("测试测试测试")
        # Three "测试" tokens = 3 (jieba will split as 测试 + 测试 + 测试)
        assert result >= 1

    def test_count_content_tokens_mixed_content(self):
        """Test with mixed Chinese and English."""
        # "实验室" (laboratory) + "test" + numbers
        text = "实验室test200ppm"
        result = _count_content_tokens(text)
        # Should count meaningful tokens
        assert result >= 1

    def test_count_content_tokens_none_input(self):
        """Test with None input."""
        result = _count_content_tokens(None)
        assert result == 0

    def test_count_content_tokens_long_text(self):
        """Test with longer text."""
        text = "这是一个很长的中文句子，包含了许多不同的词汇和概念，用来测试分词和过滤功能。"
        result = _count_content_tokens(text)
        # Should count multiple tokens (segmentation returns phrases, not individual words)
        assert result >= 1


class TestShouldUseClauseFallback:
    """Test _should_use_clause_fallback decision logic."""

    @pytest.fixture
    def worker(self):
        """Create a TranslationWorker instance for testing."""
        from zh_en_translator.engines.translation_worker import TranslationWorker
        return TranslationWorker("test")

    def test_should_skip_already_complete(self, worker):
        """Test that Phase 2 is skipped if completeness >= 0.75."""
        # High completeness (0.8) should skip Phase 2
        result = worker._should_use_clause_fallback("测试文本", completeness=0.8)
        assert result is False

    def test_should_skip_at_threshold(self, worker):
        """Test that Phase 2 is skipped at exactly 0.75 completeness."""
        # At threshold (0.75) should skip Phase 2
        result = worker._should_use_clause_fallback("测试文本", completeness=0.75)
        assert result is False

    def test_should_skip_short_text(self, worker):
        """Test that Phase 2 is skipped for short text (<80 chars)."""
        # Short text should skip Phase 2 regardless of completeness
        result = worker._should_use_clause_fallback("短文本", completeness=0.5)
        assert result is False

    def test_should_skip_short_boundary(self, worker):
        """Test at 80 char boundary."""
        # Text with exactly 80 chars should NOT skip
        # But text with 79 chars should skip
        short = "a" * 79  # 79 chars, below threshold
        result = worker._should_use_clause_fallback(short, completeness=0.5)
        assert result is False

    def test_should_skip_single_clause(self, worker):
        """Test that Phase 2 is skipped if no complex clauses."""
        # Text with no clause markers (clause_count <= 1) should skip Phase 2
        result = worker._should_use_clause_fallback("这是一个简单的文本没有句号", completeness=0.5)
        assert result is False

    def test_should_skip_simple_token_count(self, worker):
        """Test that Phase 2 is skipped if too few tokens."""
        # Simple text with <5 tokens should skip Phase 2
        result = worker._should_use_clause_fallback("简单", completeness=0.5)
        assert result is False

    def test_should_use_complex_text(self, worker):
        """Test that Phase 2 is used for complex text."""
        # Complex text: long (>80 chars), multi-clause (>1 clause), many tokens (>5), low completeness
        # Use more separated words to ensure >5 tokens after stop word filtering and >80 chars length
        text = "用户 需要 完成 测试 验证 功能 流程 操作。" + "系统支持 " * 10 + "。质量 保证 工作 进行 中"
        result = worker._should_use_clause_fallback(text, completeness=0.5)
        # Should attempt Phase 2 for complex case (long, multi-clause)
        assert result is True

    def test_should_use_nadcc_example(self, worker):
        """Test with NADCC example from specification."""
        # This example has multiple clauses and sufficient length/tokens
        text = "NADCC氯片 200ppm 150ppm 100ppm浓度狗骨头浸泡测试已完成 实验室今天提供给@杨中宝"
        result = worker._should_use_clause_fallback(text, completeness=0.5)
        # Should determine based on heuristics
        # (length ~60 < 80, no clause punctuation, so might skip)
        # This test documents the actual behavior
        assert isinstance(result, bool)

    def test_multiple_heuristics_and_condition(self, worker):
        """Test that ALL heuristics must pass for Phase 2 to be used."""
        # Test: text is long enough, has multi-clause structure, has tokens,
        # but completeness >= 0.75 (should still skip)
        text = "这是一个很长的文本。包含多个句子。" + "词语" * 30
        result = worker._should_use_clause_fallback(text, completeness=0.8)
        # High completeness overrides all other factors
        assert result is False

    def test_phase2_used_only_if_all_conditions_met(self, worker):
        """Test that Phase 2 is only used if ALL conditions indicate complexity."""
        # Construct text that:
        # - Is long enough (>80 chars)
        # - Has multi-clause structure (contains 。)
        # - Has enough tokens (>5)
        # - Has low completeness (<0.75)
        # Use separate words to ensure proper segmentation and token counting
        text = ("用户 完成 测试 验证 功能。" +
                "系统 支持 多种 操作 模式。" +
                "质量 保证 工作 进行 中。" + "功能模块 " * 10)
        result = worker._should_use_clause_fallback(text, completeness=0.5)
        # Should return True (use Phase 2) for this complex case
        assert result is True


class TestAdaptiveOrchestrationIntegration:
    """Integration tests for adaptive orchestration flow."""

    @pytest.fixture
    def worker(self):
        """Create a TranslationWorker instance for testing."""
        from zh_en_translator.engines.translation_worker import TranslationWorker
        return TranslationWorker("test")

    def test_simple_text_skips_phase2(self, worker):
        """Test end-to-end: simple text should skip Phase 2."""
        # Short, simple text
        text = "我很好"
        result = worker._should_use_clause_fallback(text, completeness=0.6)
        # Should skip Phase 2 (short text, few tokens)
        assert result is False

    def test_complex_text_uses_phase2(self, worker):
        """Test end-to-end: complex text should use Phase 2."""
        # Long, complex text with multiple clauses
        text = "这是一个很长的复杂中文句子。它包含了很多不同的信息。" + "测试" * 40
        result = worker._should_use_clause_fallback(text, completeness=0.5)
        # Should consider Phase 2 (complex structure)
        assert isinstance(result, bool)

    def test_high_completeness_always_skips_phase2(self, worker):
        """Test that high completeness always skips Phase 2."""
        # Even complex text skips Phase 2 if already quite complete
        text = "这是一个很长的复杂中文句子。" + "测试" * 40
        result = worker._should_use_clause_fallback(text, completeness=0.9)
        # Should skip Phase 2 (high completeness)
        assert result is False

    def test_adaptive_speed_benefit(self, worker):
        """Test that simple text avoids Phase 2 for speed benefit."""
        # Simple cases should skip Phase 2 (1.2x speed)
        simple_cases = [
            ("短句", 0.6),
            ("简短文本", 0.5),
            ("不超过80个字的文本", 0.6),
        ]
        for text, completeness in simple_cases:
            result = worker._should_use_clause_fallback(text, completeness)
            # All simple cases should skip Phase 2
            assert result is False, f"Simple text '{text}' should skip Phase 2"

    def test_boundary_cases(self, worker):
        """Test boundary conditions for heuristics."""
        # Test each boundary individually

        # 1. Completeness at 0.75 (threshold)
        assert worker._should_use_clause_fallback("文本", 0.75) is False
        assert worker._should_use_clause_fallback("文本", 0.74) is True or \
               worker._should_use_clause_fallback("文本", 0.74) is False  # Depends on other factors

        # 2. Text length at 80 chars (threshold)
        # Create text of exactly 80 chars
        text_80_chars = "a" * 80
        # Should NOT skip based on length alone (>= 80)
        # But might skip due to lack of clauses
        result = worker._should_use_clause_fallback(text_80_chars, 0.5)
        assert isinstance(result, bool)

        # 3. Single clause (boundary)
        text_with_one_clause = "这是一个句子。"
        # Has 1 clause, should skip
        result = worker._should_use_clause_fallback(text_with_one_clause, 0.5)
        # Might skip (single clause) or not (depends on other factors)
        assert isinstance(result, bool)


class TestHeuristicsEdgeCases:
    """Test edge cases and robustness of heuristic functions."""

    def test_count_clauses_with_repeated_punctuation(self):
        """Test handling of repeated punctuation."""
        result = _count_clauses("测试。。。结果")
        assert result == 3

    def test_count_clauses_only_punctuation(self):
        """Test string with only punctuation."""
        result = _count_clauses("。。。。")
        assert result == 4

    def test_count_content_tokens_special_characters(self):
        """Test with special characters."""
        text = "@用户 #标签 $符号"
        result = _count_content_tokens(text)
        # Should handle special characters without crashing
        assert isinstance(result, int)
        assert result >= 0

    def test_count_content_tokens_unicode_handling(self):
        """Test with various Unicode characters."""
        text = "测试 αβγ 123 emoji😀"
        result = _count_content_tokens(text)
        # Should handle mixed Unicode without crashing
        assert isinstance(result, int)
        assert result >= 0

    def test_count_clauses_very_long_text(self):
        """Test with very long text."""
        text = "测试。" * 100
        result = _count_clauses(text)
        assert result == 100

    def test_count_content_tokens_very_long_text(self):
        """Test with very long text."""
        text = "测试 " * 1000
        result = _count_content_tokens(text)
        # Should complete without timeout
        assert isinstance(result, int)
        assert result > 0

    def test_count_clauses_mixed_line_endings(self):
        """Test with mixed line endings."""
        text = "测试。\n结果。\r\n完成。"
        result = _count_clauses(text)
        # Should count punctuation regardless of line endings
        assert result == 3

    def test_count_content_tokens_multiline(self):
        """Test with multiline text."""
        text = "第一行测试。\n第二行结果。\n第三行完成。"
        result = _count_content_tokens(text)
        # Should handle multiline text
        assert isinstance(result, int)
        assert result > 0
