"""Update checker for zh-en-translator."""

from __future__ import annotations

import fnmatch
import json
import logging
import re
import urllib.request
from typing import TypedDict

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Public releases repository
# ---------------------------------------------------------------------------
REPO_OWNER = "rogerneumann"
REPO_NAME = "zh-en-translation"


class ReleaseInfo(TypedDict):
    tag_name: str
    html_url: str
    body: str


def _fetch_release_json() -> dict | None:
    """Return the raw GitHub API release JSON dict, or None on error."""
    url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/releases/latest"
    try:
        req = urllib.request.Request(url)
        req.add_header("User-Agent", "zh-en-translator-update-checker")
        with urllib.request.urlopen(req, timeout=5) as response:
            return json.loads(response.read().decode("utf-8"))
    except Exception as e:
        logger.debug("Failed to fetch release JSON: %s", e)
        return None


def get_latest_release() -> ReleaseInfo | None:
    """Fetch latest release info from the public releases GitHub repo."""
    data = _fetch_release_json()
    if data is None:
        return None
    return {
        "tag_name": data.get("tag_name", ""),
        "html_url": data.get("html_url", ""),
        "body": data.get("body", ""),
    }


def get_latest_release_assets() -> list[dict]:
    """Return the assets list from the latest GitHub release JSON.

    Each asset dict contains at minimum: name, browser_download_url, size.
    Returns an empty list if the release cannot be fetched.
    """
    data = _fetch_release_json()
    if data is None:
        return []
    return data.get("assets", [])


def find_core_asset(assets: list[dict]) -> tuple[str | None, str | None]:
    """Search *assets* for a core update package matching ``core-v*.zip``.

    Returns ``(version_string, download_url)`` for the first matching asset,
    or ``(None, None)`` when no match is found.

    Version string is extracted from the filename, e.g.
    ``core-v2026.05.04.zip`` -> ``"2026.05.04"``.
    """
    for asset in assets:
        name: str = asset.get("name", "")
        if fnmatch.fnmatch(name, "core-v*.zip"):
            url = asset.get("browser_download_url", "")
            # Extract version: strip leading "core-v" and trailing ".zip"
            m = re.match(r"core-v(.+)\.zip$", name)
            version = m.group(1) if m else ""
            return version, url
    return None, None


def is_newer(latest_tag: str, current_version: str) -> bool:
    """Compare CalVer strings of the form YYYY.MM.DD[.N].

    Both SemVer (0.1.0) and CalVer (2026.05.01, 2026.05.01.1) are handled
    by splitting on '.' and comparing integer tuples.  A tag prefix of 'v'
    is stripped before comparison.
    """
    latest = latest_tag.lstrip("v")
    current = current_version.lstrip("v")

    try:
        latest_parts = [int(p) for p in latest.split(".")]
        current_parts = [int(p) for p in current.split(".")]
        return latest_parts > current_parts
    except ValueError:
        return latest != current
