"""CoreUpdateDialog — in-app core update progress dialog.

Shows when a new core-v*.zip is available on GitHub.  The user can
download & apply the update in one click; the app relaunches itself
to activate the new overlay.
"""

from __future__ import annotations

import logging
import pathlib
import sys

from PyQt6.QtCore import QProcess, QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QDialog, QDialogButtonBox, QHBoxLayout, QLabel,
    QProgressBar, QPushButton, QVBoxLayout, QWidget,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Background download worker
# ---------------------------------------------------------------------------

class _DownloadWorker(QThread):
    progress = pyqtSignal(int, int)    # (bytes_done, total)
    finished = pyqtSignal(str)         # temp zip path on success
    error    = pyqtSignal(str)         # error message on failure

    def __init__(self, url: str, parent=None):
        super().__init__(parent)
        self._url = url

    def run(self) -> None:
        try:
            from zh_en_translator.engines.updater import download_core
            tmp = download_core(self._url, progress_cb=self._on_progress)
            self.finished.emit(str(tmp))
        except Exception as exc:
            self.error.emit(str(exc))

    def _on_progress(self, done: int, total: int) -> None:
        self.progress.emit(done, total)


# ---------------------------------------------------------------------------
# Dialog
# ---------------------------------------------------------------------------

class CoreUpdateDialog(QDialog):
    """One-click core update: download -> apply -> restart.

    Args:
        version:      New version string, e.g. ``"2026.05.04"``.
        download_url: Direct URL to the ``core-vX.Y.Z.zip`` asset.
        parent:       Qt parent widget.
    """

    def __init__(self, version: str, download_url: str, parent=None):
        super().__init__(parent)
        self._version      = version
        self._download_url = download_url
        self._zip_path: pathlib.Path | None = None
        self._worker: _DownloadWorker | None = None

        self.setWindowTitle("App Update Available")
        self.setMinimumWidth(420)
        self._build_ui()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        self._info_label = QLabel(
            f"Version <b>{self._version}</b> is available.<br>"
            "This is a fast in-app update (~5 MB). A restart is required."
        )
        self._info_label.setWordWrap(True)
        layout.addWidget(self._info_label)

        self._progress = QProgressBar()
        self._progress.setRange(0, 100)
        self._progress.setValue(0)
        self._progress.setVisible(False)
        layout.addWidget(self._progress)

        self._status_label = QLabel("")
        self._status_label.setVisible(False)
        layout.addWidget(self._status_label)

        # Button row
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        self._btn_later = QPushButton("Remind Me Later")
        self._btn_later.clicked.connect(self.reject)

        self._btn_download = QPushButton("Download && Apply")
        self._btn_download.setDefault(True)
        self._btn_download.clicked.connect(self._start_download)

        self._btn_restart = QPushButton("Restart Now")
        self._btn_restart.setVisible(False)
        self._btn_restart.clicked.connect(self._restart)

        btn_row.addStretch()
        btn_row.addWidget(self._btn_later)
        btn_row.addWidget(self._btn_download)
        btn_row.addWidget(self._btn_restart)

        layout.addLayout(btn_row)

    # ------------------------------------------------------------------
    # Download
    # ------------------------------------------------------------------

    def _start_download(self) -> None:
        self._btn_download.setEnabled(False)
        self._progress.setVisible(True)
        self._status_label.setText("Downloading…")
        self._status_label.setVisible(True)

        self._worker = _DownloadWorker(self._download_url, parent=self)
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_download_finished)
        self._worker.error.connect(self._on_download_error)
        self._worker.start()

    def _on_progress(self, done: int, total: int) -> None:
        if total > 0:
            self._progress.setValue(int(done * 100 / total))
        else:
            self._progress.setRange(0, 0)  # indeterminate

    def _on_download_finished(self, zip_path_str: str) -> None:
        self._zip_path = pathlib.Path(zip_path_str)
        self._progress.setRange(0, 100)
        self._progress.setValue(100)

        # Apply immediately (fast filesystem operation)
        try:
            from zh_en_translator.engines.updater import apply_core
            apply_core(self._zip_path, self._version)
            self._status_label.setText("Update ready. Restart to activate.")
        except Exception as exc:
            logger.error("apply_core failed: %s", exc)
            self._status_label.setText(f"Apply failed: {exc}")
            self._btn_download.setEnabled(True)
            return

        self._btn_restart.setVisible(True)
        self._btn_later.setText("Later")

    def _on_download_error(self, message: str) -> None:
        logger.error("Core download failed: %s", message)
        self._status_label.setText(f"Download failed: {message}")
        self._progress.setVisible(False)
        self._btn_download.setEnabled(True)

    # ------------------------------------------------------------------
    # Restart
    # ------------------------------------------------------------------

    def _restart(self) -> None:
        """Relaunch the app and exit the current process."""
        exe  = sys.executable
        args = sys.argv[:]
        QProcess.startDetached(exe, args)
        sys.exit(0)
