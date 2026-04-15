"""Main application: system tray app with global hotkey and popup translator."""

import sys

import pyperclip
from PyQt6.QtCore import Qt, QObject, pyqtSignal, QThread
from PyQt6.QtGui import QIcon, QColor
from PyQt6.QtWidgets import QApplication, QSystemTrayIcon, QMenu

from zh_en_translator.hotkey import HotKeyManager
from zh_en_translator.capture import TextCapture
from zh_en_translator.ui.popup import TranslatorPopup
from zh_en_translator.ui.sidebar import TranslatorSidebar


class _OCRWorker(QThread):
    result_ready = pyqtSignal(str)  # emits OCR text or error message

    def __init__(self, image_bytes: bytes, ocr_fn):
        super().__init__()
        self.image_bytes = image_bytes
        self.ocr_fn = ocr_fn

    def run(self):
        try:
            result = self.ocr_fn(self.image_bytes, lang="zh")
            self.result_ready.emit(result if result else "⚠ No text detected in image.")
        except Exception as e:
            self.result_ready.emit(f"⚠ OCR failed: {e}")


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
        self._ocr_worker = None

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

        # Try to capture selected text first
        captured_text = self.text_capture.capture_selection()

        if not captured_text:
            # No selection — check clipboard
            clipboard = QApplication.instance().clipboard()
            mime = clipboard.mimeData()
            if mime.hasImage():
                # Image in clipboard → OCR route
                self._run_ocr_from_clipboard(clipboard)
                return
            elif mime.hasText():
                captured_text = mime.text().strip()
                if not captured_text:
                    return
            else:
                return

        self.popup = TranslatorPopup(captured_text, original_clipboard, on_pin=self._pin_to_sidebar)
        self.popup.show()

    def _run_ocr_from_clipboard(self, clipboard):
        """Extract image from clipboard, run OCR in background, then open popup."""
        from zh_en_translator.engines.ocr.engine import is_any_engine_available
        if not is_any_engine_available():
            # Show a minimal popup with an error message
            self.popup = TranslatorPopup(
                "⚠ No OCR engine available.\nInstall winsdk, tesseract, or paddleocr.",
                "",
                on_pin=self._pin_to_sidebar,
            )
            self.popup.show()
            return

        # Convert QImage from clipboard to PNG bytes
        qimage = clipboard.image()
        from PyQt6.QtCore import QBuffer, QIODevice
        buf = QBuffer()
        buf.open(QIODevice.OpenModeFlag.WriteOnly)
        qimage.save(buf, "PNG")
        image_bytes = bytes(buf.data())
        buf.close()

        if not image_bytes:
            return

        # Open popup with placeholder, run OCR in background worker
        self.popup = TranslatorPopup(
            "🔍 Running OCR…",
            "",
            on_pin=self._pin_to_sidebar,
            is_ocr_pending=True,
        )
        self.popup.show()

        # Start OCR worker
        from zh_en_translator.engines.ocr.engine import ocr_image
        self._ocr_worker = _OCRWorker(image_bytes, ocr_image)
        self._ocr_worker.result_ready.connect(self._on_ocr_result)
        self._ocr_worker.start()

    def _on_ocr_result(self, text: str):
        """Called when OCR worker finishes — update popup with extracted text."""
        if self.popup and not self.popup._dismissed:
            self.popup.set_ocr_result(text)

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
