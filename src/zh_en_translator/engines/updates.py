"""Update checker for zh-en-translator."""

from __future__ import annotations

import json
import logging
import urllib.request
from typing import TypedDict

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Public releases repository
# ---------------------------------------------------------------------------
# TODO: Create a public GitHub repo at github.com/OWNER/zh-en-translator-releases
# and set REPO_OWNER / REPO_NAME below.  Tag each release vYYYY.MM.DD (or
# vYYYY.MM.DD.N for multiple releases on the same day) and upload the
# installer .exe as a release asset.  The private source repo stays private.
REPO_OWNER = "rogerneumann"
REPO_NAME = "zh-en-translator-releases"


class ReleaseInfo(TypedDict):
    tag_name: str
    html_url: str
    body: str


def get_latest_release() -> ReleaseInfo | None:
    """Fetch latest release info from the public releases GitHub repo."""
    url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/releases/latest"
    try:
        req = urllib.request.Request(url)
        req.add_header("User-Agent", "zh-en-translator-update-checker")
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode("utf-8"))
            return {
                "tag_name": data.get("tag_name", ""),
                "html_url": data.get("html_url", ""),
                "body": data.get("body", ""),
            }
    except Exception as e:
        logger.debug("Failed to check for updates: %s", e)
        return None


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
