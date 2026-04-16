"""Tests for Qt accessibility — accessible names, descriptions, and tab order."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from zh_en_translator.ui.popup import TranslatorPopup
from zh_en_translator.config import Config


def _cleanup(popup):
    """Stop all background threads and close the popup."""
    popup._dismissed = True
    for attr in ("_worker", "_pinyin_worker"):
        w = getattr(popup, attr, None)
        if w and w.isRunning():
            w.quit()
            w.wait(3000)
    popup.close()


# ---------------------------------------------------------------------------
# Popup accessibility
# ---------------------------------------------------------------------------


def test_popup_source_text_accessible_name(qapp):
    popup = TranslatorPopup("你好", config=Config())
    try:
        assert popup.text_display.accessibleName() == "Source text"
    finally:
        _cleanup(popup)


def test_popup_translation_accessible_name(qapp):
    popup = TranslatorPopup("你好", config=Config())
    try:
        assert popup.translation_label.accessibleName() == "Translation"
    finally:
        _cleanup(popup)


def test_popup_buttons_have_descriptions(qapp):
    popup = TranslatorPopup("你好", config=Config())
    try:
        assert popup.btn_copy.accessibleDescription()
        assert popup.btn_replace.accessibleDescription()
        assert popup.btn_lookup.accessibleDescription()
    finally:
        _cleanup(popup)


def test_popup_pinyin_label_accessible(qapp):
    popup = TranslatorPopup("你好", config=Config())
    try:
        assert popup._pinyin_label.accessibleName() == "Pinyin romanisation"
    finally:
        _cleanup(popup)


def test_popup_pin_button_has_description(qapp):
    popup = TranslatorPopup("你好", config=Config())
    try:
        assert popup.btn_pin.accessibleDescription()
    finally:
        _cleanup(popup)


def test_popup_lang_settings_button_has_description(qapp):
    popup = TranslatorPopup("你好", config=Config())
    try:
        assert popup.btn_lang_settings.accessibleDescription()
    finally:
        _cleanup(popup)


def test_popup_source_text_has_description(qapp):
    popup = TranslatorPopup("你好", config=Config())
    try:
        assert popup.text_display.accessibleDescription()
    finally:
        _cleanup(popup)


def test_popup_translation_has_description(qapp):
    popup = TranslatorPopup("你好", config=Config())
    try:
        assert popup.translation_label.accessibleDescription()
    finally:
        _cleanup(popup)


def test_popup_pinyin_label_has_description(qapp):
    popup = TranslatorPopup("你好", config=Config())
    try:
        assert popup._pinyin_label.accessibleDescription()
    finally:
        _cleanup(popup)


# ---------------------------------------------------------------------------
# Sidebar accessibility
# ---------------------------------------------------------------------------


def test_sidebar_has_accessible_name(qapp):
    from zh_en_translator.ui.sidebar import TranslatorSidebar

    sidebar = TranslatorSidebar()
    # The panel or sidebar itself should have an accessible name
    assert sidebar.accessibleName() or sidebar.translation_label.accessibleName()


def test_sidebar_translation_label_accessible(qapp):
    from zh_en_translator.ui.sidebar import TranslatorSidebar

    sidebar = TranslatorSidebar()
    assert sidebar.translation_label.accessibleName() == "Translation"


def test_sidebar_source_label_accessible(qapp):
    from zh_en_translator.ui.sidebar import TranslatorSidebar

    sidebar = TranslatorSidebar()
    assert sidebar.source_label.accessibleName() == "Source text"


def test_sidebar_self_accessible_name(qapp):
    from zh_en_translator.ui.sidebar import TranslatorSidebar

    sidebar = TranslatorSidebar()
    assert sidebar.accessibleName() == "Translation sidebar"


def test_sidebar_pin_button_has_description(qapp):
    from zh_en_translator.ui.sidebar import TranslatorSidebar

    sidebar = TranslatorSidebar()
    assert sidebar.btn_pin.accessibleDescription()


def test_sidebar_close_button_has_description(qapp):
    from zh_en_translator.ui.sidebar import TranslatorSidebar

    sidebar = TranslatorSidebar()
    assert sidebar._close_btn.accessibleDescription()
