"""Main application: system tray app with global hotkey and popup translator."""

import sys

import pyperclip
from PyQt6.QtCore import Qt, QObject, pyqtSignal
from PyQt6.QtGui import QIcon, QColor
from PyQt6.QtWidgets import QApplication, QSystemTrayIcon, QMenu

from zh_en_translator.hotkey import HotKeyManager
from zh_en_translator.capture import TextCapture
from zh_en_translator.ui.popup import TranslatorPopup
from zh_en_translator.ui.sidebar import TranslatorSidebar


class TranslatorApp(QObject):
    """System tray application with global hotkey listener."""

    # Routes the pynput callback (background thread) to the Qt main thread.
    _hotkey_signal = pyqtSignal()

    def __init__(self):
        # QApplication must exist before QObject.__init__
        self.app = QApplication.instance() or QApplication(sys.argv)
        super().__init__()

        self.tray_icon = None
        self.popup = None
        self.sidebar = TranslatorSidebar()
        self.paused = False

        self._hotkey_signal.connect(self._on_hotkey_pressed)
        self.hotkey_manager = HotKeyManager()
        self.text_capture = TextCapture()

        self._setup_tray()

    def _setup_tray(self):
        self.tray_icon = QSystemTrayIcon(self.app)
        self.tray_icon.setIcon(self._create_icon())

        menu = QMenu()

        action_translate = menu.addAction("Translate Selection")
        action_translate.triggered.connect(self._on_hotkey_pressed)

        action_sidebar = menu.addAction("Show Sidebar")
        action_sidebar.triggered.connect(self.sidebar.show)

        self.action_pause = menu.addAction("Pause")
        self.action_pause.triggered.connect(self._on_pause_resume)

        menu.addSeparator()
        action_quit = menu.addAction("Quit")
        action_quit.triggered.connect(self.app.quit)

        self.tray_icon.setContextMenu(menu)
        self.tray_icon.show()

    def _create_icon(self):
        from PyQt6.QtGui import QPixmap, QPainter

        pixmap = QPixmap(16, 16)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.fillRect(pixmap.rect(), QColor(100, 150, 255))
        painter.end()
        return QIcon(pixmap)

    def _on_hotkey_pressed(self):
        if self.paused:
            return

        if self.popup:
            self.popup.close()

        try:
            original_clipboard = pyperclip.paste()
        except Exception:
            original_clipboard = ""

        captured_text = self.text_capture.capture_selection()
        if not captured_text:
            return

        self.popup = TranslatorPopup(
            captured_text,
            original_clipboard,
            on_pin=self._pin_to_sidebar,
        )
        self.popup.show()

    def _pin_to_sidebar(self, source: str, translation: str) -> None:
        """Called by the popup's Pin button — show translation in the sidebar."""
        self.sidebar.set_translation(source, translation)

    def _on_pause_resume(self):
        self.paused = not self.paused
        if self.action_pause:
            self.action_pause.setText("Resume" if self.paused else "Pause")

    def start(self):
        try:
            self.hotkey_manager.start(self._hotkey_signal.emit)
        except RuntimeError as e:
            print(f"Warning: Failed to register global hotkey: {e}")

        sys.exit(self.app.exec())

    def stop(self):
        self.hotkey_manager.stop()
        if self.popup:
            self.popup.close()
        self.app.quit()


def main():
    app = TranslatorApp()
    app.start()


if __name__ == "__main__":
    main()
