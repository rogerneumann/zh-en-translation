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
    QFrame,
    QMessageBox,
)

from zh_en_translator.config import Config, save_config

_CLOUD_WARNING = (
    "⚠  Enabling cloud translation will send your text to Microsoft Azure servers "
    "over the internet. Only enable this if your organisation permits sending "
    "potentially sensitive data to third-party cloud services.\n\n"
    "The API key is stored in plain text in config.toml. "
    "Secure that file if the machine is shared."
)

_PREVIEW_SOURCE = "你好，世界"
_PREVIEW_PINYIN = "nǐ hǎo, shì jiè"
_PREVIEW_TRANS  = "Hello, world."


class _ColorSwatchButton(QPushButton):
    """Button that shows a colour swatch and opens QColorDialog on click."""

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
            startup=config.startup,
            font_family=config.font_family,
            font_size=config.font_size,
            bg_color=config.bg_color,
            theme=config.theme,
            side=config.side,
            sidebar_y=config.sidebar_y,
            sidebar_width=config.sidebar_width,
            color_fresh=config.color_fresh,
            color_idle=config.color_idle,
            external_lookup_url=config.external_lookup_url,
            ocr_engine=config.ocr_engine,
            show_pinyin=config.show_pinyin,
            pinyin_max_chars=config.pinyin_max_chars,
            traditional_to_simplified=config.traditional_to_simplified,
            ms_translator_enabled=config.ms_translator_enabled,
            ms_translator_api_key=config.ms_translator_api_key,
            ms_translator_region=config.ms_translator_region,
        )

        # Unsaved-changes tracking
        self._dirty = False
        self._skip_close_check = False

        self.setWindowTitle("Preferences")
        self.setMinimumWidth(520)

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

        self._tabs.addTab(self._build_general_tab(),    "General")
        self._tabs.addTab(self._build_display_tab(),    "Display")
        self._tabs.addTab(self._build_sidebar_tab(),    "Sidebar")
        self._tabs.addTab(self._build_lookup_ocr_tab(), "Lookup && OCR")
        self._tabs.addTab(self._build_cloud_tab(),      "Cloud")

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
            | QDialogButtonBox.StandardButton.Apply
        )
        buttons.accepted.connect(self._on_ok)
        buttons.rejected.connect(self._on_cancel)
        buttons.button(QDialogButtonBox.StandardButton.Apply).clicked.connect(self._on_apply)
        layout.addWidget(buttons)

    def _build_general_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(12)

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

        mode_group = QGroupBox("Translation Mode")
        mode_layout = QVBoxLayout(mode_group)
        self._mode_popup   = QRadioButton("Popup mode")
        self._mode_sidebar = QRadioButton("Sidebar mode")
        self._mode_group   = QButtonGroup()
        self._mode_group.addButton(self._mode_popup,   0)
        self._mode_group.addButton(self._mode_sidebar, 1)
        mode_layout.addWidget(self._mode_popup)
        mode_layout.addWidget(self._mode_sidebar)
        layout.addWidget(mode_group)

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

        # Theme
        theme_group = QGroupBox("Theme")
        theme_layout = QHBoxLayout(theme_group)
        theme_layout.addWidget(QLabel("Theme:"))
        self._theme_combo = QComboBox()
        for label, value in [
            ("System default", "system"),
            ("Light",          "light"),
            ("Dark",           "dark"),
            ("Sepia",          "sepia"),
        ]:
            self._theme_combo.addItem(label, userData=value)
        theme_layout.addWidget(self._theme_combo)
        theme_layout.addStretch()
        layout.addWidget(theme_group)

        # Font
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
        reset_bg.clicked.connect(self._update_preview)
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

        # ── Live preview ──────────────────────────────────────────────────
        preview_group = QGroupBox("Preview")
        preview_outer = QVBoxLayout(preview_group)
        preview_outer.setContentsMargins(8, 8, 8, 8)

        self._preview_frame = QFrame()
        self._preview_frame.setFrameShape(QFrame.Shape.NoFrame)
        self._preview_frame.setFixedHeight(100)
        preview_inner = QVBoxLayout(self._preview_frame)
        preview_inner.setContentsMargins(14, 10, 14, 10)
        preview_inner.setSpacing(4)

        self._preview_pinyin = QLabel(_PREVIEW_PINYIN)
        self._preview_pinyin.setObjectName("previewPinyin")
        preview_inner.addWidget(self._preview_pinyin)

        self._preview_source = QLabel(_PREVIEW_SOURCE)
        self._preview_source.setObjectName("previewSource")
        preview_inner.addWidget(self._preview_source)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setObjectName("previewSep")
        preview_inner.addWidget(sep)

        self._preview_trans = QLabel(_PREVIEW_TRANS)
        self._preview_trans.setObjectName("previewTrans")
        preview_inner.addWidget(self._preview_trans)
        preview_inner.addStretch()

        preview_outer.addWidget(self._preview_frame)
        layout.addWidget(preview_group)

        # Connect display controls → live preview
        self._theme_combo.currentIndexChanged.connect(self._update_preview)
        self._theme_combo.currentIndexChanged.connect(self._mark_dirty)
        self._font_combo.currentFontChanged.connect(self._update_preview)
        self._font_combo.currentFontChanged.connect(self._mark_dirty)
        self._font_size_spin.valueChanged.connect(self._update_preview)
        self._font_size_spin.valueChanged.connect(self._mark_dirty)
        self._bg_color_btn.color_changed.connect(self._update_preview)
        self._bg_color_btn.color_changed.connect(self._mark_dirty)

        return widget

    def _build_sidebar_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(12)

        side_group = QGroupBox("Side")
        side_layout = QVBoxLayout(side_group)
        self._side_left  = QRadioButton("Left")
        self._side_right = QRadioButton("Right")
        self._side_group = QButtonGroup()
        self._side_group.addButton(self._side_left,  0)
        self._side_group.addButton(self._side_right, 1)
        side_layout.addWidget(self._side_left)
        side_layout.addWidget(self._side_right)
        layout.addWidget(side_group)

        # Hint replacing the old Y-position spinbox
        pos_hint = QLabel(
            "Drag the indicator strip (screen edge) up or down to reposition the sidebar.\n"
            "Drag the inner edge of the expanded panel to resize its width.\n"
            "Position and width are saved automatically."
        )
        pos_hint.setWordWrap(True)
        pos_hint.setStyleSheet("color: gray; font-size: 9pt; padding: 2px 4px;")
        layout.addWidget(pos_hint)

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

        ocr_group = QGroupBox("OCR Engine")
        ocr_layout = QVBoxLayout(ocr_group)
        self._ocr_combo = QComboBox()
        self._ocr_combo.addItem("Auto (best available)", "auto")
        self._ocr_combo.addItem("Windows (winsdk)",      "windows")
        self._ocr_combo.addItem("Tesseract",             "tesseract")
        self._ocr_combo.addItem("PaddleOCR",             "paddle")
        ocr_layout.addWidget(self._ocr_combo)
        layout.addWidget(ocr_group)

        layout.addStretch()
        return widget

    def _build_cloud_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(12)

        warning_box = QGroupBox()
        warning_box.setStyleSheet(
            "QGroupBox { border: 2px solid #CC4400; border-radius: 6px; "
            "background: #FFF4F0; padding: 8px; }"
        )
        warning_layout = QVBoxLayout(warning_box)
        warning_label = QLabel(_CLOUD_WARNING)
        warning_label.setWordWrap(True)
        warning_label.setStyleSheet("color: #882200; font-size: 9pt; background: transparent;")
        warning_layout.addWidget(warning_label)
        layout.addWidget(warning_box)

        enable_group = QGroupBox("Microsoft Azure Translator")
        enable_layout = QVBoxLayout(enable_group)
        self._ms_enabled_check = QCheckBox("Enable cloud translation (sends text to Azure)")
        enable_layout.addWidget(self._ms_enabled_check)
        layout.addWidget(enable_group)

        creds_group = QGroupBox("API Credentials")
        creds_layout = QVBoxLayout(creds_group)
        key_row = QHBoxLayout()
        key_row.addWidget(QLabel("API Key:"))
        self._ms_api_key_edit = QLineEdit()
        self._ms_api_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self._ms_api_key_edit.setPlaceholderText("Paste your Azure subscription key here")
        key_row.addWidget(self._ms_api_key_edit, 1)
        self._ms_show_key_btn = QPushButton("Show")
        self._ms_show_key_btn.setFixedWidth(60)
        self._ms_show_key_btn.setCheckable(True)
        self._ms_show_key_btn.toggled.connect(self._on_show_key_toggled)
        key_row.addWidget(self._ms_show_key_btn)
        creds_layout.addLayout(key_row)
        region_row = QHBoxLayout()
        region_row.addWidget(QLabel("Region:"))
        self._ms_region_edit = QLineEdit()
        self._ms_region_edit.setPlaceholderText("e.g. eastus, westeurope (leave blank if unsure)")
        region_row.addWidget(self._ms_region_edit, 1)
        creds_layout.addLayout(region_row)
        hint = QLabel(
            "Get an API key from the Azure portal (Cognitive Services → Translator). "
            "The Free tier (F0) allows 2 million characters/month."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color: gray; font-size: 9pt;")
        creds_layout.addWidget(hint)
        layout.addWidget(creds_group)

        self._ms_enabled_check.toggled.connect(creds_group.setEnabled)
        creds_group.setEnabled(False)

        layout.addStretch()
        return widget

    def _on_show_key_toggled(self, checked: bool) -> None:
        self._ms_api_key_edit.setEchoMode(
            QLineEdit.EchoMode.Normal if checked else QLineEdit.EchoMode.Password
        )
        self._ms_show_key_btn.setText("Hide" if checked else "Show")

    # ------------------------------------------------------------------
    # Live preview
    # ------------------------------------------------------------------

    def _update_preview(self) -> None:
        """Re-style the preview frame to reflect current display settings."""
        from zh_en_translator.engines.themes import resolve_palette
        from PyQt6.QtWidgets import QApplication

        theme    = self._theme_combo.currentData() or "system"
        bg_color = self._bg_color_btn.get_color_str()

        from PyQt6.QtGui import QPalette
        sys_bg      = QApplication.palette().color(QPalette.ColorRole.Window)
        system_dark = sys_bg.lightness() < 128
        palette      = resolve_palette(theme, system_dark)

        if bg_color:
            bg_col = QColor(bg_color)
            is_dark = bg_col.lightness() < 128
            palette = resolve_palette("dark" if is_dark else "light", system_dark)
            bg_hex  = bg_color
        else:
            bg_hex = palette.bg

        # Font for translation label
        line_edit   = self._font_combo.lineEdit()
        family      = line_edit.text().strip() if line_edit else ""
        size        = self._font_size_spin.value()

        trans_font = QFont()
        if family:
            trans_font.setFamily(family)
        trans_font.setPointSize(size)
        self._preview_trans.setFont(trans_font)

        src_font = QFont()
        src_font.setPointSize(max(8, size - 3))
        self._preview_source.setFont(src_font)

        pinyin_font = QFont()
        pinyin_font.setPointSize(max(7, size - 4))
        self._preview_pinyin.setFont(pinyin_font)

        self._preview_frame.setStyleSheet(f"""
            QFrame {{
                background: {bg_hex};
                border: 1px solid {palette.border};
                border-radius: 10px;
            }}
            QLabel#previewSource {{
                background: transparent;
                color: {palette.muted};
                font-size: {max(8, size - 3)}pt;
                padding: 0;
            }}
            QLabel#previewPinyin {{
                background: transparent;
                color: {palette.muted};
                font-size: {max(7, size - 4)}pt;
                padding: 0;
                letter-spacing: 0.5px;
            }}
            QLabel#previewTrans {{
                background: transparent;
                color: {palette.text};
                padding: 0;
            }}
            QFrame#previewSep {{
                background: transparent;
                border: none;
                border-top: 1px solid {palette.border};
                max-height: 1px;
            }}
        """)

    # ------------------------------------------------------------------
    # Dirty tracking
    # ------------------------------------------------------------------

    def _mark_dirty(self) -> None:
        self._dirty = True

    def _connect_dirty_signals(self) -> None:
        """Wire all settings widgets to _mark_dirty (called after loading config)."""
        self._hotkey_edit.textChanged.connect(self._mark_dirty)
        self._mode_group.buttonClicked.connect(self._mark_dirty)
        self._trad_to_simp_check.toggled.connect(self._mark_dirty)
        self._side_group.buttonClicked.connect(self._mark_dirty)
        self._color_fresh_btn.color_changed.connect(self._mark_dirty)
        self._color_idle_btn.color_changed.connect(self._mark_dirty)
        self._lookup_url_edit.textChanged.connect(self._mark_dirty)
        self._ocr_combo.currentIndexChanged.connect(self._mark_dirty)
        self._show_pinyin_check.toggled.connect(self._mark_dirty)
        self._pinyin_max_spin.valueChanged.connect(self._mark_dirty)
        self._ms_enabled_check.toggled.connect(self._mark_dirty)
        self._ms_api_key_edit.textChanged.connect(self._mark_dirty)
        self._ms_region_edit.textChanged.connect(self._mark_dirty)
        # Display tab signals already wired in _build_display_tab

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
        theme_index = self._theme_combo.findData(cfg.theme)
        self._theme_combo.setCurrentIndex(max(0, theme_index))
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
        self._color_fresh_btn.set_color_str(cfg.color_fresh)
        self._color_idle_btn.set_color_str(cfg.color_idle)

        # Lookup & OCR
        self._lookup_url_edit.setText(cfg.external_lookup_url)
        engine_index = self._ocr_combo.findData(cfg.ocr_engine)
        if engine_index >= 0:
            self._ocr_combo.setCurrentIndex(engine_index)

        # Cloud
        self._ms_enabled_check.setChecked(cfg.ms_translator_enabled)
        self._ms_api_key_edit.setText(cfg.ms_translator_api_key)
        self._ms_region_edit.setText(cfg.ms_translator_region)

        # Initial preview render + connect dirty signals (after load so no false dirty)
        self._update_preview()
        self._connect_dirty_signals()
        self._dirty = False  # loading doesn't count as a change

    def _collect_config(self) -> Config:
        mode = "sidebar" if self._mode_sidebar.isChecked() else "popup"
        side = "left" if self._side_left.isChecked() else "right"

        line_edit   = self._font_combo.lineEdit()
        font_family = line_edit.text().strip() if line_edit else ""
        ocr_engine  = self._ocr_combo.currentData() or "auto"

        return Config(
            hotkey=self._hotkey_edit.text().strip() or self.config.hotkey,
            mode=mode,
            startup=self.config.startup,
            font_family=font_family,
            font_size=self._font_size_spin.value(),
            bg_color=self._bg_color_btn.get_color_str(),
            theme=self._theme_combo.currentData() or "system",
            side=side,
            sidebar_y=self.config.sidebar_y,
            sidebar_width=self.config.sidebar_width,
            color_fresh=self._color_fresh_btn.get_color_str(),
            color_idle=self._color_idle_btn.get_color_str(),
            external_lookup_url=self._lookup_url_edit.text().strip()
                or self.config.external_lookup_url,
            ocr_engine=ocr_engine,
            show_pinyin=self._show_pinyin_check.isChecked(),
            pinyin_max_chars=self._pinyin_max_spin.value(),
            traditional_to_simplified=self._trad_to_simp_check.isChecked(),
            ms_translator_enabled=self._ms_enabled_check.isChecked(),
            ms_translator_api_key=self._ms_api_key_edit.text().strip(),
            ms_translator_region=self._ms_region_edit.text().strip(),
        )

    # ------------------------------------------------------------------
    # Button handlers
    # ------------------------------------------------------------------

    def _on_apply(self):
        self.config = self._collect_config()
        save_config(self.config)
        self.settings_applied.emit(self.config)
        self._dirty = False

    def _on_ok(self):
        self._skip_close_check = True
        self._on_apply()
        self.accept()

    def _on_cancel(self):
        self._skip_close_check = True
        self.reject()

    # ------------------------------------------------------------------
    # Unsaved-changes guard
    # ------------------------------------------------------------------

    def closeEvent(self, event):
        if not self._skip_close_check and self._dirty:
            answer = QMessageBox.question(
                self,
                "Unsaved Changes",
                "You have unsaved changes. Save before closing?",
                QMessageBox.StandardButton.Save
                | QMessageBox.StandardButton.Discard
                | QMessageBox.StandardButton.Cancel,
            )
            if answer == QMessageBox.StandardButton.Save:
                self._on_apply()
            elif answer == QMessageBox.StandardButton.Cancel:
                event.ignore()
                return
        event.accept()
