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


class _SidebarTranslationWorker(QThread):
    result_ready = pyqtSignal(str)

    def __init__(self, text: str):
        super().__init__()
        self.text = text

    def run(self):
        from zh_en_translator.engines.argos import ensure_pack, translate_sentence

        if not ensure_pack():
            self.result_ready.emit("⚠ Translation model not available.")
            return
        try:
            result = translate_sentence(self.text)
        except Exception as e:
            result = None
        self.result_ready.emit(
            result if result else f"(no translation — input: {self.text[:60]!r})"
        )


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

        self.sidebar_mode: bool = False
        self._sidebar_translation_worker = None
        self._sidebar_on_left: bool = False

        self._hotkey_signal.connect(self._on_hotkey_pressed)
        self.hotkey_manager = HotKeyManager()
        self.text_capture = TextCapture()

        # Connect sidebar signals
        self.sidebar.closed.connect(self._on_sidebar_closed)

        self._setup_tray()

    def _setup_tray(self):
        self.tray_icon = QSystemTrayIcon(self.app)
        self.tray_icon.setIcon(self._create_icon())

        menu = QMenu()

        action_translate = menu.addAction("Translate Selection")
        action_translate.triggered.connect(self._on_hotkey_pressed)

        menu.addSeparator()

        self.action_sidebar = menu.addAction("Sidebar Mode: Off")
        self.action_sidebar.setCheckable(True)
        self.action_sidebar.triggered.connect(self._on_toggle_sidebar_mode)

        self.action_sidebar_side = menu.addAction("Move Sidebar to Left")
        self.action_sidebar_side.triggered.connect(self._on_toggle_sidebar_side)

        menu.addSeparator()

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

        # In sidebar mode — capture text, or if none, just expand sidebar
        if self.sidebar_mode:
            captured_text = self.text_capture.capture_selection()
            if not captured_text:
                clipboard = QApplication.instance().clipboard()
                mime = clipboard.mimeData()
                if mime.hasImage():
                    self._run_ocr_from_clipboard(clipboard)
                    return
                elif mime.hasText():
                    captured_text = mime.text().strip()
                if not captured_text:
                    self.sidebar.expand()
                    return
            # Have text in sidebar mode → update sidebar directly
            self._translate_for_sidebar(captured_text)
            return

        # Normal popup mode
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
        if not self.sidebar_mode:
            self.sidebar_mode = True
            self._update_tray_sidebar_label()
        if not self.sidebar.isVisible():
            self.sidebar.show()

    def _translate_for_sidebar(self, text: str) -> None:
        self.sidebar.set_translation_pending(text)
        self.sidebar.expand()
        if self._sidebar_translation_worker and self._sidebar_translation_worker.isRunning():
            self._sidebar_translation_worker.quit()
            self._sidebar_translation_worker.wait(300)
        self._sidebar_translation_worker = _SidebarTranslationWorker(text)
        self._sidebar_translation_worker.result_ready.connect(self.sidebar.update_translation)
        self._sidebar_translation_worker.start()

    def _on_sidebar_closed(self) -> None:
        self.sidebar_mode = False
        self._update_tray_sidebar_label()

    def _on_toggle_sidebar_mode(self, checked: bool) -> None:
        self.sidebar_mode = checked
        if checked and not self.sidebar.isVisible():
            self.sidebar.show()
        elif not checked:
            self.sidebar.collapse()
        self._update_tray_sidebar_label()

    def _on_toggle_sidebar_side(self) -> None:
        self._sidebar_on_left = not self._sidebar_on_left
        side = "left" if self._sidebar_on_left else "right"
        self.sidebar.set_side(side)
        self.action_sidebar_side.setText(
            "Move Sidebar to Right" if self._sidebar_on_left else "Move Sidebar to Left"
        )

    def _update_tray_sidebar_label(self) -> None:
        if hasattr(self, "action_sidebar"):
            self.action_sidebar.setChecked(self.sidebar_mode)
            self.action_sidebar.setText(
                "Sidebar Mode: On" if self.sidebar_mode else "Sidebar Mode: Off"
            )

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
