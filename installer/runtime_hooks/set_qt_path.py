"""
Runtime hook: extend Windows DLL search path before any imports.

PyQt6 6.x places Qt DLLs inside subdirectories of the PyQt6 package
(e.g. PyQt6/Qt6/bin/). Windows doesn't search subdirectories automatically,
so os.add_dll_directory() must be called before the first Qt import or
Python raises ModuleNotFoundError even though the .pyd and DLLs are present.

This hook runs before any user code (including PyQt6 imports).
"""
import os
import sys

if sys.platform == "win32" and getattr(sys, "frozen", False):
    base = sys._MEIPASS

    # Always add the bundle root
    os.add_dll_directory(base)

    # Walk every subdirectory of the bundle and add any that contain DLLs.
    # This covers all possible PyQt6 layouts across 6.x minor versions.
    for root, dirs, files in os.walk(base):
        if any(f.lower().endswith(".dll") for f in files):
            try:
                os.add_dll_directory(root)
            except Exception:
                pass
