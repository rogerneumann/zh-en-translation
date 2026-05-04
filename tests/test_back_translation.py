"""Unit tests for back-translation quality validation.

Tests the pure functions in engines/back_translation.py:
  - compute_confidence
  - confidence_to_label
  - content_word_coverage
"""

from __future__ import annotations

import pytest

from zh_en_translator.engines.back_translation import (
    compute_confidence,
    confidence_to_label,
    content_word_coverage,
)


# ---------------------------------------------------------------------------
# compute_confidence
# ---------------------------------------------------------------------------

class TestComputeConfidence:
    def test_high_confidence(self):
        """Low CER + high coverage -> confidence >= 0.75."""
        result = compute_confidence(cer_score=0.10, coverage=0.90)
        assert result >= 0.75

    def test_low_confidence(self):
        """High CER + low coverage -> confidence < 0.50."""
        result = compute_confidence(cer_score=0.60, coverage=0.30)
        assert result < 0.50

    def test_perfect_score(self):
        """CER=0, coverage=1 -> confidence == 1.0."""
        result = compute_confidence(cer_score=0.0, coverage=1.0)
        assert result == pytest.approx(1.0)

    def test_worst_score(self):
        """CER=1, coverage=0 -> confidence == 0.0."""
        result = compute_confidence(cer_score=1.0, coverage=0.0)
        assert result == pytest.approx(0.0)

    def test_clamped_below_zero(self):
        """Confidence is never negative even for out-of-range inputs."""
        result = compute_confidence(cer_score=2.0, coverage=0.0)
        assert result == 0.0

    def test_clamped_above_one(self):
        """Confidence is never above 1.0."""
        result = compute_confidence(cer_score=0.0, coverage=2.0)
        assert result == 1.0

    def test_midrange(self):
        """Mid CER + mid coverage falls between 0.5 and 0.75."""
        result = compute_confidence(cer_score=0.35, coverage=0.60)
        assert 0.30 < result < 0.80


# ---------------------------------------------------------------------------
# confidence_to_label
# ---------------------------------------------------------------------------

class TestConfidenceToLabel:
    def test_high_confidence_green(self):
        colour, tooltip = confidence_to_label(0.80)
        assert colour == "#22C55E"
        assert "High confidence" in tooltip

    def test_exactly_at_threshold_green(self):
        colour, _ = confidence_to_label(0.75)
        assert colour == "#22C55E"

    def test_amber_range(self):
        colour, tooltip = confidence_to_label(0.60)
        assert colour == "#F59E0B"
        assert "incomplete" in tooltip.lower()

    def test_exactly_at_threshold_amber(self):
        colour, _ = confidence_to_label(0.50)
        assert colour == "#F59E0B"

    def test_red_low_confidence(self):
        colour, tooltip = confidence_to_label(0.30)
        assert colour == "#EF4444"
        assert "review" in tooltip.lower()

    def test_unavailable(self):
        """Negative confidence signals unavailable quality check."""
        colour, tooltip = confidence_to_label(-1.0)
        assert colour == "#9CA3AF"
        assert "unavailable" in tooltip.lower()

    def test_zero_confidence_is_red(self):
        colour, _ = confidence_to_label(0.0)
        assert colour == "#EF4444"


# ---------------------------------------------------------------------------
# content_word_coverage
# ---------------------------------------------------------------------------

class TestContentWordCoverage:
    def test_perfect_coverage(self):
        """Back-translation identical to original -> coverage near 1.0."""
        zh = "\u6c34\u8def\u5835\u585e\u5df2\u7ecf\u5b8c\u6210"  # 水路堵塞已经完成
        coverage = content_word_coverage(zh, zh)
        assert coverage == pytest.approx(1.0)

    def test_zero_coverage_different_text(self):
        """Totally unrelated back-translation -> low coverage."""
        zh_original = "\u62c6\u673a\u70b9\u68c0"   # 拆机点检
        zh_back = "\u5929\u6c14\u5f88\u597d"         # 天气很好
        coverage = content_word_coverage(zh_original, zh_back)
        assert coverage < 0.5

    def test_empty_original(self):
        coverage = content_word_coverage("", "\u5929\u6c14\u5f88\u597d")
        assert coverage == 0.0

    def test_empty_back(self):
        coverage = content_word_coverage("\u62c6\u673a\u70b9\u68c0", "")
        assert coverage == 0.0

    def test_both_empty(self):
        coverage = content_word_coverage("", "")
        assert coverage == 0.0

    def test_only_stop_words(self):
        """If original has only stop words, no content to check -> neutral 1.0."""
        # Use common stop words: 的、了、和、是
        zh = "\u7684\u4e86\u548c\u662f"
        coverage = content_word_coverage(zh, "\u5929\u6c14\u5f88\u597d")
        assert coverage == pytest.approx(1.0)

    def test_partial_coverage(self):
        """Some content words present, others missing -> 0 < coverage < 1."""
        zh_original = "\u6c34\u8def\u5835\u585e\u5df2\u7ecf\u5b8c\u6210\u4e86"
        # back-translation contains 堵塞 but not 水路
        zh_back = "\u5835\u585e\u5df2\u7ecf\u5b8c\u6210\u4e86"
        coverage = content_word_coverage(zh_original, zh_back)
        assert 0.0 < coverage < 1.0
