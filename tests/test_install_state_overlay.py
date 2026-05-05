"""Tests for the [app] section additions to install_state.py.

Tests get_overlay_version(), set_overlay_version(),
get_architecture(), and set_architecture().
"""

from __future__ import annotations

import pathlib
import tempfile

import pytest

from zh_en_translator.install_state import (
    get_architecture,
    get_overlay_version,
    set_architecture,
    set_overlay_version,
    load_state,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _empty_state_file(td: pathlib.Path) -> pathlib.Path:
    """Create a minimal install_state.toml with no [app] section."""
    p = td / "install_state.toml"
    p.write_text(
        "[install]\n"
        'version = "2026.05.01"\n'
        'type    = "full"\n'
        'date    = "2026-05-01 00:00:00"\n'
        'dir     = ""\n'
        "\n"
        "[components]\n"
        "argos        = false\n"
        "windows_ocr  = false\n"
        "tesseract    = false\n",
        encoding="utf-8",
    )
    return p


# ---------------------------------------------------------------------------
# get_architecture
# ---------------------------------------------------------------------------

class TestGetArchitecture:
    def test_returns_none_when_section_absent(self):
        """Returns None when [app] section is not in the file (legacy install)."""
        with tempfile.TemporaryDirectory() as td:
            path = _empty_state_file(pathlib.Path(td))
            result = get_architecture(path=path)
        assert result is None

    def test_returns_value_after_set(self):
        """Returns the value written by set_architecture."""
        with tempfile.TemporaryDirectory() as td:
            path = _empty_state_file(pathlib.Path(td))
            set_architecture("overlay", path=path)
            result = get_architecture(path=path)
        assert result == "overlay"

    def test_missing_file_returns_none(self):
        """Returns None when the file doesn't exist at all."""
        with tempfile.TemporaryDirectory() as td:
            path = pathlib.Path(td) / "nonexistent.toml"
            result = get_architecture(path=path)
        assert result is None


# ---------------------------------------------------------------------------
# set_architecture
# ---------------------------------------------------------------------------

class TestSetArchitecture:
    def test_writes_overlay_architecture(self):
        """set_architecture('overlay') persists correctly."""
        with tempfile.TemporaryDirectory() as td:
            path = _empty_state_file(pathlib.Path(td))
            set_architecture("overlay", path=path)
            result = get_architecture(path=path)
        assert result == "overlay"

    def test_does_not_disturb_other_sections(self):
        """set_architecture preserves [install] and [components] data."""
        with tempfile.TemporaryDirectory() as td:
            path = _empty_state_file(pathlib.Path(td))
            set_architecture("overlay", path=path)
            state = load_state(path=path)
        assert state.version == "2026.05.01"
        assert state.install_type == "full"


# ---------------------------------------------------------------------------
# get_overlay_version / set_overlay_version
# ---------------------------------------------------------------------------

class TestOverlayVersion:
    def test_returns_empty_when_absent(self):
        """get_overlay_version returns '' when [app] section is absent."""
        with tempfile.TemporaryDirectory() as td:
            path = _empty_state_file(pathlib.Path(td))
            result = get_overlay_version(path=path)
        assert result == ""

    def test_round_trip(self):
        """set_overlay_version then get_overlay_version returns same value."""
        with tempfile.TemporaryDirectory() as td:
            path = _empty_state_file(pathlib.Path(td))
            set_overlay_version("2026.05.10", path=path)
            result = get_overlay_version(path=path)
        assert result == "2026.05.10"

    def test_update_does_not_disturb_architecture(self):
        """Updating overlay_version preserves architecture value."""
        with tempfile.TemporaryDirectory() as td:
            path = _empty_state_file(pathlib.Path(td))
            set_architecture("overlay", path=path)
            set_overlay_version("2026.05.10", path=path)
            arch = get_architecture(path=path)
        assert arch == "overlay"
