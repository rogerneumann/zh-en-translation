"""CC-CEDICT loader with SQLite indexing and pinyin tone-mark conversion."""

import sqlite3
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Entry:
    """Dictionary entry with traditional, simplified, pinyin (tone-marked), and glosses."""

    traditional: str
    simplified: str
    pinyin: str  # Already tone-marked, e.g., "chuán tǒng"
    glosses: list[str]  # e.g., ["tradition", "traditional", "convention"]


# Pinyin tone-mark mappings. Index 0 = no tone, 1-4 = tone 1-4, 5 = neutral tone (already handled)
TONE_MARKS = {
    "a": ["a", "ā", "á", "ǎ", "à"],
    "e": ["e", "ē", "é", "ě", "è"],
    "i": ["i", "ī", "í", "ǐ", "ì"],
    "o": ["o", "ō", "ó", "ǒ", "ò"],
    "u": ["u", "ū", "ú", "ǔ", "ù"],
    "ü": ["ü", "ǖ", "ǘ", "ǚ", "ǜ"],
}


def _convert_pinyin_tone_marks(pinyin_str: str) -> str:
    """
    Convert numeric pinyin (e.g., "chuan2 tong3") to tone marks (e.g., "chuán tǒng").

    Handles tones 1-4 and neutral tone (5 or no number).
    Tone marks are placed on: a > e > o > u (a/e always get it, then o, then u).
    """
    if not pinyin_str:
        return pinyin_str

    syllables = pinyin_str.split()
    converted = []

    for syllable in syllables:
        if not syllable:
            continue

        # Extract tone number (last character if digit, else 5 for neutral)
        tone_num = 0
        if syllable and syllable[-1].isdigit():
            tone_num = int(syllable[-1])
            syllable_base = syllable[:-1]
        else:
            tone_num = 5  # Neutral tone (no mark)
            syllable_base = syllable

        # If neutral tone or invalid, just append as-is
        if tone_num == 5 or tone_num > 4:
            converted.append(syllable_base)
            continue

        # Apply tone marks: find the vowel to mark
        if not syllable_base:
            converted.append(syllable_base)
            continue

        # Pinyin tone-mark placement rules:
        #   1. If 'a' present, mark 'a'.
        #   2. Else if 'e' present, mark 'e'.
        #   3. Else if 'ou' present, mark 'o'.
        #   4. Else mark the LAST vowel (covers i, o, u, ü, and cases like "iu"->u, "ui"->i).
        mark_idx = -1
        for i, ch in enumerate(syllable_base):
            if ch == "a":
                mark_idx = i
                break
        if mark_idx == -1:
            for i, ch in enumerate(syllable_base):
                if ch == "e":
                    mark_idx = i
                    break
        if mark_idx == -1:
            ou = syllable_base.find("ou")
            if ou != -1:
                mark_idx = ou
        if mark_idx == -1:
            # Fallback: last vowel in the syllable
            for i in range(len(syllable_base) - 1, -1, -1):
                if syllable_base[i] in "aeiouü":
                    mark_idx = i
                    break

        if mark_idx == -1:
            converted.append(syllable_base)
            continue

        result = list(syllable_base)
        target = result[mark_idx]
        if target in TONE_MARKS:
            result[mark_idx] = TONE_MARKS[target][tone_num]
        converted.append("".join(result))

    return " ".join(converted)


class Dictionary:
    """CC-CEDICT dictionary with SQLite indexing."""

    def __init__(self, db_path: Path):
        """
        Initialize dictionary from SQLite database.

        Args:
            db_path: Path to the SQLite database.
        """
        self.db_path = Path(db_path)
        self.conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row

    @classmethod
    def build_from_cedict(cls, cedict_txt: Path, db_path: Path) -> "Dictionary":
        """
        Build a SQLite dictionary from CC-CEDICT text file.

        Args:
            cedict_txt: Path to CC-CEDICT text file.
            db_path: Output path for SQLite database.

        Returns:
            Dictionary instance.
        """
        db_path = Path(db_path)
        db_path.parent.mkdir(parents=True, exist_ok=True)

        # Remove existing DB if present
        if db_path.exists():
            db_path.unlink()

        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()

        # Create schema
        cursor.execute(
            """
            CREATE TABLE entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                traditional TEXT NOT NULL,
                simplified TEXT NOT NULL,
                pinyin TEXT NOT NULL,
                glosses TEXT NOT NULL
            )
        """
        )
        cursor.execute("CREATE INDEX idx_simplified ON entries(simplified)")
        cursor.execute("CREATE INDEX idx_traditional ON entries(traditional)")

        # Parse and insert entries
        with open(cedict_txt, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                # Skip empty lines and comments
                if not line or line.startswith("#"):
                    continue

                # Parse: traditional simplified [pinyin] /gloss1/gloss2/.../
                parts = line.split(" ")
                if len(parts) < 3:
                    continue

                traditional = parts[0]
                simplified = parts[1]

                # Extract pinyin from brackets
                pinyin_start = line.find("[")
                pinyin_end = line.find("]")
                if pinyin_start < 0 or pinyin_end < 0:
                    continue
                pinyin_numeric = line[pinyin_start + 1 : pinyin_end]

                # Convert tone numbers to marks
                pinyin_marked = _convert_pinyin_tone_marks(pinyin_numeric)

                # Extract glosses
                glosses_start = pinyin_end + 2  # Skip "] /"
                if glosses_start >= len(line):
                    glosses_text = ""
                else:
                    glosses_text = line[glosses_start:]
                    if glosses_text.endswith("/"):
                        glosses_text = glosses_text[:-1]

                # Store as pipe-separated
                cursor.execute(
                    """
                    INSERT INTO entries (traditional, simplified, pinyin, glosses)
                    VALUES (?, ?, ?, ?)
                """,
                    (traditional, simplified, pinyin_marked, glosses_text),
                )

        conn.commit()
        conn.close()

        return cls(db_path)

    def lookup(self, word: str) -> list[Entry]:
        """
        Lookup a word in the dictionary (simplified or traditional).

        Args:
            word: The word to lookup.

        Returns:
            List of matching entries (may be empty if not found).
        """
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT traditional, simplified, pinyin, glosses
            FROM entries
            WHERE simplified = ? OR traditional = ?
        """,
            (word, word),
        )
        rows = cursor.fetchall()

        entries = []
        seen = set()
        for row in rows:
            trad, simp, pinyin, glosses_text = row
            # Avoid duplicates
            key = (trad, simp, pinyin)
            if key in seen:
                continue
            seen.add(key)

            # Parse glosses from pipe-separated string
            glosses = [g.strip() for g in glosses_text.split("/") if g.strip()]
            entries.append(Entry(trad, simp, pinyin, glosses))

        return entries

    def close(self) -> None:
        """Close the database connection."""
        self.conn.close()
