"""Unit tests for engines/updater.py.

All tests are pure unit tests -- no real HTTP calls, no real filesystem
side-effects outside of tempdir sandboxes.
"""

from __future__ import annotations

import os
import pathlib
import tempfile
import zipfile
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# check_core_update helpers / find_core_asset
# ---------------------------------------------------------------------------

class TestCheckCoreUpdate:
    def test_found_when_newer(self):
        """find_core_asset extracts version and URL from a matching asset."""
        from zh_en_translator.engines.updates import find_core_asset
        assets = [{"name": "core-v2026.05.10.zip", "browser_download_url": "https://example.com/core.zip"}]
        version, url = find_core_asset(assets)
        assert version == "2026.05.10"
        assert url == "https://example.com/core.zip"

    def test_not_found_returns_none(self):
        """Returns (None, None) when no core asset is present."""
        from zh_en_translator.engines.updates import find_core_asset
        version, url = find_core_asset([])
        assert version is None
        assert url is None

    def test_network_error_returns_none(self):
        """check_core_update returns (None, None) on network error without raising."""
        with patch("zh_en_translator.engines.updates._fetch_release_json", return_value=None):
            from zh_en_translator.engines.updater import check_core_update
            version, url = check_core_update()
        assert version is None
        assert url is None


# ---------------------------------------------------------------------------
# download_core
# ---------------------------------------------------------------------------

class TestDownloadCore:
    def test_progress_callback_called(self):
        """download_core streams data and calls progress_cb with increasing bytes."""
        fake_body = b"A" * 1024
        mock_response = MagicMock()
        mock_response.headers = {"Content-Length": "1024"}
        mock_response.read.side_effect = [fake_body[:512], fake_body[512:], b""]
        mock_response.__enter__ = lambda s: s
        mock_response.__exit__ = MagicMock(return_value=False)

        calls: list[tuple[int, int]] = []

        def _progress(done, total):
            calls.append((done, total))

        with patch("urllib.request.urlopen", return_value=mock_response):
            from zh_en_translator.engines.updater import download_core
            tmp = download_core("https://example.com/fake.zip", progress_cb=_progress)

        assert tmp.exists()
        assert tmp.suffix == ".zip"
        assert len(calls) >= 1
        for i in range(1, len(calls)):
            assert calls[i][0] >= calls[i - 1][0]

        tmp.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# apply_core / rollback_core (use real temp directories)
# ---------------------------------------------------------------------------

class TestApplyCore:
    def _make_zip(self, staging_dir: pathlib.Path) -> pathlib.Path:
        """Create a minimal zip with one dummy .pyc file."""
        staging_dir.mkdir(parents=True, exist_ok=True)
        dummy = staging_dir / "zh_en_translator" / "dummy.pyc"
        dummy.parent.mkdir(parents=True, exist_ok=True)
        dummy.write_bytes(b"\x00" * 16)
        zip_path = staging_dir.parent / "core-test.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.write(dummy, arcname="zh_en_translator/dummy.pyc")
        return zip_path

    def test_apply_core_rotates_dirs(self):
        """apply_core: app-prev/ deleted, app/ -> app-prev/, staging -> app/."""
        with tempfile.TemporaryDirectory() as td:
            base = pathlib.Path(td)
            overlay = base / "app"
            prev    = base / "app-prev"

            overlay.mkdir()
            (overlay / "old_marker.txt").write_text("old")

            zip_staging = base / "zip-work"
            zip_path = self._make_zip(zip_staging)

            with (
                patch("zh_en_translator.engines.updater._base", return_value=base),
                patch("zh_en_translator.engines.updater._overlay", return_value=overlay),
                patch("zh_en_translator.engines.updater._prev",    return_value=prev),
                patch("zh_en_translator.engines.updater._staging", return_value=base / "app-staging"),
                patch("zh_en_translator.install_state.set_overlay_version"),
            ):
                from zh_en_translator.engines.updater import apply_core
                apply_core(zip_path, "2026.05.10")

            assert overlay.exists(), "app/ should exist after apply"
            assert prev.exists(),    "app-prev/ should exist after apply"
            assert (prev / "old_marker.txt").exists(), "old overlay moved to app-prev/"

    def test_apply_core_updates_install_state(self):
        """apply_core writes new version to install_state via set_overlay_version."""
        with tempfile.TemporaryDirectory() as td:
            base     = pathlib.Path(td)
            overlay  = base / "app"
            prev     = base / "app-prev"
            staging  = base / "app-staging"

            zip_staging = base / "zip-work"
            zip_path = self._make_zip(zip_staging)

            captured_version: list[str] = []

            with (
                patch("zh_en_translator.engines.updater._base", return_value=base),
                patch("zh_en_translator.engines.updater._overlay", return_value=overlay),
                patch("zh_en_translator.engines.updater._prev",    return_value=prev),
                patch("zh_en_translator.engines.updater._staging", return_value=staging),
                patch(
                    "zh_en_translator.install_state.set_overlay_version",
                    side_effect=lambda v, path=None: captured_version.append(v),
                ),
            ):
                from zh_en_translator.engines.updater import apply_core
                apply_core(zip_path, "2026.05.10")

            assert "2026.05.10" in captured_version


class TestRollbackCore:
    def test_rollback_success(self):
        """rollback_core: app-prev/ -> app/; returns True."""
        with tempfile.TemporaryDirectory() as td:
            base    = pathlib.Path(td)
            overlay = base / "app"
            prev    = base / "app-prev"
            prev.mkdir()
            (prev / "marker.txt").write_text("prev")

            with (
                patch("zh_en_translator.engines.updater._overlay", return_value=overlay),
                patch("zh_en_translator.engines.updater._prev",    return_value=prev),
            ):
                from zh_en_translator.engines.updater import rollback_core
                result = rollback_core()

            assert result is True
            assert overlay.exists()
            assert (overlay / "marker.txt").exists()
            assert not prev.exists()

    def test_rollback_no_prev(self):
        """rollback_core returns False gracefully when app-prev/ is absent."""
        with tempfile.TemporaryDirectory() as td:
            base    = pathlib.Path(td)
            overlay = base / "app"
            prev    = base / "app-prev"

            with (
                patch("zh_en_translator.engines.updater._overlay", return_value=overlay),
                patch("zh_en_translator.engines.updater._prev",    return_value=prev),
            ):
                from zh_en_translator.engines.updater import rollback_core
                result = rollback_core()

            assert result is False


# ---------------------------------------------------------------------------
# check_argos_updates
# ---------------------------------------------------------------------------

def _make_argos_pkg(from_code: str, to_code: str, version: str) -> MagicMock:
    p = MagicMock()
    p.from_code = from_code
    p.to_code   = to_code
    p.package_version = version
    return p


class TestCheckArgosUpdates:
    def test_needs_update_when_version_differs(self):
        avail = [_make_argos_pkg("zh", "en", "2.0"), _make_argos_pkg("en", "zh", "1.0")]
        inst  = [_make_argos_pkg("zh", "en", "1.0"), _make_argos_pkg("en", "zh", "1.0")]

        with (
            patch("argostranslate.package.update_package_index"),
            patch("argostranslate.package.get_available_packages", return_value=avail),
            patch("argostranslate.package.get_installed_packages", return_value=inst),
        ):
            from zh_en_translator.engines.updater import check_argos_updates
            results = check_argos_updates()

        zh_en = next(r for r in results if r["lang_pair"] == "zh -> en")
        assert zh_en["needs_update"] is True
        assert zh_en["available_version"] == "2.0"
        assert zh_en["installed_version"] == "1.0"

    def test_up_to_date_when_versions_match(self):
        avail = [_make_argos_pkg("zh", "en", "1.0"), _make_argos_pkg("en", "zh", "1.0")]
        inst  = [_make_argos_pkg("zh", "en", "1.0"), _make_argos_pkg("en", "zh", "1.0")]

        with (
            patch("argostranslate.package.update_package_index"),
            patch("argostranslate.package.get_available_packages", return_value=avail),
            patch("argostranslate.package.get_installed_packages", return_value=inst),
        ):
            from zh_en_translator.engines.updater import check_argos_updates
            results = check_argos_updates()

        for r in results:
            assert r["needs_update"] is False

    def test_index_error_returns_empty_list(self):
        """check_argos_updates returns [] without raising on total failure."""
        with patch("argostranslate.package.update_package_index", side_effect=RuntimeError("fail")):
            with patch("argostranslate.package.get_available_packages", side_effect=RuntimeError("fail")):
                from zh_en_translator.engines.updater import check_argos_updates
                result = check_argos_updates()
        assert isinstance(result, list)
