"""Tests for Chinese text segmentation."""

from unittest.mock import patch

from zh_en_translator.engines.segmentation import segment, _segment_fallback
import zh_en_translator.engines.segmentation as seg_module


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
    """Test segmentation of English-only text.

    With jieba installed, English words may be split on whitespace (e.g.
    ["hello", " ", "world"]).  Without jieba the fallback groups all
    non-Chinese characters into one token.  Either way the key requirement is
    that no token is empty and all original characters are present.
    """
    result = segment("hello world")
    assert len(result) >= 1
    assert "".join(result) == "hello world"
    assert all(tok != "" for tok in result)


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


def test_segment_uses_jieba_when_available():
    """Test that segment() uses jieba.cut when jieba is available."""
    mock_tokens = ["我", "喜欢", "吃", "苹果"]
    with patch.object(seg_module, "_JIEBA_AVAILABLE", True):
        with patch("zh_en_translator.engines.segmentation.jieba") as mock_jieba:
            mock_jieba.cut.return_value = iter(mock_tokens)
            result = segment("我喜欢吃苹果")
    mock_jieba.cut.assert_called_once_with("我喜欢吃苹果", cut_all=False)
    assert result == mock_tokens


def test_segment_uses_jieba_filters_empty_strings():
    """Test that segment() filters empty strings from jieba output."""
    mock_tokens = ["我", "", "喜欢", ""]
    with patch.object(seg_module, "_JIEBA_AVAILABLE", True):
        with patch("zh_en_translator.engines.segmentation.jieba") as mock_jieba:
            mock_jieba.cut.return_value = iter(mock_tokens)
            result = segment("我喜欢")
    assert "" not in result
    assert result == ["我", "喜欢"]


def test_segment_fallback_when_jieba_missing():
    """Test that segment() uses _segment_fallback when jieba is not available."""
    with patch.object(seg_module, "_JIEBA_AVAILABLE", False):
        result = segment("你好世界")
    # _segment_fallback groups consecutive Chinese chars into one token
    assert result == ["你好世界"]


def test_segment_fallback_direct():
    """Test _segment_fallback directly for its character-run grouping behavior."""
    result = _segment_fallback("你好 world")
    assert "你好" in result
    assert " world" in result


def test_segment_fallback_empty():
    """Test _segment_fallback with empty string."""
    assert _segment_fallback("") == []
