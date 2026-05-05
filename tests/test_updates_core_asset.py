"""Tests for the core asset detection additions to engines/updates.py.

Tests find_core_asset() and get_latest_release_assets().
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from zh_en_translator.engines.updates import find_core_asset, get_latest_release_assets


# ---------------------------------------------------------------------------
# find_core_asset
# ---------------------------------------------------------------------------

class TestFindCoreAsset:
    def _asset(self, name: str, url: str = "") -> dict:
        return {
            "name": name,
            "browser_download_url": url or f"https://example.com/{name}",
            "size": 1024,
        }

    def test_present(self):
        """find_core_asset extracts version and URL from a matching asset."""
        assets = [
            self._asset("zh-en-translator-v2026.05.04-setup.exe"),
            self._asset("core-v2026.05.04.zip", "https://example.com/core-v2026.05.04.zip"),
        ]
        version, url = find_core_asset(assets)
        assert version == "2026.05.04"
        assert url == "https://example.com/core-v2026.05.04.zip"

    def test_absent(self):
        """find_core_asset returns (None, None) when no matching asset."""
        assets = [
            self._asset("zh-en-translator-v2026.05.04-setup.exe"),
        ]
        version, url = find_core_asset(assets)
        assert version is None
        assert url is None

    def test_empty_list(self):
        """find_core_asset handles an empty assets list."""
        version, url = find_core_asset([])
        assert version is None
        assert url is None

    def test_multiple_matches_picks_first(self):
        """find_core_asset returns the first matching asset when multiple match."""
        assets = [
            self._asset("core-v2026.05.04.zip", "https://example.com/first.zip"),
            self._asset("core-v2026.05.10.zip", "https://example.com/second.zip"),
        ]
        version, url = find_core_asset(assets)
        assert version == "2026.05.04"
        assert url == "https://example.com/first.zip"

    def test_version_with_counter(self):
        """Handles a version with a day-counter suffix like 2026.05.04.1."""
        assets = [
            self._asset("core-v2026.05.04.1.zip", "https://example.com/core-v2026.05.04.1.zip"),
        ]
        version, url = find_core_asset(assets)
        assert version == "2026.05.04.1"

    def test_non_core_zip_not_matched(self):
        """Zips that don't start with 'core-v' are not matched."""
        assets = [
            self._asset("portable-v2026.05.04.zip"),
            self._asset("zh-en-translator-v2026.05.04-lite-portable.zip"),
        ]
        version, url = find_core_asset(assets)
        assert version is None


# ---------------------------------------------------------------------------
# get_latest_release_assets
# ---------------------------------------------------------------------------

class TestGetLatestReleaseAssets:
    def test_returns_assets_from_release(self):
        """get_latest_release_assets parses the assets list from JSON."""
        fake_json = {
            "tag_name": "v2026.05.04",
            "assets": [
                {"name": "core-v2026.05.04.zip", "browser_download_url": "https://example.com/core.zip", "size": 5000},
            ],
        }
        with patch("zh_en_translator.engines.updates._fetch_release_json", return_value=fake_json):
            assets = get_latest_release_assets()

        assert len(assets) == 1
        assert assets[0]["name"] == "core-v2026.05.04.zip"

    def test_returns_empty_list_on_failure(self):
        """get_latest_release_assets returns [] when fetch fails."""
        with patch("zh_en_translator.engines.updates._fetch_release_json", return_value=None):
            assets = get_latest_release_assets()
        assert assets == []

    def test_returns_empty_list_when_no_assets_key(self):
        """Returns [] when release JSON has no 'assets' key."""
        with patch("zh_en_translator.engines.updates._fetch_release_json", return_value={"tag_name": "v1.0"}):
            assets = get_latest_release_assets()
        assert assets == []
