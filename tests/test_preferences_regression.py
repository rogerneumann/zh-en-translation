"""Regression tests for preferences dialog and app mode-persistence fixes.

These tests guard against regressions in bugs fixed on 2026-04-29:

  1. QFontComboBox replaced with curated QComboBox (full-screen dropdown fix)
  2. Aptos added to font list
  3. _load_config_into_ui was only restoring 5 of ~15 config fields
  4. _update_preview not applying font to preview labels
  5. "Check for Updates Now" button unconnected
  6. _on_sidebar_closed / _on_toggle_sidebar_mode / _on_toggle_sidebar_side
     mutating config.mode / config.side without calling save_config()
"""

from __future__ import annotations

import types
from unittest.mock import MagicMock

import pytest

from zh_en_translator.config import Config
from zh_en_translator.ui.preferences import PreferencesDialog, _FONT_CHOICES


# ---------------------------------------------------------------------------
# Font picker — replaced QFontComboBox with curated QComboBox
# ---------------------------------------------------------------------------

def test_font_combo_is_plain_combobox(qapp):
    """Font picker must not be QFontComboBox (which enumerates every system font)."""
    from PyQt6.QtWidgets import QFontComboBox, QComboBox
    dlg = PreferencesDialog(Config())
    assert not isinstance(dlg._font_combo, QFontComboBox)
    assert isinstance(dlg._font_combo, QComboBox)


def test_font_combo_max_visible_items(qapp):
    """Dropdown must be capped so it does not fill the full screen."""
    dlg = PreferencesDialog(Config())
    assert dlg._font_combo.maxVisibleItems() <= 15


def test_font_choices_contains_aptos():
    """Aptos must be present in the module-level _FONT_CHOICES list."""
    assert "Aptos" in _FONT_CHOICES


def test_font_combo_has_aptos_entry(qapp):
    """Aptos must be selectable in the font combo (userData == 'Aptos')."""
    dlg = PreferencesDialog(Config())
    assert dlg._font_combo.findData("Aptos") >= 0


def test_font_combo_system_default_userData_is_empty_string(qapp):
    """The '(system default)' entry must store '' as userData so font_family stays ''."""
    dlg = PreferencesDialog(Config(font_family=""))
    assert dlg._font_combo.currentIndex() == 0
    assert dlg._font_combo.currentData() == ""


def test_font_combo_reflects_named_font(qapp):
    """Opening dialog with font_family='Aptos' selects Aptos in the combo."""
    dlg = PreferencesDialog(Config(font_family="Aptos"))
    assert dlg._font_combo.currentData() == "Aptos"


def test_font_combo_reflects_custom_font_not_in_curated_list(qapp):
    """A saved font not in the curated list is still shown as editable text."""
    dlg = PreferencesDialog(Config(font_family="Wingdings"))
    assert "Wingdings" in dlg._font_combo.currentText()


def test_collect_config_system_default_produces_empty_font_family(qapp):
    """Selecting '(system default)' must write font_family='' to collected config."""
    dlg = PreferencesDialog(Config(font_family="Aptos"))
    dlg._font_combo.setCurrentIndex(0)
    assert dlg._collect_config().font_family == ""


def test_collect_config_named_font_round_trips(qapp):
    """Selecting a named font produces that exact string in collected config."""
    dlg = PreferencesDialog(Config())
    idx = dlg._font_combo.findData("Aptos")
    dlg._font_combo.setCurrentIndex(idx)
    assert dlg._collect_config().font_family == "Aptos"


# ---------------------------------------------------------------------------
# _load_config_into_ui — mode radio buttons
# ---------------------------------------------------------------------------

def test_reflects_mode_popup(qapp):
    """Popup radio is checked when config.mode == 'popup'."""
    dlg = PreferencesDialog(Config(mode="popup"))
    assert dlg._mode_popup.isChecked() is True
    assert dlg._mode_sidebar.isChecked() is False


def test_reflects_mode_sidebar(qapp):
    """Sidebar radio is checked when config.mode == 'sidebar'."""
    dlg = PreferencesDialog(Config(mode="sidebar"))
    assert dlg._mode_sidebar.isChecked() is True
    assert dlg._mode_popup.isChecked() is False


def test_collect_config_mode_reads_radio(qapp):
    """_collect_config() reads mode from the radio button, not the stale config snapshot."""
    dlg = PreferencesDialog(Config(mode="popup"))
    dlg._mode_sidebar.setChecked(True)
    assert dlg._collect_config().mode == "sidebar"


# ---------------------------------------------------------------------------
# _load_config_into_ui — theme combo
# ---------------------------------------------------------------------------

def test_reflects_theme_dark(qapp):
    assert PreferencesDialog(Config(theme="dark"))._theme_combo.currentData() == "dark"


def test_reflects_theme_sepia(qapp):
    assert PreferencesDialog(Config(theme="sepia"))._theme_combo.currentData() == "sepia"


def test_reflects_theme_system(qapp):
    assert PreferencesDialog(Config(theme="system"))._theme_combo.currentData() == "system"


# ---------------------------------------------------------------------------
# _load_config_into_ui — side radio buttons
# ---------------------------------------------------------------------------

def test_reflects_side_right(qapp):
    dlg = PreferencesDialog(Config(side="right"))
    assert dlg._side_right.isChecked() is True
    assert dlg._side_left.isChecked() is False


def test_reflects_side_left(qapp):
    dlg = PreferencesDialog(Config(side="left"))
    assert dlg._side_left.isChecked() is True
    assert dlg._side_right.isChecked() is False


# ---------------------------------------------------------------------------
# _load_config_into_ui — background color
# ---------------------------------------------------------------------------

def test_reflects_bg_color(qapp):
    dlg = PreferencesDialog(Config(bg_color="#ab1234"))
    assert dlg._bg_color_btn.get_color_str() == "#ab1234"


def test_reflects_bg_color_empty(qapp):
    dlg = PreferencesDialog(Config(bg_color=""))
    assert dlg._bg_color_btn.get_color_str() == ""


# ---------------------------------------------------------------------------
# _load_config_into_ui — pinyin
# ---------------------------------------------------------------------------

def test_reflects_show_pinyin_true_enables_spin(qapp):
    dlg = PreferencesDialog(Config(show_pinyin=True))
    assert dlg._show_pinyin_check.isChecked() is True
    assert dlg._pinyin_max_spin.isEnabled() is True


def test_reflects_show_pinyin_false_disables_spin(qapp):
    """Spin box must be disabled immediately on open when show_pinyin is False."""
    dlg = PreferencesDialog(Config(show_pinyin=False))
    assert dlg._show_pinyin_check.isChecked() is False
    assert dlg._pinyin_max_spin.isEnabled() is False


def test_reflects_pinyin_max_chars(qapp):
    dlg = PreferencesDialog(Config(pinyin_max_chars=150))
    assert dlg._pinyin_max_spin.value() == 150


# ---------------------------------------------------------------------------
# _load_config_into_ui — OCR engine
# ---------------------------------------------------------------------------

def test_reflects_ocr_engine_tesseract(qapp):
    dlg = PreferencesDialog(Config(ocr_engine="tesseract"))
    assert dlg._ocr_combo.currentData() == "tesseract"


def test_reflects_ocr_engine_windows(qapp):
    dlg = PreferencesDialog(Config(ocr_engine="windows"))
    assert dlg._ocr_combo.currentData() == "windows"


# ---------------------------------------------------------------------------
# _load_config_into_ui — cloud / API checkboxes
# ---------------------------------------------------------------------------

def test_reflects_ms_translator_enabled_true(qapp):
    assert PreferencesDialog(Config(ms_translator_enabled=True))._ms_enabled_check.isChecked() is True


def test_reflects_ms_translator_enabled_false(qapp):
    assert PreferencesDialog(Config(ms_translator_enabled=False))._ms_enabled_check.isChecked() is False


def test_reflects_deepl_enabled_true(qapp):
    assert PreferencesDialog(Config(deepl_enabled=True))._deepl_enabled_check.isChecked() is True


def test_reflects_deepl_enabled_false(qapp):
    assert PreferencesDialog(Config(deepl_enabled=False))._deepl_enabled_check.isChecked() is False


# ---------------------------------------------------------------------------
# _update_preview applies font to preview labels
# ---------------------------------------------------------------------------

def test_update_preview_applies_font_family(qapp):
    """Preview labels must have the selected font family in their stylesheet.

    The dialog has a global QWidget stylesheet that overrides setFont(), so the
    correct mechanism is a per-label styleSheet() containing the font-family rule.
    """
    dlg = PreferencesDialog(Config(font_family="Aptos"))
    dlg._update_preview()
    for lbl in (dlg._preview_pinyin, dlg._preview_source, dlg._preview_trans):
        assert "Aptos" in lbl.styleSheet(), f"font-family not in styleSheet: {lbl.styleSheet()!r}"


def test_update_preview_applies_font_size(qapp):
    """Preview labels must have the selected font size in their stylesheet."""
    dlg = PreferencesDialog(Config(font_size=20))
    dlg._update_preview()
    for lbl in (dlg._preview_pinyin, dlg._preview_source, dlg._preview_trans):
        assert "20pt" in lbl.styleSheet(), f"font-size not in styleSheet: {lbl.styleSheet()!r}"


# ---------------------------------------------------------------------------
# "Check for Updates Now" button wired up
# ---------------------------------------------------------------------------

def test_check_updates_method_exists(qapp):
    """_check_updates_now must exist on the dialog."""
    dlg = PreferencesDialog(Config())
    assert hasattr(dlg, "_check_updates_now")
    assert callable(dlg._check_updates_now)


def test_check_updates_button_connected(qapp, monkeypatch):
    """Clicking the button must reach _check_updates_now (verified via its network call)."""
    import zh_en_translator.engines.updates as upd
    from PyQt6.QtWidgets import QMessageBox
    called = []
    # Stub out the network call and the result dialog so the test doesn't block
    monkeypatch.setattr(upd, "get_latest_release", lambda: called.append(True) or None)
    monkeypatch.setattr(QMessageBox, "information", staticmethod(lambda *a, **kw: None))
    dlg = PreferencesDialog(Config())
    dlg._btn_check_now.click()
    assert called, "Button click did not invoke _check_updates_now"


# ---------------------------------------------------------------------------
# App runtime persistence — mode/side changes must call save_config()
# ---------------------------------------------------------------------------
# These tests bind App unbound methods to a minimal SimpleNamespace to avoid
# full App instantiation (tray icon, hotkey listener, system-specific APIs).

def _fake_app(**overrides):
    """Minimal stand-in with the attributes each method touches."""
    ns = types.SimpleNamespace(
        sidebar_mode=True,
        config=Config(mode="sidebar", side="left"),
        sidebar=MagicMock(),
        action_sidebar=MagicMock(),
        action_sidebar_side=MagicMock(),
        _sidebar_on_left=True,
        _update_tray_sidebar_label=lambda: None,
    )
    for k, v in overrides.items():
        setattr(ns, k, v)
    return ns


def test_on_sidebar_closed_persists_mode(monkeypatch):
    """Closing the sidebar must write mode='popup' to disk via save_config."""
    import zh_en_translator.app as app_mod
    saved = []
    monkeypatch.setattr(app_mod, "save_config", lambda cfg: saved.append(cfg.mode))
    fake = _fake_app(sidebar_mode=True, config=Config(mode="sidebar"))
    app_mod.TranslatorApp._on_sidebar_closed(fake)
    assert fake.sidebar_mode is False
    assert fake.config.mode == "popup"
    assert saved == ["popup"], f"save_config not called correctly; got {saved}"


def test_on_toggle_sidebar_mode_on_persists(monkeypatch):
    """Enabling sidebar via tray toggle must persist mode='sidebar'."""
    import zh_en_translator.app as app_mod
    saved = []
    monkeypatch.setattr(app_mod, "save_config", lambda cfg: saved.append(cfg.mode))
    fake = _fake_app(sidebar_mode=False, config=Config(mode="popup"))
    app_mod.TranslatorApp._on_toggle_sidebar_mode(fake, True)
    assert fake.config.mode == "sidebar"
    assert "sidebar" in saved, f"save_config not called; got {saved}"


def test_on_toggle_sidebar_mode_off_persists(monkeypatch):
    """Disabling sidebar via tray toggle must persist mode='popup'."""
    import zh_en_translator.app as app_mod
    saved = []
    monkeypatch.setattr(app_mod, "save_config", lambda cfg: saved.append(cfg.mode))
    fake = _fake_app(sidebar_mode=True, config=Config(mode="sidebar"))
    app_mod.TranslatorApp._on_toggle_sidebar_mode(fake, False)
    assert fake.config.mode == "popup"
    assert "popup" in saved, f"save_config not called; got {saved}"


def test_on_toggle_sidebar_side_updates_config_and_persists(monkeypatch):
    """Toggling side via tray must update config.side and call save_config."""
    import zh_en_translator.app as app_mod
    saved_sides = []
    monkeypatch.setattr(app_mod, "save_config", lambda cfg: saved_sides.append(cfg.side))
    fake = _fake_app(_sidebar_on_left=True, config=Config(side="left"))
    app_mod.TranslatorApp._on_toggle_sidebar_side(fake)
    assert fake.config.side == "right"
    assert "right" in saved_sides, f"save_config not called; got {saved_sides}"


def test_on_toggle_sidebar_side_round_trips(monkeypatch):
    """Toggling side twice must restore the original value."""
    import zh_en_translator.app as app_mod
    monkeypatch.setattr(app_mod, "save_config", lambda cfg: None)
    fake = _fake_app(_sidebar_on_left=False, config=Config(side="right"))
    app_mod.TranslatorApp._on_toggle_sidebar_side(fake)   # right -> left
    assert fake.config.side == "left"
    app_mod.TranslatorApp._on_toggle_sidebar_side(fake)   # left -> right
    assert fake.config.side == "right"
