"""
Runtime hook: extend Windows DLL search path before any imports.

PyQt6 6.x places Qt DLLs in PyQt6/Qt6/bin/ (relative to the bundle root).
In a PyInstaller onedir bundle on Windows, os.add_dll_directory() must be
called early enough — before the first Qt import — otherwise Python raises
ModuleNotFoundError for PyQt6.QtCore even though the .pyd file is present.
"""
import os
import sys

if sys.platform == "win32" and getattr(sys, "frozen", False):
    base = sys._MEIPASS

    # The bundle root always needs to be on the DLL path
    os.add_dll_directory(base)

    # PyQt6 6.x: Qt6 binaries live in PyQt6/Qt6/bin/
    for candidate in (
        os.path.join(base, "PyQt6", "Qt6", "bin"),
        os.path.join(base, "PyQt6", "Qt6"),
        os.path.join(base, "PyQt6"),
    ):
        if os.path.isdir(candidate):
            os.add_dll_directory(candidate)
