"""Unit tests for clipboard capture logic."""

from unittest.mock import Mock, MagicMock

import pytest

from zh_en_translator.capture import TextCapture


def test_capture_selection_success(monkeypatch):
    """Test successful text capture with clipboard restore."""
    capture = TextCapture()

    # Mock pyperclip and keyboard
    original_clipboard = "original text"
    captured_text = "你好世界"

    paste_call_count = [0]

    def mock_paste():
        paste_call_count[0] += 1
        if paste_call_count[0] == 1:
            return original_clipboard
        else:
            return captured_text

    mock_copy = Mock()
    mock_keyboard = MagicMock()

    monkeypatch.setattr("zh_en_translator.capture.pyperclip.paste", mock_paste)
    monkeypatch.setattr("zh_en_translator.capture.pyperclip.copy", mock_copy)
    monkeypatch.setattr("zh_en_translator.capture.KeyboardController", lambda: mock_keyboard)

    # Recreate capture with mocked keyboard
    capture.keyboard = mock_keyboard

    result = capture.capture_selection()

    # Verify result
    assert result == captured_text

    # Verify keyboard was used to send Ctrl+C
    assert mock_keyboard.press.called
    assert mock_keyboard.release.called

    # Verify clipboard was restored
    mock_copy.assert_called_with(original_clipboard)


def test_capture_selection_empty_clipboard(monkeypatch):
    """Test capture when clipboard read fails initially."""
    capture = TextCapture()

    captured_text = "captured text"

    paste_call_count = [0]

    def mock_paste():
        paste_call_count[0] += 1
        if paste_call_count[0] == 1:
            raise Exception("Clipboard error")
        return captured_text

    mock_copy = Mock()
    mock_keyboard = MagicMock()

    monkeypatch.setattr("zh_en_translator.capture.pyperclip.paste", mock_paste)
    monkeypatch.setattr("zh_en_translator.capture.pyperclip.copy", mock_copy)

    capture.keyboard = mock_keyboard

    result = capture.capture_selection()

    # Should still return captured text despite initial clipboard error
    assert result == captured_text

    # Restore should be called with empty string
    mock_copy.assert_called_with("")


def test_capture_selection_restore_fails(monkeypatch):
    """Test that capture succeeds even if clipboard restore fails."""
    capture = TextCapture()

    original_clipboard = "original"
    captured_text = "captured"

    paste_call_count = [0]

    def mock_paste():
        paste_call_count[0] += 1
        if paste_call_count[0] == 1:
            return original_clipboard
        return captured_text

    def mock_copy(text):
        if text == original_clipboard:
            raise Exception("Restore failed")

    mock_keyboard = MagicMock()

    monkeypatch.setattr("zh_en_translator.capture.pyperclip.paste", mock_paste)
    monkeypatch.setattr("zh_en_translator.capture.pyperclip.copy", mock_copy)

    capture.keyboard = mock_keyboard

    # Should not raise, just return captured text
    result = capture.capture_selection()
    assert result == captured_text


def test_capture_no_selection(monkeypatch):
    """Test capture when Ctrl+C copies nothing (no selection)."""
    capture = TextCapture()

    original_clipboard = "original"

    paste_call_count = [0]

    def mock_paste():
        paste_call_count[0] += 1
        if paste_call_count[0] == 1:
            return original_clipboard
        # No change after Ctrl+C means no selection
        return original_clipboard

    mock_copy = Mock()
    mock_keyboard = MagicMock()

    monkeypatch.setattr("zh_en_translator.capture.pyperclip.paste", mock_paste)
    monkeypatch.setattr("zh_en_translator.capture.pyperclip.copy", mock_copy)

    capture.keyboard = mock_keyboard

    result = capture.capture_selection()

    # Should return the original clipboard (unchanged)
    assert result == original_clipboard

    # Restore should still be attempted
    mock_copy.assert_called_with(original_clipboard)


def test_hotkey_string_parseable():
    """Test that default hotkey string can be parsed by pynput."""
    from zh_en_translator.hotkey import DEFAULT_HOTKEY_STRING, HotKeyManager

    # This tests that the string is in valid format
    manager = HotKeyManager(DEFAULT_HOTKEY_STRING)
    assert manager.hotkey_string == "<ctrl>+<shift>+t"


def test_hotkey_manager_lifecycle(monkeypatch):
    """Test hotkey manager start/stop lifecycle."""
    from zh_en_translator.hotkey import HotKeyManager

    manager = HotKeyManager()

    # Mock the GlobalHotKeys listener
    mock_listener = MagicMock()

    def mock_global_hotkeys(hotkey_dict):
        return mock_listener

    monkeypatch.setattr(
        "zh_en_translator.hotkey.GlobalHotKeys", mock_global_hotkeys
    )

    callback = Mock()

    # Should not raise
    manager.start(callback)
    assert manager.listener is not None

    # Trigger the hotkey
    manager._on_hotkey()
    callback.assert_called_once()

    # Stop should work
    manager.stop()
    mock_listener.stop.assert_called()


def test_hotkey_manager_register_fail(monkeypatch):
    """Test that hotkey manager raises on registration failure."""
    from zh_en_translator.hotkey import HotKeyManager

    manager = HotKeyManager()

    def mock_global_hotkeys_fail(hotkey_dict):
        raise KeyError("Invalid hotkey")

    monkeypatch.setattr(
        "zh_en_translator.hotkey.GlobalHotKeys", mock_global_hotkeys_fail
    )

    with pytest.raises(RuntimeError, match="Failed to register global hotkey"):
        manager.start(Mock())
