"""Test configuration - setup Qt for testing."""

import os
import sys

# Set Qt platform before any Qt imports
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

# Mock pynput to prevent X11 connection attempts
try:
    from unittest.mock import MagicMock
    if "pynput" not in sys.modules:
        sys.modules["pynput"] = MagicMock()
        sys.modules["pynput.keyboard"] = MagicMock()
except Exception:
    pass
