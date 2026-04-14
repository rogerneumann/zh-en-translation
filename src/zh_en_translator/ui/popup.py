"""Frameless popup widget for displaying captured text and word-by-word translations."""

import pyperclip
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QCursor, QColor
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QLabel,
    QTextEdit,
    QApplication,
    QGraphicsDropShadowEffect,
    QTableWidget,
    QTableWidgetItem,
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
    - Optional word-by-word table if dictionary is provided.
    """

    def __init__(
        self, text: str, original_clipboard: str = "", dictionary: Dictionary | None = None
    ):
        """
        Initialize the popup.

        Args:
            text: The text to display (captured selection).
            original_clipboard: The clipboard contents to restore on dismiss.
            dictionary: Optional Dictionary instance for word-by-word lookup.
        """
        super().__init__()
        self.captured_text = text
        self.original_clipboard = original_clipboard
        self.dictionary = dictionary
        self._dismissed = False

        self._setup_ui()
        self._apply_styling()
        self._position_near_cursor()

    def _setup_ui(self):
        """Build the UI: title + text display + optional word-by-word table."""
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        layout = QVBoxLayout()
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        # Title label
        title_text = "M2 — dictionary lookup" if self.dictionary else "M1 — captured text"
        title = QLabel(title_text)
        title_font = title.font()
        title_font.setPointSize(10)
        title_font.setBold(True)
        title.setFont(title_font)
        layout.addWidget(title)

        # Text display (read-only, selectable)
        self.text_display = QTextEdit()
        self.text_display.setPlainText(self.captured_text)
        self.text_display.setReadOnly(True)
        self.text_display.setMaximumSize(600, 150)
        self.text_display.setMaximumHeight(100)
        # Allow text selection
        self.text_display.setTextInteractionFlags(
            self.text_display.textInteractionFlags()
            | Qt.TextInteractionFlag.TextSelectableByMouse
        )
        layout.addWidget(self.text_display)

        # Word-by-word table if dictionary provided
        if self.dictionary:
            self._setup_word_table(layout)

        # Auto-size the popup based on content
        self._resize_to_fit()

        self.setLayout(layout)

    def _setup_word_table(self, parent_layout: QVBoxLayout):
        """Create and populate the word-by-word translation table."""
        from zh_en_translator.engines.pipeline import translate

        # Create table
        self.word_table = QTableWidget()
        self.word_table.setColumnCount(3)
        self.word_table.setHorizontalHeaderLabels(["Token", "Pinyin", "English"])
        self.word_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.word_table.setMaximumHeight(400)

        # Translate and populate
        results = translate(self.captured_text, self.dictionary)
        self.word_table.setRowCount(len(results))

        for row, result in enumerate(results):
            # Token column
            token_item = QTableWidgetItem(result.token)
            token_item.setFlags(
                token_item.flags()
                | Qt.ItemFlag.ItemIsSelectable
                | Qt.ItemFlag.ItemIsEnabled
            )
            self.word_table.setItem(row, 0, token_item)

            # Pinyin column
            pinyin_text = result.pinyin if result.pinyin else ""
            pinyin_item = QTableWidgetItem(pinyin_text)
            pinyin_item.setFlags(
                pinyin_item.flags()
                | Qt.ItemFlag.ItemIsSelectable
                | Qt.ItemFlag.ItemIsEnabled
            )
            self.word_table.setItem(row, 1, pinyin_item)

            # English column
            if not result.is_chinese:
                # Non-Chinese token
                english_item = QTableWidgetItem("")
                english_item.setFlags(
                    english_item.flags()
                    | Qt.ItemFlag.ItemIsSelectable
                    | Qt.ItemFlag.ItemIsEnabled
                )
            elif result.glosses:
                # Known Chinese token
                english_text = "; ".join(result.glosses)
                english_item = QTableWidgetItem(english_text)
                english_item.setFlags(
                    english_item.flags()
                    | Qt.ItemFlag.ItemIsSelectable
                    | Qt.ItemFlag.ItemIsEnabled
                )
            else:
                # Unknown Chinese token
                english_item = QTableWidgetItem("unknown")
                english_item.setFlags(
                    english_item.flags()
                    | Qt.ItemFlag.ItemIsSelectable
                    | Qt.ItemFlag.ItemIsEnabled
                )
                # Highlight with yellow background
                english_item.setBackground(QColor(255, 255, 200))

            self.word_table.setItem(row, 2, english_item)

        # Resize columns to content
        self.word_table.resizeColumnsToContents()

        parent_layout.addWidget(self.word_table)

    def _resize_to_fit(self):
        """Resize popup to fit content, with reasonable bounds."""
        # Start with default size
        min_width, _min_height = 400, 200
        max_width, max_height = 700, 600

        # Estimate height: title + text + optional table
        estimated_height = 40  # Title
        estimated_height += 100  # Text display

        if self.dictionary:
            # Add height for word table (capped at 400px)
            num_rows = len(self.word_table) if hasattr(self, "word_table") else 0
            table_height = min(400, 30 + num_rows * 25)
            estimated_height += table_height + 10

        estimated_height = min(max_height, estimated_height)

        # Adjust width based on longest line
        longest_line = max(
            (len(line) for line in self.captured_text.split("\n")),
            default=0,
        )
        estimated_width = min(max_width, max(min_width, longest_line * 8))

        self.resize(int(estimated_width), int(estimated_height))

    def _apply_styling(self):
        """Apply rounded corners and drop shadow."""
        # Stylesheet for rounded corners and background
        self.setStyleSheet(
            """
            QWidget {
                border-radius: 10px;
                background-color: palette(window);
            }
            QTextEdit {
                border: none;
                border-radius: 8px;
                padding: 4px;
            }
        """
        )

        # Drop shadow effect
        from PyQt6.QtGui import QColor

        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(15)
        # Set color with alpha (30% opacity = 76/255)
        shadow.setColor(QColor(0, 0, 0, 76))
        shadow.setOffset(2, 2)
        self.setGraphicsEffect(shadow)

    def _position_near_cursor(self):
        """Position popup near the cursor, staying on-screen."""
        cursor_pos = QCursor.pos()
        popup_rect = self.rect()
        popup_width = popup_rect.width()
        popup_height = popup_rect.height()

        # Get the screen containing the cursor
        app = QApplication.instance()
        if not app:
            return
        screen = app.screenAt(cursor_pos)
        if not screen:
            return

        available_geometry = screen.availableGeometry()

        # Start slightly offset from cursor
        x = cursor_pos.x() + 10
        y = cursor_pos.y() + 10

        # Adjust if popup goes off the right edge
        if x + popup_width > available_geometry.right():
            x = available_geometry.right() - popup_width - 10

        # Adjust if popup goes off the bottom edge
        if y + popup_height > available_geometry.bottom():
            y = available_geometry.bottom() - popup_height - 10

        # Ensure popup doesn't go off the left or top
        x = max(x, available_geometry.left() + 10)
        y = max(y, available_geometry.top() + 10)

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
        # Use a timer to allow the widget to process the focus loss first
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

        # Restore original clipboard
        try:
            pyperclip.copy(self.original_clipboard)
        except Exception:
            pass

        self.close()

    def mousePressEvent(self, event):
        """Handle click-outside detection."""
        # Clicks inside the widget are handled normally.
        # For click-outside, we rely on focusOutEvent which fires when
        # another window gains focus. PyQt will emit focusOutEvent.
        super().mousePressEvent(event)
