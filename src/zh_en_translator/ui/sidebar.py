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
from PyQt6.QtGui import QFont, QPainter, QPainterPath, QPen, QColor
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
from zh_en_translator.ui.popup import wrap_words

logger = logging.getLogger(__name__)

_RESIZE_HANDLE_W = 6   # px — width of the inner-edge resize grab zone
_MIN_WIDTH = 180
_MAX_WIDTH = 600


class _ResizeHandle(QWidget):
    """Transparent strip at the panel's inner edge; drag it to resize the panel."""

    def __init__(self, sidebar: "TranslatorSidebar"):
        super().__init__(sidebar)
        self.setCursor(Qt.CursorShape.SizeHorCursor)
        self.setFixedWidth(_RESIZE_HANDLE_W)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)
        self.setStyleSheet("background: transparent;")
        self._drag_active = False
        self._drag_start: QPoint = QPoint()
        self._drag_start_width: int = 280

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_active = True
            self._drag_start = event.globalPosition().toPoint()
            self._drag_start_width = self.parent()._width
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._drag_active:
            sb: TranslatorSidebar = self.parent()
            delta = event.globalPosition().toPoint().x() - self._drag_start.x()
            if sb._side == "right":
                # inner edge is LEFT side — drag left = wider, drag right = narrower
                new_w = max(_MIN_WIDTH, min(_MAX_WIDTH, self._drag_start_width - delta))
            else:
                # inner edge is RIGHT side — drag right = wider, drag left = narrower
                new_w = max(_MIN_WIDTH, min(_MAX_WIDTH, self._drag_start_width + delta))
            sb._set_width(new_w)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self._drag_active:
            self._drag_active = False
            self.parent()._save_geometry_to_config()
        super().mouseReleaseEvent(event)


class TranslatorSidebar(QWidget):
    """
    Frameless panel docked to the right (or left) edge of the screen.

    Two states
    ----------
    Collapsed (default):
        Only 6 px of the window is visible at the screen edge — the "peek strip".
        The strip is painted with the indicator colour.  Click or drag it to expand
        or reposition.

    Expanded:
        The full panel slides into view.  Mouse leaving starts a 300 ms collapse
        timer (unless keep-pinned is on).

    Resizing / repositioning
    ------------------------
    • Drag the indicator strip (screen-edge side) up/down to move the panel.
    • Drag the inner edge (content-area side, shown by SizeHorCursor) to resize.

    Indicator colours
    -----------------
    COLOUR_FRESH   — cyan  — new translation arrived while collapsed
    COLOUR_IDLE    — muted rose — idle / stale
    COLOUR_NEUTRAL — grey  — viewed
    """

    # ── Signals ──────────────────────────────────────────────────────────────
    closed = pyqtSignal()  # emitted when ✕ is clicked (revert to popup mode)

    # ── Constants ────────────────────────────────────────────────────────────
    STRIP_WIDTH    = 6
    COLOUR_FRESH   = QColor("#00C9CC")
    COLOUR_IDLE    = QColor("#9E8080")
    COLOUR_NEUTRAL = QColor("#AAAAAA")

    def __init__(self, config=None):
        super().__init__()
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        # Reset widget palette — WA_TranslucentBackground corrupts the per-widget
        # palette on Windows (DWM sets Window role to black).
        self.setPalette(QApplication.palette())

        self._config = config
        self.dictionary = None  # Set by TranslatorApp
        self._history_manager = HistoryManager(get_config_path().parent / "history.json")

        if config is not None:
            if config.color_fresh:
                self.COLOUR_FRESH = QColor(config.color_fresh)
            if config.color_idle:
                self.COLOUR_IDLE = QColor(config.color_idle)

        # ── State ─────────────────────────────────────────────────────────
        self._side: str     = config.side if config is not None else "right"
        self._width: int    = getattr(config, "sidebar_width", 280) if config is not None else 280
        self._expanded: bool       = False
        self._pinned: bool         = False
        self._indicator_colour: QColor = self.COLOUR_IDLE
        self._pos_y: int    = config.sidebar_y if config is not None else 200

        # ── Drag tracking (strip drag → Y reposition) ─────────────────────
        self._drag_active: bool       = False
        self._drag_start_mouse: QPoint = QPoint()
        self._drag_start_y: int       = 0

        # ── Collapse-on-leave timer ────────────────────────────────────────
        self._leave_timer = QTimer(self)
        self._leave_timer.setSingleShot(True)
        self._leave_timer.setInterval(300)
        self._leave_timer.timeout.connect(self.collapse)

        # ── Slide animation ────────────────────────────────────────────────
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
        # Check if we are in OCR mode or normal translation mode based on title or source
        if "OCR" in self.source_label.text():
            self.translation_label.setText(f"Running OCR{dots}")
        else:
            self.translation_label.setText(f"Translating{dots}")

    # ──────────────────────────────────────────────────────────────────────────
    # UI construction
    # ──────────────────────────────────────────────────────────────────────────

    def _setup_ui(self):
        outer = QVBoxLayout()
        outer.setContentsMargins(12, 8, 12, 12)
        outer.setSpacing(4)

        # ── Header row ────────────────────────────────────────────────────
        header = QHBoxLayout()
        header.setSpacing(4)

        # Drag grip hint
        self._drag_hint = QLabel("⠿")
        self._drag_hint.setFixedSize(16, 20)
        self._drag_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._drag_hint.setToolTip("Drag to reposition; drag screen-edge strip up/down")
        self._drag_hint.setCursor(Qt.CursorShape.SizeVerCursor)
        header.addWidget(self._drag_hint)

        self._title_label = QLabel("Translation")
        title_font = QFont()
        title_font.setPointSize(9)
        self._title_label.setFont(title_font)
        header.addWidget(self._title_label)
        header.addStretch()

        self.btn_pin = QPushButton("📌")
        self.btn_pin.setFixedSize(22, 22)
        self.btn_pin.setCheckable(True)
        self.btn_pin.setChecked(False)
        self.btn_pin.setToolTip("Keep pinned (don't auto-collapse on mouse leave)")
        self.btn_pin.toggled.connect(self._on_pin_toggled)
        header.addWidget(self.btn_pin)

        self._close_btn = QPushButton("✕")
        self._close_btn.setFixedSize(22, 22)
        self._close_btn.setToolTip("Revert to popup mode")
        self._close_btn.clicked.connect(self._on_close_clicked)
        header.addWidget(self._close_btn)

        outer.addLayout(header)

        # ── Separator ─────────────────────────────────────────────────────
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("border: none; border-top: 1px solid rgba(0,0,0,0.08);")
        outer.addWidget(sep)

        # ── Scroll area ───────────────────────────────────────────────────
        scroll_content = QWidget()
        scroll_content.setStyleSheet("background: transparent;")
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setContentsMargins(0, 4, 0, 4)
        scroll_layout.setSpacing(6)

        self.source_label = QLabel("")
        self.source_label.setWordWrap(True)
        src_font = QFont()
        src_font.setPointSize(10)
        self.source_label.setFont(src_font)
        self.source_label.setStyleSheet("background: transparent;")
        scroll_layout.addWidget(self.source_label)

        self.translation_label = QLabel("")
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
        trans_font = QFont()
        trans_font.setPointSize(12)
        self.translation_label.setFont(trans_font)
        self.translation_label.setStyleSheet("background: transparent;")
        scroll_layout.addWidget(self.translation_label)
        
        # ── History Section ──────────────────────────────────────────────
        hist_header = QHBoxLayout()
        hist_header.setContentsMargins(0, 10, 0, 0)
        hist_header.setSpacing(4)
        
        self._hist_title = QLabel("History")
        hist_font = QFont()
        hist_font.setPointSize(9)
        hist_font.setBold(True)
        self._hist_title.setFont(hist_font)
        hist_header.addWidget(self._hist_title)
        hist_header.addStretch()
        
        self.btn_clear = QPushButton("🗑")
        self.btn_clear.setFixedSize(22, 22)
        self.btn_clear.setToolTip("Clear History")
        self.btn_clear.clicked.connect(self._on_clear_history)
        hist_header.addWidget(self.btn_clear)
        
        self.btn_export = QPushButton("📤")
        self.btn_export.setFixedSize(22, 22)
        self.btn_export.setToolTip("Export History to CSV")
        self.btn_export.clicked.connect(self._on_export_history)
        hist_header.addWidget(self.btn_export)
        
        scroll_layout.addLayout(hist_header)
        
        self.history_list = QListWidget()
        self.history_list.setMinimumHeight(200)
        self.history_list.itemClicked.connect(self._on_history_item_clicked)
        # Ensure it doesn't have its own scrollbar to avoid nested scrolling issues
        self.history_list.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.history_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_layout.addWidget(self.history_list)

        scroll_layout.addStretch()

        self._scroll = QScrollArea()
        ...
        self._load_history_ui()
        self._scroll.setWidget(scroll_content)
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setStyleSheet("background: transparent;")
        outer.addWidget(self._scroll, 1)

        self.setLayout(outer)
        self.setFixedWidth(self._width)
        self.setMinimumHeight(160)

        # Resize handle — transparent widget at the inner edge, hidden when collapsed
        self._resize_handle = _ResizeHandle(self)
        self._resize_handle.hide()

    def _set_width(self, new_width: int) -> None:
        """Update panel width and reposition."""
        self._width = new_width
        self.setFixedWidth(new_width)
        self._reposition()
        self._position_resize_handle()

    def _position_resize_handle(self) -> None:
        h = max(1, self.height())
        self._resize_handle.setFixedHeight(h)
        if self._side == "right":
            self._resize_handle.move(0, 0)
        else:
            self._resize_handle.move(self._width - _RESIZE_HANDLE_W, 0)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._position_resize_handle()

    # ──────────────────────────────────────────────────────────────────────────
    # Theme / styling
    # ──────────────────────────────────────────────────────────────────────────

    def _effective_bg(self) -> QColor:
        if self._config and getattr(self._config, "bg_color", None):
            return QColor(self._config.bg_color)
        if self._config and getattr(self._config, "theme", "system") != "system":
            from zh_en_translator.engines.themes import THEMES
            palette = THEMES.get(self._config.theme)
            if palette:
                return QColor(palette.bg)
        app_bg = QApplication.palette().color(self.backgroundRole())
        if app_bg.lightness() < 10:
            return QColor(248, 248, 248)
        return app_bg

    def _apply_styling(self) -> None:
        from zh_en_translator.engines.themes import resolve_palette

        sys_bg = QApplication.palette().color(self.backgroundRole())
        system_is_dark = sys_bg.lightness() < 128
        theme = getattr(self._config, "theme", "system") if self._config else "system"
        theme_palette = resolve_palette(theme, system_is_dark)

        if self._config and getattr(self._config, "bg_color", None):
            bg = QColor(self._config.bg_color)
            is_dark = bg.lightness() < 128
            theme_palette = resolve_palette("dark" if is_dark else "light", system_is_dark)
        else:
            bg = self._effective_bg()
            is_dark = bg.lightness() < 128
            if is_dark != (theme_palette.text == "#E8E8E8"):
                theme_palette = resolve_palette("dark" if is_dark else "light", system_is_dark)

        text_color   = theme_palette.text
        muted_color  = theme_palette.muted
        btn_hover    = theme_palette.btn_hover
        border_color = getattr(theme_palette, "border", "rgba(0,0,0,0.1)")

        unified_css = f"""
            QLabel {{
                background: transparent;
                color: {text_color};
            }}
            QPushButton {{
                background: transparent;
                border: none;
                border-radius: 5px;
                font-size: 11pt;
                color: {muted_color};
                padding: 1px;
            }}
            QPushButton:checked {{
                background: rgba(0,160,255,0.15);
                border: 1px solid rgba(0,160,255,0.4);
                color: {text_color};
            }}
            QPushButton:hover {{
                background: {btn_hover};
                color: {text_color};
            }}
            QListWidget {{
                background: transparent;
                border: none;
                color: {text_color};
                outline: none;
            }}
            QListWidget::item {{
                background: transparent;
                color: {text_color};
                padding: 6px;
                border-bottom: 1px solid {border_color};
            }}
            QListWidget::item:selected {{
                background: {btn_hover};
                color: {text_color};
                border-radius: 4px;
            }}
            QMenu {{
                background: {theme_palette.bg};
                color: {text_color};
                padding: 4px;
                border: 1px solid {border_color};
                border-radius: 6px;
            }}
            QMenu::item:selected {{
                background: {btn_hover};
                border-radius: 3px;
            }}
            QMenu::separator {{
                background: {border_color};
                height: 1px;
                margin: 2px 4px;
            }}
        """
        self.setStyleSheet(unified_css)

        self._title_label.setStyleSheet(
            f"color: {muted_color}; background: transparent; font-weight: 600;"
        )
        self._hist_title.setStyleSheet(
            f"color: {muted_color}; background: transparent; font-weight: 600; margin-top: 10px;"
        )
        self._drag_hint.setStyleSheet(
            f"color: {muted_color}; background: transparent;"
        )
        self.source_label.setStyleSheet(
            f"QLabel {{ font-size: 10pt; color: {muted_color}; background: transparent; }}"
        )
        self.translation_label.setStyleSheet(
            f"QLabel {{ background: transparent; color: {text_color}; padding: 2px 0; }}"
        )
        self.btn_pin.setStyleSheet(
            f"QPushButton {{ background: transparent; border: none;"
            f" border-radius: 5px; font-size: 11pt; color: {muted_color}; padding: 1px; }}"
            f"QPushButton:checked {{ background: rgba(0,160,255,0.15);"
            f" border: 1px solid rgba(0,160,255,0.4); color: {text_color}; }}"
            f"QPushButton:hover {{ background: {btn_hover}; color: {text_color}; }}"
        )
        self._close_btn.setStyleSheet(
            f"QPushButton {{ background: transparent; border: none;"
            f" border-radius: 5px; color: {muted_color}; font-size: 11pt; padding: 1px; }}"
            f"QPushButton:hover {{ background: {btn_hover}; color: {text_color}; }}"
        )
        self.btn_clear.setStyleSheet(
            f"QPushButton {{ background: transparent; border: none;"
            f" border-radius: 5px; color: {muted_color}; font-size: 11pt; padding: 1px; }}"
            f"QPushButton:hover {{ background: {btn_hover}; color: {text_color}; }}"
        )
        self.btn_export.setStyleSheet(
            f"QPushButton {{ background: transparent; border: none;"
            f" border-radius: 5px; color: {muted_color}; font-size: 11pt; padding: 1px; }}"
            f"QPushButton:hover {{ background: {btn_hover}; color: {text_color}; }}"
        )

    def _setup_accessibility(self) -> None:
        self.setAccessibleName("Translation sidebar")
        self.source_label.setAccessibleName("Source text")
        self.translation_label.setAccessibleName("Translation")
        self.btn_pin.setAccessibleDescription("Keep the sidebar expanded")
        self._close_btn.setAccessibleDescription("Close sidebar and return to popup mode")

    # ──────────────────────────────────────────────────────────────────────────
    # Public API
    # ──────────────────────────────────────────────────────────────────────────

    def set_translation(self, source: str, translation: str) -> None:
        self.source_label.setText(source)
        if not translation.startswith("Running OCR") and not translation.startswith("⚠"):
            self.translation_label.setText(wrap_words(translation))
        else:
            self.translation_label.setText(translation)
        self._indicator_colour = self.COLOUR_FRESH
        self.update()
        self.expand()
        
        # Save to history
        self._history_manager.add_entry(source, translation)
        self._load_history_ui()

    def set_translation_pending(self, source: str) -> None:
        self.source_label.setText(source)
        self.translation_label.setText("Translating…")
        self._indicator_colour = self.COLOUR_IDLE
        self.update()

    def update_translation(self, translation: str) -> None:
        if not translation.startswith("Running OCR") and not translation.startswith("⚠") and translation != "Translating…":
            self.translation_label.setText(wrap_words(translation))
        else:
            self.translation_label.setText(translation)
            
        if not self._expanded:
            self._indicator_colour = self.COLOUR_FRESH
            self.update()

        # Save to history
        source = self.source_label.text()
        if source and translation and not translation.startswith("Running OCR") and translation != "Translating…":
            self._history_manager.add_entry(source, translation)
            self._load_history_ui()

    def _on_link_activated(self, link: str):
        """Handle clicking on a wrapped English word."""
        if not link.startswith("word:"):
            return
        word = link[5:]
        if not self.dictionary:
            return
        
        from PyQt6.QtGui import QCursor
        entries = self.dictionary.lookup_english(word)
        if not entries:
            QToolTip.showText(QCursor.pos(), f"No dictionary entries found for '{word}'", self)
            return

        # Format tooltip content
        tip_lines = [f"<b>{word}</b>"]
        for entry in entries[:5]:  # Limit to 5 entries
            tip_lines.append(f"• {entry.simplified} ({entry.pinyin}): {', '.join(entry.glosses[:3])}")
        
        QToolTip.showText(QCursor.pos(), "<br>".join(tip_lines), self)

    def set_side(self, side: str) -> None:
        if side not in ("left", "right"):
            return
        self._side = side
        self._reposition()
        self._position_resize_handle()

    def apply_config(self, config) -> None:
        old_bg    = getattr(self._config, "bg_color", None) if self._config else None
        old_theme = getattr(self._config, "theme", "system") if self._config else "system"
        self._config = config

        was_fresh = (self._indicator_colour == self.COLOUR_FRESH)
        was_idle  = (self._indicator_colour == self.COLOUR_IDLE)

        if config.color_fresh:
            self.COLOUR_FRESH = QColor(config.color_fresh)
        if config.color_idle:
            self.COLOUR_IDLE = QColor(config.color_idle)

        if was_fresh:
            self._indicator_colour = self.COLOUR_FRESH
        elif was_idle:
            self._indicator_colour = self.COLOUR_IDLE

        new_width = getattr(config, "sidebar_width", self._width)
        if new_width != self._width:
            self._set_width(new_width)

        self._pos_y = config.sidebar_y
        self.set_side(config.side)

        new_theme = getattr(config, "theme", "system")
        if getattr(config, "bg_color", None) != old_bg or new_theme != old_theme:
            self._apply_styling()

        self.update()

    def expand(self) -> None:
        if self._expanded:
            return
        self._expanded = True
        self._indicator_colour = self.COLOUR_NEUTRAL
        self.update()
        self._resize_handle.show()
        self._position_resize_handle()
        self._animate_to(self._expanded_x())

    def collapse(self) -> None:
        if not self._expanded:
            return
        self._expanded = False
        self._resize_handle.hide()
        self._animate_to(self._collapsed_x())

    # ──────────────────────────────────────────────────────────────────────────
    # Positioning helpers
    # ──────────────────────────────────────────────────────────────────────────

    def _screen_geometry(self):
        app = QApplication.instance()
        if not app:
            return None
        screen = app.primaryScreen()
        if not screen:
            return None
        return screen.availableGeometry()

    def _collapsed_x(self) -> int:
        geom = self._screen_geometry()
        if geom is None:
            return -(self._width - self.STRIP_WIDTH)
        if self._side == "right":
            return geom.right() - self.STRIP_WIDTH
        else:
            return geom.left() - (self._width - self.STRIP_WIDTH)

    def _expanded_x(self) -> int:
        geom = self._screen_geometry()
        if geom is None:
            return 0
        if self._side == "right":
            return geom.right() - self._width
        else:
            return geom.left()

    def _reposition(self) -> None:
        x = self._expanded_x() if self._expanded else self._collapsed_x()
        geom = self._screen_geometry()
        if geom is not None:
            max_y = geom.bottom() - self.height()
            self._pos_y = max(geom.top(), min(self._pos_y, max_y))
        self.move(x, self._pos_y)

    def _animate_to(self, target_x: int) -> None:
        from PyQt6.QtCore import QAbstractAnimation, QPoint as _QPoint
        if self._animation.state() == QAbstractAnimation.State.Running:
            self._animation.stop()
        self._animation.setStartValue(_QPoint(self.pos().x(), self._pos_y))
        self._animation.setEndValue(_QPoint(target_x, self._pos_y))
        self._animation.start()

    def _save_geometry_to_config(self) -> None:
        if self._config is None:
            return
        self._config.sidebar_y     = self._pos_y
        self._config.sidebar_width = self._width
        from zh_en_translator.config import save_config
        try:
            save_config(self._config)
        except Exception as e:
            logger.warning("Failed to save sidebar geometry: %s", e)

    # ──────────────────────────────────────────────────────────────────────────
    # Mouse events — strip drag (Y reposition) for both states
    # ──────────────────────────────────────────────────────────────────────────

    def _is_on_strip(self, pos: QPoint) -> bool:
        """Visible 6-px strip when collapsed."""
        if self._side == "right":
            return pos.x() <= self.STRIP_WIDTH
        else:
            return pos.x() >= self._width - self.STRIP_WIDTH

    def _is_on_expanded_strip(self, pos: QPoint) -> bool:
        """Screen-edge strip when expanded."""
        if self._side == "right":
            return pos.x() >= self._width - self.STRIP_WIDTH
        else:
            return pos.x() <= self.STRIP_WIDTH

    def _is_on_drag_grip(self, pos: QPoint) -> bool:
        """True when the cursor is over the drag-grip icon in the header."""
        return self._drag_hint.geometry().contains(pos)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            pos = event.pos()
            on_strip = (
                self._is_on_expanded_strip(pos) if self._expanded
                else self._is_on_strip(pos)
            )
            if on_strip or (self._expanded and self._is_on_drag_grip(pos)):
                self._drag_active = True
                self._drag_start_mouse = event.globalPosition().toPoint()
                self._drag_start_y = self._pos_y
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._drag_active:
            delta_y = event.globalPosition().toPoint().y() - self._drag_start_mouse.y()
            new_y = self._drag_start_y + delta_y
            geom = self._screen_geometry()
            if geom is not None:
                max_y = geom.bottom() - self.height()
                new_y = max(geom.top(), min(new_y, max_y))
            self._pos_y = new_y
            self.move(self.x(), new_y)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self._drag_active:
            self._drag_active = False
            delta = (event.globalPosition().toPoint() - self._drag_start_mouse).manhattanLength()
            if delta < 6 and not self._expanded:
                self.expand()
            else:
                self._save_geometry_to_config()
        super().mouseReleaseEvent(event)

    # ──────────────────────────────────────────────────────────────────────────
    # Mouse leave → auto-collapse
    # ──────────────────────────────────────────────────────────────────────────

    def enterEvent(self, event):
        self._leave_timer.stop()
        super().enterEvent(event)

    def leaveEvent(self, event):
        if self._expanded and not self._pinned:
            self._leave_timer.start()
        super().leaveEvent(event)

    # ──────────────────────────────────────────────────────────────────────────
    # Paint
    # ──────────────────────────────────────────────────────────────────────────

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)

        path = QPainterPath()
        path.addRoundedRect(rect, 12, 12)
        bg = self._effective_bg()
        painter.fillPath(path, bg)
        is_dark = bg.lightness() < 128
        border = QColor(255, 255, 255, 25) if is_dark else QColor(0, 0, 0, 30)
        painter.setPen(QPen(border, 1))
        painter.drawPath(path)

        # Indicator strip — on screen-edge side in both states
        if self._expanded:
            if self._side == "right":
                strip_rect = QRectF(
                    self._width - self.STRIP_WIDTH, 0, self.STRIP_WIDTH, self.height()
                )
            else:
                strip_rect = QRectF(0, 0, self.STRIP_WIDTH, self.height())
        else:
            if self._side == "right":
                strip_rect = QRectF(0, 0, self.STRIP_WIDTH, self.height())
            else:
                strip_rect = QRectF(
                    self._width - self.STRIP_WIDTH, 0, self.STRIP_WIDTH, self.height()
                )

        strip_path = QPainterPath()
        strip_path.addRoundedRect(strip_rect, 4, 4)
        painter.fillPath(strip_path, self._indicator_colour)

        painter.end()

    # ──────────────────────────────────────────────────────────────────────────
    # Internal slots
    # ──────────────────────────────────────────────────────────────────────────

    def _on_pin_toggled(self, checked: bool) -> None:
        self._pinned = checked
        if checked:
            self._leave_timer.stop()

    def _on_close_clicked(self) -> None:
        self.collapse()
        self.hide()
        self.closed.emit()

    # ──────────────────────────────────────────────────────────────────────────
    # History slots
    # ──────────────────────────────────────────────────────────────────────────

    def _load_history_ui(self) -> None:
        """Clear and repopulate the history QListWidget."""
        self.history_list.clear()
        history = self._history_manager.load_history()
        for entry in history:
            item = QListWidgetItem()
            # Create a compact preview: Source \n Translation (truncated)
            src = entry["source"].replace("\n", " ").strip()
            trans = entry["translation"].replace("\n", " ").strip()
            
            if len(src) > 40:
                src = src[:37] + "..."
            if len(trans) > 40:
                trans = trans[:37] + "..."
                
            item.setText(f"{src}\n{trans}")
            item.setData(Qt.ItemDataRole.UserRole, entry)
            
            # Subtle tool tip with full text
            item.setToolTip(f"{entry['source']}\n\n{entry['translation']}")
            self.history_list.addItem(item)

    def _on_history_item_clicked(self, item: QListWidgetItem) -> None:
        """Restore a history item to the main labels."""
        entry = item.data(Qt.ItemDataRole.UserRole)
        if entry:
            self.source_label.setText(entry["source"])
            self.translation_label.setText(entry["translation"])
            # Visual feedback that this is an "old" translation
            self._indicator_colour = self.COLOUR_NEUTRAL
            self.update()

    def _on_clear_history(self) -> None:
        """Wipe history and update UI."""
        self._history_manager.clear_history()
        self._load_history_ui()

    def _on_export_history(self) -> None:
        """Prompt user for a CSV location and export."""
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Translation History",
            "translations_export.csv",
            "CSV Files (*.csv);;All Files (*)"
        )
        if path:
            from pathlib import Path as _Path
            self._history_manager.export_to_csv(_Path(path))
