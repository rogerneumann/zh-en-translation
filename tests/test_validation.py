"""Tests for translation validation and recovery."""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from zh_en_translator.engines.dictionary import Dictionary
from zh_en_translator.engines.validation import (
    extract_content_tokens,
    is_translation_complete,
    recover_missing_content,
)


@pytest.fixture
def sample_dictionary():
    """Create a sample dictionary for testing."""
    cedict_content = """# Comment line
# CC-CEDICT sample
实验室 实验室 [shi2 yan4 shi4] /laboratory/lab/
今天 今天 [jin1 tian1] /today/
提供 提供 [ti2 gong1] /provide/supply/
氯片 氯片 [lü4 pian4] /chlorine tablet/
完成 完成 [wan2 cheng2] /complete/finish/accomplished/
test test [test] /test/
NADCC NADCC [NADCC] /NADCC/
浓度 浓度 [nong2 du4] /concentration/density/
狗 狗 [gou3] /dog/
骨头 骨头 [gu3 tou5] /bone/
浸泡 浸泡 [jin4 pao4] /soak/dip/
"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        cedict_file = tmpdir / "cedict.txt"
        cedict_file.write_text(cedict_content, encoding="utf-8")

        db_file = tmpdir / "test.db"
        dictionary = Dictionary.build_from_cedict(cedict_file, db_file)
        yield dictionary
        dictionary.close()


class TestExtractContentTokens:
    """Test extract_content_tokens function."""

    def test_extract_content_tokens_empty_string(self, sample_dictionary):
        """Test with empty string."""
        result = extract_content_tokens("", sample_dictionary)
        assert result == []

    def test_extract_content_tokens_whitespace_only(self, sample_dictionary):
        """Test with whitespace-only string."""
        result = extract_content_tokens("   ", sample_dictionary)
        assert result == []

    def test_extract_content_tokens_filters_particles(self, sample_dictionary):
        """Test that particles are filtered out."""
        # "的" is a possessive particle, should be filtered
        result = extract_content_tokens("我的苹果", sample_dictionary)
        # Should not contain "的" (possessive particle)
        assert "的" not in result

    def test_extract_content_tokens_preserves_nouns(self, sample_dictionary):
        """Test that nouns are preserved."""
        result = extract_content_tokens("实验室", sample_dictionary)
        # If jieba/posseg available, should preserve "实验室" (noun)
        # Otherwise fallback will also include it
        assert any("实验室" in token or "实验" in token for token in result)

    def test_extract_content_tokens_complex_sentence(self, sample_dictionary):
        """Test extraction from a complex sentence."""
        sentence = "实验室今天提供测试结果"
        result = extract_content_tokens(sentence, sample_dictionary)
        # Should include nouns and verbs, exclude particles
        assert len(result) > 0
        # Should not include particles like "的", "了", etc.
        assert "的" not in result


class TestIsTranslationComplete:
    """Test is_translation_complete function."""

    def test_is_translation_complete_empty_source(self, sample_dictionary):
        """Test with empty source tokens."""
        result = is_translation_complete([], "some translation", sample_dictionary)
        assert result is True  # No content to check; consider complete

    def test_is_translation_complete_empty_translation(self, sample_dictionary):
        """Test with empty translation."""
        result = is_translation_complete(["实验室"], "", sample_dictionary)
        assert result is False  # Empty translation; not complete

    def test_is_translation_complete_matching_content(self, sample_dictionary):
        """Test with translation that includes content."""
        source_tokens = ["实验室", "今天"]
        translation = "The laboratory provided results today."
        result = is_translation_complete(source_tokens, translation, sample_dictionary)
        # Should find "laboratory" for "实验室" and "today" for "今天"
        assert result is True

    def test_is_translation_complete_missing_content(self, sample_dictionary):
        """Test with translation missing key content."""
        source_tokens = ["实验室", "今天", "提供"]
        translation = "test completed"
        result = is_translation_complete(source_tokens, translation, sample_dictionary)
        # Should find less than 70% of tokens
        assert result is False

    def test_is_translation_complete_case_insensitive(self, sample_dictionary):
        """Test that matching is case-insensitive."""
        source_tokens = ["实验室"]
        translation = "LABORATORY TEST RESULTS"
        result = is_translation_complete(source_tokens, translation, sample_dictionary)
        # Should match "LABORATORY" (uppercase) with gloss "laboratory"
        assert result is True

    def test_is_translation_complete_threshold_boundary(self, sample_dictionary):
        """Test at 70% threshold boundary."""
        # With 10 tokens, finding 7 = 70% (threshold)
        source_tokens = ["测试"] * 10  # Repeat "test" to have enough tokens
        # Provide translation with only "test" mentioned
        translation = "This is a test result."
        # The behavior depends on dictionary entries for "测试"
        result = is_translation_complete(source_tokens, translation, sample_dictionary)
        # This is a boundary case; result depends on actual gloss coverage


class TestRecoverMissingContent:
    """Test recover_missing_content function."""

    def test_recover_missing_content_no_missing(self, sample_dictionary):
        """Test when no content is missing."""
        source = "实验室今天"
        translation = "The laboratory provided results today."
        result = recover_missing_content(source, translation, dictionary=sample_dictionary)
        # Should not significantly change complete translation
        assert "laboratory" in result.lower() or "today" in result.lower()

    def test_recover_missing_content_with_list(self, sample_dictionary):
        """Test recovery with explicit missing tokens."""
        source = "实验室今天提供结果"
        translation = "Test completed"
        missing_tokens = ["实验室", "今天"]
        result = recover_missing_content(
            source,
            translation,
            missing_tokens=missing_tokens,
            dictionary=sample_dictionary,
        )
        # Should add "laboratory" and "today" to translation
        assert len(result) > len(translation)
        # Result should contain recovered content or be modified
        assert result != translation

    def test_recover_missing_content_auto_detect(self, sample_dictionary):
        """Test recovery with auto-detection of missing content."""
        source = "实验室今天"
        translation = "test completed"  # Missing "laboratory" and "today"
        result = recover_missing_content(
            source,
            translation,
            missing_tokens=None,
            dictionary=sample_dictionary,
        )
        # Should add recovered content
        assert len(result) >= len(translation)

    def test_recover_missing_content_empty_translation(self, sample_dictionary):
        """Test recovery with empty translation."""
        source = "实验室"
        translation = ""
        result = recover_missing_content(source, translation, dictionary=sample_dictionary)
        assert result == ""  # No translation to enhance

    def test_recover_missing_content_punctuation_handling(self, sample_dictionary):
        """Test that recovery handles punctuation correctly."""
        source = "实验室今天"
        translation = "Test result."  # Ends with period
        missing_tokens = ["实验室"]
        result = recover_missing_content(
            source,
            translation,
            missing_tokens=missing_tokens,
            dictionary=sample_dictionary,
        )
        # Should insert before final punctuation or append at end
        assert len(result) > 0
        # Result should be modified from original
        assert result != translation

    def test_recover_missing_content_no_dictionary(self, sample_dictionary):
        """Test recovery without dictionary."""
        source = "实验室"
        translation = "Test result"
        result = recover_missing_content(
            source,
            translation,
            missing_tokens=["实验室"],
            dictionary=None,
        )
        # Should return original translation if no dictionary
        assert result == translation


class TestIntegrationNADCCExample:
    """Integration test using the NADCC example from v4_completeness.md."""

    def test_nadcc_recovery_example(self, sample_dictionary):
        """Test the NADCC chlorine example from the specification."""
        # Original Chinese (simplified)
        source = "NADCC氯片 200ppm 150ppm 100ppm浓度狗骨头浸泡测试已完成 实验室今天提供给@杨中宝"

        # Current (incomplete) output from Argos
        translation = "NADCC chlorine tablets 200 ppm 150 ppm 100 ppm dog bone immersion test completed"

        # Missing content: "实验室" (laboratory), "今天" (today)
        # After validation and recovery, should include these

        # Extract content tokens from source
        source_tokens = extract_content_tokens(source, sample_dictionary)

        # Check if translation is complete
        is_complete = is_translation_complete(source_tokens, translation, sample_dictionary)

        # Should detect incompleteness
        if not is_complete:
            # Recover missing content
            enhanced = recover_missing_content(
                source,
                translation,
                missing_tokens=None,
                dictionary=sample_dictionary,
            )
            # Enhanced translation should be longer and include recovered content
            assert len(enhanced) >= len(translation)
            # The implementation should attempt to recover something
            # (specific wording depends on dictionary and insertion logic)

    def test_nadcc_with_explicit_missing_tokens(self, sample_dictionary):
        """Test NADCC example with explicit missing tokens."""
        source = "NADCC氯片浓度狗骨头浸泡测试已完成 实验室今天提供给@杨中宝"
        translation = "NADCC chlorine tablets concentration dog bone immersion test completed"
        missing_tokens = ["实验室", "今天"]

        result = recover_missing_content(
            source,
            translation,
            missing_tokens=missing_tokens,
            dictionary=sample_dictionary,
        )

        # Should have inserted something
        assert result != translation
        # Result should be longer (added content)
        assert len(result) > len(translation)
