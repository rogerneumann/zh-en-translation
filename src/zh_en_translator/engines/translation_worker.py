"""Shared background worker for zh→en sentence translation."""

from __future__ import annotations
import logging

from PyQt6.QtCore import QThread, pyqtSignal

logger = logging.getLogger(__name__)


class TranslationWorker(QThread):
    """Background thread: runs ensure_pack() + translate_sentence() and emits the result."""

    result_ready = pyqtSignal(str)

    def __init__(self, text: str):
        super().__init__()
        self.text = text

    def run(self):
        from zh_en_translator.engines.argos import ensure_pack, translate_sentence

        logger.debug("input (%d chars): %r", len(self.text), self.text[:80])

        if not ensure_pack():
            logger.warning("ensure_pack() failed")
            self.result_ready.emit("⚠ Translation model not available.")
            return

        try:
            result = translate_sentence(self.text)
            logger.debug("result: %r", result)
        except Exception as e:
            logger.debug("exception: %s", e)
            result = None

        self.result_ready.emit(
            result if result else f"(no translation — input: {self.text[:60]!r})"
        )
