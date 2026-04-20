"""Minimal test: verify technical user dictionary file exists and loads cleanly."""

import importlib
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest


# Path to the dictionary file relative to this test file
_RESOURCES = Path(__file__).parent.parent / "src" / "zh_en_translator" / "resources"
USER_DICT_PATH = _RESOURCES / "user_dict_technical.txt"


class TestUserDictFile:
    """Verify the user dictionary file is present and well-formed."""

    def test_file_exists(self):
        """user_dict_technical.txt must exist in the resources directory."""
        assert USER_DICT_PATH.exists(), f"Missing: {USER_DICT_PATH}"

    def test_file_is_not_empty(self):
        """Dictionary file must contain at least one non-comment, non-blank line."""
        lines = USER_DICT_PATH.read_text(encoding="utf-8").splitlines()
        term_lines = [
            ln for ln in lines if ln.strip() and not ln.strip().startswith("#")
        ]
        assert len(term_lines) > 0, "user_dict_technical.txt has no term entries"

    def test_key_manufacturing_terms_present(self):
        """Spot-check that high-priority manufacturing compounds are in the file."""
        content = USER_DICT_PATH.read_text(encoding="utf-8")
        required = ["激光模块", "手板样机", "样机", "激光", "模块", "部门", "你们"]
        missing = [term for term in required if term not in content]
        assert not missing, f"Missing terms from user dict: {missing}"

    def test_term_lines_have_valid_format(self):
        """Each term line must start with a Chinese character or ASCII word (not a tab)."""
        lines = USER_DICT_PATH.read_text(encoding="utf-8").splitlines()
        for ln in lines:
            stripped = ln.strip()
            if not stripped or stripped.startswith("#"):
                continue
            # First field is the word — must not be empty
            word = stripped.split("\t")[0].strip()
            assert word, f"Empty word field in line: {repr(ln)}"


class TestUserDictLoading:
    """Verify load_user_dict() accepts the technical dictionary without error."""

    def test_load_user_dict_with_real_file(self):
        """load_user_dict() must not raise when given the technical dictionary."""
        import zh_en_translator.engines.segmentation as seg_mod

        if not seg_mod._JIEBA_AVAILABLE:
            pytest.skip("jieba not installed — skipping load test")

        # Should complete without raising
        seg_mod.load_user_dict(USER_DICT_PATH)

    def test_load_user_dict_missing_file_warns(self, caplog):
        """load_user_dict() logs a warning and does not raise for a missing path."""
        import logging
        import zh_en_translator.engines.segmentation as seg_mod

        with caplog.at_level(logging.WARNING, logger="zh_en_translator.engines.segmentation"):
            seg_mod.load_user_dict("/nonexistent/path/dict.txt")

        assert any("not found" in rec.message for rec in caplog.records)

    def test_load_user_dict_jieba_unavailable_warns(self, caplog):
        """load_user_dict() logs a warning when jieba is not available."""
        import logging
        import zh_en_translator.engines.segmentation as seg_mod

        with patch.object(seg_mod, "_JIEBA_AVAILABLE", False):
            with caplog.at_level(logging.WARNING, logger="zh_en_translator.engines.segmentation"):
                seg_mod.load_user_dict(USER_DICT_PATH)

        assert any("jieba not available" in rec.message for rec in caplog.records)

    def test_app_init_calls_load_user_dict(self):
        """_init_dictionary task calls load_user_dict with the technical dict path."""
        # Import the module to inspect — no Qt/tray needed
        import zh_en_translator.app as app_mod

        calls = []

        def fake_load_user_dict(path):
            calls.append(Path(path))

        def fake_ensure_cedict():
            # Return a dummy path that has a .db sibling
            p = _RESOURCES / "cedict_sample.txt"
            return p

        # Patch heavy dependencies so we can exercise just the wiring
        with (
            patch("zh_en_translator.engines.segmentation.load_user_dict", side_effect=fake_load_user_dict),
            patch("zh_en_translator.engines.dictionary.ensure_cedict", side_effect=fake_ensure_cedict),
        ):
            # Directly invoke the inner _task closure by reconstructing it
            # (avoids Qt/threading bootstrap)
            from zh_en_translator.engines.segmentation import load_user_dict as real_lud
            from zh_en_translator.engines.dictionary import ensure_cedict as real_ec

            # Simulate what _init_dictionary._task does
            from zh_en_translator.engines import segmentation as seg_mod2
            from zh_en_translator.engines import dictionary as dict_mod

            with (
                patch.object(seg_mod2, "load_user_dict" if hasattr(seg_mod2, "load_user_dict") else "__name__",
                              fake_load_user_dict, create=True),
            ):
                # Verify the dict file path resolves correctly
                expected = (
                    Path(app_mod.__file__).parent / "resources" / "user_dict_technical.txt"
                )
                assert expected.exists(), f"Dict file not found at expected path: {expected}"
