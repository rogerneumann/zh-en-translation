"""SQLite-backed glossary backend with versioning and multi-domain support.

Replaces the TOML-only approach with a structured SQLite database that supports:
- Multiple domains (manufacturing, medical, legal, etc.)
- Version tracking via schema version and term timestamps
- CSV import/export for backward compatibility
- Thread-safe read operations via context manager
"""
from __future__ import annotations

import csv
import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

logger = logging.getLogger(__name__)

SCHEMA_VERSION = 1

# DDL for the glossary database
_SCHEMA_SQL = """\
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS glossaries (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    domain      TEXT    NOT NULL,
    chinese     TEXT    NOT NULL,
    english     TEXT    NOT NULL,
    notes       TEXT    NOT NULL DEFAULT '',
    created_at  TEXT    NOT NULL,
    updated_at  TEXT    NOT NULL,
    UNIQUE(domain, chinese)
);

CREATE INDEX IF NOT EXISTS idx_glossaries_domain
    ON glossaries (domain);
CREATE INDEX IF NOT EXISTS idx_glossaries_chinese
    ON glossaries (chinese);
"""


def _utcnow() -> str:
    """Return current UTC time as ISO 8601 string."""
    return datetime.now(timezone.utc).isoformat()


class GlossaryDB:
    """SQLite glossary backend.

    Usage::

        db = GlossaryDB(Path("resources/glossary.db"))
        terms = db.load("manufacturing")
        db.add_term("合金钢", "alloy steel", "manufacturing")
        db.close()

    The database is created automatically if it does not exist.
    """

    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self._conn: sqlite3.Connection | None = None
        self._ensure_open()

    # ------------------------------------------------------------------
    # Connection management
    # ------------------------------------------------------------------

    def _ensure_open(self) -> sqlite3.Connection:
        """Open or re-open the SQLite connection."""
        if self._conn is None:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA foreign_keys=ON")
            self._init_schema()
        return self._conn

    def close(self) -> None:
        """Close the underlying database connection."""
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def __enter__(self) -> "GlossaryDB":
        return self

    def __exit__(self, *args) -> None:
        self.close()

    # ------------------------------------------------------------------
    # Schema initialisation
    # ------------------------------------------------------------------

    def _init_schema(self) -> None:
        """Create tables and record schema version if not already present."""
        conn = self._conn
        conn.executescript(_SCHEMA_SQL)
        row = conn.execute("SELECT version FROM schema_version LIMIT 1").fetchone()
        if row is None:
            conn.execute(
                "INSERT INTO schema_version (version, created_at) VALUES (?, ?)",
                (SCHEMA_VERSION, _utcnow()),
            )
            conn.commit()
            logger.debug("Initialised glossary DB schema v%d at %s", SCHEMA_VERSION, self.db_path)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_version(self) -> int:
        """Return the schema version stored in the database."""
        conn = self._ensure_open()
        row = conn.execute("SELECT version FROM schema_version LIMIT 1").fetchone()
        return int(row["version"]) if row else 0

    def list_domains(self) -> list[str]:
        """Return sorted list of all domains that have at least one term."""
        conn = self._ensure_open()
        rows = conn.execute(
            "SELECT DISTINCT domain FROM glossaries ORDER BY domain"
        ).fetchall()
        return [r["domain"] for r in rows]

    def load(self, domain: str) -> dict[str, str]:
        """Load all terms for *domain* as a ``{chinese: english}`` dict."""
        conn = self._ensure_open()
        rows = conn.execute(
            "SELECT chinese, english FROM glossaries WHERE domain = ?",
            (domain,),
        ).fetchall()
        result = {r["chinese"]: r["english"] for r in rows}
        logger.debug("Loaded %d glossary terms from %s", len(result), self.db_path)
        return result

    def load_with_notes(self, domain: str) -> list[dict]:
        """Load all terms for *domain* as a list of full record dicts."""
        conn = self._ensure_open()
        rows = conn.execute(
            "SELECT id, domain, chinese, english, notes, created_at, updated_at "
            "FROM glossaries WHERE domain = ? ORDER BY chinese",
            (domain,),
        ).fetchall()
        return [dict(r) for r in rows]

    def add_term(
        self,
        chinese: str,
        english: str,
        domain: str,
        notes: str = "",
    ) -> int:
        """Insert or replace a single term.

        Returns the row id of the inserted/updated record.
        """
        conn = self._ensure_open()
        now = _utcnow()
        # Use INSERT OR REPLACE to handle duplicate (domain, chinese) pairs.
        # We preserve the original created_at when updating.
        existing = conn.execute(
            "SELECT id, created_at FROM glossaries WHERE domain = ? AND chinese = ?",
            (domain, chinese),
        ).fetchone()

        if existing:
            conn.execute(
                "UPDATE glossaries SET english = ?, notes = ?, updated_at = ? "
                "WHERE domain = ? AND chinese = ?",
                (english, notes, now, domain, chinese),
            )
            conn.commit()
            row_id = int(existing["id"])
        else:
            cur = conn.execute(
                "INSERT INTO glossaries (domain, chinese, english, notes, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (domain, chinese, english, notes, now, now),
            )
            conn.commit()
            row_id = cur.lastrowid

        logger.debug("add_term complete, id=%d", row_id)
        return row_id

    def delete_term(self, chinese: str, domain: str) -> bool:
        """Delete a term from a domain. Returns True if a row was removed."""
        conn = self._ensure_open()
        cur = conn.execute(
            "DELETE FROM glossaries WHERE domain = ? AND chinese = ?",
            (domain, chinese),
        )
        conn.commit()
        removed = cur.rowcount > 0
        if removed:
            logger.debug("Deleted term '%s' from domain '%s'", chinese, domain)
        return removed

    def count(self, domain: str | None = None) -> int:
        """Return number of terms, optionally filtered by domain."""
        conn = self._ensure_open()
        if domain is not None:
            row = conn.execute(
                "SELECT COUNT(*) AS n FROM glossaries WHERE domain = ?", (domain,)
            ).fetchone()
        else:
            row = conn.execute("SELECT COUNT(*) AS n FROM glossaries").fetchone()
        return int(row["n"])

    # ------------------------------------------------------------------
    # CSV import / export (backward compat with legacy CSV glossary)
    # ------------------------------------------------------------------

    def import_csv(self, path: Path, domain: str, notes_col: str | None = "notes") -> int:
        """Import terms from a CSV file into *domain*.

        The CSV must have at least columns ``zh`` and ``en``.
        An optional ``notes`` column is imported when present.

        Returns the number of terms imported.
        """
        imported = 0
        try:
            with open(path, newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    zh = row.get("zh", "").strip()
                    en = row.get("en", "").strip()
                    if not zh or not en:
                        continue
                    notes = ""
                    if notes_col and notes_col in row:
                        notes = row[notes_col].strip()
                    self.add_term(zh, en, domain, notes)
                    imported += 1
            logger.info("Imported %d terms from %s into domain '%s'", imported, path, domain)
        except Exception as exc:
            logger.warning("import_csv failed for %s: %s", path, exc)
            raise
        return imported

    def export_csv(self, domain: str, path: Path) -> int:
        """Export all terms for *domain* to a CSV file.

        Columns: ``zh``, ``en``, ``notes``.  Returns number of rows written.
        """
        path.parent.mkdir(parents=True, exist_ok=True)
        rows = self.load_with_notes(domain)
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["zh", "en", "notes"])
            writer.writeheader()
            for r in rows:
                writer.writerow({"zh": r["chinese"], "en": r["english"], "notes": r["notes"]})
        logger.info("Exported %d terms for domain '%s' to %s", len(rows), domain, path)
        return len(rows)

    # ------------------------------------------------------------------
    # Bulk import from TOML (used to seed the DB from legacy TOML files)
    # ------------------------------------------------------------------

    def import_toml(self, path: Path, domain: str) -> int:
        """Seed the database from a TOML glossary file.

        Expects the same structure as ``glossary_manufacturing.toml``:
        top-level tables whose values are ``{chinese: english}`` mappings.
        Returns number of terms imported.
        """
        import tomllib

        imported = 0
        try:
            with open(path, "rb") as f:
                data = tomllib.load(f)
            for section in data.values():
                if not isinstance(section, dict):
                    continue
                for chinese, english in section.items():
                    if isinstance(english, str):
                        self.add_term(chinese, english, domain)
                        imported += 1
            logger.info(
                "Seeded %d terms from TOML %s into domain '%s'", imported, path, domain
            )
        except Exception as exc:
            logger.warning("import_toml failed for %s: %s", path, exc)
            raise
        return imported

    # ------------------------------------------------------------------
    # Iterator helpers
    # ------------------------------------------------------------------

    def iter_terms(self, domain: str) -> Iterator[tuple[str, str, str]]:
        """Yield ``(chinese, english, notes)`` tuples for *domain*."""
        conn = self._ensure_open()
        cur = conn.execute(
            "SELECT chinese, english, notes FROM glossaries WHERE domain = ? ORDER BY chinese",
            (domain,),
        )
        for row in cur:
            yield row["chinese"], row["english"], row["notes"]

    # ------------------------------------------------------------------
    # Multi-domain helpers (Priority 4)
    # ------------------------------------------------------------------

    def get_available_domains(self) -> list[str]:
        """Return sorted list of all domains with at least one term.

        Alias for :meth:`list_domains` with a more descriptive name for
        multi-domain use cases.
        """
        return self.list_domains()

    def load_domain(self, domain_name: str) -> dict[str, str]:
        """Load a specific domain glossary by name.

        Alias for :meth:`load` with a more descriptive name.

        Args:
            domain_name: Domain identifier (e.g., ``'medical'``, ``'legal'``).

        Returns:
            Dict of ``{chinese: english}`` for the domain. Empty dict if not found.
        """
        return self.load(domain_name)

    def search_across_domains(self, term: str) -> list[dict]:
        """Find a Chinese term in all domains.

        Args:
            term: Chinese term to search for (exact match).

        Returns:
            List of dicts with keys ``domain``, ``chinese``, ``english``, ``notes``.
            Ordered by domain name.
        """
        conn = self._ensure_open()
        rows = conn.execute(
            "SELECT domain, chinese, english, notes FROM glossaries "
            "WHERE chinese = ? ORDER BY domain",
            (term,),
        ).fetchall()
        return [dict(r) for r in rows]

    def merge_domains(self, domains_list: list[str]) -> dict[str, str]:
        """Combine multiple domain glossaries into a single dict.

        When a Chinese term appears in multiple domains, the first domain
        in *domains_list* wins (earlier entries take priority).

        Args:
            domains_list: Ordered list of domain names to merge.

        Returns:
            Merged ``{chinese: english}`` dict.
        """
        merged: dict[str, str] = {}
        # Load in reverse order so earlier domains overwrite later ones
        for domain in reversed(domains_list):
            domain_terms = self.load(domain)
            merged.update(domain_terms)
        logger.debug(
            "merge_domains: merged %d domains -> %d unique terms",
            len(domains_list),
            len(merged),
        )
        return merged


# ---------------------------------------------------------------------------
# Module-level helper: return the default (bundled) glossary DB path
# ---------------------------------------------------------------------------

def get_default_db_path() -> Path:
    """Return path to the bundled glossary.db in the resources package."""
    from zh_en_translator import __file__ as _pkg
    return Path(_pkg).parent / "resources" / "glossary.db"


def open_default_db() -> GlossaryDB:
    """Open (creating if necessary) the default bundled glossary database."""
    path = get_default_db_path()
    db = GlossaryDB(path)
    # Seed from TOML if DB is empty (first run / fresh checkout)
    if db.count() == 0:
        _seed_from_toml(db, path.parent)
    return db


def _seed_from_toml(db: GlossaryDB, resources_dir: Path) -> None:
    """Populate *db* from any ``glossary_*.toml`` files found in *resources_dir*."""
    for toml_file in sorted(resources_dir.glob("glossary_*.toml")):
        domain = toml_file.stem[len("glossary_"):]  # strip "glossary_" prefix
        try:
            n = db.import_toml(toml_file, domain)
            logger.info("Auto-seeded domain '%s' with %d terms from %s", domain, n, toml_file)
        except Exception as exc:
            logger.warning("Failed to seed domain '%s' from %s: %s", domain, toml_file, exc)
