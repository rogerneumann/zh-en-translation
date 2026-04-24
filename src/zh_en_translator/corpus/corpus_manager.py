"""Corpus loading, versioning, and management for domain-specific translation.

Corpora are stored as JSONL files (one JSON object per line) following the
CorpusEntry schema.  The manager supports:

- Loading one or more JSONL files
- Filtering by domain, verification status, or source
- Iterating entries for evaluation or training
- Writing new entries (contributions / data augmentation output)
- Basic statistics (counts by domain, verification status)

Usage::

    from zh_en_translator.corpus import CorpusManager, CorpusEntry

    mgr = CorpusManager()
    mgr.load_file(Path("corpus/manufacturing_samples.jsonl"))

    for entry in mgr.iter_entries(domain="manufacturing"):
        print(entry.chinese, "->", entry.english)

    # Add a new sentence pair
    mgr.add_entry(CorpusEntry(
        source="manual",
        chinese="镀锌钢板的表面处理工艺",
        english="Surface treatment processes for galvanized steel sheets",
        domain="manufacturing",
        verified=True,
    ))
    mgr.save_file(Path("corpus/my_additions.jsonl"))
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Iterator

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Schema documentation
# ---------------------------------------------------------------------------

CORPUS_SCHEMA: dict[str, str] = {
    "source": "Origin of the sentence pair (e.g. 'patent', 'manual', 'standard', 'web')",
    "chinese": "Source Chinese text (simplified preferred; traditional accepted)",
    "english": "Reference English translation",
    "domain": "Subject domain: 'manufacturing', 'medical', 'legal', etc.",
    "verified": "true if translation was reviewed by a human expert, false otherwise",
    "notes": "(optional) Free-text notes: context, ambiguities, variant translations",
    "source_url": "(optional) URL or citation for the original document",
    "added_at": "(optional) ISO 8601 timestamp when this entry was added",
}

# Required fields that must be present in every entry
_REQUIRED_FIELDS = {"source", "chinese", "english", "domain", "verified"}


# ---------------------------------------------------------------------------
# CorpusEntry dataclass
# ---------------------------------------------------------------------------


@dataclass
class CorpusEntry:
    """A single bilingual sentence pair in the corpus."""

    source: str          # e.g. "patent/CN2024XXXXX", "manual", "standard/GB_T_1234"
    chinese: str         # source Chinese sentence
    english: str         # reference English translation
    domain: str          # e.g. "manufacturing"
    verified: bool       # True = human-reviewed

    notes: str = ""              # optional free-text notes
    source_url: str = ""         # optional URL / citation
    added_at: str = ""           # optional ISO 8601 timestamp

    def to_dict(self) -> dict:
        """Serialise to a plain dict (suitable for JSON)."""
        d = asdict(self)
        # Omit empty optional fields to keep JSONL compact
        for opt in ("notes", "source_url", "added_at"):
            if not d[opt]:
                del d[opt]
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "CorpusEntry":
        """Deserialise from a dict (e.g. parsed from JSONL)."""
        return cls(
            source=d["source"],
            chinese=d["chinese"],
            english=d["english"],
            domain=d["domain"],
            verified=bool(d.get("verified", False)),
            notes=d.get("notes", ""),
            source_url=d.get("source_url", ""),
            added_at=d.get("added_at", ""),
        )

    def validate(self) -> list[str]:
        """Return a list of validation errors; empty list means valid."""
        errors: list[str] = []
        if not self.chinese.strip():
            errors.append("chinese field is empty")
        if not self.english.strip():
            errors.append("english field is empty")
        if not self.source.strip():
            errors.append("source field is empty")
        if not self.domain.strip():
            errors.append("domain field is empty")
        return errors


# ---------------------------------------------------------------------------
# CorpusManager
# ---------------------------------------------------------------------------


class CorpusManager:
    """Load, manage, and iterate bilingual sentence-pair corpora.

    Each corpus is a JSONL file.  Multiple files can be loaded and their
    entries are pooled together for iteration.

    Thread safety: NOT thread-safe for concurrent writes.  Reads are safe.
    """

    def __init__(self) -> None:
        self._entries: list[CorpusEntry] = []
        self._loaded_files: list[Path] = []

    # ------------------------------------------------------------------
    # Loading
    # ------------------------------------------------------------------

    def load_file(self, path: Path, skip_invalid: bool = True) -> int:
        """Load corpus entries from a JSONL file.

        Args:
            path: Path to a ``.jsonl`` file.
            skip_invalid: When True, log a warning for malformed lines and
                          continue.  When False, raise on the first error.

        Returns:
            Number of entries successfully loaded from this file.
        """
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"Corpus file not found: {path}")

        loaded = 0
        with open(path, encoding="utf-8") as f:
            for line_no, line in enumerate(f, start=1):
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                try:
                    d = json.loads(line)
                    # Validate required keys
                    missing = _REQUIRED_FIELDS - d.keys()
                    if missing:
                        raise ValueError(f"Missing required fields: {missing}")
                    entry = CorpusEntry.from_dict(d)
                    errors = entry.validate()
                    if errors:
                        raise ValueError(f"Validation errors: {errors}")
                    self._entries.append(entry)
                    loaded += 1
                except Exception as exc:
                    msg = f"{path}:{line_no}: {exc}"
                    if skip_invalid:
                        logger.warning("Skipping invalid corpus entry -- %s", msg)
                    else:
                        raise ValueError(msg) from exc

        self._loaded_files.append(path)
        logger.info("Loaded %d corpus entries from %s", loaded, path)
        return loaded

    def load_directory(self, directory: Path, pattern: str = "*.jsonl") -> int:
        """Load all matching JSONL files from a directory.

        Returns total number of entries loaded.
        """
        directory = Path(directory)
        total = 0
        for path in sorted(directory.glob(pattern)):
            total += self.load_file(path)
        return total

    # ------------------------------------------------------------------
    # Querying / iteration
    # ------------------------------------------------------------------

    def iter_entries(
        self,
        domain: str | None = None,
        verified_only: bool = False,
        source_prefix: str | None = None,
    ) -> Iterator[CorpusEntry]:
        """Yield entries, optionally filtered.

        Args:
            domain: Filter by domain name (exact match).
            verified_only: If True, yield only entries where ``verified=True``.
            source_prefix: If set, yield only entries whose ``source`` starts
                           with this string (e.g. ``"patent"``).
        """
        for entry in self._entries:
            if domain is not None and entry.domain != domain:
                continue
            if verified_only and not entry.verified:
                continue
            if source_prefix is not None and not entry.source.startswith(source_prefix):
                continue
            yield entry

    def count(
        self,
        domain: str | None = None,
        verified_only: bool = False,
    ) -> int:
        """Return the number of entries matching the given filters."""
        return sum(1 for _ in self.iter_entries(domain=domain, verified_only=verified_only))

    def list_domains(self) -> list[str]:
        """Return sorted list of all unique domains in the loaded corpus."""
        return sorted({e.domain for e in self._entries})

    def stats(self) -> dict:
        """Return a summary statistics dict.

        Keys:
            total           -- total entries loaded
            verified        -- entries marked as human-verified
            domains         -- dict of {domain: count}
            files_loaded    -- number of files loaded
        """
        total = len(self._entries)
        verified = sum(1 for e in self._entries if e.verified)
        domain_counts: dict[str, int] = {}
        for e in self._entries:
            domain_counts[e.domain] = domain_counts.get(e.domain, 0) + 1

        return {
            "total": total,
            "verified": verified,
            "domains": domain_counts,
            "files_loaded": len(self._loaded_files),
        }

    # ------------------------------------------------------------------
    # Adding entries
    # ------------------------------------------------------------------

    def add_entry(self, entry: CorpusEntry, validate: bool = True) -> None:
        """Add a single CorpusEntry to the in-memory corpus.

        Args:
            entry: The entry to add.
            validate: If True, raise ValueError on invalid entries.
        """
        if validate:
            errors = entry.validate()
            if errors:
                raise ValueError(f"Invalid corpus entry: {errors}")
        self._entries.append(entry)

    # ------------------------------------------------------------------
    # Saving
    # ------------------------------------------------------------------

    def save_file(self, path: Path, domain: str | None = None) -> int:
        """Write (append) entries to a JSONL file.

        Existing file content is preserved; new entries are appended.

        Args:
            path: Output path.
            domain: If given, only write entries for this domain.

        Returns:
            Number of entries written.
        """
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        written = 0
        with open(path, "a", encoding="utf-8") as f:
            for entry in self.iter_entries(domain=domain):
                f.write(json.dumps(entry.to_dict(), ensure_ascii=False) + "\n")
                written += 1
        logger.info("Appended %d corpus entries to %s", written, path)
        return written

    def export_jsonl(self, path: Path, domain: str | None = None) -> int:
        """Overwrite *path* with entries (optionally filtered by domain).

        Unlike ``save_file``, this truncates then writes fresh.
        """
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        written = 0
        with open(path, "w", encoding="utf-8") as f:
            for entry in self.iter_entries(domain=domain):
                f.write(json.dumps(entry.to_dict(), ensure_ascii=False) + "\n")
                written += 1
        logger.info("Exported %d corpus entries to %s", written, path)
        return written


# ---------------------------------------------------------------------------
# Module-level convenience: path to bundled sample corpus
# ---------------------------------------------------------------------------


def get_examples_dir() -> Path:
    """Return the path to the bundled example corpus directory."""
    return Path(__file__).parent / "examples"


def load_examples(domain: str | None = None) -> CorpusManager:
    """Load all bundled example JSONL files into a CorpusManager.

    Returns an empty manager if no example files are found.
    """
    mgr = CorpusManager()
    examples_dir = get_examples_dir()
    if examples_dir.exists():
        mgr.load_directory(examples_dir)
    return mgr
