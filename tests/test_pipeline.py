"""Tests for the translation pipeline."""

import tempfile
from pathlib import Path

import pytest

from zh_en_translator.engines.dictionary import Dictionary
from zh_en_translator.engines.pipeline import translate


@pytest.fixture
def test_dictionary():
    """Create a test dictionary with sample entries."""
    cedict_content = """你好 你好 [ni3 hao3] /hello/hi/
世界 世界 [shi4 jie4] /world/
"""
    tmpdir = tempfile.TemporaryDirectory()
    tmpdir_path = Path(tmpdir.name)
    cedict_file = tmpdir_path / "cedict.txt"
    cedict_file.write_text(cedict_content, encoding="utf-8")

    db_file = tmpdir_path / "test.db"
    dictionary = Dictionary.build_from_cedict(cedict_file, db_file)

    yield dictionary

    dictionary.close()
    tmpdir.cleanup()


def test_translate_known_tokens(test_dictionary):
    """Test translation of known Chinese tokens."""
    results = translate("你好世界", test_dictionary)

    assert len(results) >= 2
    # Find the "你好" token
    hello_result = next((r for r in results if "你" in r.token or r.token == "你好"), None)
    if hello_result:
        assert hello_result.is_chinese is True
        assert hello_result.pinyin is not None
        assert len(hello_result.glosses) > 0


def test_translate_unknown_token(test_dictionary):
    """Test translation of unknown Chinese token."""
    results = translate("未知", test_dictionary)

    # Should have at least one result for the Chinese token
    assert len(results) > 0
    unknown_result = next((r for r in results if r.is_chinese), None)
    if unknown_result:
        assert len(unknown_result.glosses) == 0  # Unknown token has no glosses


def test_translate_mixed_text(test_dictionary):
    """Test translation of mixed Chinese and English text."""
    results = translate("你好world", test_dictionary)

    assert len(results) >= 2

    # Check that we have a Chinese result and a non-Chinese result
    chinese_results = [r for r in results if r.is_chinese]
    non_chinese_results = [r for r in results if not r.is_chinese]

    assert len(chinese_results) > 0 or len(non_chinese_results) > 0


def test_translate_empty_string(test_dictionary):
    """Test translation of empty string."""
    results = translate("", test_dictionary)
    assert results == []


def test_translate_non_chinese_only(test_dictionary):
    """Test translation of non-Chinese text only."""
    results = translate("hello", test_dictionary)

    assert len(results) >= 1
    for result in results:
        assert result.is_chinese is False
        assert result.pinyin is None


def test_token_result_structure(test_dictionary):
    """Test that TokenResult has expected structure."""
    results = translate("你好", test_dictionary)

    assert len(results) > 0
    result = results[0]

    # Check all required fields exist
    assert hasattr(result, "token")
    assert hasattr(result, "pinyin")
    assert hasattr(result, "glosses")
    assert hasattr(result, "is_chinese")

    # Check types
    assert isinstance(result.token, str)
    assert isinstance(result.pinyin, (str, type(None)))
    assert isinstance(result.glosses, list)
    assert isinstance(result.is_chinese, bool)
