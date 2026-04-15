"""Frameless popup widget for displaying captured text and word-by-word translations."""

import pyperclip
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QCursor, QColor
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QTextEdit,
    QApplication,
    QGraphicsDropShadowEffect,
    QScrollArea,
    QFrame,
)

from zh_en_translator.engines.dictionary import Dictionary


class TranslatorPopup(QWidget):
    """
    Frameless popup that displays captured text and word-by-word translations.

    Features:
    - Frameless, rounded corners, drop shadow.
    - Positioned near cursor, auto-repositions to stay on-screen.
    - Dismiss on Esc, click-outside, or focus loss.
    - Restores original clipboard on dismiss.
    - Pinyin + English list when dictionary is provided.
    """

    def __init__(
        self, text: str, original_clipboard: str = "", dictionary: Dictionary | None = None
    ):
        super().__init__()
        self.captured_text = text
        self.original_clipboard = original_clipboard
        self.dictionary = dictionary
        self._dismissed = False
        self._word_count = 0

        self._setup_ui()
        self._apply_styling()
        self._position_near_cursor()

    def _setup_ui(self):
        """Build the UI: source text + pinyin/English word list."""
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        layout = QVBoxLayout()
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(10)

        # Source text (read-only, selectable, no border)
        self.text_display = QTextEdit()
        self.text_display.setPlainText(self.captured_text)
        self.text_display.setReadOnly(True)
        self.text_display.setFrameShape(QFrame.Shape.NoFrame)
        self.text_display.setMaximumHeight(72)
        self.text_display.setStyleSheet(
            "QTextEdit { background: transparent; font-size: 13pt; }"
        )
        self.text_display.setTextInteractionFlags(
            self.text_display.textInteractionFlags()
            | Qt.TextInteractionFlag.TextSelectableByMouse
        )
        layout.addWidget(self.text_display)

        # Separator
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("border: none; border-top: 1px solid rgba(0,0,0,0.10); margin: 0px;")
        layout.addWidget(sep)

        # Word list (pinyin + English)
        if self.dictionary:
            self._setup_word_list(layout)

        self._resize_to_fit()
        self.setLayout(layout)

    def _setup_word_list(self, parent_layout: QVBoxLayout):
        """Build a scrollable pinyin → English list (no Token column)."""
        from zh_en_translator.engines.pipeline import translate

        results = translate(self.captured_text, self.dictionary)
        self._word_count = sum(1 for r in results if r.is_chinese)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setMaximumHeight(280)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        container = QWidget()
        container.setStyleSheet("background: transparent;")
        vbox = QVBoxLayout(container)
        vbox.setSpacing(2)
        vbox.setContentsMargins(0, 2, 4, 2)

        for result in results:
            if not result.is_chinese:
                continue

            row_widget = QWidget()
            row_widget.setStyleSheet("background: transparent;")
            row = QHBoxLayout(row_widget)
            row.setSpacing(12)
            row.setContentsMargins(0, 3, 0, 3)

            # Pinyin — fixed width, blue
            pinyin_lbl = QLabel(result.pinyin or "—")
            pinyin_lbl.setFixedWidth(130)
            pinyin_lbl.setStyleSheet("color: #5b9bd5; font-size: 10.5pt; background: transparent;")
            pinyin_lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

            # English
            if result.glosses:
                eng_text = "; ".join(result.glosses[:3])
                eng_lbl = QLabel(eng_text)
                eng_lbl.setStyleSheet("font-size: 11pt; background: transparent;")
            else:
                eng_lbl = QLabel(f"<i style='color:#d4880a;'>{result.token} — unknown</i>")
                eng_lbl.setTextFormat(Qt.TextFormat.RichText)
                eng_lbl.setStyleSheet("background: transparent;")

            eng_lbl.setWordWrap(True)
            eng_lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

            row.addWidget(pinyin_lbl)
            row.addWidget(eng_lbl, 1)

            vbox.addWidget(row_widget)

        vbox.addStretch()
        scroll.setWidget(container)
        parent_layout.addWidget(scroll)

    def _resize_to_fit(self):
        """Resize popup to fit content, with reasonable bounds."""
        min_w, max_w = 380, 540
        max_h = 520

        source_h = 72 + 10 + 1 + 10  # text_display + spacing + sep + spacing
        word_h = min(280, max(60, self._word_count * 30 + 8)) if self.dictionary else 0
        padding = 28  # top + bottom margins
        estimated_h = min(max_h, source_h + word_h + padding)

        longest = max((len(line) for line in self.captured_text.split("\n")), default=0)
        estimated_w = min(max_w, max(min_w, longest * 9))

        self.resize(int(estimated_w), int(estimated_h))

    def _apply_styling(self):
        """Apply rounded corners and drop shadow."""
        self.setStyleSheet(
            """
            QWidget {
                border-radius: 12px;
                background-color: palette(window);
            }
            QScrollBar:vertical {
                width: 6px;
                background: transparent;
            }
            QScrollBar::handle:vertical {
                background: rgba(0,0,0,0.18);
                border-radius: 3px;
                min-height: 20px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """
        )

        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(22)
        shadow.setColor(QColor(0, 0, 0, 90))
        shadow.setOffset(0, 4)
        self.setGraphicsEffect(shadow)

    def _position_near_cursor(self):
        """Position popup near the cursor, staying on-screen."""
        cursor_pos = QCursor.pos()
        popup_width = self.rect().width()
        popup_height = self.rect().height()

        app = QApplication.instance()
        if not app:
            return
        screen = app.screenAt(cursor_pos)
        if not screen:
            return

        available = screen.availableGeometry()

        x = cursor_pos.x() + 12
        y = cursor_pos.y() + 12

        if x + popup_width > available.right():
            x = available.right() - popup_width - 12
        if y + popup_height > available.bottom():
            y = available.bottom() - popup_height - 12

        x = max(x, available.left() + 12)
        y = max(y, available.top() + 12)

        self.move(int(x), int(y))

    def keyPressEvent(self, event):
        """Handle Esc key to dismiss."""
        if event.key() == Qt.Key.Key_Escape:
            self._dismiss()
        else:
            super().keyPressEvent(event)

    def focusOutEvent(self, event):
        """Handle focus loss to dismiss."""
        super().focusOutEvent(event)
        QTimer.singleShot(10, self._dismiss)

    def changeEvent(self, event):
        """Handle window deactivation to dismiss."""
        from PyQt6.QtCore import QEvent

        if event.type() == QEvent.Type.WindowDeactivate:
            QTimer.singleShot(10, self._dismiss)
        super().changeEvent(event)

    def _dismiss(self):
        """Dismiss the popup and restore clipboard."""
        if self._dismissed:
            return
        self._dismissed = True

        try:
            pyperclip.copy(self.original_clipboard)
        except Exception:
            pass

        self.close()

    def mousePressEvent(self, event):
        """Handle click-outside detection."""
        super().mousePressEvent(event)
