"""Tests for the Traditional Chinese → Simplified Chinese converter."""

from __future__ import annotations

from zh_en_translator.engines.converter import is_available, to_simplified


def test_to_simplified_pure_simplified():
    """Simplified text passes through unchanged."""
    text = "电脑"
    result = to_simplified(text)
    assert result == text


def test_to_simplified_traditional():
    """Traditional characters are converted (if opencc available) or returned unchanged."""
    traditional = "電腦"
    result = to_simplified(traditional)
    if is_available():
        assert result == "电脑"
    else:
        assert result == traditional


def test_to_simplified_never_raises():
    """to_simplified() must not raise on any input."""
    inputs = [
        "",
        "hello",
        "電腦",
        "mixed 電腦 content with ASCII",
        "😀🎉🐉",
        "123 !@# \n\t",
    ]
    for text in inputs:
        result = to_simplified(text)
        assert isinstance(result, str)


def test_to_simplified_empty_string():
    """Empty string input returns empty string."""
    assert to_simplified("") == ""


def test_to_simplified_ascii_unchanged():
    """Pure ASCII text is returned unchanged."""
    text = "Hello, world!"
    assert to_simplified(text) == text


def test_is_available_returns_bool():
    """is_available() always returns a plain bool."""
    result = is_available()
    assert isinstance(result, bool)


def test_is_available_idempotent():
    """Calling is_available() multiple times returns the same value."""
    first = is_available()
    second = is_available()
    assert first == second
