"""User glossary: CSV-based custom Chinese-English term pairs + domain glossaries.

Domain glossaries are loaded from the SQLite backend (glossary_db.py) with a
TOML fallback for first-run seeding and development.  The user's personal
CSV glossary continues to work unchanged.
"""
from __future__ import annotations
import csv
import logging
import tomllib
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


def load_domain_glossary(domain: str = "manufacturing") -> dict[str, str]:
    """Load domain-specific glossary, preferring the SQLite backend.

    First tries the SQLite database (via GlossaryDB / open_default_db).
    Falls back to the legacy TOML file if the database is unavailable or empty.

    Args:
        domain: Domain name (e.g., 'manufacturing').

    Returns:
        Dict of {zh: en} terms from the domain glossary.
        Returns empty dict if neither source is available.
    """
    # --- Try SQLite backend first -----------------------------------------
    try:
        from zh_en_translator.engines.glossary_db import open_default_db

        with open_default_db() as db:
            result = db.load(domain)
        if result:
            logger.info(
                "Loaded %d domain glossary entries for '%s' from SQLite", len(result), domain
            )
            return result
        logger.debug("SQLite domain '%s' is empty, falling back to TOML", domain)
    except Exception as exc:
        logger.debug("SQLite backend unavailable (%s), falling back to TOML", exc)

    # --- TOML fallback (legacy / development) -----------------------------
    try:
        from zh_en_translator import __file__ as module_file
        resources_dir = Path(module_file).parent / "resources"
        glossary_file = resources_dir / f"glossary_{domain}.toml"

        if not glossary_file.exists():
            logger.debug("Domain glossary not found: %s", glossary_file)
            return {}

        with open(glossary_file, "rb") as f:
            data = tomllib.load(f)

        result = {}
        for section in data.values():
            if isinstance(section, dict):
                for chinese, english in section.items():
                    if isinstance(english, str):
                        result[chinese] = english

        logger.info("Loaded %d domain glossary entries from %s (TOML)", len(result), glossary_file)
        return result
    except Exception as e:
        logger.warning("Failed to load domain glossary '%s': %s", domain, e)
        return {}


def load_all_glossaries(include_domains: list[str] | None = None) -> dict[str, str]:
    """Load user glossary + domain glossaries and merge them.

    User glossary takes precedence over domain glossaries.

    Args:
        include_domains: List of domain glossaries to load (default: ["manufacturing"]).

    Returns:
        Merged dict of all glossary entries.
    """
    if include_domains is None:
        include_domains = ["manufacturing"]

    merged = {}

    # Load domain glossaries first
    for domain in include_domains:
        domain_terms = load_domain_glossary(domain)
        merged.update(domain_terms)

    # User glossary overrides domain glossaries
    user_terms = load_glossary()
    merged.update(user_terms)

    return merged
