"""Tests for Chinese text segmentation."""

from zh_en_translator.engines.segmentation import segment


def test_segment_chinese():
    """Test segmentation of pure Chinese text."""
    result = segment("我喜欢吃苹果")
    assert len(result) > 0
    assert "我" in result or any("我" in token for token in result)


def test_segment_mixed_zh_en():
    """Test segmentation of mixed Chinese and English text."""
    result = segment("我love你")
    assert len(result) >= 2
    # Check that "love" is preserved as a single token
    assert "love" in result


def test_segment_empty_string():
    """Test segmentation of empty string."""
    result = segment("")
    assert result == []


def test_segment_english_only():
    """Test segmentation of English-only text."""
    result = segment("hello world")
    assert len(result) == 1
    assert result[0] == "hello world"


def test_segment_with_punctuation():
    """Test segmentation with punctuation."""
    result = segment("你好，世界！")
    assert len(result) > 0
    # Should contain Chinese tokens and punctuation
    assert any(c in "你好世界" for token in result for c in token)


def test_segment_numbers():
    """Test segmentation with numbers."""
    result = segment("2024年12月")
    assert len(result) >= 2
    # Numbers should be grouped with surrounding punctuation/spaces


def test_segment_whitespace():
    """Test segmentation with whitespace."""
    result = segment("你好 世界")
    assert len(result) >= 2
