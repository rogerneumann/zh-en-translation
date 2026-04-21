"""Preferences dialog for zh-en-translator."""

from __future__ import annotations

from PyQt6.QtCore import pyqtSignal, Qt
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
    QApplication,
    QFileDialog,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
)

from zh_en_translator.config import Config, save_config

_CLOUD_WARNING = (
    "⚠  Enabling cloud translation will send your text to Microsoft Azure or DeepL servers "
    "over the internet. Only enable this if your organisation permits sending "
    "potentially sensitive data to third-party cloud services.\n\n"
    "The API keys are stored in plain text in config.toml. "
    "Secure that file if the machine is shared."
)

_PREVIEW_SOURCE = "你好，世界"
_PREVIEW_PINYIN = "nǐ hǎo, shì jiè"
_PREVIEW_TRANS  = "Hello, world."

# Windows 11 / Microsoft 365 modern font stack
_FONT_STACK = "'Segoe UI Variable Display', 'Aptos', 'Segoe UI', 'Microsoft YaHei', 'sans-serif'"

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
                f"border: 1px solid rgba(0,0,0,0.1); border-radius: 12px; padding: 4px 12px; }}"
            )
        else:
            self.setText("Use system default")
            self.setStyleSheet(
                "QPushButton { background-color: #E0E0E0; border: none; "
                "border-radius: 12px; padding: 4px 12px; color: #333; }"
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
            auto_check_updates=config.auto_check_updates,
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
            deepl_enabled=config.deepl_enabled,
            deepl_api_key=config.deepl_api_key,
            deepl_pro=config.deepl_pro,
        )

        # Unsaved-changes tracking
        self._dirty = False
        self._skip_close_check = False

        self.setWindowTitle("Preferences")
        self.setMinimumWidth(540)
        self._apply_global_styling()

        self._setup_ui()
        self._load_config_into_ui()

    def _apply_global_styling(self):
        self.setStyleSheet(f"""
            QWidget {{ font-family: {_FONT_STACK}; font-size: 10pt; }}
            QGroupBox {{ font-weight: bold; border: 1px solid rgba(0,0,0,0.08); border-radius: 8px; margin-top: 10px; padding-top: 10px; }}
            QGroupBox::title {{ subcontrol-origin: margin; left: 8px; padding: 0 3px; }}
            QPushButton {{ background: rgba(0,0,0,0.05); border: 1px solid rgba(0,0,0,0.05); border-radius: 12px; padding: 5px 15px; }}
            QPushButton:hover {{ background: rgba(0,0,0,0.08); }}
            QLineEdit {{ border: 1px solid rgba(0,0,0,0.1); border-radius: 6px; padding: 4px; }}
            QTabWidget::pane {{ border: 1px solid rgba(0,0,0,0.08); border-radius: 4px; }}
        """)

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        self._tabs = QTabWidget()
        layout.addWidget(self._tabs)

        self._tabs.addTab(self._build_general_tab(),    "General")
        self._tabs.addTab(self._build_display_tab(),    "Display")
        self._tabs.addTab(self._build_sidebar_tab(),    "Sidebar")
        self._tabs.addTab(self._build_lookup_ocr_tab(), "Lookup && OCR")
        self._tabs.addTab(self._build_glossary_tab(),   "Glossary")
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

        update_group = QGroupBox("Updates")
        update_layout = QVBoxLayout(update_group)
        self._auto_update_check = QCheckBox("Check for updates automatically on startup")
        update_layout.addWidget(self._auto_update_check)
        self._btn_check_now = QPushButton("Check for Updates Now")
        self._btn_check_now.setFixedWidth(180)
        update_layout.addWidget(self._btn_check_now)
        layout.addWidget(update_group)

        layout.addStretch()
        return widget

    def _build_display_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(12)

        theme_group = QGroupBox("Theme")
        theme_layout = QHBoxLayout(theme_group)
        theme_layout.addWidget(QLabel("Theme:"))
        self._theme_combo = QComboBox()
        for label, value in [
            ("System default", "system"),
            ("Light",          "light"),
            ("Dark",           "dark"),
            ("Sepia",          "sepia"),
            ("High Contrast",  "high_contrast"),
        ]:
            self._theme_combo.addItem(label, userData=value)
        theme_layout.addWidget(self._theme_combo)
        theme_layout.addStretch()
        layout.addWidget(theme_group)

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
        self._font_size_spin.setSuffix(" pt")
        size_row.addWidget(self._font_size_spin)
        size_row.addStretch()
        font_layout.addLayout(size_row)
        layout.addWidget(font_group)

        bg_group = QGroupBox("Background Color")
        bg_layout = QHBoxLayout(bg_group)
        self._bg_color_btn = _ColorSwatchButton()
        bg_layout.addWidget(self._bg_color_btn)
        reset_bg = QPushButton("Reset to default")
        reset_bg.clicked.connect(lambda: self._bg_color_btn.set_color_str(""))
        bg_layout.addWidget(reset_bg)
        bg_layout.addStretch()
        layout.addWidget(bg_group)

        pinyin_group = QGroupBox("Pinyin")
        pinyin_layout = QVBoxLayout(pinyin_group)
        self._show_pinyin_check = QCheckBox("Show pinyin")
        pinyin_layout.addWidget(self._show_pinyin_check)
        pinyin_max_row = QHBoxLayout()
        pinyin_max_row.addWidget(QLabel("Max chars for pinyin:"))
        self._pinyin_max_spin = QSpinBox()
        self._pinyin_max_spin.setRange(10, 500)
        pinyin_max_row.addWidget(self._pinyin_max_spin)
        pinyin_max_row.addStretch()
        pinyin_layout.addLayout(pinyin_max_row)
        self._show_pinyin_check.toggled.connect(self._pinyin_max_spin.setEnabled)
        layout.addWidget(pinyin_group)

        preview_group = QGroupBox("Preview")
        preview_outer = QVBoxLayout(preview_group)
        self._preview_frame = QFrame()
        self._preview_frame.setFixedHeight(100)
        preview_inner = QVBoxLayout(self._preview_frame)
        self._preview_pinyin = QLabel(_PREVIEW_PINYIN)
        preview_inner.addWidget(self._preview_pinyin)
        self._preview_source = QLabel(_PREVIEW_SOURCE)
        preview_inner.addWidget(self._preview_source)
        self._preview_trans = QLabel(_PREVIEW_TRANS)
        preview_inner.addWidget(self._preview_trans)
        preview_outer.addWidget(self._preview_frame)
        layout.addWidget(preview_group)

        for w in [self._theme_combo, self._font_combo, self._font_size_spin]:
            w.currentIndexChanged.connect(self._update_preview) if hasattr(w, "currentIndexChanged") else w.valueChanged.connect(self._update_preview)
        self._bg_color_btn.color_changed.connect(self._update_preview)

        layout.addStretch()
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
        pos_hint = QLabel("Interactive repositioning enabled: drag the strip to move, edge to resize.")
        pos_hint.setStyleSheet("color: gray; font-size: 9pt;")
        layout.addWidget(pos_hint)
        layout.addStretch()
        return widget

    def _build_lookup_ocr_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(12)
        lookup_group = QGroupBox("External Lookup")
        lookup_layout = QVBoxLayout(lookup_group)
        self._lookup_url_edit = QLineEdit()
        lookup_layout.addWidget(self._lookup_url_edit)
        hint = QLabel("{query} is replaced with the source text at runtime.")
        hint.setStyleSheet("color: gray; font-size: 9pt;")
        lookup_layout.addWidget(hint)
        layout.addWidget(lookup_group)
        ocr_group = QGroupBox("OCR Engine")
        ocr_layout = QVBoxLayout(ocr_group)
        self._ocr_combo = QComboBox()
        for label, val in [("Auto", "auto"), ("Windows", "windows"), ("Tesseract", "tesseract"), ("PaddleOCR", "paddle")]:
            self._ocr_combo.addItem(label, val)
        ocr_layout.addWidget(self._ocr_combo)
        layout.addWidget(ocr_group)

        # Tesseract status
        import sys, shutil, os
        tess_group = QGroupBox("Tesseract Status")
        tess_layout = QVBoxLayout(tess_group)

        tess_path = shutil.which("tesseract")
        if not tess_path and sys.platform == "win32":
            candidates = [
                os.path.expandvars(r"%LOCALAPPDATA%\Programs\Tesseract-OCR\tesseract.exe"),
                r"C:\Program Files\Tesseract-OCR\tesseract.exe",
            ]
            for c in candidates:
                if os.path.isfile(c):
                    tess_path = c
                    break

        if tess_path:
            status_label = QLabel(f"Tesseract: Found at {tess_path}")
            status_label.setStyleSheet("color: #1a7a1a; font-weight: bold;")
            tess_layout.addWidget(status_label)
        else:
            status_label = QLabel("Tesseract: Not found. Check install log:")
            status_label.setStyleSheet("color: #b85c00; font-weight: bold;")
            tess_layout.addWidget(status_label)

            def _open_tess_log():
                log_path = os.path.join(os.environ.get("TEMP", ""), "zh-en-translator-tesseract-install.log")
                if os.path.isfile(log_path):
                    import subprocess
                    subprocess.Popen(["notepad.exe", log_path])
                else:
                    QMessageBox.information(
                        self,
                        "Log Not Found",
                        f"Install log not found:\n{log_path}\n\n"
                        "Run the Tesseract installer to generate it.",
                    )

            btn_open_log = QPushButton("Open Log")
            btn_open_log.setFixedWidth(100)
            btn_open_log.clicked.connect(_open_tess_log)
            tess_layout.addWidget(btn_open_log)

        layout.addWidget(tess_group)
        layout.addStretch()
        return widget

    def _build_glossary_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(8)

        hint = QLabel(
            "Glossary terms override the translation engine for exact phrase matches.\n"
            "Format: Chinese phrase → English translation"
        )
        hint.setStyleSheet("color: gray; font-size: 9pt;")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        self._glossary_table = QTableWidget(0, 2)
        self._glossary_table.setHorizontalHeaderLabels(["Chinese", "English translation"])
        self._glossary_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self._glossary_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self._glossary_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        layout.addWidget(self._glossary_table)

        btn_row = QHBoxLayout()
        btn_add = QPushButton("Add row")
        btn_add.clicked.connect(self._glossary_add_row)
        btn_remove = QPushButton("Remove selected")
        btn_remove.clicked.connect(self._glossary_remove_row)
        btn_import = QPushButton("Import CSV…")
        btn_import.clicked.connect(self._glossary_import_csv)
        btn_export = QPushButton("Export CSV…")
        btn_export.clicked.connect(self._glossary_export_csv)
        btn_row.addWidget(btn_add)
        btn_row.addWidget(btn_remove)
        btn_row.addStretch()
        btn_row.addWidget(btn_import)
        btn_row.addWidget(btn_export)
        layout.addLayout(btn_row)
        return widget

    def _glossary_add_row(self) -> None:
        """Append a blank row to the glossary table."""
        row = self._glossary_table.rowCount()
        self._glossary_table.insertRow(row)
        self._glossary_table.setItem(row, 0, QTableWidgetItem(""))
        self._glossary_table.setItem(row, 1, QTableWidgetItem(""))

    def _glossary_remove_row(self) -> None:
        """Remove all currently selected rows from the glossary table."""
        selected_rows = sorted(
            {idx.row() for idx in self._glossary_table.selectedIndexes()},
            reverse=True,
        )
        for row in selected_rows:
            self._glossary_table.removeRow(row)

    def _glossary_import_csv(self, path=None) -> None:
        """Import a zh,en CSV file, merging entries into the current table."""
        if path is None:
            path, _ = QFileDialog.getOpenFileName(
                self,
                "Import Glossary CSV",
                "",
                "CSV files (*.csv);;All files (*)",
            )
            if not path:
                return
        from zh_en_translator.engines.glossary import load_glossary
        from pathlib import Path as _Path
        imported = load_glossary(_Path(path))
        if not imported:
            QMessageBox.information(self, "Import Glossary", "No valid entries found in the selected file.")
            return
        existing = self._glossary_get_terms()
        existing.update(imported)
        self._glossary_load_terms(existing)

    def _glossary_export_csv(self) -> None:
        """Export the current glossary table to a CSV file."""
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Glossary CSV",
            "glossary.csv",
            "CSV files (*.csv);;All files (*)",
        )
        if not path:
            return
        from zh_en_translator.engines.glossary import save_glossary
        from pathlib import Path as _Path
        save_glossary(self._glossary_get_terms(), _Path(path))

    def _glossary_get_terms(self) -> dict[str, str]:
        """Read the current glossary table into a {zh: en} dict."""
        terms: dict[str, str] = {}
        for row in range(self._glossary_table.rowCount()):
            zh_item = self._glossary_table.item(row, 0)
            en_item = self._glossary_table.item(row, 1)
            zh = zh_item.text().strip() if zh_item else ""
            en = en_item.text().strip() if en_item else ""
            if zh and en:
                terms[zh] = en
        return terms

    def _glossary_load_terms(self, terms: dict[str, str]) -> None:
        """Populate the glossary table from a {zh: en} dict."""
        self._glossary_table.setRowCount(0)
        for zh, en in sorted(terms.items()):
            row = self._glossary_table.rowCount()
            self._glossary_table.insertRow(row)
            self._glossary_table.setItem(row, 0, QTableWidgetItem(zh))
            self._glossary_table.setItem(row, 1, QTableWidgetItem(en))

    def _build_cloud_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        warning_box = QFrame()
        warning_box.setStyleSheet("background: #FFF4F0; border: 1px solid #CC4400; border-radius: 8px;")
        w_layout = QVBoxLayout(warning_box)
        w_layout.addWidget(QLabel(_CLOUD_WARNING))
        layout.addWidget(warning_box)

        self._ms_enabled_check = QCheckBox("Enable Azure Cloud translation")
        layout.addWidget(self._ms_enabled_check)
        self._ms_api_key_edit = QLineEdit()
        self._ms_api_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        layout.addWidget(QLabel("Azure API Key:"))
        layout.addWidget(self._ms_api_key_edit)
        
        self._deepl_enabled_check = QCheckBox("Enable DeepL translation")
        layout.addWidget(self._deepl_enabled_check)
        self._deepl_key_edit = QLineEdit()
        self._deepl_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        layout.addWidget(QLabel("DeepL API Key:"))
        layout.addWidget(self._deepl_key_edit)
        layout.addStretch()
        return widget

    def _update_preview(self):
        from zh_en_translator.engines.themes import resolve_palette
        theme = self._theme_combo.currentData() or "system"
        bg_col = self._bg_color_btn.get_color_str()
        palette = resolve_palette(theme, False)
        bg = bg_col if bg_col else palette.bg
        self._preview_frame.setStyleSheet(f"background: {bg}; border: 1px solid {palette.border}; border-radius: 12px; color: {palette.text};")

    def _on_apply(self):
        self.config = self._collect_config()
        save_config(self.config)
        from zh_en_translator.engines.glossary import save_glossary
        save_glossary(self._glossary_get_terms())
        self.settings_applied.emit(self.config)
        self._dirty = False

    def _on_ok(self): self._skip_close_check = True; self._on_apply(); self.accept()
    def _on_cancel(self): self._skip_close_check = True; self.reject()

    def _mark_dirty(self): self._dirty = True
    def _connect_dirty_signals(self):
        for w in self.findChildren((QLineEdit, QCheckBox, QComboBox, QSpinBox, QRadioButton)):
            if hasattr(w, "textChanged"): w.textChanged.connect(self._mark_dirty)
            if hasattr(w, "toggled"): w.toggled.connect(self._mark_dirty)

    def _load_config_into_ui(self):
        cfg = self.config
        self._hotkey_edit.setText(cfg.hotkey)
        self._auto_update_check.setChecked(cfg.auto_check_updates)
        self._font_size_spin.setValue(cfg.font_size)
        self._ms_api_key_edit.setText(cfg.ms_translator_api_key)
        self._deepl_key_edit.setText(cfg.deepl_api_key)
        from zh_en_translator.engines.glossary import load_glossary
        self._glossary_load_terms(load_glossary())
        self._update_preview()
        self._connect_dirty_signals()

    def _collect_config(self) -> Config:
        return Config(
            hotkey=self._hotkey_edit.text(),
            mode="sidebar" if self._mode_sidebar.isChecked() else "popup",
            startup=self.config.startup,
            auto_check_updates=self._auto_update_check.isChecked(),
            font_family=self._font_combo.currentText(),
            font_size=self._font_size_spin.value(),
            bg_color=self._bg_color_btn.get_color_str(),
            theme=self._theme_combo.currentData(),
            side="left" if self._side_left.isChecked() else "right",
            sidebar_y=self.config.sidebar_y,
            sidebar_width=self.config.sidebar_width,
            color_fresh=self.config.color_fresh,
            color_idle=self.config.color_idle,
            external_lookup_url=self._lookup_url_edit.text(),
            ocr_engine=self._ocr_combo.currentData(),
            show_pinyin=self._show_pinyin_check.isChecked(),
            pinyin_max_chars=self._pinyin_max_spin.value(),
            traditional_to_simplified=self._trad_to_simp_check.isChecked(),
            ms_translator_enabled=self._ms_enabled_check.isChecked(),
            ms_translator_api_key=self._ms_api_key_edit.text(),
            ms_translator_region=self.config.ms_translator_region,
            deepl_enabled=self._deepl_enabled_check.isChecked(),
            deepl_api_key=self._deepl_key_edit.text(),
            deepl_pro=self.config.deepl_pro,
        )

    def closeEvent(self, event):
        if not self._skip_close_check and self._dirty:
            if QMessageBox.question(self, "Unsaved Changes", "Save before closing?", QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard) == QMessageBox.StandardButton.Save:
                self._on_apply()
        event.accept()
