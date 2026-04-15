"""Persistent sidebar widget — pinned to the right edge of the screen."""

from PyQt6.QtCore import Qt, QRectF
from PyQt6.QtGui import QFont, QPainter, QPainterPath, QPen, QColor
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QFrame,
    QApplication,
)


class TranslatorSidebar(QWidget):
    """
    Frameless panel docked to the right edge of the screen.

    Stays on top of other windows. Content is updated via set_translation()
    each time the user pins a popup. Clicking ✕ hides it (it persists in
    memory so the next pin is instant).
    """

    WIDTH = 300

    def __init__(self):
        super().__init__()
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._setup_ui()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _setup_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(16, 12, 16, 16)
        layout.setSpacing(8)

        # ── Header row ──────────────────────────────────────────────────
        header = QHBoxLayout()

        title = QLabel("Pinned Translation")
        title_font = QFont()
        title_font.setPointSize(9)
        title.setFont(title_font)
        title.setStyleSheet("color: palette(mid); background: transparent;")
        header.addWidget(title)
        header.addStretch()

        close_btn = QPushButton("✕")
        close_btn.setFixedSize(22, 22)
        close_btn.setStyleSheet(
            "QPushButton { background: transparent; border: none;"
            " color: palette(mid); font-size: 11pt; }"
            "QPushButton:hover { color: palette(text); }"
        )
        close_btn.clicked.connect(self.hide)
        header.addWidget(close_btn)
        layout.addLayout(header)

        # ── Divider ─────────────────────────────────────────────────────
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("border: none; border-top: 1px solid rgba(0,0,0,0.10);")
        layout.addWidget(sep)

        # ── Source text (small, muted) ──────────────────────────────────
        self.source_label = QLabel("")
        self.source_label.setWordWrap(True)
        src_font = QFont()
        src_font.setPointSize(10)
        self.source_label.setFont(src_font)
        self.source_label.setStyleSheet(
            "QLabel { font-size: 10pt; color: palette(mid); background: transparent; }"
        )
        layout.addWidget(self.source_label)

        # ── Translation (main content, selectable) ──────────────────────
        self.translation_label = QLabel("")
        self.translation_label.setWordWrap(True)
        self.translation_label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self.translation_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        trans_font = QFont()
        trans_font.setPointSize(12)
        self.translation_label.setFont(trans_font)
        self.translation_label.setStyleSheet(
            "QLabel { background: transparent; color: palette(text); padding: 2px 0; }"
        )
        layout.addWidget(self.translation_label)
        layout.addStretch()

        self.setLayout(layout)
        self.setFixedWidth(self.WIDTH)

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

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_translation(self, source: str, translation: str) -> None:
        """Replace content and show/raise the sidebar."""
        self.source_label.setText(source)
        self.translation_label.setText(translation)
        self._fit_and_position()
        self.show()
        self.raise_()

    def update_translation(self, translation: str) -> None:
        """Update only the translation text (e.g. when worker finishes)."""
        self.translation_label.setText(translation)
        self._fit_and_position()

    # ------------------------------------------------------------------
    # Positioning
    # ------------------------------------------------------------------

    def _fit_and_position(self):
        self.translation_label.adjustSize()
        self.adjustSize()
        self._position_on_right_edge()

    def _position_on_right_edge(self):
        app = QApplication.instance()
        if not app:
            return
        screen = app.primaryScreen()
        if not screen:
            return
        geom = screen.availableGeometry()
        x = geom.right() - self.WIDTH - 8
        y = geom.top() + max(40, (geom.height() - self.height()) // 3)
        self.move(x, y)
