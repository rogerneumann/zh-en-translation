"""Frameless popup widget — shows source text and English sentence translation."""

from __future__ import annotations

import urllib.parse
import pyperclip
from PyQt6.QtCore import Qt, QTimer, QThread, pyqtSignal, QRectF, QUrl
from PyQt6.QtGui import QCursor, QFont, QPainter, QPainterPath, QPen, QColor, QDesktopServices
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QTextEdit,
    QPushButton,
    QApplication,
    QFrame,
)

from zh_en_translator.engines.dictionary import Dictionary


class _TranslationWorker(QThread):
    """Background thread: runs translation and emits the result."""

    result_ready = pyqtSignal(str)

    def __init__(self, text: str):
        super().__init__()
        self.text = text

    def run(self):
        from zh_en_translator.engines.argos import ensure_pack, translate_sentence

        print(f"[translate] input ({len(self.text)} chars): {self.text[:80]!r}")

        if not ensure_pack():
            print("[translate] ensure_pack() failed")
            self.result_ready.emit("⚠ Translation model not available.")
            return

        try:
            result = translate_sentence(self.text)
            print(f"[translate] result: {result!r}")
        except Exception as e:
            print(f"[translate] exception: {e}")
            result = None

        self.result_ready.emit(
            result if result else f"(no translation — input: {self.text[:60]!r})"
        )


class TranslatorPopup(QWidget):
    """
    Frameless popup: source text at top, English sentence translation below.

    Translation runs in a background thread — the popup appears immediately
    with a 'Translating…' placeholder that is replaced when the result arrives.

    Buttons (enabled once translation is ready):
      • Replace text — pastes the translation over the original selection
      • Pin →        — sends the translation to the persistent sidebar

    Dismiss: Esc key or clicking outside the popup.
    """

    def __init__(
        self,
        text: str,
        original_clipboard: str = "",
        dictionary: Dictionary | None = None,   # reserved for future word-lookup
        on_pin=None,                             # Callable[[str, str], None] | None
        is_ocr_pending: bool = False,
    ):
        super().__init__()
        self.captured_text = text
        self.original_clipboard = original_clipboard
        self.dictionary = dictionary
        self._on_pin = on_pin
        self._dismissed = False
        self._worker: _TranslationWorker | None = None
        self._is_ocr_pending = is_ocr_pending

        self._setup_ui()
        self._apply_styling()
        self._position_near_cursor()
        if not is_ocr_pending:
            self._start_translation()
        else:
            self.translation_label.setText("Waiting for OCR…")

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _setup_ui(self):
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        layout = QVBoxLayout()
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(10)

        # ── Source text (small, muted, selectable) ──────────────────────
        self.text_display = QTextEdit()
        self.text_display.setPlainText(self.captured_text)
        self.text_display.setReadOnly(True)
        self.text_display.setFrameShape(QFrame.Shape.NoFrame)
        self.text_display.setMaximumHeight(60)
        self.text_display.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
            | Qt.TextInteractionFlag.TextSelectableByKeyboard
        )
        layout.addWidget(self.text_display)

        # ── Divider ─────────────────────────────────────────────────────
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("border: none; border-top: 1px solid rgba(0,0,0,0.10);")
        layout.addWidget(sep)

        # ── English translation (main content, selectable) ──────────────
        self.translation_label = QLabel("Translating…")
        self.translation_label.setWordWrap(True)
        self.translation_label.setAlignment(
            Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft
        )
        self.translation_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
            | Qt.TextInteractionFlag.TextSelectableByKeyboard
        )
        font = QFont()
        font.setPointSize(13)
        self.translation_label.setFont(font)
        layout.addWidget(self.translation_label)

        # ── Action buttons ───────────────────────────────────────────────
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        btn_row.addStretch()

        self.btn_copy = QPushButton("Copy")
        self.btn_copy.setEnabled(False)
        self.btn_copy.setToolTip("Copy translation to clipboard")
        self.btn_copy.clicked.connect(self._copy_translation)
        btn_row.addWidget(self.btn_copy)

        self.btn_lookup = QPushButton("Look up")
        self.btn_lookup.setEnabled(False)
        self.btn_lookup.setToolTip("Look up source text on MDBG")
        self.btn_lookup.clicked.connect(self._lookup_external)
        btn_row.addWidget(self.btn_lookup)

        self.btn_replace = QPushButton("Replace text")
        self.btn_replace.setEnabled(False)
        self.btn_replace.setToolTip("Paste translation over the selected text")
        self.btn_replace.clicked.connect(self._replace_text)
        btn_row.addWidget(self.btn_replace)

        self.btn_pin = QPushButton("Pin →")
        self.btn_pin.setEnabled(False)
        self.btn_pin.setToolTip("Pin translation to the sidebar")
        self.btn_pin.setVisible(self._on_pin is not None)
        self.btn_pin.clicked.connect(self._pin_to_sidebar)
        btn_row.addWidget(self.btn_pin)

        layout.addLayout(btn_row)

        self.setLayout(layout)
        self.resize(420, 190)

    def _apply_styling(self):
        self.setStyleSheet(
            """
            QTextEdit {
                border: none;
                background: transparent;
                font-size: 11pt;
                color: palette(mid);
            }
            QLabel {
                border: none;
                background: transparent;
                color: palette(text);
                padding: 4px 0;
            }
            QFrame { background: transparent; }
            QPushButton {
                background: transparent;
                border: 1px solid rgba(0,0,0,0.15);
                border-radius: 4px;
                padding: 3px 10px;
                font-size: 10pt;
                color: palette(text);
            }
            QPushButton:hover  { background: rgba(0,0,0,0.06); }
            QPushButton:pressed { background: rgba(0,0,0,0.12); }
            QPushButton:disabled { color: palette(mid); border-color: rgba(0,0,0,0.07); }
            """
        )

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        path = QPainterPath()
        path.addRoundedRect(rect, 10, 10)
        bg = self.palette().color(self.backgroundRole())
        painter.fillPath(path, bg)
        painter.setPen(QPen(QColor(0, 0, 0, 40), 1))
        painter.drawPath(path)
        painter.end()

    def showEvent(self, event):
        """Grab keyboard focus so Esc works immediately."""
        super().showEvent(event)
        self.activateWindow()
        self.raise_()

    def _position_near_cursor(self):
        cursor_pos = QCursor.pos()
        w, h = self.width(), self.height()

        app = QApplication.instance()
        if not app:
            return
        screen = app.screenAt(cursor_pos)
        if not screen:
            return

        avail = screen.availableGeometry()
        x = cursor_pos.x() + 14
        y = cursor_pos.y() + 14

        if x + w > avail.right():
            x = avail.right() - w - 14
        if y + h > avail.bottom():
            y = avail.bottom() - h - 14

        x = max(x, avail.left() + 14)
        y = max(y, avail.top() + 14)

        self.move(int(x), int(y))

    # ------------------------------------------------------------------
    # Translation
    # ------------------------------------------------------------------

    def _start_translation(self):
        self._worker = _TranslationWorker(self.captured_text)
        self._worker.result_ready.connect(self._on_translation_ready)
        self._worker.start()

    def set_ocr_result(self, text: str):
        """Called by app after OCR completes — set source text and start translation."""
        if self._dismissed:
            return
        self.captured_text = text
        self.text_display.setPlainText(text)
        self.translation_label.setText("Translating…")
        self._start_translation()

    def _on_translation_ready(self, text: str):
        if self._dismissed:
            return
        self.translation_label.setText(text)
        self.translation_label.adjustSize()

        needed_h = (
            self.text_display.height()
            + 10 + 1 + 10                           # spacing + sep + spacing
            + self.translation_label.sizeHint().height()
            + 40                                    # button row
            + 14 + 14                               # top + bottom margins
        )
        self.resize(self.width(), min(540, max(190, needed_h)))
        self._position_near_cursor()

        # Enable action buttons now that we have a real translation
        is_real = not text.startswith("⚠") and text != "Translating…"
        self.btn_copy.setEnabled(is_real)
        self.btn_lookup.setEnabled(is_real)
        self.btn_replace.setEnabled(is_real)
        if self._on_pin is not None:
            self.btn_pin.setEnabled(is_real)

    # ------------------------------------------------------------------
    # Action buttons
    # ------------------------------------------------------------------

    def _replace_text(self):
        """Copy the translation to clipboard and paste it over the selection."""
        translation = self.translation_label.text()
        if not translation or translation == "Translating…":
            return

        try:
            pyperclip.copy(translation)
        except Exception:
            return

        # Close without restoring original clipboard (translation stays in clipboard).
        self._dismissed = True
        if self._worker and self._worker.isRunning():
            self._worker.quit()
            self._worker.wait(500)
        self.close()

        # Give the source app ~120 ms to regain focus before we paste.
        QTimer.singleShot(120, self._do_paste)

    def _do_paste(self):
        try:
            from pynput.keyboard import Controller as KeyboardController, Key
            kb = KeyboardController()
            kb.press(Key.ctrl)
            kb.press("v")
            kb.release("v")
            kb.release(Key.ctrl)
        except Exception as e:
            print(f"[replace] paste failed: {e}")

    def _pin_to_sidebar(self):
        """Send the current translation to the sidebar and dismiss."""
        if self._on_pin is None:
            return
        translation = self.translation_label.text()
        if not translation or translation == "Translating…":
            return
        self._on_pin(self.captured_text, translation)
        self._dismiss()

    def _copy_translation(self):
        """Copy the translation text to the system clipboard without dismissing."""
        translation = self.translation_label.text()
        if not translation or translation == "Translating…":
            return
        try:
            QApplication.clipboard().setText(translation)
        except Exception:
            return
        # Brief visual feedback
        self.btn_copy.setText("Copied!")
        QTimer.singleShot(1500, lambda: self.btn_copy.setText("Copy"))

    def _lookup_external(self):
        """Open MDBG in the default browser with the source Chinese text as query."""
        encoded = urllib.parse.quote(self.captured_text)
        url = QUrl(f"https://www.mdbg.net/chinese/dictionary?wdqb={encoded}")
        QDesktopServices.openUrl(url)

    # ------------------------------------------------------------------
    # Dismiss behaviour
    # ------------------------------------------------------------------

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self._dismiss()
        else:
            super().keyPressEvent(event)

    def changeEvent(self, event):
        from PyQt6.QtCore import QEvent

        if event.type() == QEvent.Type.WindowDeactivate:
            # Delay slightly so button-click signals fire before we close.
            QTimer.singleShot(150, self._dismiss)
        super().changeEvent(event)

    def _dismiss(self):
        if self._dismissed:
            return
        self._dismissed = True
        try:
            pyperclip.copy(self.original_clipboard)
        except Exception:
            pass
        if self._worker and self._worker.isRunning():
            self._worker.quit()
            self._worker.wait(500)
        self.close()

    def mousePressEvent(self, event):
        super().mousePressEvent(event)
