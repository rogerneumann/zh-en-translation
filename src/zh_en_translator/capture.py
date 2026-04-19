"""Selected-text capture using clipboard save/restore pattern."""

import time

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QMimeData
from pynput.keyboard import Controller as KeyboardController
from pynput.keyboard import Key

# Time to wait for clipboard to populate after Ctrl+C
CLIPBOARD_WAIT_MS = 0.12


class TextCapture:
    """Captures selected text from any application without modifying clipboard."""

    def __init__(self):
        """Initialize the text capture handler."""
        self.keyboard = KeyboardController()

    def capture_selection(self) -> str:
        """
        Capture currently selected text.

        Steps:
        1. Save current clipboard contents (as QMimeData).
        2. Simulate Ctrl+C to copy selection.
        3. Small sleep for OS clipboard propagation.
        4. Read clipboard text.
        5. Restore original clipboard contents.

        Returns:
            The captured text, or empty string if capture failed or clipboard
            was empty/binary.
        """
        clipboard = QApplication.clipboard()

        # Step 1: Save current clipboard
        # We must create a copy of the mime data, because the one returned by
        # clipboard.mimeData() is owned by the clipboard and will change.
        original_mime = clipboard.mimeData()
        saved_mime = QMimeData()

        # Copy all formats
        for fmt in original_mime.formats():
            saved_mime.setData(fmt, original_mime.data(fmt))

        try:
            # Step 2: Simulate Ctrl+C
            self.keyboard.press(Key.ctrl)
            self.keyboard.press('c')
            self.keyboard.release('c')
            self.keyboard.release(Key.ctrl)

            # Step 3: Wait for clipboard to populate
            time.sleep(CLIPBOARD_WAIT_MS)

            # Step 4: Read clipboard
            captured_text = clipboard.text().strip()
            return captured_text

        except Exception:
            # Capture failed
            return ""
        finally:
            # Step 5: Restore original clipboard (always)
            # Use a small delay before restoring to ensure the 'c' key release
            # and OS clipboard updates from Ctrl+C have settled.
            clipboard.setMimeData(saved_mime)
