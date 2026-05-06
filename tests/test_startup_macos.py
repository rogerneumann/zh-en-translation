"""Tests for macOS-specific startup/autostart in _apply_startup_setting().

Covers the LaunchAgents plist branch (darwin) and verifies the Linux XDG
branch is unaffected (regression guard).
"""

from __future__ import annotations

import pathlib
import sys
from unittest.mock import patch

import pytest

from zh_en_translator.app import _apply_startup_setting


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _startup(enabled: bool, exe: str, platform: str, home: pathlib.Path) -> None:
    """Call _apply_startup_setting with mocked sys.platform and Path.home()."""
    with (
        patch.object(sys, "platform", platform),
        patch("pathlib.Path.home", return_value=home),
    ):
        _apply_startup_setting(enabled, exe)


# ---------------------------------------------------------------------------
# macOS — LaunchAgents plist
# ---------------------------------------------------------------------------

class TestLaunchAgentsMacOS:
    def test_creates_plist_when_enabled(self, tmp_path):
        """_apply_startup_setting(True) on darwin creates the LaunchAgents plist."""
        _startup(True, "/fake/zh-en-translator", "darwin", tmp_path)
        plist = tmp_path / "Library" / "LaunchAgents" / "com.rogerneumann.zh-en-translator.plist"
        assert plist.exists()

    def test_plist_contains_correct_exe(self, tmp_path):
        """The plist ProgramArguments array contains the supplied executable path."""
        exe = "/Applications/Zh-En Translator.app/Contents/MacOS/zh-en-translator"
        _startup(True, exe, "darwin", tmp_path)
        plist = tmp_path / "Library" / "LaunchAgents" / "com.rogerneumann.zh-en-translator.plist"
        content = plist.read_text(encoding="utf-8")
        assert exe in content

    def test_plist_has_run_at_load(self, tmp_path):
        """The plist includes RunAtLoad = true."""
        _startup(True, "/fake/exe", "darwin", tmp_path)
        plist = tmp_path / "Library" / "LaunchAgents" / "com.rogerneumann.zh-en-translator.plist"
        content = plist.read_text(encoding="utf-8")
        assert "<key>RunAtLoad</key>" in content
        assert "<true/>" in content

    def test_plist_has_correct_label(self, tmp_path):
        """The plist Label is com.rogerneumann.zh-en-translator."""
        _startup(True, "/fake/exe", "darwin", tmp_path)
        plist = tmp_path / "Library" / "LaunchAgents" / "com.rogerneumann.zh-en-translator.plist"
        content = plist.read_text(encoding="utf-8")
        assert "com.rogerneumann.zh-en-translator" in content

    def test_creates_launch_agents_dir(self, tmp_path):
        """~/Library/LaunchAgents/ is created if it does not already exist."""
        launch_agents = tmp_path / "Library" / "LaunchAgents"
        assert not launch_agents.exists()
        _startup(True, "/fake/exe", "darwin", tmp_path)
        assert launch_agents.is_dir()

    def test_removes_plist_when_disabled(self, tmp_path):
        """_apply_startup_setting(False) on darwin removes an existing plist."""
        _startup(True, "/fake/exe", "darwin", tmp_path)
        plist = tmp_path / "Library" / "LaunchAgents" / "com.rogerneumann.zh-en-translator.plist"
        assert plist.exists()

        _startup(False, "/fake/exe", "darwin", tmp_path)
        assert not plist.exists()

    def test_remove_when_plist_absent_is_safe(self, tmp_path):
        """Disabling startup when no plist exists does not raise."""
        _startup(False, "/fake/exe", "darwin", tmp_path)  # must not raise

    def test_no_op_when_exe_empty_and_not_on_path(self, tmp_path):
        """Empty exe_path with no system binary on PATH skips plist creation silently."""
        with (
            patch.object(sys, "platform", "darwin"),
            patch("pathlib.Path.home", return_value=tmp_path),
            patch("shutil.which", return_value=None),
        ):
            _apply_startup_setting(True, "")
        launch_agents = tmp_path / "Library" / "LaunchAgents"
        assert not launch_agents.exists() or not any(launch_agents.glob("*.plist"))

    def test_uses_which_when_exe_path_empty(self, tmp_path):
        """When exe_path is empty but binary is on PATH, plist is created using the which result."""
        with (
            patch.object(sys, "platform", "darwin"),
            patch("pathlib.Path.home", return_value=tmp_path),
            patch("shutil.which", return_value="/usr/local/bin/zh-en-translator"),
        ):
            _apply_startup_setting(True, "")
        plist = tmp_path / "Library" / "LaunchAgents" / "com.rogerneumann.zh-en-translator.plist"
        assert plist.exists()
        assert "/usr/local/bin/zh-en-translator" in plist.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Linux — XDG autostart (regression: macOS branch must not break Linux)
# ---------------------------------------------------------------------------

class TestXDGAutostartLinux:
    def test_creates_desktop_file_on_linux(self, tmp_path):
        """_apply_startup_setting(True) on linux creates an XDG .desktop file."""
        _startup(True, "/fake/zh-en-translator", "linux", tmp_path)
        desktop = tmp_path / ".config" / "autostart" / "zh-en-translator.desktop"
        assert desktop.exists()

    def test_desktop_file_contains_exec_line(self, tmp_path):
        """.desktop file contains the correct Exec= line."""
        exe = "/usr/local/bin/zh-en-translator"
        _startup(True, exe, "linux", tmp_path)
        desktop = tmp_path / ".config" / "autostart" / "zh-en-translator.desktop"
        content = desktop.read_text(encoding="utf-8")
        assert f"Exec={exe}" in content

    def test_removes_desktop_file_on_linux(self, tmp_path):
        """_apply_startup_setting(False) on linux removes the .desktop file."""
        _startup(True, "/fake/exe", "linux", tmp_path)
        desktop = tmp_path / ".config" / "autostart" / "zh-en-translator.desktop"
        assert desktop.exists()

        _startup(False, "/fake/exe", "linux", tmp_path)
        assert not desktop.exists()

    def test_linux_does_not_create_launchagents(self, tmp_path):
        """On linux, no ~/Library/LaunchAgents/ directory is created."""
        _startup(True, "/fake/exe", "linux", tmp_path)
        assert not (tmp_path / "Library" / "LaunchAgents").exists()
