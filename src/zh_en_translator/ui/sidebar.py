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
        # Reset widget palette from app palette — WA_TranslucentBackground
        # corrupts the per-widget palette on Windows (DWM sets Window role to
        # black), making text invisible in child widgets.
        self.setPalette(QApplication.palette())

        self._config = config

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
        self._apply_styling()
        self._setup_accessibility()
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

        self._title_label = QLabel("Translation")
        title_font = QFont()
        title_font.setPointSize(9)
        self._title_label.setFont(title_font)
        header.addWidget(self._title_label)
        header.addStretch()

        # Pin button
        self.btn_pin = QPushButton("📌")
        self.btn_pin.setFixedSize(24, 24)
        self.btn_pin.setCheckable(True)
        self.btn_pin.setChecked(False)
        self.btn_pin.setToolTip("Keep pinned (don't auto-collapse on mouse leave)")
        self.btn_pin.toggled.connect(self._on_pin_toggled)
        header.addWidget(self.btn_pin)

        # Close button
        self._close_btn = QPushButton("✕")
        self._close_btn.setFixedSize(22, 22)
        self._close_btn.setToolTip("Revert to popup mode")
        self._close_btn.clicked.connect(self._on_close_clicked)
        header.addWidget(self._close_btn)

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
        self.source_label.setStyleSheet("background: transparent;")
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
        self.translation_label.setStyleSheet("background: transparent;")
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

    def _effective_bg(self) -> QColor:
        """Safe background colour — immune to WA_TranslucentBackground palette corruption."""
        if self._config and getattr(self._config, "bg_color", None):
            return QColor(self._config.bg_color)
        if self._config and getattr(self._config, "theme", "system") != "system":
            from zh_en_translator.engines.themes import THEMES
            palette = THEMES.get(self._config.theme)
            if palette:
                return QColor(palette.bg)
        app_bg = QApplication.palette().color(self.backgroundRole())
        # Lightness < 10 almost certainly means the palette was corrupted to
        # transparent-black by DWM after WA_TranslucentBackground was set.
        if app_bg.lightness() < 10:
            return QColor(248, 248, 248)
        return app_bg

    def _apply_styling(self) -> None:
        """Set child-widget stylesheets using explicit colours (no palette() tokens).

        palette(text) / palette(mid) resolve from the per-widget palette which
        WA_TranslucentBackground can corrupt on Windows — making all text
        invisible.  Computing colours once from the resolved theme palette and
        baking them as hex strings avoids the problem.
        """
        from zh_en_translator.engines.themes import resolve_palette

        sys_bg = QApplication.palette().color(self.backgroundRole())
        system_is_dark = sys_bg.lightness() < 128

        theme = getattr(self._config, "theme", "system") if self._config else "system"
        theme_palette = resolve_palette(theme, system_is_dark)

        # bg_color override: re-resolve palette based on override bg's darkness
        if self._config and getattr(self._config, "bg_color", None):
            from PyQt6.QtGui import QColor as _QColor
            bg = _QColor(self._config.bg_color)
            is_dark = bg.lightness() < 128
            theme_palette = resolve_palette("dark" if is_dark else "light", system_is_dark)
        else:
            bg = self._effective_bg()
            is_dark = bg.lightness() < 128
            if is_dark != (theme_palette.text == "#E8E8E8"):
                theme_palette = resolve_palette("dark" if is_dark else "light", system_is_dark)

        text_color  = theme_palette.text
        muted_color = theme_palette.muted
        btn_hover   = theme_palette.btn_hover

        self._title_label.setStyleSheet(
            f"color: {muted_color}; background: transparent;"
        )
        self.source_label.setStyleSheet(
            f"QLabel {{ font-size: 10pt; color: {muted_color}; background: transparent; }}"
        )
        self.translation_label.setStyleSheet(
            f"QLabel {{ background: transparent; color: {text_color}; padding: 2px 0; }}"
        )
        self.btn_pin.setStyleSheet(
            f"QPushButton {{ background: transparent; border: 1px solid transparent;"
            f" border-radius: 4px; font-size: 11pt; color: {muted_color}; }}"
            f"QPushButton:checked {{ background: rgba(0,160,255,0.15);"
            f" border: 1px solid rgba(0,160,255,0.5); color: {text_color}; }}"
            f"QPushButton:hover {{ background: {btn_hover}; }}"
        )
        self._close_btn.setStyleSheet(
            f"QPushButton {{ background: transparent; border: none;"
            f" color: {muted_color}; font-size: 11pt; }}"
            f"QPushButton:hover {{ color: {text_color}; }}"
        )

    def _setup_accessibility(self) -> None:
        """Set accessible names and descriptions for screen readers."""
        self.setAccessibleName("Translation sidebar")

        self.source_label.setAccessibleName("Source text")

        self.translation_label.setAccessibleName("Translation")

        self.btn_pin.setAccessibleDescription("Keep the sidebar expanded")

        self._close_btn.setAccessibleDescription(
            "Close sidebar and return to popup mode"
        )

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
        old_bg = getattr(self._config, "bg_color", None) if self._config else None
        old_theme = getattr(self._config, "theme", "system") if self._config else "system"
        self._config = config

        # Compare against OLD colors before updating, then re-point indicator
        was_fresh = (self._indicator_colour == self.COLOUR_FRESH)
        was_idle = (self._indicator_colour == self.COLOUR_IDLE)

        if config.color_fresh:
            self.COLOUR_FRESH = QColor(config.color_fresh)
        if config.color_idle:
            self.COLOUR_IDLE = QColor(config.color_idle)

        if was_fresh:
            self._indicator_colour = self.COLOUR_FRESH
        elif was_idle:
            self._indicator_colour = self.COLOUR_IDLE

        self._pos_y = config.sidebar_y
        self.set_side(config.side)

        # Re-apply text colours if bg or theme changed (or on first apply)
        new_theme = getattr(config, "theme", "system")
        if getattr(config, "bg_color", None) != old_bg or new_theme != old_theme:
            self._apply_styling()

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
        """True when the cursor is within the visible 6px strip (collapsed only)."""
        # When collapsed, the window is mostly off-screen:
        #   right side → window pushed RIGHT, leftmost 6px visible at screen edge
        #   left side  → window pushed LEFT, rightmost 6px visible at screen edge
        if self._side == "right":
            return local_pos.x() <= self.STRIP_WIDTH
        else:
            return local_pos.x() >= self.WIDTH - self.STRIP_WIDTH

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

        path = QPainterPath()
        path.addRoundedRect(rect, 10, 10)
        bg = self._effective_bg()
        painter.fillPath(path, bg)
        is_dark = bg.lightness() < 128
        border = QColor(255, 255, 255, 30) if is_dark else QColor(0, 0, 0, 40)
        painter.setPen(QPen(border, 1))
        painter.drawPath(path)

        # Indicator strip — position depends on which edge is actually visible.
        # Collapsed: window is mostly off-screen, visible edge is opposite to
        #            what you'd expect from the side name.
        #   right collapsed → leftmost STRIP_WIDTH px are on-screen
        #   left  collapsed → rightmost STRIP_WIDTH px are on-screen
        # Expanded: full panel visible; strip sits at the screen-edge side.
        #   right expanded  → rightmost STRIP_WIDTH px (near screen-right edge)
        #   left  expanded  → leftmost  STRIP_WIDTH px (near screen-left edge)
        if self._expanded:
            if self._side == "right":
                strip_rect = QRectF(
                    self.WIDTH - self.STRIP_WIDTH, 0, self.STRIP_WIDTH, self.height()
                )
            else:
                strip_rect = QRectF(0, 0, self.STRIP_WIDTH, self.height())
        else:
            if self._side == "right":
                strip_rect = QRectF(0, 0, self.STRIP_WIDTH, self.height())
            else:
                strip_rect = QRectF(
                    self.WIDTH - self.STRIP_WIDTH, 0, self.STRIP_WIDTH, self.height()
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
