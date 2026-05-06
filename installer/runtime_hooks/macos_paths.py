"""Runtime hook: set TESSDATA_PREFIX for the bundled Tesseract on macOS."""
import os
import sys
from pathlib import Path

if getattr(sys, "_MEIPASS", None):
    os.environ["TESSDATA_PREFIX"] = str(Path(sys._MEIPASS) / "tesseract" / "tessdata")
