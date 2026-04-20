"""Frameless popup widget — shows source text and English sentence translation."""

from __future__ import annotations

import logging
import re
import urllib.parse
from PyQt6.QtCore import Qt, QTimer, QRectF, QUrl, QPoint
from PyQt6.QtGui import QCursor, QFont, QPainter, QPainterPath, QPen, QColor, QDesktopServices, QKeyEvent
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QTextEdit,
    QPushButton,
    QApplication,
    QFrame,
    QToolTip,
    QScrollArea,
)

from zh_en_translator.engines.dictionary import Dictionary, Entry
from zh_en_translator.engines.translation_worker import TranslationWorker, PinyinWorker

logger = logging.getLogger(__name__)

# Windows 11 / Microsoft 365 modern font stack
_FONT_STACK = "'Segoe UI Variable Display', 'Aptos', 'Segoe UI', 'Microsoft YaHei', 'sans-serif'"

def wrap_words(text: str) -> str:
    """Wrap English words in <a> tags for interaction."""
    # Match sequences of alphabetic characters
    return re.sub(
        r"([a-zA-Z']+)",
        r'<a href="word:\1" style="text-decoration:none; color:inherit;">\1</a>',
        text,
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
        dictionary: Dictionary | None = None,
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
        self._pinned = False
        self._drag_pos: QPoint | None = None
        self._worker: TranslationWorker | None = None
        self._pinyin_worker: PinyinWorker | None = None
        self._is_ocr_pending = is_ocr_pending
        self._config = config
        self._loading_dots = 0
        self._loading_timer = QTimer(self)
        self._loading_timer.setInterval(400)
        self._loading_timer.timeout.connect(self._animate_loading)

        self._setup_ui()
        self._apply_styling()
        self._apply_config(config)
        self._position_near_cursor()
        if not is_ocr_pending:
            self._start_translation()
            self._start_pinyin(text)
            self._loading_timer.start()
        else:
            self.translation_label.setText("Waiting for OCR…")

    def _animate_loading(self):
        self._loading_dots = (self._loading_dots + 1) % 4
        dots = "." * self._loading_dots
        if self._is_ocr_pending:
            self.translation_label.setText(f"Waiting for OCR{dots}")
        else:
            self.translation_label.setText(f"Translating{dots}")

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
        # WA_TranslucentBackground can corrupt the per-widget palette on Windows.
        self.setPalette(QApplication.palette())
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        layout = QVBoxLayout()
        layout.setContentsMargins(16, 10, 16, 14)
        layout.setSpacing(8)

        # ── Header row (drag grip · stretch · pin · close) ───────────────
        header = QHBoxLayout()
        header.setSpacing(4)

        self._drag_grip = QLabel("⠿")
        self._drag_grip.setFixedSize(22, 22)
        self._drag_grip.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._drag_grip.setCursor(Qt.CursorShape.SizeAllCursor)
        self._drag_grip.setToolTip("Drag to move")
        header.addWidget(self._drag_grip)

        header.addStretch()

        self.btn_pin = QPushButton("📌")
        self.btn_pin.setEnabled(False)
        self.btn_pin.setCheckable(True)
        self.btn_pin.setChecked(False)
        self.btn_pin.setFixedSize(24, 24)
        self.btn_pin.setToolTip("Keep popup open")
        self.btn_pin.toggled.connect(self._on_pin_toggled)
        header.addWidget(self.btn_pin)

        self.btn_close = QPushButton("✕")
        self.btn_close.setFixedSize(24, 24)
        self.btn_close.setToolTip("Close popup")
        self.btn_close.clicked.connect(self._dismiss)
        header.addWidget(self.btn_close)

        layout.addLayout(header)

        # ── Pinyin label ────────────────────────────────────────────────
        self._pinyin_label = QLabel("")
        self._pinyin_label.setObjectName("pinyinLabel")
        self._pinyin_label.setWordWrap(True)
        self._pinyin_label.setVisible(False)
        layout.addWidget(self._pinyin_label)

        # ── Source text ─────────────────────────────────────────────────
        source_row = QHBoxLayout()
        source_row.setSpacing(6)
        
        self.text_display = QTextEdit()
        self.text_display.setPlainText(self.captured_text)
        self.text_display.setReadOnly(False)
        self.text_display.setFrameShape(QFrame.Shape.NoFrame)
        self.text_display.setMaximumHeight(60)
        self.text_display.installEventFilter(self) # For Ctrl+Enter
        source_row.addWidget(self.text_display, 1)

        self.btn_retranslate = QPushButton("↺")
        self.btn_retranslate.setFixedSize(28, 28)
        self.btn_retranslate.setToolTip("Retranslate (Ctrl+Enter)")
        self.btn_retranslate.clicked.connect(self._retranslate)
        source_row.addWidget(self.btn_retranslate)
        
        layout.addLayout(source_row)

        # ── Divider ─────────────────────────────────────────────────────
        self._sep = QFrame()
        self._sep.setFrameShape(QFrame.Shape.HLine)
        layout.addWidget(self._sep)

        # ── Translation text ────────────────────────────────────────────
        self.translation_label = QLabel("Translating…")
        self.translation_label.setWordWrap(True)
        self.translation_label.setAlignment(
            Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft
        )
        self.translation_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
            | Qt.TextInteractionFlag.TextSelectableByKeyboard
            | Qt.TextInteractionFlag.LinksAccessibleByMouse
        )
        self.translation_label.linkActivated.connect(self._on_link_activated)
        font = QFont()
        font.setPointSize(13)
        self.translation_label.setFont(font)
        layout.addWidget(self.translation_label)

        # ── Collapsible Details ─────────────────────────────────────────
        self._details_toggle = QPushButton("▼ Details")
        self._details_toggle.setCheckable(True)
        self._details_toggle.setChecked(False)
        self._details_toggle.setFixedWidth(84)
        self._details_toggle.clicked.connect(self._toggle_details)
        layout.addWidget(self._details_toggle)

        self._details_area = QScrollArea()
        self._details_area.setWidgetResizable(True)
        self._details_area.setFrameShape(QFrame.Shape.NoFrame)
        self._details_area.setMaximumHeight(0)  # Collapsed by default
        self._details_area.setVisible(False)
        
        self._details_content = QLabel("Word-by-word breakdown...")
        self._details_content.setWordWrap(True)
        self._details_content.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self._details_content.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self._details_content.setContentsMargins(4, 4, 4, 4)
        self._details_area.setWidget(self._details_content)
        layout.addWidget(self._details_area)

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

        self.btn_replace = QPushButton("Replace")
        self.btn_replace.setEnabled(False)
        self.btn_replace.setToolTip("Paste translation over the selected text")
        self.btn_replace.clicked.connect(self._replace_text)
        btn_row.addWidget(self.btn_replace)

        self.btn_pin_sidebar = QPushButton("Pin →")
        self.btn_pin_sidebar.setEnabled(False)
        self.btn_pin_sidebar.setToolTip("Pin translation to the sidebar")
        self.btn_pin_sidebar.setVisible(self._on_pin is not None)
        self.btn_pin_sidebar.clicked.connect(self._pin_to_sidebar)
        btn_row.addWidget(self.btn_pin_sidebar)

        self.btn_lang_settings = QPushButton("Open Language Settings")
        self.btn_lang_settings.setVisible(False)
        self.btn_lang_settings.clicked.connect(self._open_language_settings)
        btn_row.addWidget(self.btn_lang_settings)

        layout.addLayout(btn_row)

        self.setLayout(layout)
        self._setup_accessibility()
        self.resize(420, 180)

    def eventFilter(self, obj, event):
        if obj is self.text_display and event.type() == event.Type.KeyPress:
            if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and (event.modifiers() & Qt.KeyboardModifier.ControlModifier):
                self._retranslate()
                return True
        return super().eventFilter(obj, event)

    def _setup_accessibility(self):
        self._pinyin_label.setAccessibleName("Pinyin romanisation")
        self.text_display.setAccessibleName("Source text")
        self.translation_label.setAccessibleName("Translation")
        self.btn_copy.setAccessibleDescription("Copy the English translation to the clipboard")
        self.btn_lookup.setAccessibleDescription("Open the source text in an external dictionary")
        self.btn_replace.setAccessibleDescription("Replace the original selected text with the English translation")
        self.btn_pin.setAccessibleName("Pin")
        self.btn_close.setAccessibleName("Close")
        self.btn_pin_sidebar.setAccessibleDescription("Pin this translation to the persistent sidebar panel")
        QWidget.setTabOrder(self.text_display, self.translation_label)
        QWidget.setTabOrder(self.translation_label, self.btn_copy)

    def _apply_styling(self):
        from zh_en_translator.engines.themes import resolve_palette

        sys_bg = QApplication.palette().color(self.backgroundRole())
        system_is_dark = sys_bg.lightness() < 128
        theme = "system"
        if self._config:
            theme = self._config.theme
        palette = resolve_palette(theme, system_is_dark)

        if self._config and self._config.bg_color:
            bg_hex = self._config.bg_color
        else:
            bg_hex = palette.bg

        self.setStyleSheet(f"""
            QWidget {{
                font-family: {_FONT_STACK};
            }}
            QTextEdit {{
                border: 1px solid {palette.border};
                background: {palette.btn_bg};
                border-radius: 8px;
                font-size: 11pt;
                color: {palette.text};
                padding: 4px;
            }}
            QTextEdit:focus {{
                border-color: rgba(0, 120, 215, 0.4);
                background: {bg_hex};
            }}
            QLabel {{
                background: transparent;
                color: {palette.text};
            }}
            QLabel#pinyinLabel {{
                color: {palette.muted};
                font-size: 9pt;
                letter-spacing: 0.5px;
            }}
            QPushButton {{
                background: {palette.btn_bg};
                border: 1px solid {palette.border};
                border-radius: 14px;
                padding: 4px 16px;
                font-size: 10pt;
                color: {palette.text};
                min-height: 24px;
            }}
            QPushButton:hover  {{
                background: {palette.btn_hover};
                border-color: {palette.muted};
            }}
            QPushButton:pressed {{ background: {palette.btn_pressed}; }}
            QPushButton:disabled {{
                color: {palette.muted};
                background: transparent;
                border-color: transparent;
            }}
            QPushButton:checked {{
                background: rgba(0,160,255,0.1);
                border: 1px solid rgba(0,160,255,0.4);
            }}
        """)
        
        # Header buttons: circular hover
        _hdr = (
            f"QPushButton {{ background: transparent; border: none; border-radius: 12px;"
            f" padding: 0; font-size: 11pt; color: {palette.muted}; }}"
            f"QPushButton:hover {{ background: {palette.btn_hover}; color: {palette.text}; }}"
        )
        self.btn_pin.setStyleSheet(_hdr + f"QPushButton:checked {{ background: {palette.btn_pressed}; }}")
        self.btn_close.setStyleSheet(_hdr)
        
        # Retranslate button style
        self.btn_retranslate.setStyleSheet(f"""
            QPushButton {{ border-radius: 14px; background: {palette.btn_bg}; border: none; font-size: 12pt; }}
            QPushButton:hover {{ background: {palette.btn_hover}; }}
        """)

        # Divider color
        self._sep.setStyleSheet(f"border: none; border-top: 1px solid {palette.border};")

        # Ensure QTextEdit text color is set explicitly via QPalette (Qt quirk fix)
        text_palette = self.text_display.palette()
        text_palette.setColor(text_palette.ColorRole.Text, QColor(palette.text))
        self.text_display.setPalette(text_palette)
        
        # Details toggle style
        self._details_toggle.setStyleSheet(f"""
            QPushButton {{ font-size: 9pt; padding: 2px 8px; border-radius: 10px; background: {palette.btn_bg}; border: none; }}
            QPushButton:hover {{ background: {palette.btn_hover}; }}
        """)

    def _apply_config(self, config):
        if config is None:
            return
        font = self.translation_label.font()
        if config.font_family:
            font.setFamily(config.font_family)
        if config.font_size != 13:
            font.setPointSize(config.font_size)
        self.translation_label.setFont(font)

    def _effective_bg(self) -> QColor:
        if self._config and self._config.bg_color:
            return QColor(self._config.bg_color)
        if self._config and self._config.theme != "system":
            from zh_en_translator.engines.themes import THEMES
            palette = THEMES.get(self._config.theme)
            if palette:
                return QColor(palette.bg)
        return QApplication.palette().color(self.backgroundRole())

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        path = QPainterPath()
        path.addRoundedRect(rect, 16, 16)
        bg = self._effective_bg()
        is_dark = bg.lightness() < 128
        painter.fillPath(path, bg)
        border = QColor(255, 255, 255, 20) if is_dark else QColor(0, 0, 0, 15)
        painter.setPen(QPen(border, 1.2))
        painter.drawPath(path)
        painter.end()

    def showEvent(self, event):
        super().showEvent(event)
        self.activateWindow()
        self.raise_()

    def _position_near_cursor(self):
        cursor_pos = QCursor.pos()
        w, h = self.width(), self.height()
        screen = QApplication.screenAt(cursor_pos)
        if not screen: return
        avail = screen.availableGeometry()
        x = max(avail.left() + 14, min(cursor_pos.x() + 14, avail.right() - w - 14))
        y = max(avail.top() + 14, min(cursor_pos.y() + 14, avail.bottom() - h - 14))
        self.move(int(x), int(y))

    def _start_translation(self):
        self._worker = TranslationWorker(self.captured_text, config=self._config)
        self._worker.result_ready.connect(self._on_translation_ready)
        self._worker.start()

    def _start_pinyin(self, text: str):
        if self._config is None or not self._config.show_pinyin: return
        if len(text) > self._config.pinyin_max_chars: return
        self._pinyin_worker = PinyinWorker(text)
        self._pinyin_worker.result_ready.connect(self._on_pinyin_ready)
        self._pinyin_worker.start()

    def set_ocr_result(self, text: str):
        if self._dismissed: return
        if text.startswith("⚠"):
            self._loading_timer.stop()
            self.translation_label.setText(text)
            return
        self.captured_text = text
        self.text_display.setPlainText(text)
        self.translation_label.setText("Translating…")
        self._loading_timer.start()
        self._start_translation()

    def _retranslate(self):
        new_text = self.text_display.toPlainText().strip()
        if not new_text: return
        self.captured_text = new_text
        self.translation_label.setText("Translating…")
        self._loading_timer.start()
        self._start_translation()
        self._start_pinyin(new_text)

    def _on_translation_ready(self, text: str):
        if self._dismissed: return
        self._loading_timer.stop()
        if not text.startswith("⚠"):
            self.translation_label.setText(wrap_words(text))
            self._update_details()
        else:
            self.translation_label.setText(text)
        
        self.translation_label.adjustSize()
        needed_h = (self.layout().sizeHint().height() + 20)
        self.resize(self.width(), min(520, max(180, needed_h)))
        
        is_real = not text.startswith("⚠") and text != "Translating…"
        self.btn_copy.setEnabled(is_real)
        self.btn_lookup.setEnabled(is_real)
        self.btn_replace.setEnabled(is_real)
        self.btn_pin.setEnabled(is_real)
        if self._on_pin: self.btn_pin_sidebar.setEnabled(is_real)

    def _on_link_activated(self, link: str):
        if not link.startswith("word:") or not self.dictionary: return
        word = link[5:]
        entries = self.dictionary.lookup_english(word)
        if not entries: return
        tip = f"<b>{word}</b><br>" + "<br>".join([f"• {e.simplified} [{e.pinyin}]: {', '.join(e.glosses[:2])}" for e in entries[:4]])
        QToolTip.showText(QCursor.pos(), tip, self)

    def _toggle_details(self, checked: bool):
        self._details_toggle.setText("▲ Details" if checked else "▼ Details")
        self._details_area.setVisible(checked)
        self._details_area.setMaximumHeight(150 if checked else 0)
        self._on_translation_ready(self.translation_label.text())

    def _update_details(self):
        if not self.dictionary or not self.captured_text: return
        try:
            from zh_en_translator.engines import pipeline
            results = pipeline.translate(self.captured_text, self.dictionary)
            html = "".join([f"<div><b>{r.token}</b> {f'[{r.pinyin}]' if r.pinyin else ''}<br><span style='color:gray;'>{', '.join(r.glosses[:2])}</span></div>" if r.is_chinese else f"<span>{r.token}</span>" for r in results])
            self._details_content.setText(html)
        except: pass

    def _on_pinyin_ready(self, pinyin: str):
        if self._dismissed or not pinyin: return
        self._pinyin_label.setText(pinyin)
        self._pinyin_label.setVisible(True)

    def _replace_text(self):
        trans = self.translation_label.text()
        if not trans or trans == "Translating…": return
        QApplication.clipboard().setText(trans)
        self._dismissed = True
        self.close()
        QTimer.singleShot(150, self._do_paste)

    def _do_paste(self):
        from pynput.keyboard import Controller, Key
        kb = Controller()
        with kb.pressed(Key.ctrl): kb.tap('v')

    def _on_pin_toggled(self, checked): self._pinned = checked

    def _pin_to_sidebar(self):
        if self._on_pin and self.translation_label.text() != "Translating…":
            self._on_pin(self.captured_text, self.translation_label.text())
            self._dismiss()

    def _copy_translation(self):
        QApplication.clipboard().setText(self.translation_label.text())
        self.btn_copy.setText("Copied!")
        QTimer.singleShot(1500, lambda: self.btn_copy.setText("Copy"))

    def _lookup_external(self):
        template = (self._config.external_lookup_url if self._config else None) or "https://www.mdbg.net/chinese/dictionary?wdqb={query}"
        QDesktopServices.openUrl(QUrl(template.replace("{query}", urllib.parse.quote(self.captured_text))))

    def _open_language_settings(self): QDesktopServices.openUrl(QUrl("ms-settings:regionlanguage"))

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape: self._dismiss()
        else: super().keyPressEvent(event)

    def changeEvent(self, event):
        if event.type() == event.Type.WindowDeactivate and not self._pinned and not self.isActiveWindow():
            QTimer.singleShot(150, self._dismiss)
        super().changeEvent(event)

    def _dismiss(self):
        if self._dismissed: return
        self._dismissed = True
        try: QApplication.clipboard().setText(self.original_clipboard)
        except: pass
        self.close()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            child = self.childAt(event.pos())
            if not isinstance(child, (QPushButton, QTextEdit)):
                self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
                self.setCursor(Qt.CursorShape.SizeAllCursor)
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._drag_pos and (event.buttons() & Qt.MouseButton.LeftButton):
            self.move(event.globalPosition().toPoint() - self._drag_pos)

    def mouseReleaseEvent(self, event):
        self._drag_pos = None
        self.unsetCursor()
