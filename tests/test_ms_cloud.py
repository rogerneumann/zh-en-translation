"""Tests for the MS Azure Translator engine (engines/ms_cloud.py).

Key guarantees verified here:
  - is_configured() returns False for empty/blank keys
  - translate_sentence() returns None when key is empty (no HTTP attempt)
  - translate_sentence() handles HTTP errors gracefully (returns None, no raise)
  - translate_sentence() handles network errors gracefully
  - translate_sentence() handles malformed JSON responses gracefully
  - Config round-trip for cloud fields
  - PreferencesDialog exposes cloud tab with warning and controls
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from zh_en_translator.config import Config, load_config, save_config
from zh_en_translator.engines.ms_cloud import is_configured, translate_sentence


# ---------------------------------------------------------------------------
# is_configured
# ---------------------------------------------------------------------------

def test_is_configured_empty_key():
    assert is_configured("") is False


def test_is_configured_blank_key():
    assert is_configured("   ") is False


def test_is_configured_valid_key():
    assert is_configured("abc123") is True


# ---------------------------------------------------------------------------
# translate_sentence — zero network when key empty
# ---------------------------------------------------------------------------

def test_translate_no_network_when_key_empty():
    """No HTTP request is made when the API key is empty."""
    with patch("urllib.request.urlopen") as mock_urlopen:
        result = translate_sentence("你好", api_key="")
    mock_urlopen.assert_not_called()
    assert result is None


def test_translate_empty_text_returns_none():
    """Empty / whitespace input returns None without a network call."""
    with patch("urllib.request.urlopen") as mock_urlopen:
        result = translate_sentence("   ", api_key="somekey")
    mock_urlopen.assert_not_called()
    assert result is None


# ---------------------------------------------------------------------------
# translate_sentence — mocked HTTP success
# ---------------------------------------------------------------------------

def _mock_response(text: str):
    payload = json.dumps([{"translations": [{"text": text, "to": "en"}]}]).encode()
    mock_resp = MagicMock()
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = MagicMock(return_value=False)
    mock_resp.read.return_value = payload
    return mock_resp


def test_translate_success():
    """Returns the translated string on a successful API response."""
    with patch("urllib.request.urlopen", return_value=_mock_response("Hello world")):
        result = translate_sentence("你好世界", api_key="validkey")
    assert result == "Hello world"


def test_translate_includes_region_header():
    """Region is forwarded as Ocp-Apim-Subscription-Region when provided."""
    captured_req = {}

    def fake_urlopen(req, timeout=None):
        captured_req["headers"] = dict(req.headers)
        return _mock_response("Hi")

    with patch("urllib.request.urlopen", side_effect=fake_urlopen):
        translate_sentence("你好", api_key="key", region="eastus")

    assert captured_req["headers"].get("Ocp-apim-subscription-region") == "eastus"


def test_translate_no_region_header_when_blank():
    """No region header is added when region is empty."""
    captured_req = {}

    def fake_urlopen(req, timeout=None):
        captured_req["headers"] = dict(req.headers)
        return _mock_response("Hi")

    with patch("urllib.request.urlopen", side_effect=fake_urlopen):
        translate_sentence("你好", api_key="key", region="")

    assert "Ocp-apim-subscription-region" not in captured_req.get("headers", {})


# ---------------------------------------------------------------------------
# translate_sentence — graceful failure (no raises)
# ---------------------------------------------------------------------------

def test_translate_http_error_returns_none():
    """HTTP 401 / 403 / 5xx returns None without raising."""
    import urllib.error
    http_err = urllib.error.HTTPError(url="", code=401, msg="Unauthorized", hdrs={}, fp=None)
    with patch("urllib.request.urlopen", side_effect=http_err):
        result = translate_sentence("你好", api_key="badkey")
    assert result is None


def test_translate_network_error_returns_none():
    """Network-level errors (URLError) return None without raising."""
    import urllib.error
    url_err = urllib.error.URLError(reason="Name or service not known")
    with patch("urllib.request.urlopen", side_effect=url_err):
        result = translate_sentence("你好", api_key="key")
    assert result is None


def test_translate_malformed_json_returns_none():
    """Malformed JSON from the server returns None without raising."""
    bad_resp = MagicMock()
    bad_resp.__enter__ = lambda s: s
    bad_resp.__exit__ = MagicMock(return_value=False)
    bad_resp.read.return_value = b"not json at all"
    with patch("urllib.request.urlopen", return_value=bad_resp):
        result = translate_sentence("你好", api_key="key")
    assert result is None


# ---------------------------------------------------------------------------
# Config — cloud fields round-trip
# ---------------------------------------------------------------------------

def test_config_cloud_defaults():
    cfg = Config()
    assert cfg.ms_translator_enabled is False
    assert cfg.ms_translator_api_key == ""
    assert cfg.ms_translator_region == ""


def test_config_cloud_roundtrip(tmp_path):
    cfg = Config(
        ms_translator_enabled=True,
        ms_translator_api_key="abc-key-123",
        ms_translator_region="westeurope",
    )
    path = tmp_path / "config.toml"
    save_config(cfg, config_path=path)
    loaded = load_config(config_path=path)

    assert loaded.ms_translator_enabled is True
    assert loaded.ms_translator_api_key == "abc-key-123"
    assert loaded.ms_translator_region == "westeurope"


def test_config_cloud_disabled_roundtrip(tmp_path):
    cfg = Config(ms_translator_enabled=False, ms_translator_api_key="", ms_translator_region="")
    path = tmp_path / "config.toml"
    save_config(cfg, config_path=path)
    loaded = load_config(config_path=path)
    assert loaded.ms_translator_enabled is False


# ---------------------------------------------------------------------------
# TranslationWorker — zero network when ms_cloud disabled
# (skipped when PyQt6 is not installed)
# ---------------------------------------------------------------------------

import importlib as _importlib

_qt_worker_skip = pytest.mark.skipif(
    _importlib.util.find_spec("PyQt6") is None,
    reason="PyQt6 not installed",
)


@_qt_worker_skip
def test_worker_skips_cloud_when_disabled():
    """TranslationWorker never calls ms_cloud when ms_translator_enabled=False."""
    from zh_en_translator.engines.translation_worker import TranslationWorker

    cfg = Config(ms_translator_enabled=False, ms_translator_api_key="somekey")
    worker = TranslationWorker("你好", config=cfg)

    with patch("zh_en_translator.engines.ms_cloud.translate_sentence") as mock_ms:
        with patch("zh_en_translator.engines.argos.ensure_pack", return_value=False):
            worker.run()

    mock_ms.assert_not_called()


@_qt_worker_skip
def test_worker_uses_cloud_when_enabled():
    """TranslationWorker calls ms_cloud when ms_translator_enabled=True."""
    from zh_en_translator.engines.translation_worker import TranslationWorker

    cfg = Config(ms_translator_enabled=True, ms_translator_api_key="key", ms_translator_region="")

    results = []
    worker = TranslationWorker("你好", config=cfg)
    worker.result_ready.connect(results.append)

    with patch(
        "zh_en_translator.engines.ms_cloud.translate_sentence", return_value="Hello"
    ) as mock_ms:
        worker.run()

    mock_ms.assert_called_once_with("你好", "key", "")
    assert results == ["Hello"]


# ---------------------------------------------------------------------------
# Preferences — Cloud tab UI  (skipped without PyQt6)
# ---------------------------------------------------------------------------

import os as _os
_os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_qt_skip = pytest.mark.skipif(
    _importlib.util.find_spec("PyQt6") is None,
    reason="PyQt6 not installed",
)


@pytest.fixture
def qapp():
    from PyQt6.QtWidgets import QApplication
    import sys
    return QApplication.instance() or QApplication(sys.argv)


@_qt_skip
def test_preferences_has_cloud_tab(qapp):
    from zh_en_translator.ui.preferences import PreferencesDialog
    dlg = PreferencesDialog(Config())
    tab_titles = [dlg._tabs.tabText(i) for i in range(dlg._tabs.count())]
    assert "Cloud" in tab_titles
    dlg.destroy()


@_qt_skip
def test_preferences_cloud_disabled_by_default(qapp):
    from zh_en_translator.ui.preferences import PreferencesDialog
    dlg = PreferencesDialog(Config())
    assert dlg._ms_enabled_check.isChecked() is False
    dlg.destroy()


@_qt_skip
def test_preferences_cloud_collect_config(qapp):
    from zh_en_translator.ui.preferences import PreferencesDialog
    dlg = PreferencesDialog(Config())
    dlg._ms_enabled_check.setChecked(True)
    dlg._ms_api_key_edit.setText("mykey")
    dlg._ms_region_edit.setText("eastus")
    cfg = dlg._collect_config()
    assert cfg.ms_translator_enabled is True
    assert cfg.ms_translator_api_key == "mykey"
    assert cfg.ms_translator_region == "eastus"
    dlg.destroy()


@_qt_skip
def test_preferences_cloud_key_masked_by_default(qapp):
    """API key field uses Password echo mode by default."""
    from PyQt6.QtWidgets import QLineEdit
    from zh_en_translator.ui.preferences import PreferencesDialog
    dlg = PreferencesDialog(Config())
    assert dlg._ms_api_key_edit.echoMode() == QLineEdit.EchoMode.Password
    dlg.destroy()
