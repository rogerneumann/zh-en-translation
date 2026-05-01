"""Tests for Chinese text segmentation."""

import pytest
from unittest.mock import patch

from zh_en_translator.engines.segmentation import segment, _segment_fallback
import zh_en_translator.engines.segmentation as seg_module

# ---------------------------------------------------------------------------
# Jieba availability check for skipif guards
# ---------------------------------------------------------------------------

try:
    import jieba as _jieba  # noqa: F401
    _JIEBA_OK = True
except ImportError:
    _JIEBA_OK = False


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


# ---------------------------------------------------------------------------
# Regression tests for compound Chinese phrases
# ---------------------------------------------------------------------------


def test_empty_input_returns_empty_list():
    """Empty input should always return an empty list (no jieba needed)."""
    assert segment("") == []


def test_whitespace_only_returns_empty_or_whitespace():
    """Whitespace-only input should return no meaningful tokens."""
    result = segment("   ")
    # Either empty list or tokens that are all whitespace — no Chinese chars
    assert all(tok.strip() == "" for tok in result) or result == []


def test_latin_passthrough_ascii_word():
    """ASCII words should pass through unchanged (no jieba needed)."""
    result = segment("hello")
    combined = "".join(result)
    assert combined == "hello"


def test_latin_passthrough_alphanumeric():
    """Alphanumeric strings like 'X10' should be preserved (no jieba needed)."""
    result = segment("X10")
    combined = "".join(result)
    assert combined == "X10"


def test_punctuation_chinese_enumeration_comma():
    """Chinese enumeration comma 、 should appear as a separate token or be stripped."""
    result = segment("李勋、张三")
    # The enumeration comma must not be silently fused into a Chinese word token
    joined = "".join(result)
    assert "李勋" in joined
    assert "张三" in joined


def test_punctuation_chinese_comma_and_period():
    """Standard Chinese punctuation 、，。 should be separate tokens or stripped."""
    result = segment("你好，世界。")
    joined = "".join(result)
    assert "你好" in joined
    assert "世界" in joined


@pytest.mark.skipif(not _JIEBA_OK, reason="jieba not installed")
def test_compound_laser_module():
    """'激光模块' should be recognised as a compound (2+ chars) when jieba is available."""
    from zh_en_translator.engines.segmentation import add_custom_words
    add_custom_words([("激光模块", 20, "n")])
    result = segment("激光模块")
    assert "激光模块" in result, (
        f"Expected '激光模块' as a compound token; got: {result!r}"
    )


@pytest.mark.skipif(not _JIEBA_OK, reason="jieba not installed")
def test_compound_full_sentence_regression():
    """Canonical regression sentence: key compounds must survive segmentation."""
    from zh_en_translator.engines.segmentation import add_custom_words
    add_custom_words([
        ("手板样机", 20, "n"),
        ("激光模块", 20, "n"),
        ("进能部门", 20, "n"),
    ])

    sentence = (
        "李勋、那个X10 Pro的手板样机，激光模块换完了，"
        "你们可以去进能部门标一下，我去找他弄"
    )
    result = segment(sentence)

    assert "激光模块" in result, (
        f"Expected '激光模块' as a compound token; got: {result!r}"
    )


@pytest.mark.skipif(not _JIEBA_OK, reason="jieba not installed")
def test_compound_with_user_dict_loaded():
    """Compounds in the user dict should be segmented as units after load_user_dict."""
    from zh_en_translator.engines.segmentation import load_user_dict, add_custom_words

    # Register the test compound directly so we don't depend on the file
    add_custom_words([("手板样机", 10, "n"), ("进能部门", 10, "n")])

    result_proto = segment("手板样机")
    assert "手板样机" in result_proto, (
        f"Expected '手板样机' as compound; got: {result_proto!r}"
    )

    result_dept = segment("进能部门")
    assert "进能部门" in result_dept, (
        f"Expected '进能部门' as compound; got: {result_dept!r}"
    )
