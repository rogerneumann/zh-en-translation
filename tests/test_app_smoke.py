"""Smoke tests for the app: imports, basic instantiation."""

import sys
import os

# Ensure offscreen platform for headless testing
os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PyQt6.QtWidgets import QApplication

from zh_en_translator.ui.popup import TranslatorPopup


def test_popup_import():
    """Test that popup module can be imported."""
    from zh_en_translator.ui.popup import TranslatorPopup

    assert TranslatorPopup is not None


def test_popup_instantiation():
    """Test that TranslatorPopup can be instantiated with test text."""
    # Ensure QApplication exists
    _ = QApplication.instance() or QApplication(sys.argv)

    test_text = "你好世界 Hello World"
    popup = TranslatorPopup(test_text, original_clipboard="")

    # Verify basic properties
    assert popup.captured_text == test_text
    assert popup.isVisible() is False  # Not shown yet
    assert popup.windowFlags() & popup.windowFlags()  # Has window flags set
    assert popup.text_display.toPlainText() == test_text


def test_popup_window_flags():
    """Test that popup has correct window flags."""
    _ = QApplication.instance() or QApplication(sys.argv)

    popup = TranslatorPopup("Test", original_clipboard="")
    from PyQt6.QtCore import Qt

    flags = popup.windowFlags()
    assert flags & Qt.WindowType.FramelessWindowHint
    assert flags & Qt.WindowType.Tool
    assert flags & Qt.WindowType.WindowStaysOnTopHint


def test_popup_text_display_selectable():
    """Test that popup text is selectable."""
    _ = QApplication.instance() or QApplication(sys.argv)

    popup = TranslatorPopup("Test text", original_clipboard="")
    from PyQt6.QtCore import Qt

    text_flags = popup.text_display.textInteractionFlags()
    assert text_flags & Qt.TextInteractionFlag.TextSelectableByMouse


def test_popup_long_text_sizing():
    """Test that popup handles long text with reasonable sizing."""
    _ = QApplication.instance() or QApplication(sys.argv)

    long_text = "这是一段很长的中文文本。" * 20
    popup = TranslatorPopup(long_text, original_clipboard="")

    assert popup.width() <= 700
    assert popup.height() <= 600


def test_popup_with_dictionary():
    """Popup accepts dictionary kwarg without crashing (reserved for future word-lookup)."""
    import tempfile
    from pathlib import Path
    from zh_en_translator.engines.dictionary import Dictionary

    _ = QApplication.instance() or QApplication(sys.argv)

    cedict_content = "你好 你好 [ni3 hao3] /hello/hi/\n世界 世界 [shi4 jie4] /world/\n"
    with tempfile.TemporaryDirectory() as tmpdir:
        cedict_file = Path(tmpdir) / "cedict.txt"
        cedict_file.write_text(cedict_content, encoding="utf-8")
        db_file = Path(tmpdir) / "test.db"
        dictionary = Dictionary.build_from_cedict(cedict_file, db_file)

        popup = TranslatorPopup("你好世界", original_clipboard="", dictionary=dictionary)

        assert popup.captured_text == "你好世界"
        assert popup.translation_label.text() == "Translating…"
        dictionary.close()


def test_hotkey_manager_import():
    """Test that hotkey manager can be imported."""
    from zh_en_translator.hotkey import HotKeyManager, DEFAULT_HOTKEY_STRING

    assert HotKeyManager is not None
    assert DEFAULT_HOTKEY_STRING == "<ctrl>+<alt>+t"


def test_hotkey_manager_instantiation():
    """Test that HotKeyManager can be instantiated."""
    from zh_en_translator.hotkey import HotKeyManager

    manager = HotKeyManager()
    assert manager.hotkey_string == "<ctrl>+<alt>+t"
    assert manager.listener is None


def test_capture_import():
    """Test that text capture module can be imported."""
    from zh_en_translator.capture import TextCapture

    assert TextCapture is not None


def test_capture_instantiation():
    """Test that TextCapture can be instantiated."""
    from zh_en_translator.capture import TextCapture

    capture = TextCapture()
    assert capture.keyboard is not None
