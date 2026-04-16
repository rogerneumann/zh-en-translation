"""Tests for pinyin display: Config fields, PinyinWorker, popup label, preferences."""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch, MagicMock

os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PyQt6.QtWidgets import QCheckBox, QSpinBox  # noqa: E402


# ---------------------------------------------------------------------------
# 1. Config defaults
# ---------------------------------------------------------------------------

def test_config_pinyin_defaults():
    """Config() has show_pinyin=True and pinyin_max_chars=80 by default."""
    from zh_en_translator.config import Config
    cfg = Config()
    assert cfg.show_pinyin is True
    assert cfg.pinyin_max_chars == 80


# ---------------------------------------------------------------------------
# 2. Config round-trip (save/load)
# ---------------------------------------------------------------------------

def test_config_pinyin_save_load(tmp_path):
    """Saving show_pinyin=False / pinyin_max_chars=40 and reloading preserves the values."""
    from zh_en_translator.config import Config, save_config, load_config
    config_file = tmp_path / "config.toml"
    original = Config(show_pinyin=False, pinyin_max_chars=40)
    save_config(original, config_path=config_file)
    loaded = load_config(config_path=config_file)
    assert loaded.show_pinyin is False
    assert loaded.pinyin_max_chars == 40


# ---------------------------------------------------------------------------
# 3. PinyinWorker emits correct pinyin string (pipeline mocked)
# ---------------------------------------------------------------------------

def test_pinyin_worker_emits_string(qapp):
    """PinyinWorker emits a pinyin string derived from pipeline.translate results."""
    from zh_en_translator.engines.translation_worker import PinyinWorker
    from zh_en_translator.engines.pipeline import TokenResult
    import zh_en_translator.engines.dictionary as dict_mod
    import zh_en_translator.engines.pipeline as pipeline_mod

    fake_results = [TokenResult("你好", "nǐ hǎo", [], True)]
    emitted: list[str] = []

    worker = PinyinWorker("你好")
    worker.result_ready.connect(lambda s: emitted.append(s))

    fake_db_path = MagicMock(spec=Path)
    fake_db_path.exists.return_value = True  # skip build_from_cedict

    fake_cedict_path = MagicMock(spec=Path)
    fake_cedict_path.with_suffix.return_value = fake_db_path

    mock_dict_instance = MagicMock()
    mock_dict_instance.close = MagicMock()

    with (
        patch.object(dict_mod, "ensure_cedict", return_value=fake_cedict_path),
        patch.object(dict_mod, "Dictionary", return_value=mock_dict_instance),
        patch.object(pipeline_mod, "translate", return_value=fake_results),
    ):
        worker.run()  # call directly (no thread start needed for unit test)

    assert emitted == ["nǐ hǎo"]


# ---------------------------------------------------------------------------
# Helpers for popup tests
# ---------------------------------------------------------------------------

def _cleanup_popup(popup):
    """Stop all background threads and close the popup."""
    popup._dismissed = True
    for attr in ("_worker", "_pinyin_worker"):
        w = getattr(popup, attr, None)
        if w and w.isRunning():
            w.quit()
            w.wait(3000)
    popup.close()


# ---------------------------------------------------------------------------
# 4. Popup pinyin label hidden when show_pinyin=False
# ---------------------------------------------------------------------------

def test_popup_pinyin_label_hidden_when_disabled(qapp):
    """TranslatorPopup with show_pinyin=False has _pinyin_label hidden and no PinyinWorker."""
    from zh_en_translator.config import Config
    from zh_en_translator.ui.popup import TranslatorPopup

    cfg = Config(show_pinyin=False)
    popup = TranslatorPopup("你好", config=cfg)

    try:
        assert popup._pinyin_label.isHidden()
        assert popup._pinyin_worker is None
    finally:
        _cleanup_popup(popup)


# ---------------------------------------------------------------------------
# 5. Popup pinyin label hidden when text exceeds pinyin_max_chars
# ---------------------------------------------------------------------------

def test_popup_pinyin_label_hidden_when_text_too_long(qapp):
    """TranslatorPopup skips PinyinWorker when text length > pinyin_max_chars."""
    from zh_en_translator.config import Config
    from zh_en_translator.ui.popup import TranslatorPopup

    long_text = "你好世界" * 30  # 120 chars > default 80
    cfg = Config(show_pinyin=True, pinyin_max_chars=80)
    popup = TranslatorPopup(long_text, config=cfg)

    try:
        assert popup._pinyin_label.isHidden()
        assert popup._pinyin_worker is None
    finally:
        _cleanup_popup(popup)


# ---------------------------------------------------------------------------
# 6. Preferences dialog has pinyin checkbox and spinbox
# ---------------------------------------------------------------------------

def test_preferences_pinyin_fields_exist(qapp):
    """PreferencesDialog exposes _show_pinyin_check (QCheckBox) and _pinyin_max_spin (QSpinBox)."""
    from zh_en_translator.config import Config
    from zh_en_translator.ui.preferences import PreferencesDialog

    dlg = PreferencesDialog(Config())

    assert hasattr(dlg, "_show_pinyin_check")
    assert isinstance(dlg._show_pinyin_check, QCheckBox)
    assert hasattr(dlg, "_pinyin_max_spin")
    assert isinstance(dlg._pinyin_max_spin, QSpinBox)


def test_preferences_pinyin_fields_reflect_config(qapp):
    """PreferencesDialog loads pinyin values from Config correctly."""
    from zh_en_translator.config import Config
    from zh_en_translator.ui.preferences import PreferencesDialog

    cfg = Config(show_pinyin=False, pinyin_max_chars=120)
    dlg = PreferencesDialog(cfg)

    assert dlg._show_pinyin_check.isChecked() is False
    assert dlg._pinyin_max_spin.value() == 120
    # Spinbox should be disabled because show_pinyin=False
    assert dlg._pinyin_max_spin.isEnabled() is False


def test_preferences_pinyin_collect_config(qapp):
    """_collect_config() returns show_pinyin / pinyin_max_chars from dialog state."""
    from zh_en_translator.config import Config
    from zh_en_translator.ui.preferences import PreferencesDialog

    dlg = PreferencesDialog(Config())
    dlg._show_pinyin_check.setChecked(False)
    dlg._pinyin_max_spin.setValue(50)

    collected = dlg._collect_config()
    assert collected.show_pinyin is False
    assert collected.pinyin_max_chars == 50
