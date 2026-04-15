"""Sentence-level translation via Argos Translate (offline neural MT)."""

from __future__ import annotations


def is_available() -> bool:
    """Return True if the zh→en Argos language pack is installed and ready."""
    try:
        import argostranslate.translate

        langs = argostranslate.translate.get_installed_languages()
        zh = next((l for l in langs if l.code == "zh"), None)
        en = next((l for l in langs if l.code == "en"), None)
        if not zh or not en:
            return False
        return zh.get_translation(en) is not None
    except Exception:
        return False


def ensure_pack() -> bool:
    """
    Ensure the zh→en language pack is downloaded and installed.

    Safe to call repeatedly — returns immediately if already installed.
    Requires internet access for the one-time ~100 MB download.
    Returns True if the pack is ready to use.
    """
    if is_available():
        return True
    try:
        import argostranslate.package

        argostranslate.package.update_package_index()
        available = argostranslate.package.get_available_packages()
        pkg = next(
            (p for p in available if p.from_code == "zh" and p.to_code == "en"),
            None,
        )
        if not pkg:
            return False
        path = pkg.download()
        argostranslate.package.install_from_path(path)
        return is_available()
    except Exception:
        return False


def translate_sentence(text: str) -> str | None:
    """
    Translate Chinese text to English.

    Returns the translated string, or None if the pack is not installed
    or translation fails for any reason.
    """
    if not text.strip():
        return None
    try:
        import argostranslate.translate

        langs = argostranslate.translate.get_installed_languages()
        zh = next((l for l in langs if l.code == "zh"), None)
        en = next((l for l in langs if l.code == "en"), None)
        if not zh or not en:
            return None
        translation = zh.get_translation(en)
        if not translation:
            return None
        result = translation.translate(text)
        return result if result and result.strip() else None
    except Exception:
        return None
