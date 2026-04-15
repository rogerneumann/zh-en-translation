"""Persistent sidebar widget — M5 peek-tab style, docked to a screen edge."""

from __future__ import annotations

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
)


class TranslatorSidebar(QWidget):
    """
    Frameless panel docked to the right (or left) edge of the screen.

    Two states
    ----------
    Collapsed (default):
        Only 6 px of the window is visible at the screen edge — the "peek strip".
        The strip is painted with the indicator colour.  Clicking it expands.

    Expanded:
        The full 280 px panel slides into view.  Mouse leaving the panel
        starts a 300 ms timer that collapses it (unless keep-pinned is on).

    Indicator colours
    -----------------
    COLOUR_FRESH   — cyan  — new translation arrived while collapsed
    COLOUR_IDLE    — muted rose — idle / stale
    COLOUR_NEUTRAL — grey  — viewed
    """

    # ── Signals ──────────────────────────────────────────────────────────────
    closed = pyqtSignal()  # emitted when ✕ is clicked (revert to popup mode)

    # ── Constants ────────────────────────────────────────────────────────────
    WIDTH = 280
    STRIP_WIDTH = 6
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

        # Apply config-driven color overrides before using them
        if config is not None:
            if config.color_fresh:
                self.COLOUR_FRESH = QColor(config.color_fresh)
            if config.color_idle:
                self.COLOUR_IDLE = QColor(config.color_idle)

        # ── State ─────────────────────────────────────────────────────────
        self._side: str = config.side if config is not None else "right"
        self._expanded: bool = False
        self._pinned: bool = False         # keep-pinned toggle
        self._indicator_colour: QColor = self.COLOUR_IDLE
        self._pos_y: int = config.sidebar_y if config is not None else 200

        # ── Drag tracking ─────────────────────────────────────────────────
        self._drag_active: bool = False
        self._drag_start_mouse: QPoint = QPoint()
        self._drag_start_y: int = 0

        # ── Collapse-on-leave timer ────────────────────────────────────────
        self._leave_timer = QTimer(self)
        self._leave_timer.setSingleShot(True)
        self._leave_timer.setInterval(300)
        self._leave_timer.timeout.connect(self.collapse)

        # ── Animation ─────────────────────────────────────────────────────
        self._animation = QPropertyAnimation(self, b"pos")
        self._animation.setDuration(200)
        self._animation.setEasingCurve(QEasingCurve.Type.OutCubic)

        self._setup_ui()
        self._reposition()

    # ──────────────────────────────────────────────────────────────────────────
    # UI construction
    # ──────────────────────────────────────────────────────────────────────────

    def _setup_ui(self):
        outer = QVBoxLayout()
        outer.setContentsMargins(12, 10, 12, 12)
        outer.setSpacing(6)

        # ── Header row ────────────────────────────────────────────────────
        header = QHBoxLayout()
        header.setSpacing(4)

        title = QLabel("Translation")
        title_font = QFont()
        title_font.setPointSize(9)
        title.setFont(title_font)
        title.setStyleSheet("color: palette(mid); background: transparent;")
        header.addWidget(title)
        header.addStretch()

        # Pin button
        self.btn_pin = QPushButton("📌")
        self.btn_pin.setFixedSize(24, 24)
        self.btn_pin.setCheckable(True)
        self.btn_pin.setChecked(False)
        self.btn_pin.setToolTip("Keep pinned (don't auto-collapse on mouse leave)")
        self.btn_pin.setStyleSheet(
            "QPushButton { background: transparent; border: none;"
            " font-size: 11pt; opacity: 0.5; }"
            "QPushButton:checked { opacity: 1.0; }"
            "QPushButton:hover { background: rgba(0,0,0,0.06); border-radius: 4px; }"
        )
        self.btn_pin.toggled.connect(self._on_pin_toggled)
        header.addWidget(self.btn_pin)

        # Close button
        close_btn = QPushButton("✕")
        close_btn.setFixedSize(22, 22)
        close_btn.setToolTip("Revert to popup mode")
        close_btn.setStyleSheet(
            "QPushButton { background: transparent; border: none;"
            " color: palette(mid); font-size: 11pt; }"
            "QPushButton:hover { color: palette(text); }"
        )
        close_btn.clicked.connect(self._on_close_clicked)
        header.addWidget(close_btn)

        outer.addLayout(header)

        # ── Separator ─────────────────────────────────────────────────────
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("border: none; border-top: 1px solid rgba(0,0,0,0.10);")
        outer.addWidget(sep)

        # ── Scroll area wrapping source + translation ─────────────────────
        scroll_content = QWidget()
        scroll_content.setStyleSheet("background: transparent;")
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setContentsMargins(0, 4, 0, 4)
        scroll_layout.setSpacing(8)

        # Source text (small, muted)
        self.source_label = QLabel("")
        self.source_label.setWordWrap(True)
        src_font = QFont()
        src_font.setPointSize(10)
        self.source_label.setFont(src_font)
        self.source_label.setStyleSheet(
            "QLabel { font-size: 10pt; color: palette(mid); background: transparent; }"
        )
        scroll_layout.addWidget(self.source_label)

        # Translation (main content, selectable)
        self.translation_label = QLabel("")
        self.translation_label.setWordWrap(True)
        self.translation_label.setAlignment(
            Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft
        )
        self.translation_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
            | Qt.TextInteractionFlag.TextSelectableByKeyboard
        )
        trans_font = QFont()
        trans_font.setPointSize(12)
        self.translation_label.setFont(trans_font)
        self.translation_label.setStyleSheet(
            "QLabel { background: transparent; color: palette(text); padding: 2px 0; }"
        )
        scroll_layout.addWidget(self.translation_label)
        scroll_layout.addStretch()

        self._scroll = QScrollArea()
        self._scroll.setWidget(scroll_content)
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setStyleSheet("background: transparent;")
        outer.addWidget(self._scroll, 1)

        self.setLayout(outer)
        self.setFixedWidth(self.WIDTH)
        self.setMinimumHeight(160)

    # ──────────────────────────────────────────────────────────────────────────
    # Public API
    # ──────────────────────────────────────────────────────────────────────────

    def set_translation(self, source: str, translation: str) -> None:
        """Set content, mark as fresh, expand the panel."""
        self.source_label.setText(source)
        self.translation_label.setText(translation)
        self._indicator_colour = self.COLOUR_FRESH
        self.update()
        self.expand()

    def set_translation_pending(self, source: str) -> None:
        """Show source text with 'Translating…' placeholder; mark as pending."""
        self.source_label.setText(source)
        self.translation_label.setText("Translating…")
        self._indicator_colour = self.COLOUR_IDLE
        self.update()

    def update_translation(self, translation: str) -> None:
        """Update translation text; mark as fresh if collapsed."""
        self.translation_label.setText(translation)
        if not self._expanded:
            self._indicator_colour = self.COLOUR_FRESH
            self.update()

    def set_side(self, side: str) -> None:
        """'left' or 'right' — repositions the window."""
        if side not in ("left", "right"):
            return
        self._side = side
        self._reposition()

    def apply_config(self, config) -> None:
        """Apply a Config object: update colors, side, and Y position."""
        if config.color_fresh:
            self.COLOUR_FRESH = QColor(config.color_fresh)
        if config.color_idle:
            self.COLOUR_IDLE = QColor(config.color_idle)
        # Update indicator color to reflect new palette
        if self._indicator_colour == self.COLOUR_FRESH:
            self._indicator_colour = self.COLOUR_FRESH
        elif self._indicator_colour == self.COLOUR_IDLE:
            self._indicator_colour = self.COLOUR_IDLE
        self._pos_y = config.sidebar_y
        self.set_side(config.side)
        self.update()

    def expand(self) -> None:
        """Animate to expanded state."""
        if self._expanded:
            return
        self._expanded = True
        self._indicator_colour = self.COLOUR_NEUTRAL
        self.update()
        self._animate_to(self._expanded_x())

    def collapse(self) -> None:
        """Animate to collapsed state."""
        if not self._expanded:
            return
        self._expanded = False
        self._animate_to(self._collapsed_x())

    # ──────────────────────────────────────────────────────────────────────────
    # Positioning helpers
    # ──────────────────────────────────────────────────────────────────────────

    def _screen_geometry(self):
        """Return available screen geometry, or None in headless CI."""
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
            return -274 if self._side == "right" else -274
        if self._side == "right":
            return geom.right() - self.STRIP_WIDTH
        else:
            return geom.left() - (self.WIDTH - self.STRIP_WIDTH)

    def _expanded_x(self) -> int:
        geom = self._screen_geometry()
        if geom is None:
            return 0
        if self._side == "right":
            return geom.right() - self.WIDTH
        else:
            return geom.left()

    def _reposition(self) -> None:
        """Snap window to current state position without animation."""
        x = self._expanded_x() if self._expanded else self._collapsed_x()
        geom = self._screen_geometry()
        if geom is not None:
            # Clamp Y
            max_y = geom.bottom() - self.height()
            self._pos_y = max(geom.top(), min(self._pos_y, max_y))
        self.move(x, self._pos_y)

    def _animate_to(self, target_x: int) -> None:
        """Animate horizontal position to target_x."""
        from PyQt6.QtCore import QAbstractAnimation
        if self._animation.state() == QAbstractAnimation.State.Running:
            self._animation.stop()
        start = self.pos()
        from PyQt6.QtCore import QPoint as _QPoint
        self._animation.setStartValue(_QPoint(start.x(), self._pos_y))
        self._animation.setEndValue(_QPoint(target_x, self._pos_y))
        self._animation.start()

    # ──────────────────────────────────────────────────────────────────────────
    # Mouse events: click-to-expand on strip, drag up/down
    # ──────────────────────────────────────────────────────────────────────────

    def _is_on_strip(self, local_pos: QPoint) -> bool:
        """True when the cursor is within the visible 6px strip."""
        if self._side == "right":
            # Strip is the rightmost STRIP_WIDTH pixels
            return local_pos.x() >= self.WIDTH - self.STRIP_WIDTH
        else:
            # Strip is the leftmost STRIP_WIDTH pixels
            return local_pos.x() <= self.STRIP_WIDTH

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            if not self._expanded and self._is_on_strip(event.pos()):
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
            # If the mouse didn't move much, treat it as a click → expand
            delta = (event.globalPosition().toPoint() - self._drag_start_mouse).manhattanLength()
            if delta < 6:
                self.expand()
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

        # Rounded-rect background (same pattern as popup.py)
        path = QPainterPath()
        path.addRoundedRect(rect, 10, 10)
        bg = self.palette().color(self.backgroundRole())
        painter.fillPath(path, bg)
        painter.setPen(QPen(QColor(0, 0, 0, 40), 1))
        painter.drawPath(path)

        # Indicator strip
        if self._side == "right":
            strip_rect = QRectF(
                self.WIDTH - self.STRIP_WIDTH, 0,
                self.STRIP_WIDTH, self.height()
            )
        else:
            strip_rect = QRectF(0, 0, self.STRIP_WIDTH, self.height())

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
