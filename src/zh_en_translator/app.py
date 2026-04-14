"""Main application: system tray app with global hotkey and popup translator."""

import sys
from pathlib import Path

import platformdirs
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon, QColor
from PyQt6.QtWidgets import QApplication, QSystemTrayIcon, QMenu

from zh_en_translator.hotkey import HotKeyManager
from zh_en_translator.capture import TextCapture
from zh_en_translator.ui.popup import TranslatorPopup
from zh_en_translator.engines.dictionary import Dictionary


class TranslatorApp:
    """System tray application with global hotkey listener."""

    def __init__(self):
        """Initialize the translator app."""
        self.app = QApplication.instance() or QApplication(sys.argv)
        self.tray_icon = None
        self.popup = None
        self.paused = False

        self.hotkey_manager = HotKeyManager()
        self.text_capture = TextCapture()
        self.dictionary = self._setup_dictionary()

        self._setup_tray()

    def _setup_dictionary(self) -> Dictionary | None:
        """
        Load or build the dictionary database.

        Returns:
            Dictionary instance or None if setup fails.
        """
        try:
            # Determine DB path
            data_dir = platformdirs.user_data_dir("zh-en-translator", ensure_exists=True)
            db_path = Path(data_dir) / "cedict.sqlite"

            # If DB doesn't exist, build from sample
            if not db_path.exists():
                # Get path to bundled sample
                resource_dir = Path(__file__).parent / "resources"
                cedict_sample = resource_dir / "cedict_sample.txt"
                if cedict_sample.exists():
                    Dictionary.build_from_cedict(cedict_sample, db_path)
                else:
                    print(f"Warning: sample dictionary not found at {cedict_sample}")
                    return None

            # Open dictionary
            return Dictionary(db_path)
        except Exception as e:
            print(f"Warning: failed to setup dictionary: {e}")
            return None

    def _setup_tray(self):
        """Setup the system tray icon and menu."""
        # Create tray icon (simple emoji-based)
        self.tray_icon = QSystemTrayIcon(self.app)
        # Use a simple colored square as tray icon (emoji-like)
        self.tray_icon.setIcon(self._create_simple_icon())

        # Create context menu
        menu = QMenu()

        action_translate = menu.addAction("Translate Selection")
        action_translate.triggered.connect(self._on_hotkey_pressed)

        self.action_pause = menu.addAction("Pause")
        self.action_pause.triggered.connect(self._on_pause_resume)

        menu.addSeparator()

        # Rebuild dictionary action
        action_rebuild = menu.addAction("Rebuild Dictionary")
        action_rebuild.triggered.connect(self._on_rebuild_dictionary)

        menu.addSeparator()
        action_quit = menu.addAction("Quit")
        action_quit.triggered.connect(self.app.quit)

        self.tray_icon.setContextMenu(menu)
        self.tray_icon.show()

    def _create_simple_icon(self):
        """Create a simple tray icon (colored square)."""
        from PyQt6.QtGui import QPixmap, QPainter

        pixmap = QPixmap(16, 16)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.fillRect(pixmap.rect(), QColor(100, 150, 255))
        painter.end()
        return QIcon(pixmap)

    def _on_hotkey_pressed(self):
        """Handle hotkey press or manual menu trigger."""
        if self.paused:
            return

        # Close any existing popup
        if self.popup:
            self.popup.close()

        # Capture selected text
        original_clipboard = ""
        try:
            original_clipboard = ""
            import pyperclip

            try:
                original_clipboard = pyperclip.paste()
            except Exception:
                pass
        except Exception:
            pass

        captured_text = self.text_capture.capture_selection()

        if not captured_text:
            # No text selected or capture failed
            return

        # Show popup
        self.popup = TranslatorPopup(captured_text, original_clipboard, self.dictionary)
        self.popup.show()
        self.popup.setFocus()

    def _on_pause_resume(self):
        """Toggle pause/resume state."""
        self.paused = not self.paused
        if self.action_pause:
            self.action_pause.setText("Resume" if self.paused else "Pause")

    def _on_rebuild_dictionary(self):
        """Rebuild the dictionary from sample."""
        try:
            data_dir = platformdirs.user_data_dir("zh-en-translator", ensure_exists=True)
            db_path = Path(data_dir) / "cedict.sqlite"

            # Close existing dictionary
            if self.dictionary:
                self.dictionary.close()

            # Remove existing DB
            if db_path.exists():
                db_path.unlink()

            # Rebuild from sample
            resource_dir = Path(__file__).parent / "resources"
            cedict_sample = resource_dir / "cedict_sample.txt"
            if cedict_sample.exists():
                self.dictionary = Dictionary.build_from_cedict(cedict_sample, db_path)
                print("Dictionary rebuilt successfully")
        except Exception as e:
            print(f"Error rebuilding dictionary: {e}")

    def start(self):
        """Start the application with hotkey listener."""
        try:
            self.hotkey_manager.start(self._on_hotkey_pressed)
        except RuntimeError as e:
            # Log but don't crash; user can still manually trigger via menu
            print(f"Warning: Failed to register global hotkey: {e}")

        sys.exit(self.app.exec())

    def stop(self):
        """Stop the application."""
        self.hotkey_manager.stop()
        if self.popup:
            self.popup.close()
        if self.dictionary:
            self.dictionary.close()
        self.app.quit()


def main():
    """Entry point for the translator app."""
    app = TranslatorApp()
    app.start()


if __name__ == "__main__":
    main()
