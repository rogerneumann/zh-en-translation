"""Tests for the theme palette system."""

import sys
import os
import pytest

os.environ["QT_QPA_PLATFORM"] = "offscreen"


@pytest.fixture(scope="session")
def qapp():
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication(sys.argv)
    return app


def test_resolve_palette_light():
    from zh_en_translator.engines.themes import resolve_palette
    p = resolve_palette("light", system_is_dark=False)
    assert p.bg == "#F8F8F8"
    assert p.text == "#111111"


def test_resolve_palette_dark():
    from zh_en_translator.engines.themes import resolve_palette
    p = resolve_palette("dark", system_is_dark=False)
    assert p.bg == "#1E1E1E"


def test_resolve_palette_sepia():
    from zh_en_translator.engines.themes import resolve_palette
    p = resolve_palette("sepia", system_is_dark=False)
    assert "#" in p.bg  # sepia has a hex bg


def test_resolve_palette_system_light():
    from zh_en_translator.engines.themes import resolve_palette
    p = resolve_palette("system", system_is_dark=False)
    assert p == resolve_palette("light", False)


def test_resolve_palette_system_dark():
    from zh_en_translator.engines.themes import resolve_palette
    p = resolve_palette("system", system_is_dark=True)
    assert p == resolve_palette("dark", True)


def test_resolve_palette_unknown_fallback():
    from zh_en_translator.engines.themes import resolve_palette
    p = resolve_palette("nonexistent", system_is_dark=False)
    assert p == resolve_palette("light", False)


def test_config_theme_default():
    from zh_en_translator.config import Config
    assert Config().theme == "system"


def test_config_theme_roundtrip(tmp_path):
    from zh_en_translator.config import Config, save_config, load_config
    cfg = Config(theme="sepia")
    path = tmp_path / "config.toml"
    save_config(cfg, path)
    loaded = load_config(path)
    assert loaded.theme == "sepia"


def test_preferences_theme_combo_exists(qapp):
    from zh_en_translator.config import Config
    from zh_en_translator.ui.preferences import PreferencesDialog
    dlg = PreferencesDialog(Config())
    assert hasattr(dlg, "_theme_combo")
    # Should have 4 items: system, light, dark, sepia
    assert dlg._theme_combo.count() == 4


def test_preferences_theme_combo_reflects_config(qapp):
    from zh_en_translator.config import Config
    from zh_en_translator.ui.preferences import PreferencesDialog
    dlg = PreferencesDialog(Config(theme="dark"))
    assert dlg._theme_combo.currentData() == "dark"


def test_preferences_collect_theme(qapp):
    from zh_en_translator.config import Config
    from zh_en_translator.ui.preferences import PreferencesDialog
    dlg = PreferencesDialog(Config())
    # Select "sepia" (index 3)
    idx = dlg._theme_combo.findData("sepia")
    dlg._theme_combo.setCurrentIndex(idx)
    collected = dlg._collect_config()
    assert collected.theme == "sepia"
