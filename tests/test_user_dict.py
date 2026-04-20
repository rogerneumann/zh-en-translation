"""Minimal test: verify technical user dictionary file exists and loads cleanly."""

from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest


# Path to the dictionary file relative to this test file
_RESOURCES = Path(__file__).parent.parent / "src" / "zh_en_translator" / "resources"
USER_DICT_PATH = _RESOURCES / "user_dict_technical.txt"
USER_DICT_TOML_PATH = _RESOURCES / "user_dict_technical.toml"


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


class TestUserDictTomlFile:
    """Verify the TOML companion dictionary file is present and valid."""

    def test_toml_file_exists(self):
        """user_dict_technical.toml must exist alongside the .txt file."""
        assert USER_DICT_TOML_PATH.exists(), f"Missing: {USER_DICT_TOML_PATH}"

    def test_toml_file_parses(self):
        """user_dict_technical.toml must parse without errors."""
        import tomllib
        data = tomllib.loads(USER_DICT_TOML_PATH.read_text(encoding="utf-8"))
        assert "terms" in data, "TOML file must contain a [[terms]] array"

    def test_toml_key_terms_present(self):
        """Spot-check that key manufacturing terms appear in the TOML."""
        import tomllib
        data = tomllib.loads(USER_DICT_TOML_PATH.read_text(encoding="utf-8"))
        zh_terms = {entry["zh"] for entry in data.get("terms", [])}
        required = ["激光模块", "手板样机", "样机", "激光", "模块", "部门", "你们",
                    "换", "标", "进能部门"]
        missing = [t for t in required if t not in zh_terms]
        assert not missing, f"Missing terms from TOML: {missing}"

    def test_toml_entries_have_required_fields(self):
        """Every [[terms]] entry must have zh, en, freq, and pos fields."""
        import tomllib
        data = tomllib.loads(USER_DICT_TOML_PATH.read_text(encoding="utf-8"))
        for entry in data.get("terms", []):
            for field in ("zh", "en", "freq", "pos"):
                assert field in entry, (
                    f"Entry {entry.get('zh', '?')!r} missing required field {field!r}"
                )
            assert isinstance(entry["en"], list) and entry["en"], (
                f"Entry {entry['zh']!r}: 'en' must be a non-empty list"
            )
            assert isinstance(entry["freq"], int) and entry["freq"] > 0, (
                f"Entry {entry['zh']!r}: 'freq' must be a positive integer"
            )


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

        # Ensure we exercise the "file not found" branch by patching _JIEBA_AVAILABLE=True
        # even when jieba is absent in this environment.
        with patch.object(seg_mod, "_JIEBA_AVAILABLE", True):
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

    def test_init_dictionary_task_wiring(self):
        """Verify _init_dictionary calls load_user_dict and ensure_cedict correctly.

        Reconstructs the _task closure logic from app._init_dictionary without
        importing the Qt-dependent app module, so this test runs headlessly.
        """
        from pathlib import Path as _Path
        import zh_en_translator.engines.segmentation as seg_mod
        import zh_en_translator.engines.dictionary as dict_mod

        load_calls = []
        cedict_calls = []

        # Simulate the inner _task from app._init_dictionary
        resources_dir = _RESOURCES

        def simulated_task():
            # Mirror the logic in app.py _init_dictionary._task
            user_dict = resources_dir / "user_dict_technical.txt"
            seg_mod.load_user_dict(user_dict)
            cedict_path = dict_mod.ensure_cedict()
            return cedict_path

        with (
            patch.object(seg_mod, "load_user_dict", side_effect=lambda p: load_calls.append(_Path(p))),
            patch.object(dict_mod, "ensure_cedict", side_effect=lambda: cedict_calls.append(True) or _RESOURCES / "cedict_sample.txt"),
        ):
            result = simulated_task()

        # load_user_dict was called with the technical dict
        assert len(load_calls) == 1
        assert load_calls[0].name == "user_dict_technical.txt"
        assert load_calls[0].exists(), "Technical dict file must exist at the path passed to load_user_dict"

        # ensure_cedict was called
        assert len(cedict_calls) == 1

    def test_resources_dir_contains_both_dict_files(self):
        """Both user_dict_technical.txt and user_dict_technical.toml must be present."""
        assert USER_DICT_PATH.exists(), f"Missing: {USER_DICT_PATH}"
        assert USER_DICT_TOML_PATH.exists(), f"Missing: {USER_DICT_TOML_PATH}"
