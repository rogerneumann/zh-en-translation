"""Frameless popup widget — shows source text and English sentence translation."""

import pyperclip
from PyQt6.QtCore import Qt, QTimer, QThread, pyqtSignal, QRectF
from PyQt6.QtGui import QCursor, QFont, QPainter, QPainterPath, QPen, QColor
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QLabel,
    QTextEdit,
    QApplication,
    QFrame,
)

from zh_en_translator.engines.dictionary import Dictionary


class _TranslationWorker(QThread):
    """Background thread: downloads pack if needed, then translates."""

    result_ready = pyqtSignal(str)   # emits translated text or error message

    def __init__(self, text: str):
        super().__init__()
        self.text = text

    def run(self):
        from zh_en_translator.engines.argos import ensure_pack, translate_sentence

        print(f"[translate] input ({len(self.text)} chars): {self.text[:80]!r}")

        if not ensure_pack():
            msg = "⚠ Could not download the translation model. Check your internet connection."
            print(f"[translate] ensure_pack() failed")
            self.result_ready.emit(msg)
            return

        try:
            result = translate_sentence(self.text)
            print(f"[translate] result: {result!r}")
        except Exception as e:
            print(f"[translate] exception: {e}")
            result = None

        self.result_ready.emit(result if result else f"(no translation — input was: {self.text[:60]!r})")


class TranslatorPopup(QWidget):
    """
    Frameless popup: source text at top, English sentence translation below.

    Translation runs in a background thread — the popup appears immediately
    with a 'Translating…' placeholder that is replaced when the result arrives.

    Dismiss: Esc, click-outside, or focus loss.
    """

    def __init__(
        self,
        text: str,
        original_clipboard: str = "",
        dictionary: Dictionary | None = None,  # kept for API compatibility
    ):
        super().__init__()
        self.captured_text = text
        self.original_clipboard = original_clipboard
        self.dictionary = dictionary  # reserved for future word-lookup feature
        self._dismissed = False
        self._worker: _TranslationWorker | None = None

        self._setup_ui()
        self._apply_styling()
        self._position_near_cursor()
        self._start_translation()

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

        layout = QVBoxLayout()
        layout.setContentsMargins(18, 14, 18, 16)
        layout.setSpacing(10)

        # ── Source text (small, muted) ──────────────────────────────────
        self.text_display = QTextEdit()
        self.text_display.setPlainText(self.captured_text)
        self.text_display.setReadOnly(True)
        self.text_display.setFrameShape(QFrame.Shape.NoFrame)
        self.text_display.setMaximumHeight(60)
        self.text_display.setStyleSheet(
            "QTextEdit { background: transparent; font-size: 11pt; color: palette(mid); }"
        )
        self.text_display.setTextInteractionFlags(
            self.text_display.textInteractionFlags()
            | Qt.TextInteractionFlag.TextSelectableByMouse
        )
        layout.addWidget(self.text_display)

        # ── Divider ─────────────────────────────────────────────────────
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("border: none; border-top: 1px solid rgba(0,0,0,0.10);")
        layout.addWidget(sep)

        # ── English translation (main content) ──────────────────────────
        self.translation_label = QLabel("Translating…")
        self.translation_label.setWordWrap(True)
        self.translation_label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self.translation_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        font = QFont()
        font.setPointSize(13)
        self.translation_label.setFont(font)
        self.translation_label.setStyleSheet(
            "QLabel { background: transparent; color: palette(text); padding: 4px 0px; }"
        )
        layout.addWidget(self.translation_label)

        self.setLayout(layout)
        self.resize(420, 160)

    def _apply_styling(self):
        # Child widgets only — root background is painted in paintEvent.
        self.setStyleSheet(
            """
            QTextEdit { border: none; background: transparent; font-size: 11pt; color: palette(mid); }
            QLabel    { border: none; background: transparent; }
            QFrame    { background: transparent; }
            """
        )

    def paintEvent(self, event):
        """
        Manually paint the rounded-rect background.

        With WA_TranslucentBackground the OS does not fill the window, so
        stylesheet background-color on the root QWidget is a no-op on Windows.
        We must draw the fill ourselves.
        """
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        path = QPainterPath()
        path.addRoundedRect(rect, 10, 10)

        # Fill with window background colour
        bg = self.palette().color(self.backgroundRole())
        painter.fillPath(path, bg)

        # 1 px border
        painter.setPen(QPen(QColor(0, 0, 0, 40), 1))
        painter.drawPath(path)

        painter.end()

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

    def _on_translation_ready(self, text: str):
        if self._dismissed:
            return
        self.translation_label.setText(text)
        # Resize to fit the new text, then re-centre near cursor
        self.translation_label.adjustSize()
        needed_h = (
            self.text_display.height()
            + 10 + 1 + 10          # spacing + sep + spacing
            + self.translation_label.sizeHint().height()
            + 18 + 16              # top + bottom margins
        )
        self.resize(self.width(), min(520, max(140, needed_h)))
        self._position_near_cursor()

    # ------------------------------------------------------------------
    # Dismiss behaviour
    # ------------------------------------------------------------------

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self._dismiss()
        else:
            super().keyPressEvent(event)

    def focusOutEvent(self, event):
        super().focusOutEvent(event)
        QTimer.singleShot(10, self._dismiss)

    def changeEvent(self, event):
        from PyQt6.QtCore import QEvent

        if event.type() == QEvent.Type.WindowDeactivate:
            QTimer.singleShot(10, self._dismiss)
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
