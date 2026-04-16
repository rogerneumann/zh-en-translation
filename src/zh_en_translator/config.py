"""TOML-backed configuration system for zh-en-translator.

Reads/writes ~/.config/zh-en-translator/config.toml (Linux/Mac)
or %APPDATA%/zh-en-translator/config.toml (Windows).
"""

from __future__ import annotations

import logging
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


def get_config_path() -> Path:
    """Return the path to the config file (does not guarantee it exists)."""
    try:
        from platformdirs import user_config_dir
        config_dir = Path(user_config_dir("zh-en-translator"))
    except ImportError:
        # Fallback if platformdirs not available
        if sys.platform == "win32":
            import os
            config_dir = Path(os.environ.get("APPDATA", Path.home())) / "zh-en-translator"
        else:
            config_dir = Path.home() / ".config" / "zh-en-translator"
    return config_dir / "config.toml"


@dataclass
class Config:
    # [general]
    hotkey: str = "<ctrl>+<shift>+t"
    mode: str = "popup"           # "popup" | "sidebar"

    # [display]
    font_family: str = ""         # empty = system default
    font_size: int = 13
    bg_color: str = ""            # empty = system palette; hex like "#FFFFFF"
    theme: str = "system"         # "system" | "dark" | "light" | "sepia"

    # [sidebar]
    side: str = "right"           # "left" | "right"
    sidebar_y: int = 200
    sidebar_width: int = 280
    color_fresh: str = "#00C9CC"
    color_idle: str = "#9E8080"

    # [lookup]
    external_lookup_url: str = "https://www.mdbg.net/chinese/dictionary?wdqb={query}"

    # [ocr]
    ocr_engine: str = "auto"      # "auto" | "windows" | "tesseract" | "paddle"

    # [pinyin]
    show_pinyin: bool = True
    pinyin_max_chars: int = 80

    # [translation]
    traditional_to_simplified: bool = True

    # [cloud]
    ms_translator_enabled: bool = False
    ms_translator_api_key: str = ""
    ms_translator_region: str = ""


def load_config(config_path: Path | None = None) -> Config:
    """Read config from TOML file and return a Config instance.

    Missing keys fall back to defaults. Parse errors log a warning and
    return all defaults. Never raises.
    """
    if config_path is None:
        config_path = get_config_path()

    if not config_path.exists():
        return Config()

    try:
        with open(config_path, "rb") as f:
            data = tomllib.load(f)
    except Exception as e:
        logger.warning("Failed to parse config file %s: %s", config_path, e)
        return Config()

    defaults = Config()

    def _get(section: str, key: str, default):
        return data.get(section, {}).get(key, default)

    return Config(
        hotkey=_get("general", "hotkey", defaults.hotkey),
        mode=_get("general", "mode", defaults.mode),
        font_family=_get("display", "font_family", defaults.font_family),
        font_size=_get("display", "font_size", defaults.font_size),
        bg_color=_get("display", "bg_color", defaults.bg_color),
        theme=_get("display", "theme", defaults.theme),
        side=_get("sidebar", "side", defaults.side),
        sidebar_y=_get("sidebar", "sidebar_y", defaults.sidebar_y),
        sidebar_width=_get("sidebar", "sidebar_width", defaults.sidebar_width),
        color_fresh=_get("sidebar", "color_fresh", defaults.color_fresh),
        color_idle=_get("sidebar", "color_idle", defaults.color_idle),
        external_lookup_url=_get("lookup", "external_lookup_url", defaults.external_lookup_url),
        ocr_engine=_get("ocr", "ocr_engine", defaults.ocr_engine),
        show_pinyin=_get("pinyin", "show_pinyin", defaults.show_pinyin),
        pinyin_max_chars=_get("pinyin", "pinyin_max_chars", defaults.pinyin_max_chars),
        traditional_to_simplified=_get(
            "translation", "traditional_to_simplified", defaults.traditional_to_simplified
        ),
        ms_translator_enabled=_get("cloud", "ms_translator_enabled", defaults.ms_translator_enabled),
        ms_translator_api_key=_get("cloud", "ms_translator_api_key", defaults.ms_translator_api_key),
        ms_translator_region=_get("cloud", "ms_translator_region", defaults.ms_translator_region),
    )


def save_config(cfg: Config, config_path: Path | None = None) -> None:
    """Write the full Config to the TOML file (creating dirs as needed)."""
    if config_path is None:
        config_path = get_config_path()

    config_path.parent.mkdir(parents=True, exist_ok=True)

    toml_content = f"""\
[general]
hotkey = {_toml_str(cfg.hotkey)}
mode = {_toml_str(cfg.mode)}

[display]
font_family = {_toml_str(cfg.font_family)}
font_size = {cfg.font_size}
bg_color = {_toml_str(cfg.bg_color)}
theme = {_toml_str(cfg.theme)}

[sidebar]
side = {_toml_str(cfg.side)}
sidebar_y = {cfg.sidebar_y}
sidebar_width = {cfg.sidebar_width}
color_fresh = {_toml_str(cfg.color_fresh)}
color_idle = {_toml_str(cfg.color_idle)}

[lookup]
external_lookup_url = {_toml_str(cfg.external_lookup_url)}

[ocr]
ocr_engine = {_toml_str(cfg.ocr_engine)}

[pinyin]
show_pinyin = {_toml_bool(cfg.show_pinyin)}
pinyin_max_chars = {cfg.pinyin_max_chars}

[translation]
traditional_to_simplified = {_toml_bool(cfg.traditional_to_simplified)}

[cloud]
ms_translator_enabled = {_toml_bool(cfg.ms_translator_enabled)}
ms_translator_api_key = {_toml_str(cfg.ms_translator_api_key)}
ms_translator_region = {_toml_str(cfg.ms_translator_region)}
"""
    config_path.write_text(toml_content, encoding="utf-8")


def _toml_bool(value: bool) -> str:
    """Format a Python bool as a TOML boolean literal (lowercase true/false)."""
    return "true" if value else "false"


def _toml_str(value: str) -> str:
    """Format a Python string as a TOML string literal (double-quoted, escaped)."""
    escaped = (
        value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n").replace("\r", "\\r")
    )
    return f'"{escaped}"'
