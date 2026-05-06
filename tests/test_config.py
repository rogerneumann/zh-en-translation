"""Tests for the TOML-backed config system."""

from __future__ import annotations

from pathlib import Path


from zh_en_translator.config import Config, load_config, save_config, get_config_path


# ---------------------------------------------------------------------------
# test_config_defaults
# ---------------------------------------------------------------------------

def test_config_defaults():
    """Config() has the expected default values."""
    cfg = Config()
    assert cfg.hotkey == "<ctrl>+<shift>+t"
    assert cfg.mode == "popup"
    assert cfg.font_family == ""
    assert cfg.font_size == 13
    assert cfg.bg_color == ""
    assert cfg.side == "right"
    assert cfg.sidebar_y == 200
    assert cfg.color_fresh == "#00C9CC"
    assert cfg.color_idle == "#9E8080"
    assert cfg.external_lookup_url == "https://www.mdbg.net/chinese/dictionary?wdqb={query}"
    assert cfg.ocr_engine == "auto"


# ---------------------------------------------------------------------------
# test_save_and_load
# ---------------------------------------------------------------------------

def test_save_and_load(tmp_path):
    """Save a Config with non-default values and reload — all fields match."""
    config_file = tmp_path / "config.toml"

    original = Config(
        hotkey="<ctrl>+<alt>+z",
        mode="sidebar",
        font_family="Arial",
        font_size=16,
        bg_color="#FF0000",
        side="left",
        sidebar_y=400,
        color_fresh="#AABBCC",
        color_idle="#112233",
        external_lookup_url="https://example.com/{query}",
        ocr_engine="tesseract",
    )

    save_config(original, config_path=config_file)
    loaded = load_config(config_path=config_file)

    assert loaded.hotkey == "<ctrl>+<alt>+z"
    assert loaded.mode == "sidebar"
    assert loaded.font_family == "Arial"
    assert loaded.font_size == 16
    assert loaded.bg_color == "#FF0000"
    assert loaded.side == "left"
    assert loaded.sidebar_y == 400
    assert loaded.color_fresh == "#AABBCC"
    assert loaded.color_idle == "#112233"
    assert loaded.external_lookup_url == "https://example.com/{query}"
    assert loaded.ocr_engine == "tesseract"


# ---------------------------------------------------------------------------
# test_load_missing_file
# ---------------------------------------------------------------------------

def test_load_missing_file(tmp_path):
    """load_config() with a non-existent path returns defaults."""
    missing = tmp_path / "nonexistent" / "config.toml"
    cfg = load_config(config_path=missing)
    assert cfg == Config()


# ---------------------------------------------------------------------------
# test_load_partial_toml
# ---------------------------------------------------------------------------

def test_load_partial_toml(tmp_path):
    """A TOML with only [display]\nfont_size = 20 loads 20 for font_size, defaults elsewhere."""
    config_file = tmp_path / "config.toml"
    config_file.write_text("[display]\nfont_size = 20\n", encoding="utf-8")

    cfg = load_config(config_path=config_file)

    assert cfg.font_size == 20
    # All other fields should be defaults
    defaults = Config()
    assert cfg.hotkey == defaults.hotkey
    assert cfg.mode == defaults.mode
    assert cfg.font_family == defaults.font_family
    assert cfg.bg_color == defaults.bg_color
    assert cfg.side == defaults.side
    assert cfg.sidebar_y == defaults.sidebar_y
    assert cfg.color_fresh == defaults.color_fresh
    assert cfg.color_idle == defaults.color_idle
    assert cfg.external_lookup_url == defaults.external_lookup_url
    assert cfg.ocr_engine == defaults.ocr_engine


# ---------------------------------------------------------------------------
# test_load_invalid_toml
# ---------------------------------------------------------------------------

def test_load_invalid_toml(tmp_path, caplog):
    """Garbage TOML file returns defaults and does not raise an exception."""
    import logging
    config_file = tmp_path / "config.toml"
    config_file.write_text("this is not valid toml ][[ !!!", encoding="utf-8")

    with caplog.at_level(logging.WARNING, logger="zh_en_translator.config"):
        cfg = load_config(config_path=config_file)

    assert cfg == Config()

    # A warning should have been logged
    assert any("Failed to parse" in r.message for r in caplog.records)


# ---------------------------------------------------------------------------
# test_save_creates_dirs
# ---------------------------------------------------------------------------

def test_save_creates_dirs(tmp_path):
    """save_config creates parent directories as needed."""
    config_file = tmp_path / "nested" / "deep" / "config.toml"
    assert not config_file.parent.exists()

    cfg = Config()
    save_config(cfg, config_path=config_file)

    assert config_file.exists()
    loaded = load_config(config_path=config_file)
    assert loaded == cfg


# ---------------------------------------------------------------------------
# test_get_config_path
# ---------------------------------------------------------------------------

def test_get_config_path():
    """get_config_path() returns a Path ending in config.toml."""
    path = get_config_path()
    assert isinstance(path, Path)
    assert path.name == "config.toml"
    assert "zh-en-translator" in str(path)


# ---------------------------------------------------------------------------
# test_toml_special_chars
# ---------------------------------------------------------------------------

def test_toml_special_chars(tmp_path):
    """Config with backslashes and quotes in values round-trips correctly."""
    config_file = tmp_path / "config.toml"

    # Windows-style URL template with special chars
    original = Config(
        external_lookup_url='https://example.com/search?q={query}&lang="zh"',
    )
    save_config(original, config_path=config_file)
    loaded = load_config(config_path=config_file)

    assert loaded.external_lookup_url == original.external_lookup_url


# ---------------------------------------------------------------------------
# test_traditional_to_simplified_roundtrip
# ---------------------------------------------------------------------------

def test_traditional_to_simplified_roundtrip(tmp_path):
    """traditional_to_simplified=False saves and reloads correctly."""
    config_file = tmp_path / "config.toml"

    original = Config(traditional_to_simplified=False)
    save_config(original, config_path=config_file)
    loaded = load_config(config_path=config_file)

    assert loaded.traditional_to_simplified is False


def test_traditional_to_simplified_default():
    """traditional_to_simplified defaults to True."""
    cfg = Config()
    assert cfg.traditional_to_simplified is True


def test_traditional_to_simplified_true_roundtrip(tmp_path):
    """traditional_to_simplified=True saves and reloads correctly."""
    config_file = tmp_path / "config.toml"

    original = Config(traditional_to_simplified=True)
    save_config(original, config_path=config_file)
    loaded = load_config(config_path=config_file)

    assert loaded.traditional_to_simplified is True


# ---------------------------------------------------------------------------
# test_macos_accessibility_prompted
# ---------------------------------------------------------------------------

def test_macos_accessibility_prompted_default():
    """macos_accessibility_prompted defaults to False."""
    cfg = Config()
    assert cfg.macos_accessibility_prompted is False


def test_macos_accessibility_prompted_roundtrip_true(tmp_path):
    """macos_accessibility_prompted=True saves and reloads correctly."""
    config_file = tmp_path / "config.toml"
    original = Config(macos_accessibility_prompted=True)
    save_config(original, config_path=config_file)
    loaded = load_config(config_path=config_file)
    assert loaded.macos_accessibility_prompted is True


def test_macos_accessibility_prompted_roundtrip_false(tmp_path):
    """macos_accessibility_prompted=False saves and reloads correctly."""
    config_file = tmp_path / "config.toml"
    original = Config(macos_accessibility_prompted=False)
    save_config(original, config_path=config_file)
    loaded = load_config(config_path=config_file)
    assert loaded.macos_accessibility_prompted is False


def test_macos_accessibility_prompted_missing_section(tmp_path):
    """Legacy config without [macos] section loads with default False."""
    config_file = tmp_path / "config.toml"
    config_file.write_text("[general]\nhotkey = \"<ctrl>+<shift>+t\"\n", encoding="utf-8")
    cfg = load_config(config_path=config_file)
    assert cfg.macos_accessibility_prompted is False
