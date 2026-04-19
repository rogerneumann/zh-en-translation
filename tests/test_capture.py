"""Unit tests for clipboard capture logic."""

from unittest.mock import Mock, MagicMock
from PyQt6.QtCore import QMimeData
from PyQt6.QtWidgets import QApplication

import pytest

from zh_en_translator.capture import TextCapture


def test_capture_selection_success(qapp, monkeypatch):
    """Test successful text capture with clipboard restore."""
    capture = TextCapture()
    clipboard = QApplication.clipboard()

    # Mock original mime data
    original_text = "original text"
    original_mime = QMimeData()
    original_mime.setText(original_text)

    # Mock captured text
    captured_text = "你好世界"

    # Set initial state
    clipboard.setMimeData(original_mime)

    mock_keyboard = MagicMock()
    monkeypatch.setattr("zh_en_translator.capture.KeyboardController", lambda: mock_keyboard)
    capture.keyboard = mock_keyboard

    # We need to simulate the clipboard changing after Ctrl+C
    # and then being restored.
    state = {"captured": False}

    original_text_fn = clipboard.text
    def mock_text():
        if state["captured"]:
            return captured_text
        return original_text_fn()

    original_set_mime_fn = clipboard.setMimeData
    def mock_set_mime(data):
        # When restore is called, we go back to original state
        state["captured"] = False
        original_set_mime_fn(data)

    monkeypatch.setattr(clipboard, "text", mock_text)
    monkeypatch.setattr(clipboard, "setMimeData", mock_set_mime)

    # Trigger 'captured' state when keyboard is 'pressed'
    def mock_press(key):
        state["captured"] = True
    mock_keyboard.press.side_effect = mock_press

    result = capture.capture_selection()

    # Verify result
    assert result == captured_text

    # Verify keyboard was used to send Ctrl+C
    assert mock_keyboard.press.called
    assert mock_keyboard.release.called

    # Verify clipboard was restored
    assert clipboard.text() == original_text


def test_capture_no_selection(qapp, monkeypatch):
    """Test capture when Ctrl+C copies nothing (no selection)."""
    capture = TextCapture()
    clipboard = QApplication.clipboard()

    original_text = "original"
    original_mime = QMimeData()
    original_mime.setText(original_text)
    clipboard.setMimeData(original_mime)

    mock_keyboard = MagicMock()
    monkeypatch.setattr("zh_en_translator.capture.KeyboardController", lambda: mock_keyboard)
    capture.keyboard = mock_keyboard

    # In this case, even after "Ctrl+C", clipboard.text() returns same text
    monkeypatch.setattr(clipboard, "text", lambda: original_text)

    result = capture.capture_selection()

    # Should return original text if Ctrl+C didn't change it
    assert result == original_text
    assert clipboard.text() == original_text


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
