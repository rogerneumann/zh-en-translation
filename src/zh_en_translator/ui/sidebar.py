"""Persistent sidebar widget — M5 peek-tab style, docked to a screen edge."""

from __future__ import annotations

import logging

from PyQt6.QtCore import (
    Qt,
    QRectF,
    QPoint,
    QTimer,
    QPropertyAnimation,
    QEasingCurve,
    pyqtSignal,
)
from PyQt6.QtGui import (
    QColor,
    QPainter,
    QCursor,
)
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QFrame,
    QScrollArea,
    QApplication,
    QListWidget,
    QListWidgetItem,
    QFileDialog,
    QToolTip,
)

from zh_en_translator.engines.history import HistoryManager
from zh_en_translator.config import get_config_path
from zh_en_translator.ui.popup import wrap_words, _render_translation_html

logger = logging.getLogger(__name__)

_RESIZE_HANDLE_W = 6   # px — width of the inner-edge resize grab zone
_MIN_SIDEBAR_W   = 180 # px
_MAX_SIDEBAR_W   = 600 # px

# Windows 11 / Microsoft 365 modern font stack
_FONT_STACK = "'Segoe UI Variable Display', 'Aptos', 'Segoe UI', 'Microsoft YaHei', 'sans-serif'"

class TranslatorSidebar(QWidget):
    """
    Persistent vertical panel anchored to the left or right screen edge.

    Collapsed: shows a thin 6px colored 'strip'.
    Expanded: shows source, translation, and history.
    """

    closed = pyqtSignal()  # emitted when user clicks X to revert to popup mode

    COLOUR_FRESH   = QColor("#00C9CC") # Cyan
    COLOUR_NEUTRAL = QColor("#9E8080") # Muted rose

    def __init__(self, config=None, parent=None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setPalette(QApplication.palette())

        self._config = config
        self.dictionary = None
        self._history_manager = HistoryManager(get_config_path().parent / "history.json")

        self._side = "right"
        self._width = 280
        self._y_pos = 100
        self._expanded = False
        self._pinned = False
        self._is_dragging_y = False
        self._is_resizing_x = False
        self._drag_start_pos = QPoint()
        self._indicator_colour = self.COLOUR_NEUTRAL

        if config:
            self._side = config.side
            self._y_pos = config.sidebar_y
            self._width = config.sidebar_width

        # Collapse/expand animation
        self._animation = QPropertyAnimation(self, b"pos")
        self._animation.setDuration(200)
        self._animation.setEasingCurve(QEasingCurve.Type.OutCubic)

        self._loading_dots = 0
        self._loading_timer = QTimer(self)
        self._loading_timer.setInterval(400)
        self._loading_timer.timeout.connect(self._animate_loading)

        self._setup_ui()
        self._apply_styling()
        self._setup_accessibility()
        self._reposition()

    def _animate_loading(self):
        self._loading_dots = (self._loading_dots + 1) % 4
        dots = "." * self._loading_dots
        if "OCR" in self.source_label.text():
            self.translation_label.setText(f"Running OCR{dots}")
        else:
            self.translation_label.setText(f"Translating{dots}")

    def _setup_ui(self):
        self.main_layout = QHBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        # ── The Panel ──────────────────────────────────────────────────
        self.panel = QFrame()
        self.panel.setObjectName("sidebarPanel")
        panel_layout = QVBoxLayout(self.panel)
        panel_layout.setContentsMargins(12, 10, 12, 12)
        panel_layout.setSpacing(10)

        # Header
        header = QHBoxLayout()
        self._drag_grip = QLabel("⠿")
        self._drag_grip.setFixedSize(20, 20)
        self._drag_grip.setCursor(Qt.CursorShape.SizeAllCursor)
        header.addWidget(self._drag_grip)

        self._title_label = QLabel("TRANSLATOR")
        header.addWidget(self._title_label, 1)

        self.btn_pin = QPushButton("📌")
        self.btn_pin.setCheckable(True)
        self.btn_pin.setFixedSize(22, 22)
        self.btn_pin.toggled.connect(self._on_pin_toggled)
        header.addWidget(self.btn_pin)

        self._close_btn = QPushButton("✕")
        self._close_btn.setFixedSize(22, 22)
        self._close_btn.clicked.connect(self.close_sidebar)
        header.addWidget(self._close_btn)
        panel_layout.addLayout(header)

        # Content area
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setContentsMargins(0, 0, 0, 0)
        scroll_layout.setSpacing(8)

        self.source_label = QLabel("No translation yet")
        self.source_label.setWordWrap(True)
        self.source_label.setStyleSheet("font-weight: 500; font-size: 10pt;")
        scroll_layout.addWidget(self.source_label)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("border: none; border-top: 1px solid rgba(0,0,0,0.06);")
        scroll_layout.addWidget(sep)

        self.translation_label = QLabel("")
        self.translation_label.setWordWrap(True)
        self.translation_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
            | Qt.TextInteractionFlag.LinksAccessibleByMouse
        )
        self.translation_label.linkActivated.connect(self._on_link_activated)
        scroll_layout.addWidget(self.translation_label)

        # History
        hist_header = QHBoxLayout()
        hist_header.setContentsMargins(0, 12, 0, 0)
        self._hist_title = QLabel("History")
        hist_header.addWidget(self._hist_title, 1)

        self.btn_clear = QPushButton("🗑")
        self.btn_clear.setFixedSize(22, 22)
        self.btn_clear.clicked.connect(self._on_clear_history)
        hist_header.addWidget(self.btn_clear)

        self.btn_export = QPushButton("📤")
        self.btn_export.setFixedSize(22, 22)
        self.btn_export.clicked.connect(self._on_export_history)
        hist_header.addWidget(self.btn_export)
        scroll_layout.addLayout(hist_header)

        self.history_list = QListWidget()
        self.history_list.setMinimumHeight(180)
        self.history_list.itemClicked.connect(self._on_history_item_clicked)
        scroll_layout.addWidget(self.history_list)
        scroll_layout.addStretch()

        self._scroll = QScrollArea()
        self._scroll.setWidget(scroll_content)
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        panel_layout.addWidget(self._scroll)

        self._drag_hint = QLabel("Drag strip to move, edge to resize")
        self._drag_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._drag_hint.setStyleSheet("font-size: 8pt;")
        panel_layout.addWidget(self._drag_hint)

        self.main_layout.addWidget(self.panel)
        self._load_history_ui()

    def _apply_styling(self):
        from zh_en_translator.engines.themes import resolve_palette
        sys_bg = QApplication.palette().color(QApplication.palette().ColorRole.Window)
        palette = resolve_palette(
            self._config.theme if self._config else "system",
            sys_bg.lightness() < 128,
        )

        self.setStyleSheet(f"""
            QWidget {{ font-family: {_FONT_STACK}; color: {palette.text}; }}
            #sidebarPanel {{ background: {palette.bg}; border: 1px solid {palette.border}; border-radius: 0; }}
            QListWidget {{ background: transparent; border: none; outline: none; }}
            QListWidget::item {{ padding: 6px; border-bottom: 1px solid {palette.border}; }}
            QListWidget::item:selected {{ background: {palette.btn_bg}; border-radius: 6px; }}
            QPushButton {{ background: {palette.btn_bg}; border: none; border-radius: 11px; padding: 0; color: {palette.muted}; }}
            QPushButton:hover {{ background: {palette.btn_hover}; color: {palette.text}; }}
        """)

        self._title_label.setStyleSheet(
            f"color: {palette.muted}; font-size: 8pt; font-weight: bold; letter-spacing: 1px;"
        )
        self._hist_title.setStyleSheet(
            f"color: {palette.muted}; font-size: 9pt; font-weight: bold;"
        )
        self._drag_hint.setStyleSheet(f"color: {palette.muted};")

    def _setup_accessibility(self):
        self.setAccessibleName("Translation sidebar")
        self.source_label.setAccessibleName("Source text")
        self.translation_label.setAccessibleName("Translation")
        self.btn_pin.setAccessibleDescription("Keep sidebar expanded and prevent auto-collapse")
        self._close_btn.setAccessibleDescription("Close the sidebar and return to popup mode")

    def set_translation(self, source: str, translation: str):
        self.source_label.setText(source)
        self.translation_label.setText(
            _render_translation_html(translation) if not translation.startswith("⚠") else translation
        )
        self._indicator_colour = self.COLOUR_FRESH
        self._history_manager.add_entry(source, translation)
        self._load_history_ui()
        self.expand()

    def set_translation_pending(self, source: str):
        self.source_label.setText(source)
        self.translation_label.setText("Translating…")
        self._loading_timer.start()

    def update_translation(self, translation: str):
        self._loading_timer.stop()
        self.translation_label.setText(
            _render_translation_html(translation) if not translation.startswith("⚠") else translation
        )
        if not self._expanded:
            self._indicator_colour = self.COLOUR_FRESH
        self._history_manager.add_entry(self.source_label.text(), translation)
        self._load_history_ui()
        self.update()

    def _on_link_activated(self, link: str):
        if not link.startswith("word:") or not self.dictionary:
            return
        word = link[5:]
        entries = self.dictionary.lookup_english(word)
        if not entries:
            return
        tip = f"<b>{word}</b><br>" + "<br>".join(
            [f"• {e.simplified}: {', '.join(e.glosses[:2])}" for e in entries[:4]]
        )
        QToolTip.showText(QCursor.pos(), tip, self)

    def _reposition(self):
        screen = QApplication.primaryScreen().availableGeometry()
        if self._side == "left":
            x = 0 if self._expanded else -self._width + 6
        else:
            x = screen.right() - self._width if self._expanded else screen.right() - 6
        height = screen.height()
        self.setGeometry(int(x), 0, self._width, height)

    def expand(self):
        if self._expanded:
            return
        self._expanded = True
        self._indicator_colour = self.COLOUR_NEUTRAL
        self._reposition()
        self.update()

    def collapse(self):
        if self._pinned:
            return
        self._expanded = False
        self._reposition()
        self.update()

    def _on_pin_toggled(self, checked):
        self._pinned = checked

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        # Strip indicator
        strip_rect = (
            QRectF(0, 0, 6, self.height())
            if self._side == "right"
            else QRectF(self.width() - 6, 0, 6, self.height())
        )
        painter.fillRect(strip_rect, self._indicator_colour)
        painter.end()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._is_dragging_y = True
            self._drag_start_pos = event.globalPosition().toPoint()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._is_dragging_y:
            delta = event.globalPosition().toPoint().y() - self._drag_start_pos.y()
            self._y_pos += delta
            self._drag_start_pos = event.globalPosition().toPoint()
            self._reposition()

    def mouseReleaseEvent(self, event):
        self._is_dragging_y = False
        if self._config:
            self._config.sidebar_y = self._y_pos
            from zh_en_translator.config import save_config
            save_config(self._config)

    def enterEvent(self, event):
        if not self._expanded and not self._pinned:
            self.expand()
        super().enterEvent(event)

    def leaveEvent(self, event):
        if not self._pinned:
            QTimer.singleShot(300, self.collapse)
        super().leaveEvent(event)

    def close_sidebar(self):
        self.hide()
        self.closed.emit()

    def set_side(self, side: str) -> None:
        self._side = side
        self._reposition()

    def apply_config(self, cfg):
        self._config = cfg
        self._side = cfg.side
        self._width = cfg.sidebar_width
        self._apply_styling()
        self._reposition()

    def _load_history_ui(self):
        self.history_list.clear()
        for entry in self._history_manager.load_history():
            item = QListWidgetItem(f"{entry['source'][:30]}\n{entry['translation'][:30]}")
            item.setData(Qt.ItemDataRole.UserRole, entry)
            self.history_list.addItem(item)

    def _on_history_item_clicked(self, item):
        entry = item.data(Qt.ItemDataRole.UserRole)
        self.source_label.setText(entry['source'])
        self.translation_label.setText(_render_translation_html(entry['translation']))

    def _on_clear_history(self):
        self._history_manager.clear_history()
        self._load_history_ui()

    def _on_export_history(self):
        path, _ = QFileDialog.getSaveFileName(self, "Export History", "", "CSV Files (*.csv)")
        if path:
            self._history_manager.export_to_csv(path)
