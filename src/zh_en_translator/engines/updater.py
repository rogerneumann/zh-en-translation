"""Core update and Argos model update utilities.

Provides:
  - check_core_update()       check GitHub for a new core-v*.zip asset
  - download_core()           stream the zip to a temp file
  - apply_core()              stage -> rotate app-prev -> apply
  - rollback_core()           restore app-prev

  - check_argos_updates()     compare installed vs available Argos packages
  - download_argos_model()    install an updated Argos model package

AppData directory layout managed here:
    %APPDATA%/zh-en-translator/
        app/            <- active overlay (may not exist on fresh install)
        app-prev/       <- previous overlay kept for one rollback
        app-staging/    <- temporary unzip target (cleaned on apply)
"""

from __future__ import annotations

import logging
import os
import pathlib
import shutil
import sys
import tempfile
import urllib.request
import zipfile
from typing import Callable

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# AppData paths
# ---------------------------------------------------------------------------

def _base() -> pathlib.Path:
    if sys.platform == "win32":
        return pathlib.Path(os.environ.get("APPDATA", pathlib.Path.home())) / "zh-en-translator"
    try:
        from platformdirs import user_data_dir
        return pathlib.Path(user_data_dir("zh-en-translator"))
    except ImportError:
        return pathlib.Path.home() / ".local" / "share" / "zh-en-translator"


def _overlay()   -> pathlib.Path: return _base() / "app"
def _prev()      -> pathlib.Path: return _base() / "app-prev"
def _staging()   -> pathlib.Path: return _base() / "app-staging"


# ---------------------------------------------------------------------------
# Core update
# ---------------------------------------------------------------------------

def check_core_update(config=None) -> tuple[str | None, str | None]:
    """Return ``(latest_version, download_url)`` or ``(None, None)``.

    Queries the GitHub release for a ``core-v*.zip`` asset and compares its
    version against the currently active overlay version from install_state.
    Returns ``(None, None)`` if no update is available or on network error.
    """
    try:
        from zh_en_translator.engines.updates import get_latest_release_assets, find_core_asset, is_newer
        from zh_en_translator.install_state import get_overlay_version

        assets = get_latest_release_assets()
        version, url = find_core_asset(assets)
        if not version or not url:
            return None, None

        current = get_overlay_version()
        # If overlay_version is empty the bundle is active; compare against app version
        if not current:
            try:
                from zh_en_translator import __version__
                current = __version__
            except Exception:
                current = ""

        if current and not is_newer(version, current):
            return None, None

        return version, url
    except Exception as exc:
        logger.debug("check_core_update failed: %s", exc)
        return None, None


def download_core(
    url: str,
    progress_cb: Callable[[int, int], None] | None = None,
) -> pathlib.Path:
    """Stream *url* to a temp file; call *progress_cb(bytes_done, total)* during download.

    Returns the path to the downloaded zip file.
    Raises on network error.
    """
    tmp_fd, tmp_path = tempfile.mkstemp(prefix="zh-en-translator-core-", suffix=".zip")
    os.close(tmp_fd)
    tmp = pathlib.Path(tmp_path)

    req = urllib.request.Request(url)
    req.add_header("User-Agent", "zh-en-translator-updater")
    with urllib.request.urlopen(req, timeout=30) as response:
        total = int(response.headers.get("Content-Length", 0))
        done = 0
        chunk_size = 65536
        with open(tmp, "wb") as f:
            while True:
                chunk = response.read(chunk_size)
                if not chunk:
                    break
                f.write(chunk)
                done += len(chunk)
                if progress_cb:
                    progress_cb(done, total)

    return tmp


def apply_core(zip_path: pathlib.Path, version: str) -> None:
    """Unpack *zip_path* and rotate directories to activate the new overlay.

    Directory rotation:
        1. Delete old app-prev/ if it exists
        2. Rename app/ -> app-prev/ (if app/ exists)
        3. Unzip zip_path into app-staging/
        4. Rename app-staging/ -> app/
        5. Update install_state [app].overlay_version
    """
    base = _base()
    base.mkdir(parents=True, exist_ok=True)

    prev    = _prev()
    overlay = _overlay()
    staging = _staging()

    # 1. Remove stale prev
    if prev.exists():
        shutil.rmtree(prev, ignore_errors=True)

    # 2. Rotate current overlay to prev
    if overlay.exists():
        overlay.rename(prev)

    # 3. Unzip to staging
    if staging.exists():
        shutil.rmtree(staging, ignore_errors=True)
    staging.mkdir(parents=True)
    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(staging)

    # 4. Activate staging as overlay
    staging.rename(overlay)

    # 5. Record new version
    try:
        from zh_en_translator.install_state import set_overlay_version
        set_overlay_version(version)
    except Exception as exc:
        logger.warning("Could not record overlay_version: %s", exc)


def rollback_core() -> bool:
    """Restore the previous overlay (app-prev/ -> app/).

    Returns True if rollback succeeded, False if app-prev/ was not found.
    """
    prev    = _prev()
    overlay = _overlay()

    if not prev.exists():
        logger.warning("rollback_core: no app-prev/ directory found")
        return False

    try:
        if overlay.exists():
            shutil.rmtree(overlay, ignore_errors=True)
        prev.rename(overlay)
        logger.info("Core rollback succeeded")
        return True
    except Exception as exc:
        logger.error("rollback_core failed: %s", exc)
        return False


# ---------------------------------------------------------------------------
# Argos model updates
# ---------------------------------------------------------------------------

def check_argos_updates() -> list[dict]:
    """Compare installed Argos packages against the online package index.

    Returns a list of dicts, one per tracked lang pair::

        {
            "lang_pair":         "zh -> en",
            "installed_version": "1.0",   # "" if not installed
            "available_version": "1.1",   # "" if index unavailable
            "needs_update":      True,
        }

    Never raises — returns an empty list on error.
    """
    pairs = [("zh", "en"), ("en", "zh")]
    results: list[dict] = []

    try:
        import argostranslate.package as _pkg  # type: ignore

        # Fetch available packages from the online index
        try:
            _pkg.update_package_index()
        except Exception as exc:
            logger.debug("Argos package index update failed: %s", exc)

        available_pkgs = {
            (p.from_code, p.to_code): p
            for p in _pkg.get_available_packages()
        }
        installed_pkgs = {
            (p.from_code, p.to_code): p
            for p in _pkg.get_installed_packages()
        }

        for from_code, to_code in pairs:
            key = (from_code, to_code)
            avail   = available_pkgs.get(key)
            inst    = installed_pkgs.get(key)

            avail_ver = str(avail.package_version) if avail else ""
            inst_ver  = str(inst.package_version)  if inst  else ""

            needs = bool(avail_ver and inst_ver and avail_ver != inst_ver)

            results.append({
                "lang_pair":         f"{from_code} -> {to_code}",
                "installed_version": inst_ver,
                "available_version": avail_ver,
                "needs_update":      needs,
            })
    except Exception as exc:
        logger.debug("check_argos_updates failed: %s", exc)

    return results


def download_argos_model(
    package_info: dict,
    progress_cb: Callable[[int, int], None] | None = None,
) -> None:
    """Download and install an Argos model package.

    *package_info* is a dict from ``check_argos_updates()`` with at minimum
    ``lang_pair``.  The actual package object is re-resolved from the index.

    Raises on failure.
    """
    import argostranslate.package as _pkg  # type: ignore

    lang_pair = package_info.get("lang_pair", "")
    parts = [p.strip() for p in lang_pair.split("->")]
    if len(parts) != 2:
        raise ValueError(f"Invalid lang_pair: {lang_pair!r}")
    from_code, to_code = parts

    available = {
        (p.from_code, p.to_code): p
        for p in _pkg.get_available_packages()
    }
    pkg = available.get((from_code, to_code))
    if pkg is None:
        raise ValueError(f"Package {lang_pair!r} not found in index")

    # argostranslate handles the download; wrap in a simple progress shim
    logger.info("Downloading Argos model: %s", lang_pair)
    _pkg.install_from_path(pkg.download())
    logger.info("Argos model installed: %s", lang_pair)
