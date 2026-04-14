"""Selected-text capture using clipboard save/restore pattern."""

import time

import pyperclip
from pynput.keyboard import Controller as KeyboardController
from pynput.keyboard import Key

# Time to wait for clipboard to populate after Ctrl+C
CLIPBOARD_WAIT_MS = 0.08


class TextCapture:
    """Captures selected text from any application without modifying clipboard."""

    def __init__(self):
        """Initialize the text capture handler."""
        self.keyboard = KeyboardController()

    def capture_selection(self) -> str:
        """
        Capture currently selected text.

        Steps:
        1. Save current clipboard contents.
        2. Simulate Ctrl+C to copy selection.
        3. Small sleep for OS clipboard propagation.
        4. Read clipboard.
        5. Restore original clipboard contents.

        Returns:
            The captured text, or empty string if capture failed or clipboard
            was empty/binary.
        """
        # Step 1: Save current clipboard
        try:
            original_clipboard = pyperclip.paste()
        except Exception:
            # If clipboard read fails, assume it's empty or binary
            original_clipboard = ""

        try:
            # Step 2: Simulate Ctrl+C
            self.keyboard.press(Key.ctrl)
            self.keyboard.press('c')
            self.keyboard.release('c')
            self.keyboard.release(Key.ctrl)

            # Step 3: Wait for clipboard to populate
            time.sleep(CLIPBOARD_WAIT_MS)

            # Step 4: Read clipboard
            try:
                captured_text = pyperclip.paste()
            except Exception:
                # Clipboard may contain binary data or be inaccessible
                captured_text = ""

            return captured_text
        finally:
            # Step 5: Restore original clipboard (always)
            try:
                pyperclip.copy(original_clipboard)
            except Exception:
                # If restore fails, at least we tried
                pass
