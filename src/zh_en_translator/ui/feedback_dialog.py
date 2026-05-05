"""Feedback dialog — lets users send suggestions or bug reports."""

from __future__ import annotations

import logging
import platform
import urllib.parse
import webbrowser

from PyQt6.QtWidgets import (
    QCheckBox, QDialog, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QTextEdit, QVBoxLayout,
)

logger = logging.getLogger(__name__)

_GITHUB_ISSUES_URL = (
    "https://github.com/rogerneumann/zh-en-translation/issues/new"
)
_FEEDBACK_EMAIL = "zhentranslate@gmail.com"


class FeedbackDialog(QDialog):
    """Collect a short message and open either GitHub Issues or an email draft.

    Version and OS are always included in the submission.  The user can
    optionally attach their most recent translation (source + result).

    Args:
        version: Running app version string, e.g. '2026.05.05.3'.
        os_info: Human-readable OS string, e.g. 'Windows 11 Pro 10.0.26200'.
        last_source:      Most recent source text (may be empty).
        last_translation: Most recent translation result (may be empty).
    """

    def __init__(
        self,
        version: str,
        os_info: str,
        last_source: str = "",
        last_translation: str = "",
        parent=None,
    ):
        super().__init__(parent)
        self._version = version
        self._os_info = os_info
        self._last_source = last_source
        self._last_translation = last_translation

        self.setWindowTitle("Send Feedback")
        self.setMinimumWidth(460)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        intro = QLabel(
            "Share a suggestion, report a problem, or just tell us what you think."
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)

        layout.addWidget(QLabel("Title (optional):"))
        self._title_edit = QLineEdit()
        self._title_edit.setPlaceholderText("e.g. Translation quality on medical terms")
        layout.addWidget(self._title_edit)

        layout.addWidget(QLabel("Your message:"))
        self._body_edit = QTextEdit()
        self._body_edit.setPlaceholderText(
            "Describe what you noticed or what you'd like to see..."
        )
        self._body_edit.setFixedHeight(110)
        layout.addWidget(self._body_edit)

        if self._last_source or self._last_translation:
            self._incl_check = QCheckBox("Include last translation with this feedback")
            layout.addWidget(self._incl_check)
            preview = QLabel(
                f"  Source: “{self._last_source[:60]}{'…' if len(self._last_source) > 60 else ''}”\n"
                f"  Result: “{self._last_translation[:60]}{'…' if len(self._last_translation) > 60 else ''}”"
            )
            preview.setStyleSheet("color: #555; font-size: 9pt; margin-left: 18px;")
            layout.addWidget(preview)
        else:
            self._incl_check = None

        sysinfo = QLabel(f"Always included: version {self._version}  ·  {self._os_info}")
        sysinfo.setStyleSheet("color: #888; font-size: 9pt;")
        layout.addWidget(sysinfo)

        btn_row = QHBoxLayout()
        btn_row.addStretch()

        self._btn_cancel = QPushButton("Cancel")
        self._btn_cancel.clicked.connect(self.reject)

        self._btn_email = QPushButton("✉ Send via Email")
        self._btn_email.clicked.connect(self._send_email)

        self._btn_github = QPushButton("Open on GitHub →")
        self._btn_github.setDefault(True)
        self._btn_github.clicked.connect(self._open_github)

        btn_row.addWidget(self._btn_cancel)
        btn_row.addWidget(self._btn_email)
        btn_row.addWidget(self._btn_github)
        layout.addLayout(btn_row)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _include_translation(self) -> bool:
        return bool(self._incl_check and self._incl_check.isChecked())

    def _build_body(self, markdown: bool) -> str:
        """Assemble the feedback body.  markdown=True for GitHub, False for email."""
        msg = self._body_edit.toPlainText().strip()
        parts: list[str] = []

        if msg:
            if markdown:
                parts.append(f"## Feedback\n\n{msg}")
            else:
                parts.append(msg)

        if markdown:
            parts.append(
                f"---\n**System Information**\n"
                f"- App version: {self._version}\n"
                f"- OS: {self._os_info}"
            )
            if self._include_translation():
                parts.append(
                    f"---\n**Last Translation**\n"
                    f"- Source: {self._last_source}\n"
                    f"- Result: {self._last_translation}"
                )
        else:
            parts.append(
                f"App version: {self._version}\nOS: {self._os_info}"
            )
            if self._include_translation():
                parts.append(
                    f"Last translation:\n"
                    f"  Source:  {self._last_source}\n"
                    f"  Result:  {self._last_translation}"
                )

        sep = "\n\n" if markdown else "\n\n"
        return sep.join(parts)

    def _title_text(self) -> str:
        t = self._title_edit.text().strip()
        return t if t else "App feedback"

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def _open_github(self) -> None:
        body = self._build_body(markdown=True)
        params = urllib.parse.urlencode(
            {
                "title": f"[Feedback] {self._title_text()}",
                "body": body,
                "labels": "feedback",
            }
        )
        webbrowser.open(f"{_GITHUB_ISSUES_URL}?{params}")
        self.accept()

    def _send_email(self) -> None:
        body = self._build_body(markdown=False)
        subject = urllib.parse.quote(
            f"zh-en-translator feedback: {self._title_text()}", safe=""
        )
        encoded_body = urllib.parse.quote(body, safe="")
        webbrowser.open(
            f"mailto:{_FEEDBACK_EMAIL}?subject={subject}&body={encoded_body}"
        )
        self.accept()


# ---------------------------------------------------------------------------
# Factory helper — resolves history and OS info so callers don't have to
# ---------------------------------------------------------------------------

def open_feedback_dialog(parent=None) -> None:
    """Create and exec a FeedbackDialog, resolving version/OS/history internally."""
    try:
        from zh_en_translator import __version__
    except Exception:
        __version__ = "unknown"

    os_info = f"{platform.system()} {platform.release()} {platform.version()}".strip()

    last_source = ""
    last_translation = ""
    try:
        from zh_en_translator.engines.history import HistoryManager
        from zh_en_translator.config import get_config_path
        mgr = HistoryManager(get_config_path().parent / "history.json")
        hist = mgr.load_history()
        if hist:
            last_source = hist[0].get("source", "")
            last_translation = hist[0].get("translation", "")
    except Exception as exc:
        logger.debug("Could not load history for feedback dialog: %s", exc)

    dlg = FeedbackDialog(
        version=__version__,
        os_info=os_info,
        last_source=last_source,
        last_translation=last_translation,
        parent=parent,
    )
    dlg.exec()
