"""Tests for hotkey functionality."""

from unittest.mock import Mock, MagicMock

import pytest

from zh_en_translator.hotkey import HotKeyManager, DEFAULT_HOTKEY_STRING


def test_hotkey_default_string():
    """Test that default hotkey is set correctly."""
    assert DEFAULT_HOTKEY_STRING == "<ctrl>+<shift>+<space>"


def test_hotkey_manager_init():
    """Test HotKeyManager initialization."""
    manager = HotKeyManager()
    assert manager.hotkey_string == DEFAULT_HOTKEY_STRING
    assert manager.listener is None
    assert manager.on_activate_callback is None


def test_hotkey_manager_custom_hotkey():
    """Test HotKeyManager with custom hotkey string."""
    custom_hotkey = "<ctrl>+<alt>+x"
    manager = HotKeyManager(custom_hotkey)
    assert manager.hotkey_string == custom_hotkey


def test_hotkey_manager_register_with_mock(monkeypatch):
    """Test registering a hotkey with mocked GlobalHotKeys."""
    manager = HotKeyManager()

    mock_listener = MagicMock()

    def create_listener(hotkey_dict):
        # Verify the hotkey string is passed correctly
        assert manager.hotkey_string in hotkey_dict
        return mock_listener

    monkeypatch.setattr(
        "zh_en_translator.hotkey.GlobalHotKeys", create_listener
    )

    callback = Mock()
    manager.start(callback)

    assert manager.listener == mock_listener
    mock_listener.start.assert_called_once()


def test_hotkey_callback_invoked(monkeypatch):
    """Test that callback is invoked when hotkey fires."""
    manager = HotKeyManager()

    mock_listener = MagicMock()

    monkeypatch.setattr(
        "zh_en_translator.hotkey.GlobalHotKeys", lambda d: mock_listener
    )

    callback = Mock()
    manager.start(callback)

    # Manually trigger the hotkey
    manager._on_hotkey()

    callback.assert_called_once()


def test_hotkey_manager_stop(monkeypatch):
    """Test stopping the hotkey manager."""
    manager = HotKeyManager()

    mock_listener = MagicMock()

    monkeypatch.setattr(
        "zh_en_translator.hotkey.GlobalHotKeys", lambda d: mock_listener
    )

    callback = Mock()
    manager.start(callback)

    # Stop should call stop on listener
    manager.stop()
    mock_listener.stop.assert_called_once()
    assert manager.listener is None


def test_hotkey_manager_stop_idempotent(monkeypatch):
    """Test that calling stop multiple times is safe."""
    manager = HotKeyManager()

    mock_listener = MagicMock()

    monkeypatch.setattr(
        "zh_en_translator.hotkey.GlobalHotKeys", lambda d: mock_listener
    )

    manager.start(Mock())

    manager.stop()
    manager.stop()  # Should not raise

    # listener.stop() should only be called once
    assert mock_listener.stop.call_count == 1


def test_hotkey_manager_invalid_hotkey(monkeypatch):
    """Test that invalid hotkey raises RuntimeError."""
    manager = HotKeyManager("invalid::hotkey")

    def create_listener_fail(hotkey_dict):
        raise KeyError("Invalid hotkey format")

    monkeypatch.setattr(
        "zh_en_translator.hotkey.GlobalHotKeys", create_listener_fail
    )

    with pytest.raises(RuntimeError, match="Failed to register global hotkey"):
        manager.start(Mock())


def test_hotkey_manager_callback_none_safe(monkeypatch):
    """Test that _on_hotkey is safe if callback is None."""
    manager = HotKeyManager()

    mock_listener = MagicMock()

    monkeypatch.setattr(
        "zh_en_translator.hotkey.GlobalHotKeys", lambda d: mock_listener
    )

    manager.start(None)
    manager.on_activate_callback = None

    # Should not raise
    manager._on_hotkey()
