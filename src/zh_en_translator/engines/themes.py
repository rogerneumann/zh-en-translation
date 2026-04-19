"""Theme palettes for zh-en-translator popup and sidebar."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ThemePalette:
    bg: str          # background hex
    text: str        # primary text hex
    muted: str       # secondary/muted text hex
    border: str      # border rgba string
    btn_hover: str   # button hover rgba string
    btn_pressed: str # button pressed rgba string


THEMES: dict[str, ThemePalette] = {
    "light": ThemePalette(
        bg="#F8F8F8",
        text="#111111",
        muted="#666666",
        border="rgba(0,0,0,0.15)",
        btn_hover="rgba(0,0,0,0.06)",
        btn_pressed="rgba(0,0,0,0.12)",
    ),
    "dark": ThemePalette(
        bg="#1E1E1E",
        text="#E8E8E8",
        muted="#AAAAAA",
        border="rgba(255,255,255,0.15)",
        btn_hover="rgba(255,255,255,0.08)",
        btn_pressed="rgba(255,255,255,0.14)",
    ),
    "sepia": ThemePalette(
        bg="#F4ECD8",
        text="#3B2A1A",
        muted="#7A6347",
        border="rgba(80,50,20,0.20)",
        btn_hover="rgba(80,50,20,0.08)",
        btn_pressed="rgba(80,50,20,0.14)",
    ),
    "high_contrast": ThemePalette(
        bg="#000000",
        text="#FFFF00",  # Yellow
        muted="#00FFFF", # Cyan
        border="rgba(255,255,255,0.8)",
        btn_hover="rgba(255,255,255,0.2)",
        btn_pressed="rgba(255,255,255,0.4)",
    ),
}


def resolve_palette(theme: str, system_is_dark: bool) -> ThemePalette:
    """Return the ThemePalette for the given theme string.

    'system' picks 'dark' or 'light' based on system_is_dark.
    Falls back to 'light' for unknown theme names.
    """
    if theme == "system":
        return THEMES["dark" if system_is_dark else "light"]
    return THEMES.get(theme, THEMES["light"])
