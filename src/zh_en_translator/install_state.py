"""Read and update the installer state file written by the Inno Setup installer.

File location: %APPDATA%\\zh-en-translator\\install_state.toml  (Windows)
               ~/.local/share/zh-en-translator/install_state.toml  (Linux/Mac)

The installer creates this file after the install/upgrade completes.
The app updates [components] keys at runtime as components become available
(e.g. marking argos=true after a successful post-install download).

Never raises -- all errors are logged and a safe default is returned.
"""

from __future__ import annotations

import logging
import sys
import tomllib
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


def get_state_path() -> Path:
    """Return the path to install_state.toml (file may not exist yet)."""
    if sys.platform == "win32":
        import os
        base = Path(os.environ.get("APPDATA", Path.home())) / "zh-en-translator"
    else:
        try:
            from platformdirs import user_data_dir
            base = Path(user_data_dir("zh-en-translator"))
        except ImportError:
            base = Path.home() / ".local" / "share" / "zh-en-translator"
    return base / "install_state.toml"


@dataclass
class InstallState:
    # [install]
    version: str = ""
    install_type: str = ""   # "full" | "lite" | ""
    date: str = ""
    install_dir: str = ""

    # [components]
    argos: bool = False
    windows_ocr: bool = False
    tesseract: bool = False

    @property
    def is_full(self) -> bool:
        return self.install_type == "full"

    @property
    def is_lite(self) -> bool:
        return self.install_type == "lite"

    @property
    def installed(self) -> bool:
        """True if any install record exists (version is non-empty)."""
        return bool(self.version)


def load_state(path: Path | None = None) -> InstallState:
    """Read install_state.toml and return an InstallState.

    Returns an empty (all-defaults) InstallState if the file does not exist
    or cannot be parsed -- never raises.
    """
    if path is None:
        path = get_state_path()

    if not path.exists():
        return InstallState()

    try:
        with open(path, "rb") as f:
            data = tomllib.load(f)
    except Exception as exc:
        logger.warning("Could not read install_state.toml (%s): %s", path, exc)
        return InstallState()

    inst = data.get("install", {})
    comp = data.get("components", {})

    return InstallState(
        version     = inst.get("version", ""),
        install_type= inst.get("type", ""),
        date        = inst.get("date", ""),
        install_dir = inst.get("dir", ""),
        argos       = bool(comp.get("argos", False)),
        windows_ocr = bool(comp.get("windows_ocr", False)),
        tesseract   = bool(comp.get("tesseract", False)),
    )


# ---------------------------------------------------------------------------
# [app] section helpers — overlay architecture
# ---------------------------------------------------------------------------

def get_architecture(path: Path | None = None) -> str | None:
    """Return [app].architecture from install_state.toml, or None if absent.

    None means a legacy install that predates the overlay architecture.
    """
    if path is None:
        path = get_state_path()
    if not path.exists():
        return None
    try:
        with open(path, "rb") as f:
            data = tomllib.load(f)
        return data.get("app", {}).get("architecture") or None
    except Exception as exc:
        logger.warning("Could not read [app].architecture: %s", exc)
        return None


def set_architecture(value: str, path: Path | None = None) -> None:
    """Write [app].architecture to install_state.toml. Never raises."""
    _update_app_section(architecture=value, path=path)


def get_overlay_version(path: Path | None = None) -> str:
    """Return [app].overlay_version from install_state.toml, or '' if absent."""
    if path is None:
        path = get_state_path()
    if not path.exists():
        return ""
    try:
        with open(path, "rb") as f:
            data = tomllib.load(f)
        return data.get("app", {}).get("overlay_version", "")
    except Exception as exc:
        logger.warning("Could not read [app].overlay_version: %s", exc)
        return ""


def set_overlay_version(version: str, path: Path | None = None) -> None:
    """Write [app].overlay_version to install_state.toml. Never raises."""
    _update_app_section(overlay_version=version, path=path)


def _update_app_section(
    architecture: str | None = None,
    overlay_version: str | None = None,
    path: Path | None = None,
) -> None:
    """Patch [app] keys in install_state.toml without disturbing other sections."""
    if path is None:
        path = get_state_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)

        # Read existing raw text so we can do a surgical patch
        existing = path.read_text(encoding="utf-8") if path.exists() else ""

        # Parse current values
        try:
            with open(path, "rb") as f:
                data = tomllib.load(f) if path.exists() else {}
        except Exception:
            data = {}

        app_section = dict(data.get("app", {}))
        if architecture is not None:
            app_section["architecture"] = architecture
        if overlay_version is not None:
            app_section["overlay_version"] = overlay_version

        # Re-serialise the entire file preserving other sections
        state = load_state(path)
        date_str = state.date or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        dir_str  = state.install_dir or ""

        arch_val = app_section.get("architecture", "overlay")
        ov_val   = app_section.get("overlay_version", "")

        content = (
            "# zh-en-translator installation state\n"
            "# Written by installer and updated at runtime -- do not edit manually.\n"
            "\n"
            "[install]\n"
            f'version = "{state.version}"\n'
            f'type    = "{state.install_type}"\n'
            f'date    = "{date_str}"\n'
            f'dir     = "{dir_str}"\n'
            "\n"
            "[components]\n"
            f"argos        = {'true' if state.argos else 'false'}\n"
            f"windows_ocr  = {'true' if state.windows_ocr else 'false'}\n"
            f"tesseract    = {'true' if state.tesseract else 'false'}\n"
            "\n"
            "[app]\n"
            f'architecture    = "{arch_val}"\n'
            f'overlay_version = "{ov_val}"\n'
        )

        tmp = path.with_suffix(".toml.tmp")
        tmp.write_text(content, encoding="utf-8")
        tmp.replace(path)
    except Exception as exc:
        logger.warning("Could not update [app] section in install_state.toml: %s", exc)


# ---------------------------------------------------------------------------
# [components] helpers
# ---------------------------------------------------------------------------

def update_components(
    argos: bool | None = None,
    windows_ocr: bool | None = None,
    tesseract: bool | None = None,
    path: Path | None = None,
) -> None:
    """Update one or more [components] keys in install_state.toml.

    Only the supplied (non-None) keys are changed; everything else is preserved.
    Creates the file with minimal content if it does not exist yet.
    Never raises.
    """
    if path is None:
        path = get_state_path()

    state = load_state(path)

    if argos is not None:
        state.argos = argos
    if windows_ocr is not None:
        state.windows_ocr = windows_ocr
    if tesseract is not None:
        state.tesseract = tesseract

    _write_state(state, path)


def _write_state(state: InstallState, path: Path) -> None:
    """Serialise InstallState back to TOML and write atomically. Never raises."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)

        # Preserve existing date/dir if present; set defaults for new files
        date_str = state.date or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        dir_str  = state.install_dir or ""

        # Preserve existing [app] section if present
        existing_app: dict = {}
        if path.exists():
            try:
                with open(path, "rb") as f:
                    existing_app = tomllib.load(f).get("app", {})
            except Exception:
                pass

        arch_val = existing_app.get("architecture", "overlay")
        ov_val   = existing_app.get("overlay_version", "")

        content = (
            "# zh-en-translator installation state\n"
            "# Written by installer and updated at runtime -- do not edit manually.\n"
            "\n"
            "[install]\n"
            f'version = "{state.version}"\n'
            f'type    = "{state.install_type}"\n'
            f'date    = "{date_str}"\n'
            f'dir     = "{dir_str}"\n'
            "\n"
            "[components]\n"
            f"argos        = {'true' if state.argos else 'false'}\n"
            f"windows_ocr  = {'true' if state.windows_ocr else 'false'}\n"
            f"tesseract    = {'true' if state.tesseract else 'false'}\n"
            "\n"
            "[app]\n"
            f'architecture    = "{arch_val}"\n'
            f'overlay_version = "{ov_val}"\n'
        )

        # Write to a temp file then rename for atomic replacement
        tmp = path.with_suffix(".toml.tmp")
        tmp.write_text(content, encoding="utf-8")
        tmp.replace(path)
    except Exception as exc:
        logger.warning("Could not write install_state.toml (%s): %s", path, exc)
