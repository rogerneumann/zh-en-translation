"""Main application: system tray app with global hotkey and popup translator."""

import logging
import sys
import threading

from PyQt6.QtCore import Qt, QObject, QRectF, pyqtSignal, QThread
from PyQt6.QtGui import QBrush, QIcon, QColor, QPainter, QPainterPath, QPixmap
from PyQt6.QtWidgets import QApplication, QSystemTrayIcon, QMenu

from zh_en_translator.config import load_config, save_config, Config
from zh_en_translator.engines.dictionary import ensure_cedict
from zh_en_translator.hotkey import HotKeyManager
from zh_en_translator.capture import TextCapture
from zh_en_translator.ui.popup import TranslatorPopup
from zh_en_translator.ui.sidebar import TranslatorSidebar
from zh_en_translator.engines.translation_worker import TranslationWorker

logger = logging.getLogger(__name__)


def _resources_dir():
    """Return the resources/ directory, works both in source and frozen (PyInstaller) builds."""
    import sys
    from pathlib import Path
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        # PyInstaller onedir: data files land in sys._MEIPASS/zh_en_translator/resources/
        return Path(sys._MEIPASS) / "zh_en_translator" / "resources"
    return Path(__file__).parent / "resources"


def _svg_icon_path() -> str:
    return str(_resources_dir() / "translation_icn.svg")


def _png_icon_path(size: int) -> str:
    resources = _resources_dir()
    candidate = resources / f"icon_{size}.png"
    return str(candidate if candidate.exists() else resources / "icon.png")


def _render_svg_icon(size: int) -> "QPixmap":
    """Render translation_icn.svg at the given pixel size.

    Tries QSvgRenderer first (crisp vector), then pre-rendered PNGs.
    Raises RuntimeError if neither source is usable.
    """
    from pathlib import Path
    try:
        from PyQt6.QtSvg import QSvgRenderer
        from PyQt6.QtCore import QRectF as _QRectF
        renderer = QSvgRenderer(_svg_icon_path())
        if not renderer.isValid():
            raise RuntimeError("SVG renderer invalid — file missing or malformed")
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        renderer.render(painter, _QRectF(0, 0, size, size))
        painter.end()
        return pixmap
    except Exception:
        pass

    # QtSvg unavailable or SVG invalid — load the pre-rendered PNG
    png = _png_icon_path(size)
    if Path(png).exists():
        pm = QPixmap(png)
        if not pm.isNull():
            return pm.scaled(
                size, size,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
    raise RuntimeError("no icon source available")


def _render_icon_pixmap_fallback(size: int) -> "QPixmap":
    """Fallback programmatic icon (teal rounded square + 文 strokes) if SVG unavailable."""
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)

    p = QPainter(pixmap)
    p.setRenderHint(QPainter.Antialiasing)

    radius = size * 0.215
    path = QPainterPath()
    path.addRoundedRect(QRectF(0, 0, size, size), radius, radius)
    p.fillPath(path, QBrush(QColor("#2B6E6A")))

    from PyQt6.QtGui import QPen
    pen = QPen(QColor("#C4EDE7"))
    pen.setWidthF(size * 0.083)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    p.setPen(pen)

    s = size / 1024.0
    path2 = QPainterPath()
    path2.moveTo(512 * s, 150 * s)
    path2.cubicTo(512 * s, 400 * s, 450 * s, 750 * s, 200 * s, 874 * s)
    p.drawPath(path2)

    path3 = QPainterPath()
    path3.moveTo(512 * s, 150 * s)
    path3.cubicTo(512 * s, 400 * s, 574 * s, 750 * s, 824 * s, 874 * s)
    p.drawPath(path3)

    p.drawLine(int(310 * s), int(716 * s), int(714 * s), int(716 * s))
    p.end()
    return pixmap


def _apply_startup_setting(enabled: bool, exe_path: str) -> None:
    """Set or clear the run-at-login entry for zh-en-translator.

    Windows: writes/removes a HKCU Run registry value.
    Linux/macOS: writes/removes an XDG autostart .desktop file.
    Only operates when running as a frozen (PyInstaller) exe or when a system
    install is found on PATH. Safe to call from dev mode — becomes a no-op.
    """
    if sys.platform == "win32":
        if not exe_path:
            return  # dev mode — skip
        try:
            import winreg
            key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
            app_name = "zh-en-translator"
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE
            ) as key:
                if enabled:
                    winreg.SetValueEx(key, app_name, 0, winreg.REG_SZ, exe_path)
                    logger.info("Startup registry entry set: %s -> %s", app_name, exe_path)
                else:
                    try:
                        winreg.DeleteValue(key, app_name)
                        logger.info("Startup registry entry removed: %s", app_name)
                    except FileNotFoundError:
                        pass  # already absent — that's fine
        except Exception as e:
            logger.warning("Could not update startup registry entry: %s", e)
    else:
        import shutil
        from pathlib import Path
        autostart_dir = Path.home() / ".config" / "autostart"
        desktop_file = autostart_dir / "zh-en-translator.desktop"
        if enabled:
            launch_exe = exe_path or shutil.which("zh-en-translator") or ""
            if not launch_exe:
                logger.debug("Startup: no executable found, skipping XDG autostart")
                return
            try:
                autostart_dir.mkdir(parents=True, exist_ok=True)
                desktop_file.write_text(
                    "[Desktop Entry]\n"
                    "Type=Application\n"
                    "Name=zh-en-translator\n"
                    f"Exec={launch_exe}\n"
                    "Hidden=false\n"
                    "X-GNOME-Autostart-enabled=true\n",
                    encoding="utf-8",
                )
                logger.info("XDG autostart entry created: %s", desktop_file)
            except Exception as e:
                logger.warning("Could not create XDG autostart entry: %s", e)
        else:
            try:
                desktop_file.unlink(missing_ok=True)
                logger.info("XDG autostart entry removed: %s", desktop_file)
            except Exception as e:
                logger.warning("Could not remove XDG autostart entry: %s", e)


def _get_frozen_exe_path() -> str:
    """Return the path to the packaged .exe, or '' when running from source."""
    if getattr(sys, "frozen", False):
        return sys.executable
    return ""


def _ensure_cedict_background() -> None:
    """Download full CC-CEDICT in background so it is ready on first popup use."""
    try:
        path = ensure_cedict()
        logger.info("CC-CEDICT ready at %s", path)
    except Exception as exc:
        logger.warning("Background CC-CEDICT initialisation failed: %s", exc)


class _OCRWorker(QThread):
    result_ready = pyqtSignal(str)  # emits OCR text or error message

    def __init__(self, image_bytes: bytes, ocr_fn):
        super().__init__()
        self.image_bytes = image_bytes
        self.ocr_fn = ocr_fn

    def run(self):
        try:
            result = self.ocr_fn(self.image_bytes, lang="zh")
            if result:
                self.result_ready.emit(result)
            else:
                # Give a more helpful message if Windows OCR is available but
                # the Chinese language pack hasn't been installed in Windows.
                try:
                    from zh_en_translator.engines.ocr.windows_ocr import (
                        is_available as win_available,
                        has_chinese_language,
                    )
                    if win_available() and not has_chinese_language():
                        self.result_ready.emit(
                            "⚠ No Chinese OCR language pack found.\n\n"
                            "Install either:\n"
                            "  Chinese (Simplified, China)\n"
                            "  Chinese (Simplified, Singapore)\n\n"
                            "Click 'Open Language Settings' below, then\n"
                            "Add a language and pick either option above."
                        )
                        return
                except Exception:
                    pass
                self.result_ready.emit("⚠ No text detected in image.")
        except Exception as e:
            self.result_ready.emit(f"⚠ OCR failed: {e}")


class _UpdateWorker(QThread):
    result_ready = pyqtSignal(object)  # emits ReleaseInfo or None

    def run(self):
        from zh_en_translator.engines.updates import get_latest_release
        release = get_latest_release()
        self.result_ready.emit(release)


def _apply_update_badge(pixmap: "QPixmap", size: int) -> "QPixmap":
    """Paint a small orange dot in the top-right corner of a pixmap."""
    result = pixmap.copy()
    p = QPainter(result)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    dot_r = max(3, size // 5)
    margin = max(1, size // 16)
    cx = size - margin - dot_r
    cy = margin + dot_r
    p.setPen(Qt.PenStyle.NoPen)
    # White halo for contrast against any background
    p.setBrush(QBrush(QColor("#FFFFFF")))
    p.drawEllipse(int(cx - dot_r - 1), int(cy - dot_r - 1), (dot_r + 1) * 2, (dot_r + 1) * 2)
    # Orange badge dot
    p.setBrush(QBrush(QColor("#F5A623")))
    p.drawEllipse(int(cx - dot_r), int(cy - dot_r), dot_r * 2, dot_r * 2)
    p.end()
    return result


class TranslatorApp(QObject):
    """System tray application with global hotkey listener."""

    # Routes the pynput callback (background thread) to the Qt main thread.
    _hotkey_signal = pyqtSignal()

    def __init__(self):
        # QApplication must exist before QObject.__init__
        self.app = QApplication.instance() or QApplication(sys.argv)
        # Tray apps must not quit when the last window (popup, prefs dialog) closes.
        self.app.setQuitOnLastWindowClosed(False)
        super().__init__()

        self.config: Config = load_config()

        # Apply startup-on-login setting (Windows packaged exe only)
        _apply_startup_setting(self.config.startup, _get_frozen_exe_path())

        # Warm CC-CEDICT cache in background so it is ready before first lookup
        threading.Thread(target=_ensure_cedict_background, daemon=True).start()

        self.tray_icon = None
        self.popup = None
        self.dictionary = None
        self.sidebar = TranslatorSidebar(config=self.config)
        self.paused = False
        self._ocr_worker = None
        self._update_worker = None
        self._has_update = False
        self._update_version = ""

        # Apply mode from config
        self.sidebar_mode: bool = self.config.mode == "sidebar"
        self._sidebar_translation_worker = None
        self._sidebar_on_left: bool = self.config.side == "left"

        self._hotkey_signal.connect(self._on_hotkey_pressed)
        self.hotkey_manager = HotKeyManager(hotkey_string=self.config.hotkey)
        self.text_capture = TextCapture()

        # Connect sidebar signals
        self.sidebar.closed.connect(self._on_sidebar_closed)

        self._setup_tray()
        self._init_dictionary()

        # Warn once per session if Tesseract is missing (Windows only, 3 s delay)
        if sys.platform == "win32":
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(3000, self._check_tesseract_warning)

        # Show sidebar if starting in sidebar mode
        if self.sidebar_mode:
            self._update_tray_sidebar_label()
            self.sidebar.show()

        # Check for updates on startup if enabled and not checked within 48 hours
        if self.config.auto_check_updates and self._should_auto_check():
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(5000, lambda: self._check_for_updates(manual=False))

    def _init_dictionary(self):
        """Build/load the dictionary and user segmentation dict in a background thread."""
        def _task():
            from zh_en_translator.engines.dictionary import ensure_cedict, Dictionary
            from zh_en_translator.engines.segmentation import load_user_dict, set_segmenter
            # Apply segmenter choice from config before any segmentation happens.
            segmenter_name = getattr(self.config, "segmenter", "jieba")
            try:
                set_segmenter(segmenter_name)
            except ValueError:
                logger.warning("Unknown segmenter '%s' in config; using jieba", segmenter_name)
            # Prime jieba with domain-specific manufacturing/technical terms so
            # that multi-char compounds (e.g. 激光模块, 手板样机) are not split.
            _user_dict = _resources_dir() / "user_dict_technical.txt"
            load_user_dict(_user_dict)
            try:
                cedict_path = ensure_cedict()
                db_path = cedict_path.with_suffix(".db")
                if not db_path.exists():
                    Dictionary.build_from_cedict(cedict_path, db_path)
                self.dictionary = Dictionary(db_path)
                # Also give it to sidebar
                self.sidebar.dictionary = self.dictionary
                logger.info("Dictionary ready")
            except Exception as e:
                logger.warning("Failed to initialize dictionary: %s", e)

        threading.Thread(target=_task, daemon=True).start()

    def _setup_tray(self):
        self.tray_icon = QSystemTrayIcon(self.app)
        app_icon = self._create_icon()
        # Set on QApplication so every window (popup, sidebar) shows the same
        # icon in the Windows taskbar and Alt-Tab switcher.
        self.app.setWindowIcon(app_icon)
        self.tray_icon.setIcon(app_icon)

        menu = QMenu()

        action_translate = menu.addAction("Translate Selection")
        action_translate.triggered.connect(self._on_hotkey_pressed)

        menu.addSeparator()

        self.action_sidebar = menu.addAction("Sidebar Mode: Off")
        self.action_sidebar.setCheckable(True)
        self.action_sidebar.triggered.connect(self._on_toggle_sidebar_mode)

        self.action_sidebar_side = menu.addAction("Move Sidebar to Left")
        self.action_sidebar_side.triggered.connect(self._on_toggle_sidebar_side)

        menu.addSeparator()
        self._action_prefs = menu.addAction("Preferences\u2026")
        self._action_prefs.triggered.connect(self._open_preferences)

        menu.addSeparator()
        self.action_pause = menu.addAction("Pause")
        self.action_pause.triggered.connect(self._on_pause_resume)

        menu.addSeparator()
        action_quit = menu.addAction("Quit")
        action_quit.triggered.connect(self.app.quit)

        self.tray_icon.setContextMenu(menu)
        self.tray_icon.show()

    def _create_icon(self, update_badge: bool = False) -> QIcon:
        icon = QIcon()
        try:
            for size in (16, 24, 32, 48, 64, 128, 256):
                px = _render_svg_icon(size)
                if update_badge:
                    px = _apply_update_badge(px, size)
                icon.addPixmap(px)
        except Exception:
            for size in (16, 24, 32, 48, 64, 128, 256):
                px = _render_icon_pixmap_fallback(size)
                if update_badge:
                    px = _apply_update_badge(px, size)
                icon.addPixmap(px)
        return icon

    def _on_hotkey_pressed(self):
        if self.paused:
            return

        # Snapshot clipboard image BEFORE text capture.
        # capture_selection() does Ctrl+C and restores the clipboard via
        # QClipboard, which may wipe any image that was in the clipboard.
        clipboard = QApplication.instance().clipboard()
        pre_capture_image = None
        if clipboard.mimeData().hasImage():
            pre_capture_image = clipboard.image()

        # In sidebar mode — capture text, or if none, just expand sidebar
        if self.sidebar_mode:
            captured_text = self.text_capture.capture_selection()
            if not captured_text:
                # Re-check clipboard after Ctrl+C
                mime = clipboard.mimeData()
                if mime.hasImage():
                    self._run_ocr_from_qimage(clipboard.image())
                    return
                elif pre_capture_image is not None and not pre_capture_image.isNull():
                    self._run_ocr_from_qimage(pre_capture_image)
                    return
                elif mime.hasText():
                    captured_text = mime.text().strip()
                if not captured_text:
                    self.sidebar.expand()
                    return
            # Have text in sidebar mode → update sidebar directly
            if self.config.traditional_to_simplified:
                from zh_en_translator.engines.converter import to_simplified
                captured_text = to_simplified(captured_text)
            self._translate_for_sidebar(captured_text)
            return

        # Normal popup mode
        if self.popup:
            self.popup.close()

        try:
            original_clipboard = QApplication.clipboard().text()
        except Exception:
            original_clipboard = ""

        # Try to capture selected text first
        captured_text = self.text_capture.capture_selection()

        if not captured_text:
            # Re-check clipboard after Ctrl+C
            mime = clipboard.mimeData()
            if mime.hasImage():
                self._run_ocr_from_qimage(clipboard.image())
                return
            elif pre_capture_image is not None and not pre_capture_image.isNull():
                # Ctrl+C clobbered the clipboard image; use the pre-captured one
                self._run_ocr_from_qimage(pre_capture_image)
                return
            elif mime.hasText():
                captured_text = mime.text().strip()
                if not captured_text:
                    return
            else:
                return

        if self.config.traditional_to_simplified:
            from zh_en_translator.engines.converter import to_simplified
            captured_text = to_simplified(captured_text)

        self.popup = TranslatorPopup(
            captured_text,
            original_clipboard,
            dictionary=self.dictionary,
            on_pin=self._pin_to_sidebar,
            config=self.config,
            update_available=self._has_update,
            update_version=self._update_version,
        )
        self.popup.show()

    def _run_ocr_from_clipboard(self, clipboard):
        """Extract image from clipboard and run OCR (convenience wrapper)."""
        qimage = clipboard.image()
        if not qimage.isNull():
            self._run_ocr_from_qimage(qimage)

    def _run_ocr_from_qimage(self, qimage):
        """Convert a QImage to PNG bytes and run OCR, routing to sidebar or popup."""
        from zh_en_translator.engines.ocr.engine import is_any_engine_available
        if not is_any_engine_available():
            if sys.platform == "win32":
                install_hint = "Install winrt-* packages or Tesseract.\nSee README for instructions."
            else:
                install_hint = "Install Tesseract: sudo apt install tesseract-ocr tesseract-ocr-chi-sim\nOr install paddleocr for best accuracy."
            msg = f"⚠ No OCR engine available.\n{install_hint}"
            if self.sidebar_mode:
                self.sidebar.set_translation("OCR", msg)
                self.sidebar.expand()
            else:
                self.popup = TranslatorPopup(
                    msg, "", on_pin=self._pin_to_sidebar, config=self.config,
                    update_available=self._has_update, update_version=self._update_version,
                )
                self.popup.show()
            return

        from PyQt6.QtCore import QBuffer, QIODevice
        buf = QBuffer()
        buf.open(QIODevice.OpenModeFlag.WriteOnly)
        qimage.save(buf, "PNG")
        image_bytes = bytes(buf.data())
        buf.close()

        if not image_bytes:
            return

        from zh_en_translator.engines.ocr.engine import ocr_image
        self._ocr_worker = _OCRWorker(image_bytes, ocr_image)

        if self.sidebar_mode:
            # Route OCR result to the sidebar
            self.sidebar.set_translation_pending("🔍 Running OCR…")
            self.sidebar.expand()
            self._ocr_worker.result_ready.connect(self._on_sidebar_ocr_result)
        else:
            self.popup = TranslatorPopup(
                "🔍 Running OCR\u2026",
                "",
                on_pin=self._pin_to_sidebar,
                is_ocr_pending=True,
                config=self.config,
                update_available=self._has_update,
                update_version=self._update_version,
            )
            self.popup.show()
            self._ocr_worker.result_ready.connect(self._on_ocr_result)

        self._ocr_worker.start()

    def _on_ocr_result(self, text: str):
        """Called when OCR completes in popup mode — update popup."""
        if not text.startswith("⚠") and self.config.traditional_to_simplified:
            from zh_en_translator.engines.converter import to_simplified
            text = to_simplified(text)
        if self.popup and not self.popup._dismissed:
            self.popup.set_ocr_result(text)

    def _on_sidebar_ocr_result(self, text: str) -> None:
        """Called when OCR completes in sidebar mode — translate if text, else show error."""
        if text.startswith("⚠"):
            self.sidebar.update_translation(text)
        else:
            # OCR succeeded — apply Traditional→Simplified then translate
            if self.config.traditional_to_simplified:
                from zh_en_translator.engines.converter import to_simplified
                text = to_simplified(text)
            self._translate_for_sidebar(text)

    def _pin_to_sidebar(self, source: str, translation: str) -> None:
        """Called by the popup's Pin button — show translation in the sidebar."""
        self.sidebar.set_translation(source, translation)
        if not self.sidebar_mode:
            self.sidebar_mode = True
            self.config.mode = "sidebar"
            save_config(self.config)
            self._update_tray_sidebar_label()
        if not self.sidebar.isVisible():
            self.sidebar.show()

    def _translate_for_sidebar(self, text: str) -> None:
        self.sidebar.set_translation_pending(text)
        self.sidebar.expand()
        if self._sidebar_translation_worker and self._sidebar_translation_worker.isRunning():
            self._sidebar_translation_worker.quit()
            self._sidebar_translation_worker.wait(300)
        self._sidebar_translation_worker = TranslationWorker(text, config=self.config)
        self._sidebar_translation_worker.result_ready.connect(self.sidebar.update_translation)
        self._sidebar_translation_worker.start()

    def _on_sidebar_closed(self) -> None:
        self.sidebar_mode = False
        self.config.mode = "popup"
        save_config(self.config)
        self._update_tray_sidebar_label()

    def _on_toggle_sidebar_mode(self, checked: bool) -> None:
        self.sidebar_mode = checked
        self.config.mode = "sidebar" if checked else "popup"
        save_config(self.config)
        if checked and not self.sidebar.isVisible():
            self.sidebar.show()
        elif not checked:
            self.sidebar.collapse()
        self._update_tray_sidebar_label()

    def _on_toggle_sidebar_side(self) -> None:
        self._sidebar_on_left = not self._sidebar_on_left
        side = "left" if self._sidebar_on_left else "right"
        self.config.side = side
        save_config(self.config)
        self.sidebar.set_side(side)
        self.action_sidebar_side.setText(
            "Move Sidebar to Right" if self._sidebar_on_left else "Move Sidebar to Left"
        )

    def _update_tray_sidebar_label(self) -> None:
        if hasattr(self, "action_sidebar"):
            self.action_sidebar.setChecked(self.sidebar_mode)
            self.action_sidebar.setText(
                "Sidebar Mode: On" if self.sidebar_mode else "Sidebar Mode: Off"
            )

    def _should_auto_check(self) -> bool:
        """Return True if no check has been done or the last check was >48 hours ago."""
        last = self.config.last_update_check
        if not last:
            return True
        try:
            from datetime import datetime, timezone
            last_dt = datetime.fromisoformat(last)
            now = datetime.now(timezone.utc)
            # Make last_dt timezone-aware if it was stored naive
            if last_dt.tzinfo is None:
                last_dt = last_dt.replace(tzinfo=timezone.utc)
            return (now - last_dt).total_seconds() > 48 * 3600
        except Exception:
            return True

    def _set_update_available(self, available: bool, version: str = "") -> None:
        """Record update state and refresh all indicators."""
        self._has_update = available
        self._update_version = version
        self._refresh_tray_update_badge()
        # Notify persistent sidebar
        self.sidebar.set_update_available(available, version)

    def _refresh_tray_update_badge(self) -> None:
        """Recompose tray icon with/without orange update badge dot."""
        if not self.tray_icon:
            return
        icon = self._create_icon(update_badge=self._has_update)
        self.tray_icon.setIcon(icon)
        # Update Preferences menu item text
        if hasattr(self, "_action_prefs"):
            label = "Preferences\u2026  \u25cf" if self._has_update else "Preferences\u2026"
            self._action_prefs.setText(label)

    def _check_tesseract_warning(self) -> None:
        """Show a one-time tray warning if Tesseract is not found (Windows only)."""
        import shutil
        import os
        from pathlib import Path

        # Check bundled path first (frozen app)
        if getattr(sys, "frozen", False):
            bundled = Path(sys.executable).parent / "tesseract" / "tesseract.exe"
            if bundled.exists():
                return  # Bundled Tesseract found — no warning needed

        found = shutil.which("tesseract")
        if not found:
            # Also check common Windows install paths
            candidates = [
                os.path.expandvars(r"%LOCALAPPDATA%\Programs\Tesseract-OCR\tesseract.exe"),
                r"C:\Program Files\Tesseract-OCR\tesseract.exe",
            ]
            for c in candidates:
                if os.path.isfile(c):
                    found = c
                    break

        if not found and self.tray_icon and self.tray_icon.isVisible():
            import tempfile
            log_path = os.path.join(
                tempfile.gettempdir(), "zh-en-translator-tesseract-install.log"
            )
            message = (
                "Tesseract OCR not found. Image capture may be limited.\n"
                f"See: {log_path}"
            )
            self.tray_icon.showMessage(
                "zh-en-translator",
                message,
                QSystemTrayIcon.MessageIcon.Warning,
                8000,
            )
            logger.warning("Tesseract not found — tray warning shown.")

    def _check_for_updates(self, manual: bool = False) -> None:
        if self._update_worker and self._update_worker.isRunning():
            return
        self._update_worker = _UpdateWorker()
        self._update_worker.result_ready.connect(
            lambda info: self._on_update_check_finished(info, manual)
        )
        self._update_worker.start()

    def _on_update_check_finished(self, release_info, manual: bool) -> None:
        # Save check timestamp regardless of outcome
        from datetime import datetime, timezone
        self.config.last_update_check = datetime.now(timezone.utc).isoformat()
        from zh_en_translator.config import save_config
        save_config(self.config)

        if not release_info:
            if manual:
                from PyQt6.QtWidgets import QMessageBox
                QMessageBox.information(
                    None, "Update Check", "Could not check for updates. Please try again later."
                )
            return

        from zh_en_translator import __version__
        from zh_en_translator.engines.updates import is_newer

        tag = release_info["tag_name"]
        if is_newer(tag, __version__):
            self._set_update_available(True, tag)
            if manual:
                from PyQt6.QtWidgets import QMessageBox
                msg = f"A new version is available: {tag}\n\nWould you like to visit the download page?"
                ans = QMessageBox.question(
                    None, "Update Available", msg,
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                )
                if ans == QMessageBox.StandardButton.Yes:
                    import webbrowser
                    webbrowser.open(release_info["html_url"])
        else:
            self._set_update_available(False)
            if manual:
                from PyQt6.QtWidgets import QMessageBox
                QMessageBox.information(
                    None, "Update Check", f"You are running the latest version ({__version__})."
                )

    def _open_preferences(self):
        from zh_en_translator.ui.preferences import PreferencesDialog
        from zh_en_translator.config import Config as _Config
        # Build a snapshot that reflects current RUNTIME state (sidebar_mode may
        # have been toggled via the tray menu without being saved to config yet).
        current = _Config(
            hotkey=self.config.hotkey,
            mode="sidebar" if self.sidebar_mode else "popup",
            startup=self.config.startup,
            auto_check_updates=self.config.auto_check_updates,
            last_update_check=self.config.last_update_check,
            font_family=self.config.font_family,
            font_size=self.config.font_size,
            bg_color=self.config.bg_color,
            theme=self.config.theme,
            side=self.config.side,
            sidebar_y=self.config.sidebar_y,
            sidebar_width=self.config.sidebar_width,
            color_fresh=self.config.color_fresh,
            color_idle=self.config.color_idle,
            external_lookup_url=self.config.external_lookup_url,
            ocr_engine=self.config.ocr_engine,
            show_pinyin=self.config.show_pinyin,
            pinyin_max_chars=self.config.pinyin_max_chars,
            traditional_to_simplified=self.config.traditional_to_simplified,
            ms_translator_enabled=self.config.ms_translator_enabled,
            ms_translator_api_key=self.config.ms_translator_api_key,
            ms_translator_region=self.config.ms_translator_region,
            deepl_enabled=self.config.deepl_enabled,
            deepl_api_key=self.config.deepl_api_key,
            deepl_pro=self.config.deepl_pro,
        )
        dialog = PreferencesDialog(
            current,
            update_available=self._has_update,
            update_version=self._update_version,
        )
        dialog.settings_applied.connect(self._on_settings_applied)
        dialog._btn_check_now.clicked.connect(lambda: self._check_for_updates(manual=True))
        dialog.exec()

    def _on_settings_applied(self, cfg: Config) -> None:
        old_hotkey = self.config.hotkey
        self.config = cfg
        save_config(cfg)

        # Re-apply startup registry entry whenever settings change
        _apply_startup_setting(cfg.startup, _get_frozen_exe_path())

        # Re-register hotkey if changed
        if cfg.hotkey != old_hotkey:
            self.hotkey_manager.stop()
            self.hotkey_manager = HotKeyManager(hotkey_string=cfg.hotkey)
            try:
                self.hotkey_manager.start(self._hotkey_signal.emit)
            except RuntimeError as e:
                logger.warning("Failed to register new hotkey: %s", e)

        # Apply config to sidebar
        self.sidebar.apply_config(cfg)

        # Apply sidebar mode
        new_mode = cfg.mode == "sidebar"
        if new_mode != self.sidebar_mode:
            self.sidebar_mode = new_mode
            self._update_tray_sidebar_label()
            if self.sidebar_mode and not self.sidebar.isVisible():
                self.sidebar.show()
            elif not self.sidebar_mode:
                self.sidebar.collapse()

        # Update tray sidebar-side label to match config
        self._sidebar_on_left = cfg.side == "left"
        self.action_sidebar_side.setText(
            "Move Sidebar to Right" if self._sidebar_on_left else "Move Sidebar to Left"
        )

    def _on_pause_resume(self):
        self.paused = not self.paused
        if self.action_pause:
            self.action_pause.setText("Resume" if self.paused else "Pause")

    def start(self):
        try:
            self.hotkey_manager.start(self._hotkey_signal.emit)
        except RuntimeError as e:
            logger.warning("Failed to register global hotkey: %s", e)

        sys.exit(self.app.exec())

    def stop(self):
        self.hotkey_manager.stop()
        if self.popup:
            self.popup.close()
        self.app.quit()


def setup_logging():
    """Configure persistent file-based logging.

    Logs to %APPDATA%/zh-en-translator/logs/app.log (Windows) or
    ~/.config/zh-en-translator/logs/app.log (others).
    """
    from zh_en_translator.config import get_config_path
    log_dir = get_config_path().parent / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "app.log"

    # Use a rotating file handler to keep log size under control
    from logging.handlers import RotatingFileHandler
    handler = RotatingFileHandler(
        log_file, maxBytes=1024 * 1024, backupCount=3, encoding="utf-8"
    )
    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    )
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    root_logger.addHandler(handler)

    # Also keep stderr logging for dev/visibility
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    root_logger.addHandler(stream_handler)

    logger.info("--- Application Started ---")
    logger.info("Log file: %s", log_file)


def main():
    # Suppress Qt's harmless "Unable to open monitor interface" warning that
    # appears when a secondary display is detected by Windows but currently
    # powered off (error 0xe0000225 = ERROR_NOT_FOUND from the GDI/DXGI layer).
    # Must be set before QApplication is created.
    import os
    os.environ.setdefault("QT_LOGGING_RULES", "qt.qpa.screen.warning=false")

    setup_logging()
    app = TranslatorApp()
    app.start()


if __name__ == "__main__":
    main()
