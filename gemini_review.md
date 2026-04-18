# Gemini CLI Code Review & Recommendations
**Project:** zh-en-translator (Chinese → English Popup Translator)
**Date:** April 18, 2026

## 1. User Interface (UI) Recommendations

### **Popup Enhancements**
*   **Inline Source Editing**: Currently, the source text in the popup is read-only. Allowing the user to edit this text would be a significant UX win, especially for OCR results which might have small errors (e.g., misrecognizing a character). Users could fix the text and trigger a re-translation immediately.
*   **Visual Loading Indicators**: Instead of the "Translating..." text, use a small, indeterminate `QProgressBar` or a subtle loading spinner. This provides better visual feedback that the app hasn't frozen during longer neural MT tasks.
*   **Re-introduce Word-by-word Breakdown**: The engine for CC-CEDICT lookup is already functional but hidden. Adding this back as a **collapsible "Details" or "Dictionary" section** would be highly valuable for users who want to understand the components of a sentence or learn specific vocabulary.
*   **Action Button Grouping**: As the number of buttons grows (Copy, Look up, Replace, Pin), consider using icons with text tooltips or a "More" menu to keep the popup compact.

### **Sidebar Enhancements**
*   **Translation History**: The most requested "future" feature in the logs is a scrollable history. Implementing a basic list of the last 10–20 translations in the sidebar would make the tool much more useful for reference.
*   **Export/Vocabulary List**: Allow users to "Star" or "Save" specific translations from the sidebar into a simple CSV or TXT file ("Vocabulary list").

### **Accessibility**
*   **High Contrast Themes**: While the app has Dark and Sepia themes, a specific "High Contrast" theme for accessibility would be a great addition.
*   **Screen Reader Validation**: Perform a manual pass with **NVDA** or **JAWS** to ensure the `setAccessibleName` calls provide a logical flow during navigation.

## 2. New Feature Recommendations

*   **Region Capture OCR**: Currently, OCR only works on clipboard images. Adding a **"Select Area to Translate"** feature (similar to the Windows Snipping Tool) would allow users to translate text from images, videos, or PDFs that can't be selected, without needing to manually screenshot them first.
*   **Inline Dictionary "Look Up"**: In the translation result, allow users to double-click an English word to see a quick popup definition or synonyms.
*   **DeepL Engine Support**: DeepL often provides more natural-sounding translations than Argos for complex sentences. Adding it as an opt-in cloud provider (similar to Azure) would be a valuable alternative for users with a DeepL API key.

## 3. Technical & Architectural Recommendations

*   **Unified Clipboard Management**: I recommend replacing `pyperclip` with **`QClipboard`**. Since the app is already a PyQt6 application, using the native Qt clipboard is faster, more consistent, and reduces external dependencies. It also handles rich data (like images) more reliably than `pyperclip`'s text-focused approach.
*   **Persistent Logging**: Ensure that the `logging` output is redirected to a file in `%APPDATA%\zh-en-translator\logs\app.log`. This will make it much easier to debug issues reported by users in the field.
*   **Update Checker**: Implement a simple version check against a JSON file on GitHub. Even if you don't do auto-updates yet, a "A new version is available" notification in the tray would keep users on the latest build.

## 4. Review of PLAN.md and progress.md

*   **Plan Alignment**: The project has followed the `PLAN.md` very closely. The deviation from `jieba` to character-run segmentation was a smart move for portability, although the recent re-integration of `jieba` shows good persistence.
*   **Milestone Completion**: The project is essentially at M10. The next logical step beyond the "v1" scope would be the **Rust rewrite** mentioned in the plan, but only if performance bottlenecks are encountered. With the current Python implementation, idle overhead and lookup speeds are well within acceptable limits.
