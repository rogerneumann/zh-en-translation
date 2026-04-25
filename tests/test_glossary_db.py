"""Tests for the SQLite-backed GlossaryDB backend.

Covers:
- Schema initialisation and versioning
- load() -- read terms by domain
- add_term() -- insert and upsert
- delete_term()
- import_csv() -- CSV round-trip
- export_csv()
- import_toml() -- seed from TOML glossary files
- list_domains()
- count()
- Multiple domains support
- open_default_db() -- bundled DB helper
"""

from __future__ import annotations

import csv
import tempfile
from pathlib import Path

import pytest

from zh_en_translator.engines.glossary_db import (
    GlossaryDB,
    SCHEMA_VERSION,
    get_default_db_path,
    open_default_db,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def tmp_db(tmp_path: Path) -> GlossaryDB:
    """Fresh in-memory-equivalent DB in a temp directory."""
    db = GlossaryDB(tmp_path / "test_glossary.db")
    yield db
    db.close()


@pytest.fixture()
def populated_db(tmp_db: GlossaryDB) -> GlossaryDB:
    """DB pre-populated with a handful of manufacturing and medical terms."""
    manufacturing_terms = [
        ("镀锌", "galvanized / zinc-plated", "manufacturing", "surface treatment"),
        ("热处理", "heat treatment", "manufacturing", ""),
        ("零件", "component / part", "manufacturing", ""),
        ("焊接", "welding", "manufacturing", ""),
        ("公差", "tolerance", "manufacturing", "dimensions"),
    ]
    medical_terms = [
        ("手术", "surgery / operation", "medical", ""),
        ("诊断", "diagnosis", "medical", ""),
    ]
    for zh, en, domain, notes in manufacturing_terms + medical_terms:
        tmp_db.add_term(zh, en, domain, notes)
    return tmp_db


# ---------------------------------------------------------------------------
# Schema / versioning
# ---------------------------------------------------------------------------


class TestSchemaVersion:
    def test_schema_version_constant(self):
        assert SCHEMA_VERSION == 1

    def test_get_version_returns_schema_version(self, tmp_db: GlossaryDB):
        assert tmp_db.get_version() == SCHEMA_VERSION

    def test_fresh_db_has_correct_version(self, tmp_path: Path):
        with GlossaryDB(tmp_path / "fresh.db") as db:
            assert db.get_version() == SCHEMA_VERSION

    def test_reopening_db_preserves_version(self, tmp_path: Path):
        db_path = tmp_path / "persist.db"
        with GlossaryDB(db_path) as db:
            db.add_term("钢", "steel", "manufacturing")
        with GlossaryDB(db_path) as db:
            assert db.get_version() == SCHEMA_VERSION


# ---------------------------------------------------------------------------
# load()
# ---------------------------------------------------------------------------


class TestLoad:
    def test_load_empty_domain_returns_empty_dict(self, tmp_db: GlossaryDB):
        result = tmp_db.load("nonexistent")
        assert result == {}

    def test_load_returns_correct_terms(self, populated_db: GlossaryDB):
        terms = populated_db.load("manufacturing")
        assert len(terms) == 5
        assert terms["镀锌"] == "galvanized / zinc-plated"
        assert terms["零件"] == "component / part"

    def test_load_is_domain_isolated(self, populated_db: GlossaryDB):
        mfg = populated_db.load("manufacturing")
        med = populated_db.load("medical")
        assert "手术" not in mfg
        assert "镀锌" not in med

    def test_load_returns_dict_not_list(self, populated_db: GlossaryDB):
        result = populated_db.load("manufacturing")
        assert isinstance(result, dict)

    def test_load_all_terms_present(self, populated_db: GlossaryDB):
        terms = populated_db.load("manufacturing")
        for zh in ["镀锌", "热处理", "零件", "焊接", "公差"]:
            assert zh in terms


# ---------------------------------------------------------------------------
# add_term()
# ---------------------------------------------------------------------------


class TestAddTerm:
    def test_add_term_inserts_new_term(self, tmp_db: GlossaryDB):
        row_id = tmp_db.add_term("钢", "steel", "manufacturing")
        assert isinstance(row_id, int)
        assert row_id > 0
        assert tmp_db.load("manufacturing")["钢"] == "steel"

    def test_add_term_returns_row_id(self, tmp_db: GlossaryDB):
        id1 = tmp_db.add_term("铝", "aluminum", "manufacturing")
        id2 = tmp_db.add_term("铜", "copper", "manufacturing")
        assert id1 != id2
        assert id1 > 0 and id2 > 0

    def test_add_term_upsert_updates_translation(self, tmp_db: GlossaryDB):
        tmp_db.add_term("钢", "steel", "manufacturing")
        tmp_db.add_term("钢", "STEEL_UPDATED", "manufacturing")
        assert tmp_db.load("manufacturing")["钢"] == "STEEL_UPDATED"

    def test_add_term_upsert_preserves_created_at(self, tmp_db: GlossaryDB):
        tmp_db.add_term("钢", "steel", "manufacturing")
        records_before = tmp_db.load_with_notes("manufacturing")
        created_at_before = records_before[0]["created_at"]

        tmp_db.add_term("钢", "steel v2", "manufacturing")
        records_after = tmp_db.load_with_notes("manufacturing")
        created_at_after = records_after[0]["created_at"]

        assert created_at_before == created_at_after

    def test_add_term_with_notes(self, tmp_db: GlossaryDB):
        tmp_db.add_term("镀锌", "galvanized", "manufacturing", notes="hot-dip or electro")
        records = tmp_db.load_with_notes("manufacturing")
        assert records[0]["notes"] == "hot-dip or electro"

    def test_add_term_same_chinese_different_domain(self, tmp_db: GlossaryDB):
        tmp_db.add_term("氧化", "anodizing", "manufacturing")
        tmp_db.add_term("氧化", "oxidation reaction", "chemistry")
        assert tmp_db.load("manufacturing")["氧化"] == "anodizing"
        assert tmp_db.load("chemistry")["氧化"] == "oxidation reaction"

    def test_add_term_count_increases(self, tmp_db: GlossaryDB):
        assert tmp_db.count("manufacturing") == 0
        tmp_db.add_term("钢", "steel", "manufacturing")
        assert tmp_db.count("manufacturing") == 1
        tmp_db.add_term("铝", "aluminum", "manufacturing")
        assert tmp_db.count("manufacturing") == 2


# ---------------------------------------------------------------------------
# delete_term()
# ---------------------------------------------------------------------------


class TestDeleteTerm:
    def test_delete_existing_term_returns_true(self, populated_db: GlossaryDB):
        removed = populated_db.delete_term("焊接", "manufacturing")
        assert removed is True
        assert "焊接" not in populated_db.load("manufacturing")

    def test_delete_nonexistent_term_returns_false(self, tmp_db: GlossaryDB):
        removed = tmp_db.delete_term("nonexistent", "manufacturing")
        assert removed is False

    def test_delete_from_wrong_domain_returns_false(self, populated_db: GlossaryDB):
        removed = populated_db.delete_term("镀锌", "medical")
        assert removed is False
        assert "镀锌" in populated_db.load("manufacturing")

    def test_delete_reduces_count(self, populated_db: GlossaryDB):
        before = populated_db.count("manufacturing")
        populated_db.delete_term("零件", "manufacturing")
        assert populated_db.count("manufacturing") == before - 1


# ---------------------------------------------------------------------------
# count()
# ---------------------------------------------------------------------------


class TestCount:
    def test_count_all_terms(self, populated_db: GlossaryDB):
        total = populated_db.count()
        assert total == 7  # 5 manufacturing + 2 medical

    def test_count_by_domain(self, populated_db: GlossaryDB):
        assert populated_db.count("manufacturing") == 5
        assert populated_db.count("medical") == 2

    def test_count_empty_domain_is_zero(self, tmp_db: GlossaryDB):
        assert tmp_db.count("manufacturing") == 0
        assert tmp_db.count() == 0


# ---------------------------------------------------------------------------
# list_domains()
# ---------------------------------------------------------------------------


class TestListDomains:
    def test_list_domains_empty_db(self, tmp_db: GlossaryDB):
        assert tmp_db.list_domains() == []

    def test_list_domains_single_domain(self, tmp_db: GlossaryDB):
        tmp_db.add_term("钢", "steel", "manufacturing")
        assert tmp_db.list_domains() == ["manufacturing"]

    def test_list_domains_multiple_domains(self, populated_db: GlossaryDB):
        domains = populated_db.list_domains()
        assert "manufacturing" in domains
        assert "medical" in domains

    def test_list_domains_is_sorted(self, tmp_db: GlossaryDB):
        tmp_db.add_term("b", "b", "zebra")
        tmp_db.add_term("a", "a", "alpha")
        tmp_db.add_term("c", "c", "mango")
        assert tmp_db.list_domains() == ["alpha", "mango", "zebra"]

    def test_list_domains_no_duplicates(self, tmp_db: GlossaryDB):
        tmp_db.add_term("钢", "steel", "manufacturing")
        tmp_db.add_term("铝", "aluminum", "manufacturing")
        assert tmp_db.list_domains().count("manufacturing") == 1


# ---------------------------------------------------------------------------
# import_csv()
# ---------------------------------------------------------------------------


class TestImportCSV:
    def test_import_csv_basic(self, tmp_db: GlossaryDB, tmp_path: Path):
        csv_path = tmp_path / "terms.csv"
        csv_path.write_text("zh,en\n镀锌,galvanized\n热处理,heat treatment\n", encoding="utf-8")

        count = tmp_db.import_csv(csv_path, "manufacturing")
        assert count == 2
        terms = tmp_db.load("manufacturing")
        assert terms["镀锌"] == "galvanized"
        assert terms["热处理"] == "heat treatment"

    def test_import_csv_with_notes_column(self, tmp_db: GlossaryDB, tmp_path: Path):
        csv_path = tmp_path / "terms_notes.csv"
        csv_path.write_text(
            "zh,en,notes\n镀锌,galvanized,hot-dip process\n", encoding="utf-8"
        )
        tmp_db.import_csv(csv_path, "manufacturing")
        records = tmp_db.load_with_notes("manufacturing")
        assert records[0]["notes"] == "hot-dip process"

    def test_import_csv_skips_empty_rows(self, tmp_db: GlossaryDB, tmp_path: Path):
        csv_path = tmp_path / "sparse.csv"
        csv_path.write_text("zh,en\n镀锌,galvanized\n,,\n热处理,heat treatment\n", encoding="utf-8")
        count = tmp_db.import_csv(csv_path, "manufacturing")
        assert count == 2

    def test_import_csv_returns_count(self, tmp_db: GlossaryDB, tmp_path: Path):
        csv_path = tmp_path / "single.csv"
        csv_path.write_text("zh,en\n钢,steel\n", encoding="utf-8")
        assert tmp_db.import_csv(csv_path, "manufacturing") == 1

    def test_import_csv_missing_file_raises(self, tmp_db: GlossaryDB, tmp_path: Path):
        with pytest.raises(Exception):
            tmp_db.import_csv(tmp_path / "nonexistent.csv", "manufacturing")

    def test_import_csv_updates_existing_terms(self, tmp_db: GlossaryDB, tmp_path: Path):
        tmp_db.add_term("钢", "steel", "manufacturing")
        csv_path = tmp_path / "update.csv"
        csv_path.write_text("zh,en\n钢,STEEL_NEW\n", encoding="utf-8")
        tmp_db.import_csv(csv_path, "manufacturing")
        assert tmp_db.load("manufacturing")["钢"] == "STEEL_NEW"


# ---------------------------------------------------------------------------
# export_csv()
# ---------------------------------------------------------------------------


class TestExportCSV:
    def test_export_csv_creates_file(self, populated_db: GlossaryDB, tmp_path: Path):
        out = tmp_path / "export.csv"
        populated_db.export_csv("manufacturing", out)
        assert out.exists()

    def test_export_csv_returns_row_count(self, populated_db: GlossaryDB, tmp_path: Path):
        out = tmp_path / "export.csv"
        count = populated_db.export_csv("manufacturing", out)
        assert count == 5

    def test_export_csv_content(self, tmp_db: GlossaryDB, tmp_path: Path):
        tmp_db.add_term("钢", "steel", "manufacturing", notes="common material")
        out = tmp_path / "export.csv"
        tmp_db.export_csv("manufacturing", out)

        with open(out, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        assert len(rows) == 1
        assert rows[0]["zh"] == "钢"
        assert rows[0]["en"] == "steel"
        assert rows[0]["notes"] == "common material"

    def test_export_csv_has_headers(self, populated_db: GlossaryDB, tmp_path: Path):
        out = tmp_path / "export.csv"
        populated_db.export_csv("manufacturing", out)
        first_line = out.read_text(encoding="utf-8").splitlines()[0]
        assert "zh" in first_line
        assert "en" in first_line

    def test_export_csv_round_trip(self, tmp_db: GlossaryDB, tmp_path: Path):
        """Export then re-import should reproduce the same terms."""
        original_terms = {"镀锌": "galvanized", "热处理": "heat treatment", "零件": "part"}
        for zh, en in original_terms.items():
            tmp_db.add_term(zh, en, "manufacturing")

        out = tmp_path / "round_trip.csv"
        tmp_db.export_csv("manufacturing", out)

        db2 = GlossaryDB(tmp_path / "db2.db")
        db2.import_csv(out, "manufacturing")
        loaded = db2.load("manufacturing")
        db2.close()

        for zh, en in original_terms.items():
            assert loaded[zh] == en

    def test_export_csv_creates_parent_dirs(self, tmp_db: GlossaryDB, tmp_path: Path):
        tmp_db.add_term("钢", "steel", "manufacturing")
        out = tmp_path / "nested" / "deep" / "export.csv"
        tmp_db.export_csv("manufacturing", out)
        assert out.exists()


# ---------------------------------------------------------------------------
# import_toml()
# ---------------------------------------------------------------------------


class TestImportTOML:
    def test_import_toml_manufacturing_glossary(self, tmp_db: GlossaryDB):
        """Should import all terms from the bundled manufacturing TOML."""
        from zh_en_translator import __file__ as pkg_file
        toml_path = Path(pkg_file).parent / "resources" / "glossary_manufacturing.toml"
        if not toml_path.exists():
            pytest.skip("Manufacturing TOML not found")

        count = tmp_db.import_toml(toml_path, "manufacturing")
        assert count >= 149, f"Expected 149+ terms, got {count}"
        terms = tmp_db.load("manufacturing")
        assert "镀锌" in terms
        assert "热处理" in terms

    def test_import_toml_missing_file_raises(self, tmp_db: GlossaryDB, tmp_path: Path):
        with pytest.raises(Exception):
            tmp_db.import_toml(tmp_path / "nonexistent.toml", "manufacturing")

    def test_import_toml_custom_file(self, tmp_db: GlossaryDB, tmp_path: Path):
        toml_content = '[terms]\n"钢" = "steel"\n"铝" = "aluminum"\n'
        toml_path = tmp_path / "custom.toml"
        toml_path.write_text(toml_content, encoding="utf-8")
        count = tmp_db.import_toml(toml_path, "test")
        assert count == 2
        assert tmp_db.load("test")["钢"] == "steel"


# ---------------------------------------------------------------------------
# Multiple domains
# ---------------------------------------------------------------------------


class TestMultipleDomains:
    def test_two_domains_coexist(self, tmp_db: GlossaryDB):
        tmp_db.add_term("零件", "component", "manufacturing")
        tmp_db.add_term("诊断", "diagnosis", "medical")
        assert tmp_db.count("manufacturing") == 1
        assert tmp_db.count("medical") == 1
        assert tmp_db.count() == 2

    def test_domain_isolation_on_load(self, tmp_db: GlossaryDB):
        tmp_db.add_term("氧化", "anodizing", "manufacturing")
        tmp_db.add_term("氧化", "oxidation", "chemistry")
        mfg = tmp_db.load("manufacturing")
        chem = tmp_db.load("chemistry")
        assert mfg["氧化"] == "anodizing"
        assert chem["氧化"] == "oxidation"

    def test_delete_from_one_domain_leaves_other_intact(self, tmp_db: GlossaryDB):
        tmp_db.add_term("氧化", "anodizing", "manufacturing")
        tmp_db.add_term("氧化", "oxidation", "chemistry")
        tmp_db.delete_term("氧化", "manufacturing")
        assert "氧化" not in tmp_db.load("manufacturing")
        assert "氧化" in tmp_db.load("chemistry")

    def test_three_domains_list(self, tmp_db: GlossaryDB):
        for domain in ["manufacturing", "medical", "legal"]:
            tmp_db.add_term("test", "test", domain)
        domains = tmp_db.list_domains()
        assert set(domains) == {"manufacturing", "medical", "legal"}


# ---------------------------------------------------------------------------
# iter_terms()
# ---------------------------------------------------------------------------


class TestIterTerms:
    def test_iter_terms_yields_tuples(self, populated_db: GlossaryDB):
        items = list(populated_db.iter_terms("manufacturing"))
        assert len(items) == 5
        for item in items:
            assert len(item) == 3  # (chinese, english, notes)

    def test_iter_terms_empty_domain(self, tmp_db: GlossaryDB):
        assert list(tmp_db.iter_terms("nonexistent")) == []

    def test_iter_terms_ordered_by_chinese(self, tmp_db: GlossaryDB):
        tmp_db.add_term("钢", "steel", "manufacturing")
        tmp_db.add_term("铝", "aluminum", "manufacturing")
        tmp_db.add_term("铜", "copper", "manufacturing")
        items = list(tmp_db.iter_terms("manufacturing"))
        chinese_terms = [item[0] for item in items]
        assert chinese_terms == sorted(chinese_terms)


# ---------------------------------------------------------------------------
# open_default_db() and bundled DB
# ---------------------------------------------------------------------------


class TestDefaultDB:
    def test_default_db_path_is_in_resources(self):
        path = get_default_db_path()
        assert path.name == "glossary.db"
        assert "resources" in str(path)

    def test_open_default_db_returns_glossary_db(self):
        with open_default_db() as db:
            assert isinstance(db, GlossaryDB)

    def test_default_db_has_manufacturing_domain(self):
        with open_default_db() as db:
            domains = db.list_domains()
        assert "manufacturing" in domains

    def test_default_db_has_manufacturing_terms(self):
        with open_default_db() as db:
            terms = db.load("manufacturing")
        assert len(terms) >= 149, f"Expected 149+ terms, got {len(terms)}"
        assert "镀锌" in terms
        assert terms["镀锌"] == "galvanized / zinc-plated"

    def test_default_db_schema_version(self):
        with open_default_db() as db:
            assert db.get_version() == SCHEMA_VERSION

    def test_default_db_has_expected_key_terms(self):
        """Spot-check key manufacturing terms are in the bundled DB."""
        with open_default_db() as db:
            terms = db.load("manufacturing")

        key_terms = [
            "镀锌", "表面处理", "热处理", "零件", "焊接",
            "公差", "精度", "钢", "铝", "铜",
            "齿轮", "轴承", "螺栓", "螺母",
        ]
        for term in key_terms:
            assert term in terms, f"Missing key term in bundled DB: {term}"

    def test_default_db_is_readable_as_context_manager(self):
        with open_default_db() as db:
            version = db.get_version()
        assert version == SCHEMA_VERSION


# ---------------------------------------------------------------------------
# Context manager / connection management
# ---------------------------------------------------------------------------


class TestContextManager:
    def test_context_manager_closes_connection(self, tmp_path: Path):
        db_path = tmp_path / "cm.db"
        db = GlossaryDB(db_path)
        with db:
            db.add_term("钢", "steel", "manufacturing")
        assert db._conn is None

    def test_db_usable_after_explicit_close_and_reopen(self, tmp_path: Path):
        db_path = tmp_path / "reopen.db"
        with GlossaryDB(db_path) as db:
            db.add_term("钢", "steel", "manufacturing")

        with GlossaryDB(db_path) as db:
            terms = db.load("manufacturing")
        assert terms["钢"] == "steel"

    def test_multiple_opens_same_file(self, tmp_path: Path):
        db_path = tmp_path / "multi.db"
        with GlossaryDB(db_path) as db:
            db.add_term("钢", "steel", "manufacturing")
        with GlossaryDB(db_path) as db:
            db.add_term("铝", "aluminum", "manufacturing")
        with GlossaryDB(db_path) as db:
            assert db.count("manufacturing") == 2


# ---------------------------------------------------------------------------
# Persistence / data integrity
# ---------------------------------------------------------------------------


class TestPersistence:
    def test_data_persists_across_instances(self, tmp_path: Path):
        db_path = tmp_path / "persist.db"
        with GlossaryDB(db_path) as db:
            db.add_term("钢", "steel", "manufacturing")
            db.add_term("铝", "aluminum", "manufacturing")

        with GlossaryDB(db_path) as db:
            terms = db.load("manufacturing")
        assert len(terms) == 2
        assert terms["钢"] == "steel"

    def test_large_import_round_trip(self, tmp_db: GlossaryDB):
        """Simulate importing a realistic-sized glossary."""
        terms = {f"term_{i}": f"translation_{i}" for i in range(200)}
        for zh, en in terms.items():
            tmp_db.add_term(zh, en, "manufacturing")

        loaded = tmp_db.load("manufacturing")
        assert len(loaded) == 200
        for zh, en in terms.items():
            assert loaded[zh] == en
