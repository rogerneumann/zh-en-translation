"""User glossary: CSV-based custom Chinese→English term pairs."""
from __future__ import annotations
import csv
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def get_glossary_path() -> Path:
    from zh_en_translator.config import get_config_path
    return get_config_path().parent / "glossary.csv"


def load_glossary(path: Path | None = None) -> dict[str, str]:
    """Load glossary CSV. Returns {zh: en} dict, empty dict on any error."""
    if path is None:
        path = get_glossary_path()
    if not path.exists():
        return {}
    try:
        result = {}
        with open(path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                zh = row.get("zh", "").strip()
                en = row.get("en", "").strip()
                if zh and en:
                    result[zh] = en
        logger.debug("Loaded %d glossary entries from %s", len(result), path)
        return result
    except Exception as e:
        logger.warning("Failed to load glossary from %s: %s", path, e)
        return {}


def save_glossary(terms: dict[str, str], path: Path | None = None) -> None:
    """Save glossary dict to CSV."""
    if path is None:
        path = get_glossary_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["zh", "en"])
        writer.writeheader()
        for zh, en in sorted(terms.items()):
            writer.writerow({"zh": zh, "en": en})
    logger.info("Saved %d glossary entries to %s", len(terms), path)
