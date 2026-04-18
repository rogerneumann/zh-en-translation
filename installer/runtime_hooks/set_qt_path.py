import os, sys

if sys.platform == "win32" and getattr(sys, "frozen", False):
    base = sys._MEIPASS
    os.add_dll_directory(base)
    for root, dirs, files in os.walk(base):
        if any(f.lower().endswith(".dll") for f in files):
            try:
                os.add_dll_directory(root)
            except Exception:
                pass
