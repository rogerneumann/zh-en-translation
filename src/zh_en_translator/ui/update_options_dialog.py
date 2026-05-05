"""Update options dialog — user chooses how to install an available update."""

from __future__ import annotations

import logging
import webbrowser

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QButtonGroup, QDialog, QHBoxLayout, QLabel,
    QPushButton, QRadioButton, QVBoxLayout, QWidget,
)

logger = logging.getLogger(__name__)

_CORE_SIZE = "~5 MB"
_LITE_SIZE = "~100 MB"
_FULL_SIZE = "~350 MB"


class UpdateOptionsDialog(QDialog):
    """Let the user pick how to install an available update.

    Args:
        version:          Version string without 'v' prefix, e.g. '2026.05.05.3'.
        core_url:         Direct download URL for core-v*.zip, or None if unavailable.
        lite_url:         Direct download URL for lite setup .exe, or None.
        full_url:         Direct download URL for full setup .exe, or None.
        release_html_url: GitHub release page (fallback when a direct asset URL is None).
    """

    def __init__(
        self,
        version: str,
        core_url: str | None,
        lite_url: str | None,
        full_url: str | None,
        release_html_url: str,
        parent=None,
    ):
        super().__init__(parent)
        self._version = version
        self._core_url = core_url
        self._lite_url = lite_url or release_html_url
        self._full_url = full_url or release_html_url
        self._release_html_url = release_html_url

        self.setWindowTitle("Update Available")
        self.setMinimumWidth(440)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        intro = QLabel(f"Version <b>{self._version}</b> is available.")
        intro.setTextFormat(Qt.TextFormat.RichText)
        intro.setWordWrap(True)
        layout.addWidget(intro)

        sub = QLabel("How would you like to update?")
        sub.setStyleSheet("color: #555;")
        layout.addWidget(sub)

        self._group = QButtonGroup(self)

        # --- Core update ---
        self._radio_core = QRadioButton()
        self._radio_core.setEnabled(bool(self._core_url))
        if self._core_url:
            self._radio_core.setChecked(True)
        self._group.addButton(self._radio_core, 0)

        if self._core_url:
            core_badge = (
                f"  <span style='color:#2563EB;font-weight:bold;'>← Recommended</span>"
            )
        else:
            core_badge = (
                f"  <span style='color:#9CA3AF;'>(not available for this release)</span>"
            )
        core_title = QLabel(f"<b>Quick update</b>  ({_CORE_SIZE}){core_badge}")
        core_title.setTextFormat(Qt.TextFormat.RichText)
        if not self._core_url:
            core_title.setEnabled(False)
        core_desc = QLabel(
            "Updates your existing installation in-place. A restart is required to activate."
        )
        core_desc.setEnabled(bool(self._core_url))
        layout.addWidget(_option_row(self._radio_core, core_title, core_desc))

        # --- Lite installer ---
        self._radio_lite = QRadioButton()
        if not self._core_url:
            self._radio_lite.setChecked(True)
        self._group.addButton(self._radio_lite, 1)

        lite_title = QLabel(f"<b>Lite installer</b>  ({_LITE_SIZE})")
        lite_title.setTextFormat(Qt.TextFormat.RichText)
        lite_desc = QLabel(
            "Fresh install with just the essentials. AI models download automatically on "
            "first use. Use this if you are having trouble with the current installation."
        )
        layout.addWidget(_option_row(self._radio_lite, lite_title, lite_desc))

        # --- Full installer ---
        self._radio_full = QRadioButton()
        self._group.addButton(self._radio_full, 2)

        full_title = QLabel(f"<b>Full installer</b>  ({_FULL_SIZE})")
        full_title.setTextFormat(Qt.TextFormat.RichText)
        full_desc = QLabel(
            "Complete offline bundle — all AI models pre-installed. "
            "Best for offline or enterprise use."
        )
        layout.addWidget(_option_row(self._radio_full, full_title, full_desc))

        layout.addSpacing(4)

        btn_row = QHBoxLayout()
        btn_row.addStretch()

        self._btn_cancel = QPushButton("Cancel")
        self._btn_cancel.clicked.connect(self.reject)

        self._btn_continue = QPushButton("Continue →")
        self._btn_continue.setDefault(True)
        self._btn_continue.clicked.connect(self._on_continue)

        btn_row.addWidget(self._btn_cancel)
        btn_row.addWidget(self._btn_continue)
        layout.addLayout(btn_row)

    def _on_continue(self) -> None:
        choice = self._group.checkedId()
        self.accept()
        if choice == 0 and self._core_url:
            self._launch_core_update()
        elif choice == 1:
            webbrowser.open(self._lite_url)
        else:
            webbrowser.open(self._full_url)

    def _launch_core_update(self) -> None:
        try:
            from zh_en_translator.ui.update_dialog import CoreUpdateDialog
            dlg = CoreUpdateDialog(self._version, self._core_url)
            dlg.exec()
        except Exception as exc:
            logger.warning("Could not open CoreUpdateDialog: %s", exc)


def _option_row(radio: QRadioButton, title: QLabel, desc: QLabel) -> QWidget:
    row = QWidget()
    outer = QVBoxLayout(row)
    outer.setContentsMargins(0, 4, 0, 4)
    outer.setSpacing(2)

    title_row = QHBoxLayout()
    title_row.setSpacing(6)
    title_row.addWidget(radio)
    title_row.addWidget(title)
    title_row.addStretch()
    outer.addLayout(title_row)

    desc_layout = QHBoxLayout()
    desc_layout.setContentsMargins(22, 0, 0, 0)
    desc.setStyleSheet("color: #555; font-size: 9pt;")
    desc.setWordWrap(True)
    desc_layout.addWidget(desc)
    outer.addLayout(desc_layout)

    return row
