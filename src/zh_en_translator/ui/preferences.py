"""Preferences dialog for zh-en-translator."""

from __future__ import annotations

import dataclasses

import time as _time

from PyQt6.QtCore import pyqtSignal, QThread, QTimer, QUrl
from PyQt6.QtGui import QColor, QDesktopServices
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
    QPushButton,
    QColorDialog,
    QComboBox,
    QGroupBox,
    QCheckBox,
    QFrame,
    QMessageBox,
    QApplication,
    QFileDialog,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QTextBrowser,
    QScrollArea,
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

# Curated font list shown in the font picker (user can still type any name)
_FONT_CHOICES = [
    "",                        # (system default)
    "Aptos",
    "Aptos Display",
    "Segoe UI Variable Display",
    "Segoe UI",
    "Calibri",
    "Arial",
    "Verdana",
    "Tahoma",
    "Trebuchet MS",
    "Georgia",
    "Cambria",
    "Consolas",
    "Courier New",
    "Microsoft YaHei",
    "Microsoft JhengHei",
    "SimSun",
    "SimHei",
    "Noto Sans",
]

_SPIN_FRAMES = ('⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏')
_INSTALL_LOG_NAME = 'zh-en-translator-elevated-setup.log'

# Muted style for "Reinstall" buttons (already installed, but re-clickable)
_REINSTALL_STYLE = (
    "QPushButton { color: #888; background: rgba(0,0,0,0.03); "
    "border: 1px solid rgba(0,0,0,0.08); border-radius: 12px; padding: 5px 15px; }"
    "QPushButton:hover { color: #333; background: rgba(0,0,0,0.06); }"
)


class _InstallMonitor:
    """Polls the elevated-setup log file and drives a spinner QLabel in the UI.

    The elevated PowerShell process writes timestamped lines to the log. This
    monitor reads the last non-empty line every tick, strips the timestamp
    prefix, and updates the label with a braille spinner + message + elapsed
    time counter. It stops when it sees 'SETUP_STATUS:' in the log.
    """

    def __init__(self, status_label: 'QLabel', on_done):
        import tempfile
        self._log_path = os.path.join(
            tempfile.gettempdir(), _INSTALL_LOG_NAME
        )
        self._label = status_label
        self._on_done = on_done
        self._frame = 0
        self._start = 0.0
        self._last_msg = ''
        self._timer = QTimer()
        self._timer.timeout.connect(self._tick)

    def start(self) -> None:
        self._start = _time.monotonic()
        self._last_msg = ''
        self._frame = 0
        self._label.setVisible(True)
        self._label.setText('⠋  Starting installer…  (0:00)')
        self._label.setStyleSheet('color: #555;')
        self._timer.start(150)

    def stop(self) -> None:
        self._timer.stop()

    def _elapsed(self) -> str:
        s = int(_time.monotonic() - self._start)
        return f'{s // 60}:{s % 60:02d}'

    def _read_last_line(self) -> str:
        try:
            with open(self._log_path, encoding='utf-8-sig', errors='replace') as fh:
                lines = fh.readlines()
            for raw in reversed(lines):
                line = raw.strip()
                if not line:
                    continue
                # strip "[YYYY-MM-DD HH:MM:SS] " prefix written by Write-Log
                if line.startswith('[') and '] ' in line:
                    line = line[line.index('] ') + 2:]
                return line
        except OSError:
            pass
        return self._last_msg

    def _tick(self) -> None:
        self._frame = (self._frame + 1) % len(_SPIN_FRAMES)
        line = self._read_last_line()
        if line:
            self._last_msg = line

        if 'SETUP_STATUS:' in self._last_msg:
            self.stop()
            success = 'SUCCESS' in self._last_msg
            if success:
                self._label.setText('✓  Setup complete')
                self._label.setStyleSheet('color: #1a7a1a; font-weight: bold;')
            else:
                self._label.setText('Setup encountered errors — check the log')
                self._label.setStyleSheet('color: #b85c00; font-weight: bold;')
            self._on_done(success)
            return

        spin = _SPIN_FRAMES[self._frame]
        msg = self._last_msg or 'Starting…'
        self._label.setText(f'{spin}  {msg}  ({self._elapsed()})')
        self._label.setStyleSheet('color: #555;')


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


class _ArgosDownloadWorker(QThread):
    """Background thread: downloads and installs the Argos zh->en translation pack."""

    progress = pyqtSignal(str)   # status message
    finished = pyqtSignal(bool)  # True = success

    def run(self):
        try:
            import argostranslate.package as pkg
            self.progress.emit("Updating package index…")
            pkg.update_package_index()
            available = pkg.get_available_packages()
            zh_en = next(
                (p for p in available if p.from_code == "zh" and p.to_code == "en"),
                None,
            )
            if zh_en is None:
                self.progress.emit("zh->en pack not found in Argos index")
                self.finished.emit(False)
                return
            self.progress.emit(f"Downloading model (version {zh_en.package_version})…")
            zh_en.install()
            from zh_en_translator.install_state import update_components
            update_components(argos=True)
            self.finished.emit(True)
        except ImportError:
            self.progress.emit("argostranslate not found — app may need reinstalling")
            self.finished.emit(False)
        except Exception as exc:
            self.progress.emit(f"Error: {exc}")
            self.finished.emit(False)


class PreferencesDialog(QDialog):
    """Tabbed preferences dialog for zh-en-translator settings."""

    settings_applied = pyqtSignal(object)  # emits Config

    def __init__(self, config: Config, parent=None,
                 update_available: bool = False, update_version: str = ""):
        super().__init__(parent)
        self.config = dataclasses.replace(config)
        self._update_available = update_available
        self._update_version = update_version

        # Unsaved-changes tracking
        self._dirty = False
        self._skip_close_check = False

        self.setWindowTitle("Preferences")
        self.setMinimumWidth(540)
        self._apply_global_styling()

        self._install_monitor: '_InstallMonitor | None' = None
        self._argos_worker: '_ArgosDownloadWorker | None' = None
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
        self._tabs.addTab(self._build_help_tab(),       "Help")
        self._tabs.addTab(self._build_about_tab(),      "About")

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

        engine_group = QGroupBox("Translation Engine")
        engine_layout = QVBoxLayout(engine_group)
        seg_row = QHBoxLayout()
        seg_row.addWidget(QLabel("Word segmenter:"))
        self._segmenter_combo = QComboBox()
        self._segmenter_combo.addItem("jieba  (default, fast)", userData="jieba")
        self._segmenter_combo.addItem("pkuseg  (accurate, slower)", userData="pkuseg")
        seg_row.addWidget(self._segmenter_combo)
        seg_row.addStretch()
        engine_layout.addLayout(seg_row)
        self._clause_fallback_check = QCheckBox(
            "Enable clause-level fallback for complex sentences"
        )
        engine_layout.addWidget(self._clause_fallback_check)
        layout.addWidget(engine_group)

        update_group = QGroupBox("Updates && Startup")
        update_layout = QVBoxLayout(update_group)

        # Version row
        from zh_en_translator import __version__
        ver_row = QHBoxLayout()
        ver_row.addWidget(QLabel(f"Version: {__version__}"))
        ver_row.addStretch()
        update_layout.addLayout(ver_row)

        # Update-available banner (hidden until an update is found)
        self._update_banner = QLabel()
        self._update_banner.setStyleSheet(
            "color: #B45309; background: #FEF3C7; border: 1px solid #FCD34D; "
            "border-radius: 6px; padding: 4px 8px;"
        )
        self._update_banner.setVisible(False)
        update_layout.addWidget(self._update_banner)

        import sys as _sys
        _startup_label = "Launch at Windows login" if _sys.platform == "win32" else "Launch at login"
        self._startup_check = QCheckBox(_startup_label)
        update_layout.addWidget(self._startup_check)
        self._auto_update_check = QCheckBox("Check for updates automatically on startup")
        update_layout.addWidget(self._auto_update_check)
        self._btn_check_now = QPushButton("Check for Updates Now")
        self._btn_check_now.setFixedWidth(180)
        self._btn_check_now.clicked.connect(self._check_updates_now)
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
        self._font_combo = QComboBox()
        self._font_combo.setEditable(True)
        self._font_combo.setMaxVisibleItems(15)
        for name in _FONT_CHOICES:
            self._font_combo.addItem(name if name else "(system default)", userData=name)
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
            if hasattr(w, "currentIndexChanged"):
                w.currentIndexChanged.connect(self._update_preview)
            else:
                w.valueChanged.connect(self._update_preview)
        self._font_combo.editTextChanged.connect(self._update_preview)
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
        pos_hint = QLabel(
            "Interactive repositioning enabled: drag the strip to move, edge to resize."
        )
        pos_hint.setStyleSheet("color: gray; font-size: 9pt;")
        layout.addWidget(pos_hint)

        width_group = QGroupBox("Width")
        width_layout = QHBoxLayout(width_group)
        width_layout.addWidget(QLabel("Sidebar width:"))
        self._sidebar_width_spin = QSpinBox()
        self._sidebar_width_spin.setRange(150, 600)
        self._sidebar_width_spin.setSuffix(" px")
        width_layout.addWidget(self._sidebar_width_spin)
        width_layout.addStretch()
        layout.addWidget(width_group)

        colors_group = QGroupBox("Strip Indicator Colors")
        colors_layout = QVBoxLayout(colors_group)
        fresh_row = QHBoxLayout()
        fresh_row.addWidget(QLabel("Fresh translation:"))
        self._color_fresh_btn = _ColorSwatchButton()
        fresh_row.addWidget(self._color_fresh_btn)
        fresh_row.addStretch()
        colors_layout.addLayout(fresh_row)
        idle_row = QHBoxLayout()
        idle_row.addWidget(QLabel("Idle:"))
        self._color_idle_btn = _ColorSwatchButton()
        idle_row.addWidget(self._color_idle_btn)
        idle_row.addStretch()
        colors_layout.addLayout(idle_row)
        layout.addWidget(colors_group)

        layout.addStretch()
        return widget

    def _build_lookup_ocr_tab(self) -> QWidget:
        import sys
        import os
        from zh_en_translator.engines.ocr import windows_ocr as _wocr

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

        # ---- Offline Translation Model group ----
        from zh_en_translator.engines.argos import is_available as _argos_available
        _argos_installed = _argos_available()

        argos_group = QGroupBox("Offline Translation Model")
        argos_layout = QVBoxLayout(argos_group)

        if _argos_installed:
            self._argos_static_lbl = QLabel("Argos zh\u2192en model: Installed")
            self._argos_static_lbl.setStyleSheet("color: #1a7a1a; font-weight: bold;")
        else:
            self._argos_static_lbl = QLabel(
                "Offline translation model not installed.\n"
                "Download to enable translation without cloud services (~100 MB).\n"
                "Cloud translation (DeepL / Azure) still works without this model."
            )
            self._argos_static_lbl.setStyleSheet("color: #b85c00;")
        self._argos_static_lbl.setWordWrap(True)
        argos_layout.addWidget(self._argos_static_lbl)

        argos_btn_row = QHBoxLayout()
        self._btn_argos_download = QPushButton(
            "Re-download Model" if _argos_installed else "Download Offline Model (~100 MB)"
        )
        if _argos_installed:
            self._btn_argos_download.setStyleSheet(_REINSTALL_STYLE)
        self._btn_argos_download.clicked.connect(self._do_argos_download)
        argos_btn_row.addWidget(self._btn_argos_download)
        argos_btn_row.addStretch()
        argos_layout.addLayout(argos_btn_row)

        self._argos_status_lbl = QLabel()
        self._argos_status_lbl.setWordWrap(True)
        self._argos_status_lbl.setVisible(False)
        argos_layout.addWidget(self._argos_status_lbl)

        layout.addWidget(argos_group)

        ocr_group = QGroupBox("OCR Engine")
        ocr_layout = QVBoxLayout(ocr_group)
        self._ocr_combo = QComboBox()
        ocr_engine_choices = [("Auto", "auto"), ("Tesseract", "tesseract"), ("PaddleOCR", "paddle")]
        if sys.platform == "win32":
            ocr_engine_choices.insert(1, ("Windows", "windows"))
        for lbl_text, val in ocr_engine_choices:
            self._ocr_combo.addItem(lbl_text, val)
        ocr_layout.addWidget(self._ocr_combo)
        layout.addWidget(ocr_group)

        # ---- Windows OCR group (Windows only) ----
        self._btn_win_ocr_install = None
        self._win_ocr_status_lbl = QLabel()
        self._win_ocr_status_lbl.setWordWrap(True)
        self._win_ocr_status_lbl.setVisible(False)

        if sys.platform == "win32":
            win_group = QGroupBox("Windows OCR (primary engine)")
            win_layout = QVBoxLayout(win_group)

            wstatus = _wocr.ocr_status()

            if not wstatus["api"]:
                self._win_ocr_static_lbl = QLabel(
                    "Windows OCR API unavailable — winrt/winsdk package not installed."
                )
                self._win_ocr_static_lbl.setWordWrap(True)
                self._win_ocr_static_lbl.setStyleSheet("color: #888;")
                win_layout.addWidget(self._win_ocr_static_lbl)
            else:
                if not wstatus["chinese"]:
                    self._win_ocr_static_lbl = QLabel(
                        "Windows OCR ready, but no Chinese language pack is installed.\n"
                        "OCR will fall back to Tesseract until the Chinese pack is added."
                    )
                    self._win_ocr_static_lbl.setStyleSheet("color: #b85c00; font-weight: bold;")
                else:
                    self._win_ocr_static_lbl = QLabel(
                        "Windows OCR: ready — Chinese language pack installed."
                    )
                    self._win_ocr_static_lbl.setStyleSheet("color: #1a7a1a; font-weight: bold;")
                self._win_ocr_static_lbl.setWordWrap(True)
                win_layout.addWidget(self._win_ocr_static_lbl)

                self._btn_win_ocr_install = QPushButton(
                    "Reinstall Chinese OCR" if wstatus["chinese"]
                    else "Install Chinese OCR (requires admin)"
                )
                if wstatus["chinese"]:
                    self._btn_win_ocr_install.setStyleSheet(_REINSTALL_STYLE)
                self._btn_win_ocr_install.clicked.connect(
                    lambda: self._do_install(self._btn_win_ocr_install, self._win_ocr_status_lbl)
                )
                win_layout.addWidget(self._btn_win_ocr_install)

            win_layout.addWidget(self._win_ocr_status_lbl)
            layout.addWidget(win_group)

        # ---- Tesseract group ----
        if sys.platform == "win32":
            tess_title = "Tesseract Status (optional fallback — Windows OCR is primary)"
        else:
            tess_title = "Tesseract OCR"

        tess_group = QGroupBox(tess_title)
        tess_layout = QVBoxLayout(tess_group)

        from zh_en_translator.engines.ocr import tesseract_ocr as _tess
        tess_available = _tess.is_available()
        tess_path = _tess.get_found_path()

        if tess_available:
            self._tess_static_lbl = QLabel(f"Tesseract: Found at {tess_path}")
            self._tess_static_lbl.setStyleSheet("color: #1a7a1a; font-weight: bold;")
        elif sys.platform == "win32":
            self._tess_static_lbl = QLabel(
                "Tesseract not found. OCR still works via Windows OCR (the primary engine).\n"
                "Install Tesseract only if Windows OCR is unavailable on your system."
            )
            self._tess_static_lbl.setWordWrap(True)
            self._tess_static_lbl.setStyleSheet("color: #555;")
        else:
            self._tess_static_lbl = QLabel(
                "Tesseract not found. Install it to enable OCR:\n"
                "  Debian/Ubuntu: sudo apt install tesseract-ocr tesseract-ocr-chi-sim\n"
                "  Fedora: sudo dnf install tesseract tesseract-langpack-chi-sim\n"
                "  Arch: sudo pacman -S tesseract tesseract-data-chi_sim\n"
                "  Flatpak: Tesseract is bundled — restart the app if missing."
            )
            self._tess_static_lbl.setWordWrap(True)
            self._tess_static_lbl.setStyleSheet("color: #b85c00;")
        tess_layout.addWidget(self._tess_static_lbl)

        btn_row = QHBoxLayout()
        self._btn_tess_install = None

        if sys.platform == "win32":
            self._btn_tess_install = QPushButton(
                "Reinstall Tesseract" if tess_available else "Install Tesseract"
            )
            if tess_available:
                self._btn_tess_install.setStyleSheet(_REINSTALL_STYLE)
            self._btn_tess_install.clicked.connect(
                lambda: self._do_install(self._btn_tess_install, self._tess_status_lbl)
            )
            btn_row.addWidget(self._btn_tess_install)

        def _open_tess_log():
            import subprocess
            import tempfile
            log_path = os.path.join(
                tempfile.gettempdir(),
                "zh-en-translator-elevated-setup.log",
            )
            if os.path.isfile(log_path):
                if sys.platform == "win32":
                    subprocess.Popen(["notepad.exe", log_path])
                else:
                    subprocess.Popen(["xdg-open", log_path])
            else:
                QMessageBox.information(
                    self, "Log Not Found",
                    f"No install log found at:\n{log_path}\n\n"
                    "Click 'Install Tesseract' to run the installer.",
                )

        if sys.platform == "win32":
            btn_open_log = QPushButton("View Log")
            btn_open_log.clicked.connect(_open_tess_log)
            btn_row.addWidget(btn_open_log)
        btn_row.addStretch()
        tess_layout.addLayout(btn_row)

        self._tess_status_lbl = QLabel()
        self._tess_status_lbl.setWordWrap(True)
        self._tess_status_lbl.setVisible(False)
        tess_layout.addWidget(self._tess_status_lbl)

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
        self._glossary_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch
        )
        self._glossary_table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch
        )
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
            QMessageBox.information(
                self, "Import Glossary", "No valid entries found in the selected file."
            )
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
        warning_box.setStyleSheet(
            "background: #FFF4F0; border: 1px solid #CC4400; border-radius: 8px;"
        )
        w_layout = QVBoxLayout(warning_box)
        w_layout.addWidget(QLabel(_CLOUD_WARNING))
        layout.addWidget(warning_box)

        ms_group = QGroupBox("Azure Translator")
        ms_layout = QVBoxLayout(ms_group)
        self._ms_enabled_check = QCheckBox("Enable Azure Cloud translation")
        ms_layout.addWidget(self._ms_enabled_check)
        ms_layout.addWidget(QLabel("API Key:"))
        self._ms_api_key_edit = QLineEdit()
        self._ms_api_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        ms_layout.addWidget(self._ms_api_key_edit)
        ms_layout.addWidget(QLabel("Region (e.g. westeurope):"))
        self._ms_region_edit = QLineEdit()
        self._ms_region_edit.setPlaceholderText("Leave empty if not required")
        ms_layout.addWidget(self._ms_region_edit)
        layout.addWidget(ms_group)

        deepl_group = QGroupBox("DeepL")
        deepl_layout = QVBoxLayout(deepl_group)
        self._deepl_enabled_check = QCheckBox("Enable DeepL translation")
        deepl_layout.addWidget(self._deepl_enabled_check)
        deepl_layout.addWidget(QLabel("API Key:"))
        self._deepl_key_edit = QLineEdit()
        self._deepl_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        deepl_layout.addWidget(self._deepl_key_edit)
        self._deepl_pro_check = QCheckBox("Use DeepL Pro API endpoint")
        deepl_layout.addWidget(self._deepl_pro_check)
        layout.addWidget(deepl_group)

        google_group = QGroupBox("Google Cloud Translation")
        google_layout = QVBoxLayout(google_group)
        self._google_enabled_check = QCheckBox("Enable Google Cloud Translation")
        google_layout.addWidget(self._google_enabled_check)
        google_layout.addWidget(QLabel("API Key (GCP Cloud Translation API v2):"))
        self._google_key_edit = QLineEdit()
        self._google_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self._google_key_edit.setPlaceholderText("AIza...")
        google_layout.addWidget(self._google_key_edit)
        google_hint = QLabel(
            "Requires a GCP project with Cloud Translation API enabled.\n"
            "Pricing: $20 / 1M characters (500K chars/month free tier)."
        )
        google_hint.setStyleSheet("color: gray; font-size: 9pt;")
        google_hint.setWordWrap(True)
        google_layout.addWidget(google_hint)
        layout.addWidget(google_group)

        libre_group = QGroupBox("LibreTranslate (free / self-hosted)")
        libre_layout = QVBoxLayout(libre_group)
        self._libre_enabled_check = QCheckBox("Enable LibreTranslate")
        libre_layout.addWidget(self._libre_enabled_check)
        libre_layout.addWidget(QLabel("Instance URL:"))
        self._libre_url_edit = QLineEdit()
        self._libre_url_edit.setPlaceholderText("https://libretranslate.com")
        libre_layout.addWidget(self._libre_url_edit)
        libre_layout.addWidget(QLabel("API Key (leave blank if not required):"))
        self._libre_key_edit = QLineEdit()
        self._libre_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        libre_layout.addWidget(self._libre_key_edit)
        libre_hint = QLabel(
            "Free public instances: translate.argosopentech.com \u00b7 libretranslate.de\n"
            "No account needed on most instances. Self-host for unlimited, private use."
        )
        libre_hint.setStyleSheet("color: gray; font-size: 9pt;")
        libre_hint.setWordWrap(True)
        libre_layout.addWidget(libre_hint)
        layout.addWidget(libre_group)

        layout.addStretch()
        return widget

    def _update_preview(self):
        from zh_en_translator.engines.themes import resolve_palette
        theme = self._theme_combo.currentData() or "system"
        bg_col = self._bg_color_btn.get_color_str()
        palette = resolve_palette(theme, False)
        bg = bg_col if bg_col else palette.bg
        self._preview_frame.setStyleSheet(
            f"background: {bg}; border: 1px solid {palette.border};"
            f" border-radius: 12px; color: {palette.text};"
        )
        ff = (
            self._font_combo.currentData()
            if self._font_combo.currentIndex() >= 0
            else self._font_combo.currentText().strip()
        )
        fs = self._font_size_spin.value()
        font_css = f"font-family: '{ff}'; font-size: {fs}pt;" if ff else f"font-size: {fs}pt;"
        for lbl in (self._preview_pinyin, self._preview_source, self._preview_trans):
            lbl.setStyleSheet(font_css)

    def _on_apply(self):
        self.config = self._collect_config()
        save_config(self.config)
        from zh_en_translator.engines.glossary import save_glossary
        save_glossary(self._glossary_get_terms())
        self.settings_applied.emit(self.config)
        self._dirty = False

    def _on_ok(self):
        self._skip_close_check = True
        self._on_apply()
        self.accept()

    def _on_cancel(self):
        self._skip_close_check = True
        self.reject()

    def _mark_dirty(self):
        self._dirty = True

    def _connect_dirty_signals(self):
        for w in self.findChildren((QLineEdit, QCheckBox, QComboBox, QSpinBox, QRadioButton)):
            if hasattr(w, "textChanged"):
                w.textChanged.connect(self._mark_dirty)
            if hasattr(w, "toggled"):
                w.toggled.connect(self._mark_dirty)

    def _load_config_into_ui(self):
        cfg = self.config
        # General tab
        self._hotkey_edit.setText(cfg.hotkey)
        (self._mode_sidebar if cfg.mode == "sidebar" else self._mode_popup).setChecked(True)
        self._trad_to_simp_check.setChecked(cfg.traditional_to_simplified)
        self._auto_update_check.setChecked(cfg.auto_check_updates)
        self._startup_check.setChecked(cfg.startup)
        if self._update_available and self._update_version:
            self._show_update_banner(self._update_version)
        idx = self._segmenter_combo.findData(cfg.segmenter)
        self._segmenter_combo.setCurrentIndex(idx if idx >= 0 else 0)
        self._clause_fallback_check.setChecked(cfg.clause_fallback_enabled)
        # Display tab
        idx = self._theme_combo.findData(cfg.theme)
        self._theme_combo.setCurrentIndex(idx if idx >= 0 else 0)
        ff = cfg.font_family or ""
        fidx = self._font_combo.findData(ff)
        if fidx >= 0:
            self._font_combo.setCurrentIndex(fidx)
        elif ff:
            self._font_combo.setCurrentText(ff)
        else:
            self._font_combo.setCurrentIndex(0)
        self._font_size_spin.setValue(cfg.font_size)
        self._bg_color_btn.set_color_str(cfg.bg_color)
        self._show_pinyin_check.setChecked(cfg.show_pinyin)
        self._pinyin_max_spin.setValue(cfg.pinyin_max_chars)
        self._pinyin_max_spin.setEnabled(cfg.show_pinyin)
        # Sidebar tab
        (self._side_right if cfg.side == "right" else self._side_left).setChecked(True)
        self._sidebar_width_spin.setValue(cfg.sidebar_width)
        self._color_fresh_btn.set_color_str(cfg.color_fresh)
        self._color_idle_btn.set_color_str(cfg.color_idle)
        # Lookup & OCR tab
        self._lookup_url_edit.setText(cfg.external_lookup_url)
        idx = self._ocr_combo.findData(cfg.ocr_engine)
        self._ocr_combo.setCurrentIndex(idx if idx >= 0 else 0)
        # Glossary tab
        from zh_en_translator.engines.glossary import load_glossary
        self._glossary_load_terms(load_glossary())
        # Cloud tab
        self._ms_enabled_check.setChecked(cfg.ms_translator_enabled)
        self._ms_api_key_edit.setText(cfg.ms_translator_api_key)
        self._ms_region_edit.setText(cfg.ms_translator_region)
        self._deepl_enabled_check.setChecked(cfg.deepl_enabled)
        self._deepl_key_edit.setText(cfg.deepl_api_key)
        self._deepl_pro_check.setChecked(cfg.deepl_pro)
        self._google_enabled_check.setChecked(cfg.google_translate_enabled)
        self._google_key_edit.setText(cfg.google_translate_api_key)
        self._libre_enabled_check.setChecked(cfg.libretranslate_enabled)
        self._libre_url_edit.setText(cfg.libretranslate_url)
        self._libre_key_edit.setText(cfg.libretranslate_api_key)
        self._update_preview()
        self._connect_dirty_signals()

    def _collect_config(self) -> Config:
        return Config(
            hotkey=self._hotkey_edit.text(),
            mode="sidebar" if self._mode_sidebar.isChecked() else "popup",
            startup=self._startup_check.isChecked(),
            auto_check_updates=self._auto_update_check.isChecked(),
            font_family=(
                self._font_combo.currentData()
                if self._font_combo.currentIndex() >= 0
                else self._font_combo.currentText().strip()
            ),
            font_size=self._font_size_spin.value(),
            bg_color=self._bg_color_btn.get_color_str(),
            theme=self._theme_combo.currentData(),
            side="left" if self._side_left.isChecked() else "right",
            sidebar_y=self.config.sidebar_y,
            sidebar_width=self._sidebar_width_spin.value(),
            color_fresh=self._color_fresh_btn.get_color_str() or "#00C9CC",
            color_idle=self._color_idle_btn.get_color_str() or "#9E8080",
            external_lookup_url=self._lookup_url_edit.text(),
            ocr_engine=self._ocr_combo.currentData(),
            show_pinyin=self._show_pinyin_check.isChecked(),
            pinyin_max_chars=self._pinyin_max_spin.value(),
            traditional_to_simplified=self._trad_to_simp_check.isChecked(),
            clause_fallback_enabled=self._clause_fallback_check.isChecked(),
            segmenter=self._segmenter_combo.currentData() or "jieba",
            ms_translator_enabled=self._ms_enabled_check.isChecked(),
            ms_translator_api_key=self._ms_api_key_edit.text(),
            ms_translator_region=self._ms_region_edit.text().strip(),
            deepl_enabled=self._deepl_enabled_check.isChecked(),
            deepl_api_key=self._deepl_key_edit.text(),
            deepl_pro=self._deepl_pro_check.isChecked(),
            google_translate_enabled=self._google_enabled_check.isChecked(),
            google_translate_api_key=self._google_key_edit.text(),
            libretranslate_enabled=self._libre_enabled_check.isChecked(),
            libretranslate_url=self._libre_url_edit.text().strip() or "https://libretranslate.com",
            libretranslate_api_key=self._libre_key_edit.text(),
            last_update_check=self.config.last_update_check,
        )

    def _do_argos_download(self) -> None:
        """Start Argos model download in a background thread."""
        if self._argos_worker is not None:
            return  # already running
        self._btn_argos_download.setEnabled(False)
        self._btn_argos_download.setText("Downloading\u2026")
        self._btn_argos_download.setStyleSheet("")
        self._argos_status_lbl.setVisible(True)
        self._argos_status_lbl.setStyleSheet("color: #555;")
        self._argos_status_lbl.setText("\u29d6  Starting download\u2026")

        self._argos_worker = _ArgosDownloadWorker()
        self._argos_worker.progress.connect(self._on_argos_progress)
        self._argos_worker.finished.connect(self._on_argos_done)
        self._argos_worker.start()

    def _on_argos_progress(self, msg: str) -> None:
        self._argos_status_lbl.setText(f"\u29d6  {msg}")

    def _on_argos_done(self, success: bool) -> None:
        self._argos_worker = None
        self._btn_argos_download.setEnabled(True)
        if success:
            self._btn_argos_download.setText("Re-download Model")
            self._btn_argos_download.setStyleSheet(_REINSTALL_STYLE)
            self._argos_static_lbl.setText("Argos zh\u2192en model: Installed")
            self._argos_static_lbl.setStyleSheet("color: #1a7a1a; font-weight: bold;")
            self._argos_status_lbl.setText("\u2713  Model installed — restart the app to use offline translation")
            self._argos_status_lbl.setStyleSheet("color: #1a7a1a; font-weight: bold;")
        else:
            self._btn_argos_download.setText("Retry Download")
            self._btn_argos_download.setStyleSheet("")
            self._argos_status_lbl.setStyleSheet("color: #b85c00; font-weight: bold;")
            # keep whatever error message was last emitted via _on_argos_progress

    def _do_install(self, trigger_btn: QPushButton, status_lbl: QLabel) -> None:
        """Launch setup_elevated.ps1 elevated and start the spinner monitor."""
        import ctypes
        import sys
        import pathlib

        if self._install_monitor is not None:
            return  # already running

        candidates = [
            pathlib.Path(sys.executable).parent / "setup_elevated.ps1",
            pathlib.Path(__file__).parents[3] / "installer" / "setup_elevated.ps1",
        ]
        script = next((p for p in candidates if p.exists()), None)
        if not script:
            QMessageBox.warning(
                self, "Script Not Found",
                "setup_elevated.ps1 not found.\n\n"
                "Install manually via Windows Settings -> Time & Language -> "
                "Language & Region -> Add a language (Chinese Simplified).",
            )
            return

        args = f'-ExecutionPolicy Bypass -WindowStyle Normal -File "{script}"'
        ret = ctypes.windll.shell32.ShellExecuteW(
            None, "runas", "powershell.exe", args, str(script.parent), 1
        )
        if int(ret) == 5:  # user cancelled UAC — no message needed
            return
        if int(ret) <= 32:
            QMessageBox.warning(
                self, "Launch Failed",
                f"Could not start the elevated installer (error {int(ret)}).",
            )
            return

        trigger_btn.setEnabled(False)
        trigger_btn.setText("Installing…")
        trigger_btn.setStyleSheet("")

        def _on_done(success: bool) -> None:
            self._install_monitor = None
            self._refresh_install_buttons()

        self._install_monitor = _InstallMonitor(status_lbl, _on_done)
        self._install_monitor.start()

    def _refresh_install_buttons(self) -> None:
        """Re-probe install state after setup completes and update button labels/styles."""
        import sys
        from zh_en_translator.engines.ocr import windows_ocr as _wocr
        from zh_en_translator.engines.ocr import tesseract_ocr as _tess

        if self._btn_tess_install is not None:
            tess_available = _tess.is_available()
            tess_path = _tess.get_found_path()
            self._btn_tess_install.setEnabled(True)
            if tess_available:
                self._btn_tess_install.setText("Reinstall Tesseract")
                self._btn_tess_install.setStyleSheet(_REINSTALL_STYLE)
                self._tess_static_lbl.setText(f"Tesseract: Found at {tess_path}")
                self._tess_static_lbl.setStyleSheet("color: #1a7a1a; font-weight: bold;")
            else:
                self._btn_tess_install.setText("Install Tesseract")
                self._btn_tess_install.setStyleSheet("")
                self._tess_static_lbl.setText(
                    "Tesseract not found. OCR still works via Windows OCR (the primary engine).\n"
                    "Install Tesseract only if Windows OCR is unavailable on your system."
                )
                self._tess_static_lbl.setStyleSheet("color: #555;")

        if self._btn_win_ocr_install is not None:
            wstatus = _wocr.ocr_status()
            self._btn_win_ocr_install.setEnabled(True)
            if wstatus["chinese"]:
                self._btn_win_ocr_install.setText("Reinstall Chinese OCR")
                self._btn_win_ocr_install.setStyleSheet(_REINSTALL_STYLE)
                self._win_ocr_static_lbl.setText(
                    "Windows OCR: ready — Chinese language pack installed."
                )
                self._win_ocr_static_lbl.setStyleSheet("color: #1a7a1a; font-weight: bold;")
            else:
                self._btn_win_ocr_install.setText("Install Chinese OCR (requires admin)")
                self._btn_win_ocr_install.setStyleSheet("")

    def _show_update_banner(self, version: str) -> None:
        self._update_banner.setText(
            f"\u25cf  Update available: {version} -- click 'Check for Updates Now' to download."
        )
        self._update_banner.setVisible(True)

    def _check_updates_now(self):
        from zh_en_translator.engines.updates import get_latest_release, is_newer
        from zh_en_translator import __version__
        self._btn_check_now.setEnabled(False)
        self._btn_check_now.setText("Checking\u2026")
        QApplication.processEvents()
        try:
            info = get_latest_release()
        finally:
            self._btn_check_now.setEnabled(True)
            self._btn_check_now.setText("Check for Updates Now")
        if info is None:
            self._update_banner.setVisible(False)
            QMessageBox.information(
                self, "Update Check",
                "Could not reach the update server. Check your internet connection.",
            )
        elif is_newer(info["tag_name"], __version__):
            self._show_update_banner(info["tag_name"])
            import webbrowser
            if QMessageBox.question(
                self, "Update Available",
                f"A new version is available: {info['tag_name']}\n\nOpen download page?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            ) == QMessageBox.StandardButton.Yes:
                webbrowser.open(info["html_url"])
        else:
            self._update_banner.setVisible(False)
            QMessageBox.information(
                self, "Up to Date",
                f"You are running the latest version ({__version__}).",
            )

    # ------------------------------------------------------------------
    # Help tab
    # ------------------------------------------------------------------

    def _build_help_tab(self) -> QWidget:
        import sys as _sys

        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)

        browser = QTextBrowser()
        browser.setOpenLinks(False)
        browser.anchorClicked.connect(self._on_help_link)
        browser.setStyleSheet("QTextBrowser { border: none; background: transparent; }")

        # Format the configured hotkey into a readable form, e.g. <ctrl>+<shift>+t -> Ctrl+Shift+T
        def _fmt_hotkey(hk: str) -> str:
            parts = hk.split("+")
            out = []
            for p in parts:
                p = p.strip().strip("<>")
                out.append(p.capitalize() if len(p) > 1 else p.upper())
            return "+".join(out)

        hotkey = _fmt_hotkey(self.config.hotkey or "<ctrl>+<shift>+t")

        if _sys.platform == "win32":
            _screenshot_hint = "e.g. a screenshot with <code>Win+Shift+S</code>"
            _ocr_engines = (
                "<li>On Windows, <b>Windows OCR</b> is the primary engine "
                "(requires the Chinese language pack).</li>"
                "<li>Falls back automatically to <b>Tesseract</b> if Windows OCR is unavailable.</li>"
            )
        else:
            _screenshot_hint = "e.g. a screenshot"
            _ocr_engines = (
                "<li><b>Tesseract</b> is the primary OCR engine on Linux/macOS.</li>"
                "<li>Install: <code>sudo apt install tesseract-ocr tesseract-ocr-chi-sim</code> "
                "(Debian/Ubuntu), or see Preferences &rsaquo; Lookup &amp; OCR for other distros.</li>"
                "<li>PaddleOCR can be installed for higher accuracy.</li>"
            )

        ocr_section = (
            f"<h2>OCR &mdash; Translating Text in Images</h2>"
            f"<p>Copy an image containing Chinese text ({_screenshot_hint}), "
            f"then press <code>{hotkey}</code>. The app detects the image on the clipboard "
            f"and runs OCR automatically.</p>"
            f"<ul>{_ocr_engines}</ul>"
            f"<p><a href=\"pref://lookup\">Configure OCR engine &rarr; "
            f"Preferences &rsaquo; Lookup &amp; OCR</a></p>"
        )

        html = f"""
<style>
  body {{ margin: 8px 12px; }}
  h2 {{ font-size: 11pt; margin-top: 18px; margin-bottom: 4px;
        border-bottom: 1px solid rgba(0,0,0,0.10); padding-bottom: 3px; }}
  h2.first {{ margin-top: 4px; }}
  p, li {{ margin: 3px 0; line-height: 1.55; }}
  ul, ol {{ padding-left: 22px; margin: 4px 0; }}
  table {{ width: 100%; border-collapse: collapse; margin: 6px 0; font-size: 9.5pt; }}
  th {{ text-align: left; padding: 4px 8px; background: rgba(0,0,0,0.06); font-weight: bold; }}
  td {{ padding: 3px 8px; border-bottom: 1px solid rgba(0,0,0,0.06); vertical-align: top; }}
  tr:last-child td {{ border-bottom: none; }}
  code {{ background: rgba(0,0,0,0.07); border-radius: 3px; padding: 1px 5px;
          font-family: Consolas, 'Courier New', monospace; font-size: 9pt; }}
  a {{ color: #0078D4; text-decoration: none; }}
  .note {{ color: #666; font-style: italic; font-size: 9pt; }}
  .warn {{ color: #B45309; }}
</style>

<h2 class="first">Quick Start</h2>
<ol>
  <li>
    <b>Copy</b> Chinese text with <code>Ctrl+C</code>.<br>
    <span class="note">Tip: copy rather than just highlight &mdash; some applications do not
    expose selected text to other programs. Copying first ensures the text is available.</span>
  </li>
  <li>Press <code>{hotkey}</code> from anywhere on your desktop.</li>
  <li>The translation popup appears at your cursor with the English translation,
      pinyin romanisation, and action buttons.</li>
</ol>

<h2>Popup Controls</h2>
<table>
  <tr><th>Control</th><th>Action</th></tr>
  <tr><td><b>&#x21BA;</b> button</td>
      <td>Edit the source text, then click &#x21BA; or press <code>Ctrl+Enter</code> to retranslate.</td></tr>
  <tr><td><b>Copy</b></td><td>Copies the English translation to the clipboard.</td></tr>
  <tr><td><b>Replace</b></td>
      <td>Pastes the English translation back over the original text in the source application.</td></tr>
  <tr><td><b>Pin &rarr;</b></td><td>Sends the translation to the persistent sidebar panel.</td></tr>
  <tr><td><b>Look up</b></td><td>Opens the source text in MDBG online dictionary.</td></tr>
  <tr><td><b>&#x25BC; Details</b></td><td>Expands a word-by-word dictionary breakdown.</td></tr>
  <tr><td>&#x1F4CC; (header)</td>
      <td>Keeps the popup open when you click away, preventing auto-dismiss.</td></tr>
  <tr><td><b>&#x2715; / Esc</b></td><td>Dismiss the popup.</td></tr>
</table>

<h2>Sidebar Mode</h2>
<p>In sidebar mode the app shows a thin coloured strip at the screen edge instead of a popup.
Click the strip to expand it; the strip changes colour when a new translation arrives.</p>
<ul>
  <li>Drag the strip up/down to reposition it on the edge.</li>
  <li>Drag the inner edge to resize the panel width.</li>
  <li>The last 20 translations appear in the History list; export to CSV from the toolbar.</li>
</ul>
<p><a href="pref://general">Switch between popup and sidebar mode &rarr; Preferences &rsaquo; General</a></p>

{ocr_section}

<h2>Glossary &amp; Domain Terms</h2>
<p>Glossary terms override the translation engine for exact phrase matches &mdash;
useful for product names, abbreviations, or technical jargon.</p>
<ul>
  <li>Built-in domain glossaries: manufacturing (149 terms), medical (504), legal (409), electronics (452).</li>
  <li>Your user terms take the highest priority; built-in terms apply when no user term matches.</li>
</ul>
<p><a href="pref://glossary">Add or import user glossary terms &rarr; Preferences &rsaquo; Glossary</a></p>

<h2>Translation Pipeline</h2>
<p>Each translation request passes through these steps in order, stopping at the first success:</p>
<ol>
  <li>User glossary exact match (highest precedence)</li>
  <li>Domain glossaries (manufacturing &rarr; medical &rarr; legal &rarr; electronics)</li>
  <li>CC-CEDICT dictionary lookup + jieba word segmentation</li>
  <li><b>Cloud engines</b> (whichever are enabled, in priority order):
    <a href="pref://cloud">DeepL &rarr; Google &rarr; Azure &rarr; LibreTranslate</a></li>
  <li>Argos Translate &mdash; fully offline sentence translation
      (<a href="pref://lookup">download model &rarr; Preferences &rsaquo; Lookup &amp; OCR</a>)</li>
  <li>Dictionary-only result (fallback if all engines unavailable)</li>
</ol>

<h2>Cloud Translation</h2>
<p>By default the app is <b>fully offline</b> &mdash; no text leaves your machine.
Four cloud engines can be enabled on an opt-in basis in
<a href="pref://cloud">Preferences &rsaquo; Cloud</a>:</p>
<table>
  <tr><th>Engine</th><th>Cost</th><th>Account needed</th></tr>
  <tr><td><b>DeepL</b></td><td>Free tier: 500&thinsp;K chars/month</td><td>Yes &mdash; deepl.com</td></tr>
  <tr><td><b>Google Translate</b></td><td>Free tier: 500&thinsp;K chars/month</td><td>Yes &mdash; GCP project + API key</td></tr>
  <tr><td><b>Azure Translator</b></td><td>Free tier: 2&thinsp;M chars/month</td><td>Yes &mdash; Azure portal</td></tr>
  <tr><td><b>LibreTranslate</b></td><td><b>Free</b> (public instances)</td><td><b>No account needed</b></td></tr>
</table>
<p><b>LibreTranslate with no account:</b> set the URL to a free public instance and leave the API key blank:</p>
<ul>
  <li><code>https://translate.argosopentech.com</code> &mdash; no key required</li>
  <li><code>https://libretranslate.de</code> &mdash; no key required</li>
</ul>
<p class="warn">&#x26A0; When any cloud engine is enabled, every translated segment is sent to
that provider&rsquo;s servers. Only enable this if your organisation permits sending
potentially sensitive data externally.</p>
<p><a href="pref://cloud">Configure cloud engines &rarr; Preferences &rsaquo; Cloud</a></p>

<h2>Hotkey</h2>
<p>The current hotkey is <code>{hotkey}</code>.
Change it in <a href="pref://general">Preferences &rsaquo; General</a> using pynput syntax,
e.g. <code>&lt;ctrl&gt;+&lt;shift&gt;+t</code>.</p>
"""
        browser.setHtml(html)
        layout.addWidget(browser)
        return widget

    def _on_help_link(self, url: QUrl) -> None:
        """Handle link clicks in the Help tab browser."""
        if url.scheme() == "pref":
            tab_name = url.host()
            tab_map = {
                "general": 0, "display": 1, "sidebar": 2,
                "lookup": 3, "glossary": 4, "cloud": 5, "help": 6, "about": 7,
            }
            idx = tab_map.get(tab_name.lower())
            if idx is not None:
                self._tabs.setCurrentIndex(idx)
        else:
            QDesktopServices.openUrl(url)

    def open_to_tab(self, name: str) -> None:
        """Switch the dialog to a named tab. Call before exec()."""
        tab_map = {
            "general": 0, "display": 1, "sidebar": 2,
            "lookup": 3, "glossary": 4, "cloud": 5, "help": 6, "about": 7,
        }
        idx = tab_map.get(name.lower())
        if idx is not None:
            self._tabs.setCurrentIndex(idx)

    # ------------------------------------------------------------------
    # About tab
    # ------------------------------------------------------------------

    def _build_about_tab(self) -> QWidget:
        from zh_en_translator import __version__
        from zh_en_translator.engines.updates import REPO_OWNER, REPO_NAME

        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(12)

        # App header
        header_group = QGroupBox("zh-en-translator")
        header_layout = QVBoxLayout(header_group)

        ver_label = QLabel(f"Version: {__version__}")
        ver_label.setStyleSheet("font-weight: bold; font-size: 11pt;")
        header_layout.addWidget(ver_label)

        desc = QLabel(
            "Offline-first Chinese \u2192 English popup translator for Windows.\n"
            "Hotkey-activated, with dictionary lookup, pinyin, OCR, and domain glossaries."
        )
        desc.setWordWrap(True)
        header_layout.addWidget(desc)

        source_label = QLabel(
            f'Source code: <a href="https://github.com/{REPO_OWNER}/{REPO_NAME}">'
            f"github.com/{REPO_OWNER}/{REPO_NAME}</a>"
        )
        source_label.setOpenExternalLinks(True)
        header_layout.addWidget(source_label)

        license_label = QLabel(
            "Released under the "
            '<a href="https://www.gnu.org/licenses/gpl-3.0.html">GNU General Public License v3 or later</a>.'
        )
        license_label.setOpenExternalLinks(True)
        header_layout.addWidget(license_label)

        layout.addWidget(header_group)

        # Third-party components
        components_group = QGroupBox("Third-Party Components")
        components_layout = QVBoxLayout(components_group)

        browser = QTextBrowser()
        browser.setOpenExternalLinks(True)
        browser.setMinimumHeight(280)
        browser.setStyleSheet("QTextBrowser { border: none; background: transparent; }")

        rows = [
            ("PyQt6",                   "Riverbank Computing",  "GPL v3",        "https://riverbankcomputing.com/software/pyqt/"),
            ("pynput",                  "Moses Palmér",         "LGPL v3",       "https://github.com/moses-palmer/pynput"),
            ("Argos Translate",         "LibreTranslate team",  "MIT",           "https://github.com/argosopentech/argostranslate"),
            ("jieba",                   "Sun Junyi",            "MIT",           "https://github.com/fxsjy/jieba"),
            ("platformdirs",            "tox-dev contributors", "MIT",           "https://github.com/platformdirs/platformdirs"),
            ("opencc-python-reimpl.",   "BYVoid / yichen0831",  "Apache 2.0",    "https://github.com/yichen0831/opencc-python-reimplemented"),
            ("Tesseract OCR (bundled)", "Google",               "Apache 2.0",    "https://github.com/tesseract-ocr/tesseract"),
            ("pytesseract",             "Matthias Lee",         "Apache 2.0",    "https://github.com/madmaze/pytesseract"),
            ("Pillow",                  "PIL contributors",     "HPND (MIT-style)", "https://python-pillow.org/"),
            ("CC-CEDICT dictionary",    "MDBG",                 "CC BY-SA 4.0",  "https://cc-cedict.org/"),
            ("Argos zh\u2192en model",  "LibreTranslate team",  "CC BY 4.0",     "https://github.com/argosopentech/argostranslate"),
        ]

        html = (
            "<style>"
            "table { width: 100%; border-collapse: collapse; font-size: 9pt; }"
            "th { text-align: left; padding: 4px 8px; "
            "     background: rgba(0,0,0,0.06); font-weight: bold; }"
            "td { padding: 3px 8px; border-bottom: 1px solid rgba(0,0,0,0.06); }"
            "tr:last-child td { border-bottom: none; }"
            "a { color: inherit; }"
            "</style>"
            "<table>"
            "<tr><th>Component</th><th>Author / Maintainer</th><th>License</th></tr>"
        )
        for name, author, lic, url in rows:
            html += (
                f"<tr>"
                f'<td><a href="{url}">{name}</a></td>'
                f"<td>{author}</td>"
                f"<td>{lic}</td>"
                f"</tr>"
            )
        html += "</table>"
        browser.setHtml(html)
        components_layout.addWidget(browser)

        layout.addWidget(components_group)
        layout.addStretch()
        return widget

    def closeEvent(self, event):
        if self._install_monitor is not None:
            self._install_monitor.stop()
            self._install_monitor = None
        if not self._skip_close_check and self._dirty:
            answer = QMessageBox.question(
                self, "Unsaved Changes", "Save before closing?",
                QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard,
            )
            if answer == QMessageBox.StandardButton.Save:
                self._on_apply()
        event.accept()
