"""Tests for macOS Accessibility permission check (_check_macos_accessibility).

All tests mock ctypes and Qt so they run on any platform without real macOS
APIs or a visible dialog.
"""

from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

import pytest

from zh_en_translator.app import _check_macos_accessibility
from zh_en_translator.config import Config, load_config


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ax_context(trusted: bool):
    """Return a context-manager stack that fakes a macOS ctypes environment."""
    mock_lib = MagicMock()
    mock_lib.AXIsProcessTrusted.return_value = trusted

    return (
        patch("ctypes.util.find_library", return_value="/fake/ApplicationServices"),
        patch("ctypes.cdll.LoadLibrary", return_value=mock_lib),
    )


# ---------------------------------------------------------------------------
# Platform guard
# ---------------------------------------------------------------------------

class TestPlatformGuard:
    def test_no_op_on_windows(self):
        """Returns immediately on win32 without touching ctypes."""
        with (
            patch.object(sys, "platform", "win32"),
            patch("ctypes.util.find_library") as mock_find,
        ):
            cfg = Config()
            _check_macos_accessibility(cfg, None)
            mock_find.assert_not_called()
        assert cfg.macos_accessibility_prompted is False

    def test_no_op_on_linux(self):
        """Returns immediately on linux without touching ctypes."""
        with (
            patch.object(sys, "platform", "linux"),
            patch("ctypes.util.find_library") as mock_find,
        ):
            cfg = Config()
            _check_macos_accessibility(cfg, None)
            mock_find.assert_not_called()
        assert cfg.macos_accessibility_prompted is False


# ---------------------------------------------------------------------------
# ctypes / library availability
# ---------------------------------------------------------------------------

class TestLibraryAvailability:
    def test_no_op_when_library_not_found(self):
        """Returns safely when ApplicationServices framework is not located."""
        with (
            patch.object(sys, "platform", "darwin"),
            patch("ctypes.util.find_library", return_value=None),
            patch("ctypes.cdll.LoadLibrary") as mock_load,
        ):
            cfg = Config()
            _check_macos_accessibility(cfg, None)
            mock_load.assert_not_called()
        assert cfg.macos_accessibility_prompted is False

    def test_no_op_when_ctypes_raises(self):
        """Exception from ctypes (broken library, sandbox) is caught without crashing."""
        with (
            patch.object(sys, "platform", "darwin"),
            patch("ctypes.util.find_library", side_effect=OSError("simulated")),
        ):
            cfg = Config()
            _check_macos_accessibility(cfg, None)  # must not raise
        assert cfg.macos_accessibility_prompted is False

    def test_no_op_when_load_library_raises(self):
        """LoadLibrary failure is caught without crashing."""
        with (
            patch.object(sys, "platform", "darwin"),
            patch("ctypes.util.find_library", return_value="/fake/lib"),
            patch("ctypes.cdll.LoadLibrary", side_effect=OSError("simulated")),
        ):
            cfg = Config()
            _check_macos_accessibility(cfg, None)
        assert cfg.macos_accessibility_prompted is False


# ---------------------------------------------------------------------------
# AXIsProcessTrusted result
# ---------------------------------------------------------------------------

class TestTrustedState:
    def test_no_dialog_when_already_trusted(self):
        """No dialog and no config mutation when Accessibility is already granted."""
        ax_find, ax_load = _ax_context(trusted=True)
        with (
            patch.object(sys, "platform", "darwin"),
            ax_find,
            ax_load,
            patch("PyQt6.QtWidgets.QMessageBox") as mock_cls,
        ):
            cfg = Config()
            _check_macos_accessibility(cfg, None)
            mock_cls.assert_not_called()
        assert cfg.macos_accessibility_prompted is False

    def test_no_dialog_when_already_prompted(self):
        """No dialog when prompted flag is already True, even if not trusted."""
        ax_find, ax_load = _ax_context(trusted=False)
        with (
            patch.object(sys, "platform", "darwin"),
            ax_find,
            ax_load,
            patch("PyQt6.QtWidgets.QMessageBox") as mock_cls,
        ):
            cfg = Config(macos_accessibility_prompted=True)
            _check_macos_accessibility(cfg, None)
            mock_cls.assert_not_called()
        assert cfg.macos_accessibility_prompted is True


# ---------------------------------------------------------------------------
# Dialog shown path
# ---------------------------------------------------------------------------

class TestDialogShown:
    def test_shows_dialog_when_not_trusted_and_not_prompted(self, tmp_path):
        """Dialog is shown when not trusted and not yet prompted."""
        ax_find, ax_load = _ax_context(trusted=False)
        mock_msg = MagicMock()
        mock_msg.clickedButton.return_value = None  # "Later" clicked

        with (
            patch.object(sys, "platform", "darwin"),
            ax_find,
            ax_load,
            patch("PyQt6.QtWidgets.QMessageBox", return_value=mock_msg),
        ):
            cfg = Config(macos_accessibility_prompted=False)
            _check_macos_accessibility(cfg, tmp_path / "config.toml")

        mock_msg.exec.assert_called_once()

    def test_saves_config_after_dialog(self, tmp_path):
        """cfg.macos_accessibility_prompted is set to True and written to disk."""
        ax_find, ax_load = _ax_context(trusted=False)
        mock_msg = MagicMock()
        mock_msg.clickedButton.return_value = None

        config_path = tmp_path / "config.toml"
        with (
            patch.object(sys, "platform", "darwin"),
            ax_find,
            ax_load,
            patch("PyQt6.QtWidgets.QMessageBox", return_value=mock_msg),
        ):
            cfg = Config()
            _check_macos_accessibility(cfg, config_path)

        assert cfg.macos_accessibility_prompted is True
        loaded = load_config(config_path=config_path)
        assert loaded.macos_accessibility_prompted is True

    def test_does_not_show_dialog_twice(self, tmp_path):
        """Second call after config is saved does not show the dialog again."""
        ax_find, ax_load = _ax_context(trusted=False)
        mock_msg = MagicMock()
        mock_msg.clickedButton.return_value = None
        config_path = tmp_path / "config.toml"

        with (
            patch.object(sys, "platform", "darwin"),
            ax_find,
            ax_load,
            patch("PyQt6.QtWidgets.QMessageBox", return_value=mock_msg),
        ):
            cfg = Config()
            _check_macos_accessibility(cfg, config_path)
            assert mock_msg.exec.call_count == 1
            # Second call — prompted flag is now True on cfg
            _check_macos_accessibility(cfg, config_path)
            assert mock_msg.exec.call_count == 1  # still just once

    def test_opens_system_settings_when_button_clicked(self, tmp_path):
        """QDesktopServices.openUrl is called when user clicks Open System Settings."""
        ax_find, ax_load = _ax_context(trusted=False)

        # Arrange: make addButton return a consistent sentinel so clickedButton matches
        open_btn = MagicMock(name="open_btn")
        mock_msg = MagicMock()
        mock_msg.addButton.return_value = open_btn
        mock_msg.clickedButton.return_value = open_btn  # user chose Open

        with (
            patch.object(sys, "platform", "darwin"),
            ax_find,
            ax_load,
            patch("PyQt6.QtWidgets.QMessageBox", return_value=mock_msg),
            patch("PyQt6.QtGui.QDesktopServices.openUrl") as mock_open,
        ):
            cfg = Config()
            _check_macos_accessibility(cfg, tmp_path / "config.toml")

        mock_open.assert_called_once()
        url_arg = mock_open.call_args[0][0]
        assert "Privacy_Accessibility" in str(url_arg)

    def test_does_not_open_url_when_later_clicked(self, tmp_path):
        """QDesktopServices.openUrl is NOT called when user clicks Later."""
        ax_find, ax_load = _ax_context(trusted=False)
        mock_msg = MagicMock()
        mock_msg.clickedButton.return_value = None  # Later button (not open_btn)

        with (
            patch.object(sys, "platform", "darwin"),
            ax_find,
            ax_load,
            patch("PyQt6.QtWidgets.QMessageBox", return_value=mock_msg),
            patch("PyQt6.QtGui.QDesktopServices.openUrl") as mock_open,
        ):
            cfg = Config()
            _check_macos_accessibility(cfg, tmp_path / "config.toml")

        mock_open.assert_not_called()
        assert cfg.macos_accessibility_prompted is True
