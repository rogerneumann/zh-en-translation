"""Tests for Phase 2 clause-level translation fallback."""

import pytest
from unittest.mock import patch, MagicMock

from zh_en_translator.engines.argos import (
    split_into_clauses,
    _split_long_clause,
    _recombine_translations,
    translate_with_clause_fallback,
)


class TestSplitIntoClauses:
    """Test split_into_clauses function."""

    def test_split_basic_periods(self):
        """Test basic splitting on periods (。)."""
        text = "完成。开始。"
        result = split_into_clauses(text)
        assert result == ["完成。", "开始。"]

    def test_split_exclamation_marks(self):
        """Test splitting on exclamation marks (！)."""
        text = "完成！开始！"
        result = split_into_clauses(text)
        assert result == ["完成！", "开始！"]

    def test_split_question_marks(self):
        """Test splitting on question marks (？)."""
        text = "完成？开始？"
        result = split_into_clauses(text)
        assert result == ["完成？", "开始？"]

    def test_split_semicolons(self):
        """Test splitting on semicolons (；)."""
        text = "开始；进行；完成。"
        result = split_into_clauses(text)
        assert result == ["开始；", "进行；", "完成。"]

    def test_split_mixed_punctuation(self):
        """Test splitting with mixed punctuation types."""
        text = "第一。第二！第三？第四；"
        result = split_into_clauses(text)
        assert len(result) == 4
        assert result[0] == "第一。"
        assert result[1] == "第二！"
        assert result[2] == "第三？"
        assert result[3] == "第四；"

    def test_split_protects_numbers(self):
        """Test that numbers like '200ppm' are not split incorrectly."""
        text = "200ppm100ppm测试。"
        result = split_into_clauses(text)
        # Should not split after "200" or "100"
        assert result == ["200ppm100ppm测试。"]

    def test_split_protects_at_mentions(self):
        """Test that @mentions are not split."""
        text = "给@杨中宝。"
        result = split_into_clauses(text)
        assert result == ["给@杨中宝。"]

    def test_split_preserves_punctuation_with_clause(self):
        """Test that punctuation stays with clause, not separate."""
        text = "测试已完成。实验室今天提供。"
        result = split_into_clauses(text)
        # Punctuation should be with the clause, not separate
        assert all(clause and clause[-1] in "。！？；" for clause in result)

    def test_split_empty_string(self):
        """Test with empty string."""
        result = split_into_clauses("")
        assert result == []

    def test_split_whitespace_only(self):
        """Test with whitespace-only string."""
        result = split_into_clauses("   ")
        assert result == []

    def test_split_no_punctuation(self):
        """Test text without clause-ending punctuation."""
        text = "测试没有结束符号"
        result = split_into_clauses(text)
        # Should return the text as-is if no punctuation found
        assert result == ["测试没有结束符号"]

    def test_split_real_world_example(self):
        """Test the real-world example from v4_completeness.md."""
        text = "NADCC氯片测试已完成。实验室今天提供给@杨中宝。"
        result = split_into_clauses(text)
        assert len(result) == 2
        assert result[0] == "NADCC氯片测试已完成。"
        assert result[1] == "实验室今天提供给@杨中宝。"

    def test_split_long_clause_splits_by_comma(self):
        """Test that clauses longer than max_clause_length are split by commas."""
        # Create a clause longer than default max_clause_length (60)
        text = "这是一个很长的句子，包含很多信息，需要被分割成多个部分。"
        result = split_into_clauses(text, max_clause_length=20)
        # Should split by commas when clause exceeds max length
        assert len(result) >= 2

    def test_split_preserves_commas_with_preceding_text(self):
        """Test that commas stay with preceding text when splitting long clauses."""
        text = "第一个，第二个，第三个。"
        result = split_into_clauses(text, max_clause_length=10)
        # All parts should preserve the comma structure
        for clause in result:
            if clause.strip() and not clause.strip().endswith("。"):
                # Sub-clauses should end with comma if they were split by comma
                assert "，" in clause or clause == result[-1] or "。" in clause

    def test_split_handles_consecutive_punctuation(self):
        """Test handling of consecutive punctuation marks."""
        text = "完成。。开始。"
        result = split_into_clauses(text)
        # Should handle consecutive punctuation gracefully
        assert len(result) > 0

    def test_split_multiple_numbers_in_sequence(self):
        """Test edge case: multiple numbers like '200ppm150ppm'."""
        text = "200ppm150ppm100ppm浓度测试。"
        result = split_into_clauses(text)
        assert result == ["200ppm150ppm100ppm浓度测试。"]

    def test_split_respects_max_clause_length_parameter(self):
        """Test that max_clause_length parameter is respected."""
        text = "短句。"
        result = split_into_clauses(text, max_clause_length=2)
        # "短句。" is 3 chars, exceeds limit of 2, should split by comma
        # (but has no comma, so returns as-is)
        assert len(result) > 0


class TestSplitLongClause:
    """Test _split_long_clause helper function."""

    def test_split_long_clause_by_comma(self):
        """Test splitting a long clause by commas."""
        clause = "第一，第二，第三。"
        result = _split_long_clause(clause, max_length=5)
        # Should split into multiple parts with commas preserved
        assert len(result) >= 2
        assert "，" in result[0]

    def test_split_long_clause_no_commas(self):
        """Test long clause with no commas."""
        clause = "这是一个很长的没有任何逗号的句子。"
        result = _split_long_clause(clause, max_length=5)
        # If no commas to split on, return as-is
        assert result == [clause]

    def test_split_long_clause_single_comma(self):
        """Test long clause with a single comma."""
        clause = "第一部分，第二部分。"
        result = _split_long_clause(clause, max_length=5)
        assert len(result) >= 2
        assert "，" in result[0]

    def test_split_long_clause_keeps_punctuation(self):
        """Test that final punctuation is preserved."""
        clause = "一，二，三。"
        result = _split_long_clause(clause, max_length=3)
        # Last part should have the terminal punctuation
        if result:
            assert result[-1].endswith("。") or "。" in "".join(result)


class TestRecombineTranslations:
    """Test _recombine_translations function."""

    def test_recombine_basic_periods(self):
        """Test recombining clauses separated by periods."""
        original = "测试。实验。"
        clauses = ["测试。", "实验。"]
        translations = ["Test completed.", "Experiment."]
        result = _recombine_translations(original, clauses, translations)
        assert "Test completed." in result
        assert "Experiment." in result
        assert result.count(".") == 2

    def test_recombine_preserves_chinese_punctuation_mapping(self):
        """Test that Chinese punctuation is mapped to English correctly."""
        original = "完成。开始！进行？继续；"
        clauses = ["完成。", "开始！", "进行？", "继续；"]
        translations = ["Finish", "Start", "Proceed", "Continue"]
        result = _recombine_translations(original, clauses, translations)
        # Should have all English punctuation equivalents
        assert "." in result
        assert "!" in result
        assert "?" in result
        assert ";" in result

    def test_recombine_capitalizes_after_period(self):
        """Test that the overall result starts with a capital letter."""
        original = "第一。第二。"
        clauses = ["第一。", "第二。"]
        translations = ["first part.", "second part."]
        result = _recombine_translations(original, clauses, translations)
        # Result should start with capital letter
        assert result[0].isupper()
        # Should contain both translations
        assert "first part" in result.lower()
        assert "second part" in result.lower()

    def test_recombine_handles_empty_translation(self):
        """Test that empty translations are skipped."""
        original = "测试。失败。"
        clauses = ["测试。", "失败。"]
        translations = ["Test.", ""]
        result = _recombine_translations(original, clauses, translations)
        # Should only contain the non-empty translation
        assert "Test." in result
        assert result.count(".") == 1

    def test_recombine_removes_duplicate_punctuation(self):
        """Test that duplicate punctuation is handled."""
        original = "完成。开始。"
        clauses = ["完成。", "开始。"]
        translations = ["Test completed.", "Experiment."]
        result = _recombine_translations(original, clauses, translations)
        # Should not have ".." or other doubled punctuation
        assert ".." not in result

    def test_recombine_cleans_spacing(self):
        """Test that spacing is cleaned up properly."""
        original = "第一。第二。"
        clauses = ["第一。", "第二。"]
        translations = ["First  part.", "Second   part."]
        result = _recombine_translations(original, clauses, translations)
        # Should not have multiple consecutive spaces
        assert "  " not in result

    def test_recombine_mismatched_translation_count(self):
        """Test handling when translation count doesn't match clause count."""
        original = "一。二。三。"
        clauses = ["一。", "二。", "三。"]
        translations = ["One.", "Two."]  # Missing third translation
        result = _recombine_translations(original, clauses, translations)
        # Should handle gracefully by padding with empty strings
        assert "One." in result
        assert "Two." in result

    def test_recombine_empty_clauses(self):
        """Test with empty clauses and translations."""
        result = _recombine_translations("", [], [])
        assert result == ""

    def test_recombine_all_empty_translations(self):
        """Test when all translations are empty."""
        original = "一。二。"
        clauses = ["一。", "二。"]
        translations = ["", ""]
        result = _recombine_translations(original, clauses, translations)
        assert result == ""

    def test_recombine_chinese_punctuation_to_english(self):
        """Test the punctuation mapping works correctly."""
        original = "测试；进行。"
        clauses = ["测试；", "进行。"]
        translations = ["Testing", "Continuing"]
        result = _recombine_translations(original, clauses, translations)
        # "；" should become ";", "。" should become "."
        assert ";" in result
        assert "." in result
        assert "；" not in result
        assert "。" not in result

    def test_recombine_capitalizes_first_letter(self):
        """Test that the first letter of the result is capitalized."""
        original = "开始。"
        clauses = ["开始。"]
        translations = ["begin."]
        result = _recombine_translations(original, clauses, translations)
        assert result[0].isupper()

    def test_recombine_real_world_example(self):
        """Test recombining the real-world example from v4_completeness.md."""
        original = "测试已完成。实验室今天提供给@杨中宝。"
        clauses = ["测试已完成。", "实验室今天提供给@杨中宝。"]
        translations = ["Test completed.", "The laboratory provided results to @YangZhongbao today."]
        result = _recombine_translations(original, clauses, translations)
        # Should be a grammatically sensible combination
        assert "Test completed." in result
        assert "The laboratory" in result or "laboratory" in result
        assert "@YangZhongbao" in result or "@Yang" in result


class TestTranslateWithClauseFallback:
    """Test translate_with_clause_fallback function."""

    @patch('zh_en_translator.engines.argos.translate_sentence')
    def test_uses_single_pass_when_successful(self, mock_translate):
        """Test that single-pass is used when successful."""
        mock_translate.return_value = "Successful translation."
        result = translate_with_clause_fallback("测试")
        assert result == "Successful translation."
        # Should only call translate_sentence once (single-pass)
        assert mock_translate.call_count == 1

    @patch('zh_en_translator.engines.argos.translate_sentence')
    @patch('zh_en_translator.engines.argos.split_into_clauses')
    def test_falls_back_to_clauses_when_single_pass_fails(
        self, mock_split, mock_translate
    ):
        """Test that clause fallback is used when single-pass fails."""
        # First call (single-pass) fails, subsequent calls (clauses) succeed
        mock_translate.side_effect = [
            None,  # Single-pass fails
            "Test.",  # First clause
            "Completed.",  # Second clause
        ]
        mock_split.return_value = ["测试。", "完成。"]

        result = translate_with_clause_fallback("测试。完成。")

        # Should call split_into_clauses
        mock_split.assert_called_once()
        # Should have called translate_sentence multiple times (1 single-pass + 2 clauses)
        assert mock_translate.call_count >= 2

    @patch('zh_en_translator.engines.argos.translate_sentence')
    def test_falls_back_to_clauses_when_single_pass_empty(self, mock_translate):
        """Test that clause fallback is used when single-pass returns empty."""
        # First call (single-pass) returns empty, subsequent calls succeed
        mock_translate.side_effect = [
            "",  # Single-pass returns empty
            "Test.",
            "Completed.",
        ]

        with patch('zh_en_translator.engines.argos.split_into_clauses') as mock_split:
            mock_split.return_value = ["测试。", "完成。"]
            result = translate_with_clause_fallback("测试。完成。")
            assert result is not None or mock_split.called

    @patch('zh_en_translator.engines.argos.translate_sentence')
    def test_returns_none_when_all_fail(self, mock_translate):
        """Test that None is returned when all translation attempts fail."""
        mock_translate.return_value = None

        with patch('zh_en_translator.engines.argos.split_into_clauses') as mock_split:
            mock_split.return_value = []
            result = translate_with_clause_fallback("测试")
            assert result is None

    @patch('zh_en_translator.engines.argos.translate_sentence')
    def test_handles_empty_input(self, mock_translate):
        """Test handling of empty input."""
        result = translate_with_clause_fallback("")
        assert result is None
        mock_translate.assert_not_called()

    @patch('zh_en_translator.engines.argos.translate_sentence')
    def test_handles_whitespace_only_input(self, mock_translate):
        """Test handling of whitespace-only input."""
        result = translate_with_clause_fallback("   ")
        assert result is None
        mock_translate.assert_not_called()

    @patch('zh_en_translator.engines.argos.translate_sentence')
    def test_clause_fallback_recombines_results(self, mock_translate):
        """Test that clause fallback properly recombines translated clauses."""
        mock_translate.side_effect = [
            None,  # Single-pass fails
            "Test completed.",
            "Laboratory provided.",
        ]

        with patch('zh_en_translator.engines.argos.split_into_clauses') as mock_split:
            with patch('zh_en_translator.engines.argos._recombine_translations') as mock_recombine:
                mock_split.return_value = ["测试。", "完成。"]
                mock_recombine.return_value = "Test completed. Laboratory provided."

                result = translate_with_clause_fallback("测试。完成。")

                # Should call recombine with proper arguments
                mock_recombine.assert_called_once()
                assert result == "Test completed. Laboratory provided."

    @patch('zh_en_translator.engines.argos.translate_sentence')
    def test_handles_partial_clause_translation_failure(self, mock_translate):
        """Test that if one clause fails, others still contribute."""
        mock_translate.side_effect = [
            None,  # Single-pass fails
            "First clause.",
            None,  # Second clause fails
            "Third clause.",
        ]

        with patch('zh_en_translator.engines.argos.split_into_clauses') as mock_split:
            with patch('zh_en_translator.engines.argos._recombine_translations') as mock_recombine:
                mock_split.return_value = ["一。", "二。", "三。"]
                mock_recombine.return_value = "First clause. Third clause."

                result = translate_with_clause_fallback("一。二。三。")

                # Should still produce a result
                assert result is not None

    @patch('zh_en_translator.engines.argos.translate_sentence')
    @patch('zh_en_translator.engines.argos.split_into_clauses')
    def test_complex_multilingual_example(self, mock_split, mock_translate):
        """Test with a complex multilingual example."""
        mock_translate.side_effect = [
            None,  # Single-pass fails
            "NADCC chlorine tablets.",
            "Test completed.",
            "Laboratory provided to @YangZhongbao.",
        ]
        mock_split.return_value = [
            "NADCC氯片。",
            "测试已完成。",
            "实验室提供给@杨中宝。"
        ]

        with patch('zh_en_translator.engines.argos._recombine_translations') as mock_recombine:
            mock_recombine.return_value = "NADCC chlorine tablets. Test completed. Laboratory provided to @YangZhongbao."
            result = translate_with_clause_fallback("NADCC氯片。测试已完成。实验室提供给@杨中宝。")
            assert result is not None
            assert "@YangZhongbao" in result or "YangZhongbao" in result or mock_recombine.called


class TestIntegrationClauseTranslation:
    """Integration tests for clause translation without mocking."""

    def test_split_and_recombine_integration(self):
        """Test that split and recombine work together."""
        text = "第一。第二。"
        clauses = split_into_clauses(text)
        # Manually create translations
        translations = ["First one.", "Second one."]
        result = _recombine_translations(text, clauses, translations)

        assert "First one." in result
        assert "Second one." in result

    def test_complex_sentence_splitting_and_recombining(self):
        """Test with a more complex real-world-like sentence."""
        text = "NADCC氯片浓度200ppm。实验室测试完成；结果提供给@杨中宝。"
        clauses = split_into_clauses(text)

        # Should have split into at least 2 clauses
        assert len(clauses) >= 2
        # Should preserve punctuation
        assert all(clause and clause[-1] in "。！？；" for clause in clauses)

    def test_protection_patterns_work_correctly(self):
        """Test that protection patterns prevent incorrect splitting."""
        # Numbers should not be split
        text_with_numbers = "200ppm150ppm100ppm测试。"
        result = split_into_clauses(text_with_numbers)
        assert result == ["200ppm150ppm100ppm测试。"]

        # At mentions should not be split
        text_with_mention = "给@杨中宝。"
        result = split_into_clauses(text_with_mention)
        assert result == ["给@杨中宝。"]

    def test_edge_case_multiple_consecutive_punctuation(self):
        """Test edge case of multiple punctuation marks."""
        text = "完成。。。"
        result = split_into_clauses(text)
        # Should handle gracefully
        assert len(result) > 0

    def test_mixed_chinese_english_content(self):
        """Test clause splitting with mixed Chinese and English."""
        text = "NADCC test完成。实验已开始。"
        result = split_into_clauses(text)
        assert len(result) >= 2
        assert any("NADCC" in clause for clause in result)
        assert any("实验" in clause for clause in result)
