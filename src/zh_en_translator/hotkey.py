"""Global hotkey listener using pynput."""

from pynput.keyboard import GlobalHotKeys

# M1: hardcoded constant for default hotkey. Config file (M7) will override.
DEFAULT_HOTKEY_STRING = "ctrl+shift+t"


class HotKeyManager:
    """Wraps pynput GlobalHotKeys for reliable global hotkey handling."""

    def __init__(self, hotkey_string: str = DEFAULT_HOTKEY_STRING):
        """
        Initialize the hotkey manager.

        Args:
            hotkey_string: Hotkey string compatible with pynput (e.g., "ctrl+shift+t").
        """
        self.hotkey_string = hotkey_string
        self.listener = None
        self.on_activate_callback = None

    def start(self, on_activate):
        """
        Start listening for the hotkey.

        Args:
            on_activate: Callable invoked when the hotkey is pressed.
        """
        self.on_activate_callback = on_activate
        try:
            self.listener = GlobalHotKeys({self.hotkey_string: self._on_hotkey})
            self.listener.start()
        except Exception as e:
            raise RuntimeError(f"Failed to register global hotkey: {e}") from e

    def _on_hotkey(self):
        """Internal callback from pynput when hotkey is triggered."""
        if self.on_activate_callback:
            self.on_activate_callback()

    def stop(self):
        """Stop listening for the hotkey."""
        if self.listener:
            self.listener.stop()
            self.listener = None

    def __del__(self):
        """Cleanup on deletion."""
        self.stop()
