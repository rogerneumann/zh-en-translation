"""Integration smoke test for the core update apply -> rollback cycle.

Uses a real temporary directory tree; no HTTP calls.
"""

from __future__ import annotations

import pathlib
import tempfile
import zipfile
from unittest.mock import patch

import pytest


def _make_core_zip(base: pathlib.Path, version: str = "2026.05.10") -> pathlib.Path:
    """Create a minimal core-v*.zip in *base* with some dummy .pyc content."""
    content_dir = base / "zip-content"
    content_dir.mkdir(parents=True, exist_ok=True)
    pkg_dir = content_dir / "zh_en_translator"
    pkg_dir.mkdir()
    (pkg_dir / "dummy.pyc").write_bytes(b"\x00" * 32)
    (pkg_dir / "engines").mkdir()
    (pkg_dir / "engines" / "updater.pyc").write_bytes(b"\x00" * 32)

    zip_path = base / f"core-v{version}.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        for f in content_dir.rglob("*"):
            if f.is_file():
                zf.write(f, arcname=str(f.relative_to(content_dir)))

    return zip_path


class TestApplyRollbackIntegration:
    """Full apply -> verify -> rollback cycle in a temp directory sandbox."""

    def test_apply_then_rollback(self):
        from zh_en_translator.engines.updater import apply_core, rollback_core

        with tempfile.TemporaryDirectory() as td:
            base    = pathlib.Path(td)
            overlay = base / "app"
            prev    = base / "app-prev"
            staging = base / "app-staging"

            # Create a pre-existing "old" overlay
            overlay.mkdir()
            (overlay / "old_file.pyc").write_bytes(b"\xde\xad")

            zip_path = _make_core_zip(base)

            with (
                patch("zh_en_translator.engines.updater._base",    return_value=base),
                patch("zh_en_translator.engines.updater._overlay", return_value=overlay),
                patch("zh_en_translator.engines.updater._prev",    return_value=prev),
                patch("zh_en_translator.engines.updater._staging", return_value=staging),
                patch("zh_en_translator.install_state.set_overlay_version"),
            ):
                # -- APPLY --
                apply_core(zip_path, "2026.05.10")

                assert overlay.exists(), "overlay (app/) must exist after apply"
                assert prev.exists(),    "app-prev/ must exist after apply"

                assert (overlay / "zh_en_translator" / "dummy.pyc").exists(), \
                    "new .pyc must be present in overlay"
                assert (prev / "old_file.pyc").exists(), \
                    "old file must have moved to app-prev/"

                # -- ROLLBACK --
                result = rollback_core()

                assert result is True,     "rollback_core() must return True"
                assert overlay.exists(),   "overlay must still exist after rollback"
                assert not prev.exists(),  "app-prev/ should be gone after rollback"
                assert (overlay / "old_file.pyc").exists(), \
                    "old file must be restored to overlay after rollback"

    def test_apply_twice_removes_old_prev(self):
        """Second apply deletes the old app-prev/ before creating a new one."""
        from zh_en_translator.engines.updater import apply_core

        with tempfile.TemporaryDirectory() as td:
            base    = pathlib.Path(td)
            overlay = base / "app"
            prev    = base / "app-prev"
            staging = base / "app-staging"

            # Stale prev from a previous update cycle
            prev.mkdir()
            (prev / "stale_marker.txt").write_text("stale")

            overlay.mkdir()
            (overlay / "current_marker.txt").write_text("current v1")

            zip_path = _make_core_zip(base, version="2026.05.10")

            with (
                patch("zh_en_translator.engines.updater._base",    return_value=base),
                patch("zh_en_translator.engines.updater._overlay", return_value=overlay),
                patch("zh_en_translator.engines.updater._prev",    return_value=prev),
                patch("zh_en_translator.engines.updater._staging", return_value=staging),
                patch("zh_en_translator.install_state.set_overlay_version"),
            ):
                apply_core(zip_path, "2026.05.10")

            assert not (prev / "stale_marker.txt").exists(), \
                "stale app-prev/ marker must be deleted"
            assert (prev / "current_marker.txt").exists(), \
                "v1 overlay must have moved to app-prev/"
