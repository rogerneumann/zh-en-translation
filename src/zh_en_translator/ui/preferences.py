"""Preferences dialog for zh-en-translator."""

from __future__ import annotations

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QTabWidget,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QSpinBox,
    QRadioButton,
    QButtonGroup,
    QFontComboBox,
    QPushButton,
    QColorDialog,
    QComboBox,
    QGroupBox,
    QSizePolicy,
    QCheckBox,
)

from zh_en_translator.config import Config, save_config


class _ColorSwatchButton(QPushButton):
    """A button that shows a color swatch and opens QColorDialog on click."""

    color_changed = pyqtSignal(str)  # emits hex color string or "" for reset

    def __init__(self, color_str: str = "", parent=None):
        super().__init__(parent)
        self._color_str = color_str
        self._update_appearance()
        self.clicked.connect(self._open_color_dialog)

    def _update_appearance(self):
        if self._color_str:
            self.setText(self._color_str)
            self.setStyleSheet(
                f"QPushButton {{ background-color: {self._color_str}; "
                f"border: 1px solid #888; border-radius: 4px; padding: 4px 10px; }}"
                f"QPushButton:hover {{ border: 1px solid #444; }}"
            )
        else:
            self.setText("Use system default")
            self.setStyleSheet(
                "QPushButton { background-color: #C0C0C0; border: 1px solid #888; "
                "border-radius: 4px; padding: 4px 10px; color: #333; }"
                "QPushButton:hover { border: 1px solid #444; }"
            )

    def _open_color_dialog(self):
        initial = QColor(self._color_str) if self._color_str else QColor(255, 255, 255)
        color = QColorDialog.getColor(initial, self, "Choose Color")
        if color.isValid():
            self._color_str = color.name()
            self._update_appearance()
            self.color_changed.emit(self._color_str)

    def get_color_str(self) -> str:
        return self._color_str

    def set_color_str(self, color_str: str):
        self._color_str = color_str
        self._update_appearance()


class PreferencesDialog(QDialog):
    """Tabbed preferences dialog for zh-en-translator settings."""

    settings_applied = pyqtSignal(object)  # emits Config

    def __init__(self, config: Config, parent=None):
        super().__init__(parent)
        self.config = Config(
            hotkey=config.hotkey,
            mode=config.mode,
            font_family=config.font_family,
            font_size=config.font_size,
            bg_color=config.bg_color,
            side=config.side,
            sidebar_y=config.sidebar_y,
            color_fresh=config.color_fresh,
            color_idle=config.color_idle,
            external_lookup_url=config.external_lookup_url,
            ocr_engine=config.ocr_engine,
            show_pinyin=config.show_pinyin,
            pinyin_max_chars=config.pinyin_max_chars,
            traditional_to_simplified=config.traditional_to_simplified,
        )

        self.setWindowTitle("Preferences")
        self.setMinimumWidth(480)

        self._setup_ui()
        self._load_config_into_ui()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        self._tabs = QTabWidget()
        layout.addWidget(self._tabs)

        self._tabs.addTab(self._build_general_tab(), "General")
        self._tabs.addTab(self._build_display_tab(), "Display")
        self._tabs.addTab(self._build_sidebar_tab(), "Sidebar")
        self._tabs.addTab(self._build_lookup_ocr_tab(), "Lookup && OCR")

        # Standard dialog buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
            | QDialogButtonBox.StandardButton.Apply
        )
        buttons.accepted.connect(self._on_ok)
        buttons.rejected.connect(self.reject)
        buttons.button(QDialogButtonBox.StandardButton.Apply).clicked.connect(self._on_apply)
        layout.addWidget(buttons)

    def _build_general_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(12)

        # Hotkey
        hotkey_group = QGroupBox("Global Hotkey")
        hotkey_layout = QVBoxLayout(hotkey_group)

        self._hotkey_edit = QLineEdit()
        self._hotkey_edit.setPlaceholderText("<ctrl>+<shift>+t")
        hotkey_layout.addWidget(self._hotkey_edit)

        hint = QLabel("Use pynput angle-bracket syntax, e.g. <ctrl>+<shift>+t")
        hint.setStyleSheet("color: gray; font-size: 9pt;")
        hint.setWordWrap(True)
        hotkey_layout.addWidget(hint)

        layout.addWidget(hotkey_group)

        # Mode
        mode_group = QGroupBox("Translation Mode")
        mode_layout = QVBoxLayout(mode_group)

        self._mode_popup = QRadioButton("Popup mode")
        self._mode_sidebar = QRadioButton("Sidebar mode")
        self._mode_group = QButtonGroup()
        self._mode_group.addButton(self._mode_popup, 0)
        self._mode_group.addButton(self._mode_sidebar, 1)

        mode_layout.addWidget(self._mode_popup)
        mode_layout.addWidget(self._mode_sidebar)
        layout.addWidget(mode_group)

        # Traditional Chinese
        trad_group = QGroupBox("Traditional Chinese")
        trad_layout = QVBoxLayout(trad_group)

        self._trad_to_simp_check = QCheckBox("Convert Traditional → Simplified automatically")
        trad_layout.addWidget(self._trad_to_simp_check)

        layout.addWidget(trad_group)

        layout.addStretch()
        return widget

    def _build_display_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(12)

        # Font family
        font_group = QGroupBox("Font")
        font_layout = QVBoxLayout(font_group)

        font_row = QHBoxLayout()
        font_row.addWidget(QLabel("Family:"))
        self._font_combo = QFontComboBox()
        self._font_combo.setEditable(True)
        self._font_combo.lineEdit().setPlaceholderText("(system default)")
        font_row.addWidget(self._font_combo, 1)
        font_layout.addLayout(font_row)

        size_row = QHBoxLayout()
        size_row.addWidget(QLabel("Size:"))
        self._font_size_spin = QSpinBox()
        self._font_size_spin.setRange(8, 36)
        self._font_size_spin.setValue(13)
        self._font_size_spin.setSuffix(" pt")
        size_row.addWidget(self._font_size_spin)
        size_row.addStretch()
        font_layout.addLayout(size_row)

        layout.addWidget(font_group)

        # Background color
        bg_group = QGroupBox("Background Color")
        bg_layout = QHBoxLayout(bg_group)

        self._bg_color_btn = _ColorSwatchButton()
        bg_layout.addWidget(self._bg_color_btn)

        reset_bg = QPushButton("Reset to default")
        reset_bg.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        reset_bg.clicked.connect(lambda: self._bg_color_btn.set_color_str(""))
        bg_layout.addWidget(reset_bg)
        bg_layout.addStretch()

        layout.addWidget(bg_group)

        # Pinyin
        pinyin_group = QGroupBox("Pinyin")
        pinyin_layout = QVBoxLayout(pinyin_group)

        self._show_pinyin_check = QCheckBox("Show pinyin")
        pinyin_layout.addWidget(self._show_pinyin_check)

        pinyin_max_row = QHBoxLayout()
        pinyin_max_row.addWidget(QLabel("Max chars for pinyin:"))
        self._pinyin_max_spin = QSpinBox()
        self._pinyin_max_spin.setRange(10, 500)
        self._pinyin_max_spin.setSingleStep(10)
        self._pinyin_max_spin.setValue(80)
        pinyin_max_row.addWidget(self._pinyin_max_spin)
        pinyin_max_row.addStretch()
        pinyin_layout.addLayout(pinyin_max_row)

        self._show_pinyin_check.toggled.connect(self._pinyin_max_spin.setEnabled)

        layout.addWidget(pinyin_group)
        layout.addStretch()
        return widget

    def _build_sidebar_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(12)

        # Side
        side_group = QGroupBox("Side")
        side_layout = QVBoxLayout(side_group)

        self._side_left = QRadioButton("Left")
        self._side_right = QRadioButton("Right")
        self._side_group = QButtonGroup()
        self._side_group.addButton(self._side_left, 0)
        self._side_group.addButton(self._side_right, 1)

        side_layout.addWidget(self._side_left)
        side_layout.addWidget(self._side_right)
        layout.addWidget(side_group)

        # Y position
        y_group = QGroupBox("Vertical Position")
        y_layout = QHBoxLayout(y_group)

        y_layout.addWidget(QLabel("Y position (px from top):"))
        self._sidebar_y_spin = QSpinBox()
        self._sidebar_y_spin.setRange(0, 2000)
        self._sidebar_y_spin.setValue(200)
        y_layout.addWidget(self._sidebar_y_spin)
        y_layout.addStretch()
        layout.addWidget(y_group)

        # Indicator colors
        colors_group = QGroupBox("Indicator Colors")
        colors_layout = QVBoxLayout(colors_group)

        fresh_row = QHBoxLayout()
        fresh_row.addWidget(QLabel("Fresh (new translation):"))
        self._color_fresh_btn = _ColorSwatchButton("#00C9CC")
        fresh_row.addWidget(self._color_fresh_btn)
        fresh_row.addStretch()
        colors_layout.addLayout(fresh_row)

        idle_row = QHBoxLayout()
        idle_row.addWidget(QLabel("Idle (stale):"))
        self._color_idle_btn = _ColorSwatchButton("#9E8080")
        idle_row.addWidget(self._color_idle_btn)
        idle_row.addStretch()
        colors_layout.addLayout(idle_row)

        layout.addWidget(colors_group)
        layout.addStretch()
        return widget

    def _build_lookup_ocr_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(12)

        # External lookup URL
        lookup_group = QGroupBox("External Lookup")
        lookup_layout = QVBoxLayout(lookup_group)

        self._lookup_url_edit = QLineEdit()
        self._lookup_url_edit.setPlaceholderText(
            "https://www.mdbg.net/chinese/dictionary?wdqb={query}"
        )
        lookup_layout.addWidget(self._lookup_url_edit)

        hint = QLabel("{query} is replaced with the source text at runtime.")
        hint.setStyleSheet("color: gray; font-size: 9pt;")
        lookup_layout.addWidget(hint)

        layout.addWidget(lookup_group)

        # OCR engine
        ocr_group = QGroupBox("OCR Engine")
        ocr_layout = QVBoxLayout(ocr_group)

        self._ocr_combo = QComboBox()
        self._ocr_combo.addItem("Auto (best available)", "auto")
        self._ocr_combo.addItem("Windows (winsdk)", "windows")
        self._ocr_combo.addItem("Tesseract", "tesseract")
        self._ocr_combo.addItem("PaddleOCR", "paddle")
        ocr_layout.addWidget(self._ocr_combo)

        layout.addWidget(ocr_group)
        layout.addStretch()
        return widget

    # ------------------------------------------------------------------
    # Load / collect config values
    # ------------------------------------------------------------------

    def _load_config_into_ui(self):
        cfg = self.config

        # General
        self._hotkey_edit.setText(cfg.hotkey)
        if cfg.mode == "sidebar":
            self._mode_sidebar.setChecked(True)
        else:
            self._mode_popup.setChecked(True)
        self._trad_to_simp_check.setChecked(cfg.traditional_to_simplified)

        # Display
        if cfg.font_family:
            self._font_combo.setCurrentFont(QFont(cfg.font_family))
        else:
            self._font_combo.lineEdit().setText("")
        self._font_size_spin.setValue(cfg.font_size)
        self._bg_color_btn.set_color_str(cfg.bg_color)
        self._show_pinyin_check.setChecked(cfg.show_pinyin)
        self._pinyin_max_spin.setValue(cfg.pinyin_max_chars)
        self._pinyin_max_spin.setEnabled(cfg.show_pinyin)

        # Sidebar
        if cfg.side == "left":
            self._side_left.setChecked(True)
        else:
            self._side_right.setChecked(True)
        self._sidebar_y_spin.setValue(cfg.sidebar_y)
        self._color_fresh_btn.set_color_str(cfg.color_fresh)
        self._color_idle_btn.set_color_str(cfg.color_idle)

        # Lookup & OCR
        self._lookup_url_edit.setText(cfg.external_lookup_url)
        engine_index = self._ocr_combo.findData(cfg.ocr_engine)
        if engine_index >= 0:
            self._ocr_combo.setCurrentIndex(engine_index)

    def _collect_config(self) -> Config:
        """Build a Config from the current UI state."""
        mode = "sidebar" if self._mode_sidebar.isChecked() else "popup"
        side = "left" if self._side_left.isChecked() else "right"

        line_edit = self._font_combo.lineEdit()
        font_family = line_edit.text().strip() if line_edit else ""

        ocr_engine = self._ocr_combo.currentData() or "auto"

        return Config(
            hotkey=self._hotkey_edit.text().strip() or self.config.hotkey,
            mode=mode,
            font_family=font_family,
            font_size=self._font_size_spin.value(),
            bg_color=self._bg_color_btn.get_color_str(),
            side=side,
            sidebar_y=self._sidebar_y_spin.value(),
            color_fresh=self._color_fresh_btn.get_color_str(),
            color_idle=self._color_idle_btn.get_color_str(),
            external_lookup_url=self._lookup_url_edit.text().strip()
                or self.config.external_lookup_url,
            ocr_engine=ocr_engine,
            show_pinyin=self._show_pinyin_check.isChecked(),
            pinyin_max_chars=self._pinyin_max_spin.value(),
            traditional_to_simplified=self._trad_to_simp_check.isChecked(),
        )

    # ------------------------------------------------------------------
    # Button handlers
    # ------------------------------------------------------------------

    def _on_apply(self):
        self.config = self._collect_config()
        save_config(self.config)
        self.settings_applied.emit(self.config)

    def _on_ok(self):
        self._on_apply()
        self.accept()
