"""Tests for the CC-CEDICT dictionary module."""

import io
import tempfile
import zipfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from zh_en_translator.engines.dictionary import (
    Dictionary,
    _convert_pinyin_tone_marks,
    _bundled_sample_path,
    ensure_cedict,
)


class TestToneMarkConversion:
    """Test pinyin tone-mark conversion."""

    def test_tone_1(self):
        """Test tone 1 (high level)."""
        assert _convert_pinyin_tone_marks("ma1") == "mā"

    def test_tone_2(self):
        """Test tone 2 (rising)."""
        assert _convert_pinyin_tone_marks("ma2") == "má"

    def test_tone_3(self):
        """Test tone 3 (low dipping)."""
        assert _convert_pinyin_tone_marks("ma3") == "mǎ"

    def test_tone_4(self):
        """Test tone 4 (falling)."""
        assert _convert_pinyin_tone_marks("ma4") == "mà"

    def test_tone_neutral(self):
        """Test neutral tone (no mark)."""
        assert _convert_pinyin_tone_marks("ma5") == "ma"
        assert _convert_pinyin_tone_marks("de") == "de"

    def test_multiple_syllables(self):
        """Test conversion of multiple syllables."""
        assert _convert_pinyin_tone_marks("chuan2 tong3") == "chuán tǒng"

    def test_complex_syllable(self):
        """Test complex syllables with multiple vowels."""
        # For 'ai', the first vowel (a) should get the mark
        assert _convert_pinyin_tone_marks("ai3") == "ǎi"
        # For 'ou', the first vowel (o) should get the mark
        assert _convert_pinyin_tone_marks("ou3") == "ǒu"

    def test_empty_string(self):
        """Test empty string handling."""
        assert _convert_pinyin_tone_marks("") == ""

    def test_u_umlaut(self):
        """Test ü character."""
        assert _convert_pinyin_tone_marks("lü3") == "lǚ"


class TestDictionaryBuild:
    """Test dictionary building from CC-CEDICT."""

    def test_build_from_cedict(self):
        """Test building dictionary from sample CC-CEDICT."""
        cedict_content = """# Comment line
你好 你好 [ni3 hao3] /hello/hi/
世界 世界 [shi4 jie4] /world/
电脑 电脑 [dian4 nao3] /computer/
"""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            cedict_file = tmpdir / "cedict.txt"
            cedict_file.write_text(cedict_content, encoding="utf-8")

            db_file = tmpdir / "test.db"
            dictionary = Dictionary.build_from_cedict(cedict_file, db_file)

            # Verify entries
            entries = dictionary.lookup("你好")
            assert len(entries) == 1
            assert entries[0].traditional == "你好"
            assert entries[0].simplified == "你好"
            assert entries[0].pinyin == "nǐ hǎo"
            assert entries[0].glosses == ["hello", "hi"]

            dictionary.close()

    def test_lookup_simplified(self):
        """Test lookup by simplified characters."""
        cedict_content = """你好 你好 [ni3 hao3] /hello/hi/"""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            cedict_file = tmpdir / "cedict.txt"
            cedict_file.write_text(cedict_content, encoding="utf-8")

            db_file = tmpdir / "test.db"
            dictionary = Dictionary.build_from_cedict(cedict_file, db_file)

            entries = dictionary.lookup("你好")
            assert len(entries) == 1
            dictionary.close()

    def test_lookup_traditional(self):
        """Test lookup by traditional characters."""
        cedict_content = """電腦 电脑 [dian4 nao3] /computer/"""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            cedict_file = tmpdir / "cedict.txt"
            cedict_file.write_text(cedict_content, encoding="utf-8")

            db_file = tmpdir / "test.db"
            dictionary = Dictionary.build_from_cedict(cedict_file, db_file)

            # Lookup by traditional
            entries = dictionary.lookup("電腦")
            assert len(entries) == 1
            assert entries[0].simplified == "电脑"
            dictionary.close()

    def test_lookup_unknown(self):
        """Test lookup of unknown word."""
        cedict_content = """你好 你好 [ni3 hao3] /hello/hi/"""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            cedict_file = tmpdir / "cedict.txt"
            cedict_file.write_text(cedict_content, encoding="utf-8")

            db_file = tmpdir / "test.db"
            dictionary = Dictionary.build_from_cedict(cedict_file, db_file)

            entries = dictionary.lookup("未知")
            assert len(entries) == 0
            dictionary.close()

    def test_skip_comments(self):
        """Test that comment lines are skipped."""
        cedict_content = """# Comment
# Another comment
你好 你好 [ni3 hao3] /hello/hi/
"""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            cedict_file = tmpdir / "cedict.txt"
            cedict_file.write_text(cedict_content, encoding="utf-8")

            db_file = tmpdir / "test.db"
            dictionary = Dictionary.build_from_cedict(cedict_file, db_file)

            entries = dictionary.lookup("你好")
            assert len(entries) == 1
            dictionary.close()


def _make_fake_zip(cedict_content: str) -> bytes:
    """Create an in-memory ZIP containing cedict_ts.u8 with the given content."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_STORED) as zf:
        zf.writestr("cedict_ts.u8", cedict_content)
    return buf.getvalue()


class TestEnsureCedict:
    """Tests for ensure_cedict() download and fallback logic."""

    def test_ensure_cedict_downloads_if_missing(self, tmp_path):
        """ensure_cedict() downloads the ZIP and extracts cedict_ts.u8 when absent."""
        cedict_content = "# CC-CEDICT\n你好 你好 [ni3 hao3] /hello/hi/\n"
        fake_zip_bytes = _make_fake_zip(cedict_content)

        target_path = tmp_path / "cedict_ts.u8"

        # Fake urlopen response
        mock_response = MagicMock()
        mock_response.read.return_value = fake_zip_bytes
        mock_response.__enter__ = lambda s: s
        mock_response.__exit__ = MagicMock(return_value=False)

        with (
            patch(
                "zh_en_translator.engines.dictionary.get_cedict_path",
                return_value=target_path,
            ),
            patch(
                "zh_en_translator.engines.dictionary.urllib.request.urlopen",
                return_value=mock_response,
            ),
        ):
            result = ensure_cedict()

        assert result == target_path
        assert target_path.exists()
        assert "你好" in target_path.read_text(encoding="utf-8")

    def test_ensure_cedict_returns_existing_file(self, tmp_path):
        """ensure_cedict() returns the existing path without downloading."""
        target_path = tmp_path / "cedict_ts.u8"
        target_path.write_text("# already downloaded\n", encoding="utf-8")

        with patch(
            "zh_en_translator.engines.dictionary.get_cedict_path",
            return_value=target_path,
        ):
            result = ensure_cedict()

        assert result == target_path

    def test_ensure_cedict_returns_sample_on_download_failure(self, tmp_path):
        """ensure_cedict() falls back to bundled sample when download raises."""
        target_path = tmp_path / "cedict_ts.u8"

        with (
            patch(
                "zh_en_translator.engines.dictionary.get_cedict_path",
                return_value=target_path,
            ),
            patch(
                "zh_en_translator.engines.dictionary.urllib.request.urlopen",
                side_effect=OSError("network unreachable"),
            ),
        ):
            result = ensure_cedict()

        # Must not raise; must return the bundled sample path
        assert result == _bundled_sample_path()
        assert result.exists()
