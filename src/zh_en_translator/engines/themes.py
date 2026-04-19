"""Theme palettes for zh-en-translator popup and sidebar."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ThemePalette:
    bg: str          # background hex
    text: str        # primary text hex
    muted: str       # secondary/muted text hex
    border: str      # border rgba string
    btn_bg: str      # button background rgba
    btn_hover: str   # button hover rgba
    btn_pressed: str # button pressed rgba


THEMES: dict[str, ThemePalette] = {
    "light": ThemePalette(
        bg="#FFFFFF",
        text="#1A1A1A",
        muted="#5F5F5F",
        border="rgba(0,0,0,0.08)",
        btn_bg="rgba(0,0,0,0.04)",
        btn_hover="rgba(0,0,0,0.08)",
        btn_pressed="rgba(0,0,0,0.12)",
    ),
    "dark": ThemePalette(
        bg="#202020",
        text="#EEEEEE",
        muted="#A0A0A0",
        border="rgba(255,255,255,0.08)",
        btn_bg="rgba(255,255,255,0.06)",
        btn_hover="rgba(255,255,255,0.10)",
        btn_pressed="rgba(255,255,255,0.15)",
    ),
    "sepia": ThemePalette(
        bg="#F4ECD8",
        text="#3B2A1A",
        muted="#7A6347",
        border="rgba(80,50,20,0.12)",
        btn_bg="rgba(80,50,20,0.05)",
        btn_hover="rgba(80,50,20,0.10)",
        btn_pressed="rgba(80,50,20,0.15)",
    ),
    "high_contrast": ThemePalette(
        bg="#000000",
        text="#FFFF00",  # Yellow
        muted="#00FFFF", # Cyan
        border="rgba(255,255,255,0.8)",
        btn_bg="rgba(255,255,255,0.1)",
        btn_hover="rgba(255,255,255,0.3)",
        btn_pressed="rgba(255,255,255,0.5)",
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
