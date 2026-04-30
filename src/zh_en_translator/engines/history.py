"""History management for translations."""

from __future__ import annotations

import csv
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import TypedDict

logger = logging.getLogger(__name__)

class HistoryEntry(TypedDict):
    source: str
    translation: str
    timestamp: str

class HistoryManager:
    """Manages a rotating list of the last 20 translations."""

    def __init__(self, history_file: Path, max_items: int = 20):
        self.history_file = history_file
        self.max_items = max_items

    def load_history(self) -> list[HistoryEntry]:
        """Load history from JSON file."""
        if not self.history_file.exists():
            return []
        try:
            with open(self.history_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    return data
                return []
        except Exception as e:
            # Do not log the content, just the error
            logger.error("Failed to load history from %s: %s", self.history_file, e)
            return []

    def save_history(self, history: list[HistoryEntry]) -> None:
        """Save history to JSON file."""
        try:
            self.history_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.history_file, "w", encoding="utf-8") as f:
                json.dump(history, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error("Failed to save history to %s: %s", self.history_file, e)

    def add_entry(self, source: str, translation: str) -> list[HistoryEntry]:
        """Add a new entry to the history and rotate if necessary."""
        if not source or not translation:
            return self.load_history()

        history = self.load_history()

        # Avoid duplicate consecutive entries
        if (
            history
            and history[0].get("source") == source
            and history[0].get("translation") == translation
        ):
            return history

        entry: HistoryEntry = {
            "source": source,
            "translation": translation,
            "timestamp": datetime.now().isoformat()
        }

        history.insert(0, entry)
        if len(history) > self.max_items:
            history = history[:self.max_items]

        self.save_history(history)
        return history

    def clear_history(self) -> None:
        """Wipe the history file."""
        if self.history_file.exists():
            try:
                self.history_file.unlink()
            except Exception as e:
                logger.error("Failed to delete history file %s: %s", self.history_file, e)

    def export_to_csv(self, export_path: Path) -> bool:
        """Export history to a CSV file."""
        history = self.load_history()
        if not history:
            return False

        try:
            with open(export_path, "w", encoding="utf-8", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=["timestamp", "source", "translation"])
                writer.writeheader()
                for entry in history:
                    writer.writerow(entry)
            return True
        except Exception as e:
            logger.error("Failed to export history to %s: %s", export_path, e)
            return False
