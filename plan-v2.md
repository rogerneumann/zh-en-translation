# Implementation Plan: zh-en-translator Enhancements (v2)

This plan outlines the next phase of development for the `zh-en-translator` application, derived from the April 2026 Gemini CLI code review.

## Milestone 1: Core Infrastructure & Robustness (COMPLETED)
- **Refactor Clipboard Management**: Replaced `pyperclip` with native `QClipboard` for better state preservation and performance.
- **Persistent & Private Logging**: Implemented `RotatingFileHandler` logging to `%LOCALAPPDATA%` while strictly excluding sensitive translation text.
- **Visual Loading Indicator**: Added animated "Translating..." and "Waiting for OCR..." indicators to the popup and sidebar.

## Milestone 2: Sidebar History & Management
**Focus:** Persistence and utility in the sidebar.

*   **History Storage**:
    *   Create a simple local storage mechanism (JSON-based) for the last 20 translations in `src/zh_en_translator/engines/history.py`.
    *   Ensure thread-safe writes and automatic rotation at 20 items.
*   **Sidebar UI Update**:
    *   Add a scrollable "History" list to the `TranslatorSidebar`.
    *   Allow users to click a history item to restore it to the main view.
*   **History Actions**:
    *   Implement a "Clear History" button in the sidebar header or context menu.
    *   Implement an "Export History" feature to save the history to a CSV or TXT file.

## Milestone 3: Intelligence & Accessibility
**Focus:** Learning tools and inclusive design.

*   **Inline Dictionary Lookup**:
    *   Modify the translation label to allow word-level interaction (e.g., via `setOpenExternalLinks` or a custom link handler).
    *   Enable users to "look up" specific English words in the translation.
*   **Collapsible Details Section**:
    *   Re-integrate the word-by-word CC-CEDICT breakdown.
    *   Design it as an unobtrusive, collapsible section at the bottom of the popup.
*   **High Contrast Accessibility**:
    *   Add a "High Contrast" theme to `src/zh_en_translator/engines/themes.py`.
    *   Verify all UI components respect accessible color ratios.

## Milestone 4: External Integrations & Lifecycle
**Focus:** Expanding translation options and maintenance.

*   **DeepL Engine Support**:
    *   Add DeepL as an opt-in cloud provider in `src/zh_en_translator/engines/deepl.py`.
    *   Update Preferences dialog to include DeepL API key and usage tier.
*   **Update Checker Hooks**:
    *   Implement infrastructure for checking for updates (background version check).
    *   Add "Check for Updates" button to Preferences.
*   **Inline Editing (Low Priority)**:
    *   Convert the source text label in the popup into an editable field to allow manual OCR corrections.

---

## Verification Plan

### Automated Tests
- `tests/test_history.py`: Verify history rotation, persistence, and clear/export logic.
- `tests/test_deepl.py`: Mocked DeepL API success/failure paths.

### Manual Verification
1. **History Check**: Perform translations and verify they appear in the sidebar list; check persistence across restarts.
2. **Export Check**: Verify CSV/TXT export contains the expected fields.
3. **Accessibility Check**: Toggle High Contrast mode and verify visibility.
