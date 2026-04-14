"""Main application: system tray app with global hotkey and popup translator."""

import sys

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon, QColor
from PyQt6.QtWidgets import QApplication, QSystemTrayIcon, QMenu

from zh_en_translator.hotkey import HotKeyManager
from zh_en_translator.capture import TextCapture
from zh_en_translator.ui.popup import TranslatorPopup


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

        self._setup_tray()

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
        self.popup = TranslatorPopup(captured_text, original_clipboard)
        self.popup.show()
        self.popup.setFocus()

    def _on_pause_resume(self):
        """Toggle pause/resume state."""
        self.paused = not self.paused
        if self.action_pause:
            self.action_pause.setText("Resume" if self.paused else "Pause")

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
        self.app.quit()


def main():
    """Entry point for the translator app."""
    app = TranslatorApp()
    app.start()


if __name__ == "__main__":
    main()
