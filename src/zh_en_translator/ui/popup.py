"""Frameless popup widget — shows source text and English sentence translation."""

from __future__ import annotations

import logging
import urllib.parse
import pyperclip
from PyQt6.QtCore import Qt, QTimer, QRectF, QUrl
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
from zh_en_translator.engines.translation_worker import TranslationWorker, PinyinWorker

logger = logging.getLogger(__name__)


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
        config=None,                             # Config | None
    ):
        super().__init__()
        self.captured_text = text
        self.original_clipboard = original_clipboard
        self.dictionary = dictionary
        self._on_pin = on_pin
        self._dismissed = False
        self._worker: TranslationWorker | None = None
        self._pinyin_worker: PinyinWorker | None = None
        self._is_ocr_pending = is_ocr_pending
        self._config = config

        self._setup_ui()
        self._apply_styling()
        self._apply_config(config)
        self._position_near_cursor()
        if not is_ocr_pending:
            self._start_translation()
            self._start_pinyin(text)
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
        # WA_TranslucentBackground can corrupt the per-widget palette on Windows
        # (DWM sets the window-role color to transparent/black). Reset it from
        # the application palette so palette(text), palette(mid) etc. resolve
        # correctly in child-widget stylesheets.
        self.setPalette(QApplication.palette())
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        layout = QVBoxLayout()
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(10)

        # ── Pinyin label (hidden until PinyinWorker returns a result) ────
        self._pinyin_label = QLabel("")
        self._pinyin_label.setObjectName("pinyinLabel")
        self._pinyin_label.setWordWrap(True)
        self._pinyin_label.setVisible(False)
        layout.addWidget(self._pinyin_label)

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

        # Hidden button — shown only when OCR reports a missing language pack
        self.btn_lang_settings = QPushButton("Open Language Settings")
        self.btn_lang_settings.setToolTip(
            "Open Windows Language Settings to install the Chinese language pack"
        )
        self.btn_lang_settings.setVisible(False)
        self.btn_lang_settings.clicked.connect(self._open_language_settings)
        btn_row.addWidget(self.btn_lang_settings)

        layout.addLayout(btn_row)

        self.setLayout(layout)
        self._setup_accessibility()
        self.resize(420, 190)

    def _setup_accessibility(self):
        """Set accessible names, descriptions, and logical tab order for screen readers."""
        # Pinyin label
        self._pinyin_label.setAccessibleName("Pinyin romanisation")
        self._pinyin_label.setAccessibleDescription(
            "Pinyin phonetic reading of the source text"
        )

        # Source text
        self.text_display.setAccessibleName("Source text")
        self.text_display.setAccessibleDescription(
            "Original Chinese text being translated. Editable."
        )

        # Translation
        self.translation_label.setAccessibleName("Translation")
        self.translation_label.setAccessibleDescription(
            "English translation of the source text"
        )

        # Buttons (accessible names are already implied by button text, but add descriptions)
        self.btn_copy.setAccessibleDescription(
            "Copy the English translation to the clipboard"
        )
        self.btn_lookup.setAccessibleDescription(
            "Open the source text in an external dictionary"
        )
        self.btn_replace.setAccessibleDescription(
            "Replace the original selected text with the English translation"
        )
        self.btn_pin.setAccessibleDescription(
            "Pin this translation to the persistent sidebar panel"
        )
        self.btn_lang_settings.setAccessibleDescription(
            "Open Windows Language Settings to install the Chinese OCR language pack"
        )

        # Logical tab order: source → translation → copy → lookup → replace → pin
        QWidget.setTabOrder(self.text_display, self.translation_label)
        QWidget.setTabOrder(self.translation_label, self.btn_copy)
        QWidget.setTabOrder(self.btn_copy, self.btn_lookup)
        QWidget.setTabOrder(self.btn_lookup, self.btn_replace)
        QWidget.setTabOrder(self.btn_replace, self.btn_pin)

    def _apply_styling(self):
        from zh_en_translator.engines.themes import resolve_palette

        # Determine if system is in dark mode
        sys_bg = QApplication.palette().color(self.backgroundRole())
        system_is_dark = sys_bg.lightness() < 128

        theme = "system"
        if self._config:
            theme = self._config.theme

        palette = resolve_palette(theme, system_is_dark)

        # bg_color override takes priority over theme background
        if self._config and self._config.bg_color:
            from PyQt6.QtGui import QColor
            bg = QColor(self._config.bg_color)
            is_dark = bg.lightness() < 128
            # Re-resolve using the overridden bg's darkness
            palette = resolve_palette("dark" if is_dark else "light", system_is_dark)
            bg_hex = self._config.bg_color
        else:
            bg_hex = palette.bg
            # Update the widget's palette so paintEvent uses the theme bg
            from PyQt6.QtGui import QColor, QPalette
            qpalette = self.palette()
            qpalette.setColor(QPalette.ColorRole.Window, QColor(bg_hex))
            self.setPalette(qpalette)

        self.setStyleSheet(f"""
            QTextEdit {{
                border: none;
                background: transparent;
                font-size: 11pt;
                color: {palette.muted};
            }}
            QLabel {{
                border: none;
                background: transparent;
                color: {palette.text};
                padding: 4px 0;
            }}
            QLabel#pinyinLabel {{
                color: {palette.muted};
                font-size: 9pt;
                padding: 0;
            }}
            QFrame {{ background: transparent; }}
            QPushButton {{
                background: transparent;
                border: 1px solid {palette.border};
                border-radius: 4px;
                padding: 3px 10px;
                font-size: 10pt;
                color: {palette.text};
            }}
            QPushButton:hover  {{ background: {palette.btn_hover}; }}
            QPushButton:pressed {{ background: {palette.btn_pressed}; }}
            QPushButton:disabled {{ color: {palette.muted}; border-color: {palette.border}; }}
        """)

    def _apply_config(self, config):
        """Apply config settings to font and background color."""
        if config is None:
            return

        font = self.translation_label.font()
        changed = False

        if config.font_family:
            font.setFamily(config.font_family)
            changed = True

        if config.font_size != 13:
            font.setPointSize(config.font_size)
            changed = True

        if changed:
            self.translation_label.setFont(font)

        if config.bg_color:
            from PyQt6.QtGui import QPalette
            palette = self.palette()
            palette.setColor(QPalette.ColorRole.Window, QColor(config.bg_color))
            self.setPalette(palette)

    def _effective_bg(self) -> QColor:
        """Safe background colour for both light and dark mode on Windows."""
        if self._config and self._config.bg_color:
            return QColor(self._config.bg_color)
        if self._config and self._config.theme != "system":
            from zh_en_translator.engines.themes import THEMES
            palette = THEMES.get(self._config.theme)
            if palette:
                return QColor(palette.bg)
        app_bg = QApplication.palette().color(self.backgroundRole())
        # Near-pure-black (lightness < 10) almost certainly indicates the
        # WA_TranslucentBackground palette corruption rather than intentional
        # dark mode (Windows dark mode gives ~#202020, lightness ≈ 12).
        if app_bg.lightness() < 10:
            return QColor(248, 248, 248)
        return app_bg

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        path = QPainterPath()
        path.addRoundedRect(rect, 10, 10)
        bg = self._effective_bg()
        is_dark = bg.lightness() < 128
        painter.fillPath(path, bg)
        border = QColor(255, 255, 255, 30) if is_dark else QColor(0, 0, 0, 40)
        painter.setPen(QPen(border, 1))
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
        self._worker = TranslationWorker(self.captured_text)
        self._worker.result_ready.connect(self._on_translation_ready)
        self._worker.start()

    def _start_pinyin(self, text: str):
        """Start PinyinWorker if config enables it for this text length."""
        if self._config is None or not self._config.show_pinyin:
            return
        if len(text) > self._config.pinyin_max_chars:
            return
        self._pinyin_worker = PinyinWorker(text)
        self._pinyin_worker.result_ready.connect(self._on_pinyin_ready)
        self._pinyin_worker.start()

    def _on_pinyin_ready(self, pinyin_str: str):
        """Show pinyin label when worker returns a non-empty result."""
        if self._dismissed or not pinyin_str:
            return
        self._pinyin_label.setText(pinyin_str)
        self._pinyin_label.setVisible(True)
        self._position_near_cursor()

    def set_ocr_result(self, text: str):
        """Called by app after OCR completes — either start translation or show error."""
        if self._dismissed:
            return

        if text.startswith("⚠"):
            # OCR error — display in translation area, do NOT try to translate it
            self.translation_label.setText(text)
            self.translation_label.adjustSize()
            if "language pack" in text.lower():
                self.btn_lang_settings.setVisible(True)
            return

        # Normal OCR success — set as source text and translate
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

    def _on_pinyin_ready(self, pinyin_str: str):
        """Show pinyin label when PinyinWorker returns a non-empty result."""
        if self._dismissed:
            return
        if not pinyin_str:
            return
        self._pinyin_label.setText(pinyin_str)
        self._pinyin_label.setVisible(True)
        self._pinyin_label.adjustSize()
        # Expand popup height slightly to accommodate the new label
        extra = self._pinyin_label.sizeHint().height() + 4
        self.resize(self.width(), min(580, self.height() + extra))
        self._position_near_cursor()

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
        if self._pinyin_worker and self._pinyin_worker.isRunning():
            self._pinyin_worker.quit()
            self._pinyin_worker.wait(500)
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
            logger.warning("paste failed: %s", e)

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
        """Open the configured lookup URL in the default browser."""
        encoded = urllib.parse.quote(self.captured_text)
        if self._config and self._config.external_lookup_url:
            url_template = self._config.external_lookup_url
        else:
            url_template = "https://www.mdbg.net/chinese/dictionary?wdqb={query}"
        url_str = url_template.replace("{query}", encoded)
        QDesktopServices.openUrl(QUrl(url_str))

    def _open_language_settings(self):
        """Open Windows Language Settings to install the Chinese OCR language pack."""
        QDesktopServices.openUrl(QUrl("ms-settings:regionlanguage"))

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
        if self._pinyin_worker and self._pinyin_worker.isRunning():
            self._pinyin_worker.quit()
            self._pinyin_worker.wait(500)
        self.close()

    def mousePressEvent(self, event):
        super().mousePressEvent(event)
