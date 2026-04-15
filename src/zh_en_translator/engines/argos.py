"""Offline Chinese→English translation via ctranslate2 + sentencepiece.

Calls ctranslate2 and sentencepiece directly from the installed argostranslate
pack, bypassing argostranslate.translate which hard-imports stanza (and stanza
requires downloading Chinese NLP models that are unavailable on restricted networks).
"""

from __future__ import annotations
from pathlib import Path


def _find_pack_dir() -> Path | None:
    """
    Locate the installed zh→en ctranslate2 pack directory.

    Uses argostranslate.settings (which does NOT import stanza) to find the
    correct platform-specific packages directory.
    """
    try:
        import argostranslate.settings
        package_dirs = argostranslate.settings.package_dirs
    except Exception:
        return None

    for pkg_dir in package_dirs:
        pkg_path = Path(pkg_dir)
        if not pkg_path.exists():
            continue
        for d in pkg_path.iterdir():
            if d.is_dir() and "zh_en" in d.name:
                model_dir = d / "model"
                spm_file = d / "sentencepiece.model"
                if (model_dir / "model.bin").exists() and spm_file.exists():
                    return d
    return None


def is_available() -> bool:
    """Return True if the zh→en pack and required libraries are present."""
    if _find_pack_dir() is None:
        return False
    try:
        import ctranslate2  # noqa: F401
        import sentencepiece  # noqa: F401
        return True
    except ImportError:
        return False


def ensure_pack() -> bool:
    """
    Ensure the zh→en pack is ready to use.

    Returns True immediately if already installed. Falls back to downloading
    via argostranslate.package (requires internet for one-time ~100 MB download).
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

    Uses ctranslate2 + sentencepiece directly — no stanza, no network calls.
    Returns the translated string, or None on failure.
    """
    if not text.strip():
        return None

    pack_dir = _find_pack_dir()
    if not pack_dir:
        print("[argos] pack directory not found")
        return None

    try:
        import ctranslate2
        import sentencepiece as spm

        model_dir = str(pack_dir / "model")
        spm_path = str(pack_dir / "sentencepiece.model")

        print(f"[argos] model: {pack_dir.name}")

        translator = ctranslate2.Translator(model_dir, device="cpu")
        sp_model = spm.SentencePieceProcessor()
        sp_model.Load(spm_path)

        tokens = sp_model.encode(text, out_type=str)
        print(f"[argos] encoded {len(tokens)} tokens")

        results = translator.translate_batch([tokens])
        target_tokens = results[0].hypotheses[0]

        translation = sp_model.decode(target_tokens)
        # Sentencepiece ▁ (U+2581) marks word boundaries; strip from decoded output
        translation = translation.replace("\u2581", " ").strip()
        # Collapse any double-spaces left by the substitution
        while "  " in translation:
            translation = translation.replace("  ", " ")
        print(f"[argos] translation: {translation!r}")

        return translation if translation else None

    except Exception as e:
        print(f"[argos] exception: {e}")
        import traceback
        traceback.print_exc()
        return None
