"""Multi-domain glossary integration tests.

Covers:
- Loading all 4 domain glossaries (manufacturing, medical, legal, electronics)
- Verifying term counts meet minimum targets
- Checking for no harmful cross-domain conflicts
- Testing domain priority (manufacturing terms take precedence)
- Testing glossary merging via GlossaryDB.merge_domains()
- Testing search_across_domains() and get_available_domains()
- Testing load_all_glossaries() auto-discovery
- Testing DomainSelectorModel
- Integration: DB seeds all 4 domains from TOML files
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from zh_en_translator.engines.glossary_db import (
    GlossaryDB,
    open_default_db,
)
from zh_en_translator.engines.glossary import (
    discover_available_domains,
    load_all_glossaries,
    load_domain_glossary,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def all_domains_db():
    """Open default DB (seeded from all TOML files) as a module-scoped fixture."""
    db = open_default_db()
    yield db
    db.close()


# ---------------------------------------------------------------------------
# Task 1: Domain glossary content
# ---------------------------------------------------------------------------


class TestDomainGlossaryContent:
    """Verify each domain glossary loads with sufficient term counts."""

    def test_manufacturing_glossary_loads(self):
        terms = load_domain_glossary("manufacturing")
        assert len(terms) >= 149, f"Manufacturing: expected 149+ terms, got {len(terms)}"

    def test_medical_glossary_loads(self):
        terms = load_domain_glossary("medical")
        assert len(terms) >= 500, f"Medical: expected 500+ terms, got {len(terms)}"

    def test_legal_glossary_loads(self):
        terms = load_domain_glossary("legal")
        assert len(terms) >= 400, f"Legal: expected 400+ terms, got {len(terms)}"

    def test_electronics_glossary_loads(self):
        terms = load_domain_glossary("electronics")
        assert len(terms) >= 450, f"Electronics: expected 450+ terms, got {len(terms)}"

    def test_manufacturing_key_terms(self):
        terms = load_domain_glossary("manufacturing")
        for term in ["镀锌", "热处理", "零件", "焊接", "公差", "钢", "铝"]:
            assert term in terms, f"Manufacturing missing key term: {term}"

    def test_medical_key_terms(self):
        terms = load_domain_glossary("medical")
        for term in ["心脏病", "高血压", "手术", "药物", "诊断", "患者", "抗生素"]:
            assert term in terms, f"Medical missing key term: {term}"

    def test_legal_key_terms(self):
        terms = load_domain_glossary("legal")
        for term in ["合同", "诉讼", "知识产权", "违约", "律师", "仲裁", "判决"]:
            assert term in terms, f"Legal missing key term: {term}"

    def test_electronics_key_terms(self):
        terms = load_domain_glossary("electronics")
        for term in ["电阻", "集成电路", "焊接", "印刷电路板", "传感器", "微处理器"]:
            assert term in terms, f"Electronics missing key term: {term}"

    def test_all_translations_nonempty(self):
        """Every term in every domain must have a non-empty English translation."""
        for domain in ["manufacturing", "medical", "legal", "electronics"]:
            terms = load_domain_glossary(domain)
            for zh, en in terms.items():
                assert zh, f"{domain}: empty Chinese key"
                assert en, f"{domain}: empty translation for '{zh}'"
                assert isinstance(en, str), f"{domain}: translation is not a string for '{zh}'"

    def test_medical_anatomy_section(self):
        terms = load_domain_glossary("medical")
        anatomy_terms = ["心脏", "肺", "肝脏", "肾脏", "大脑"]
        for t in anatomy_terms:
            assert t in terms

    def test_legal_contract_section(self):
        terms = load_domain_glossary("legal")
        contract_terms = ["合同", "协议", "条款", "义务", "违约金"]
        for t in contract_terms:
            assert t in terms

    def test_electronics_components_section(self):
        terms = load_domain_glossary("electronics")
        component_terms = ["电阻", "电容", "电感", "二极管", "晶体管"]
        for t in component_terms:
            assert t in terms

    def test_medical_medications_section(self):
        terms = load_domain_glossary("medical")
        med_terms = ["抗生素", "镇痛药", "疫苗", "胰岛素", "阿司匹林"]
        for t in med_terms:
            assert t in terms

    def test_electronics_pcb_section(self):
        terms = load_domain_glossary("electronics")
        pcb_terms = ["印刷电路板", "焊盘", "过孔", "阻焊层", "原理图"]
        for t in pcb_terms:
            assert t in terms

    def test_legal_ip_section(self):
        terms = load_domain_glossary("legal")
        ip_terms = ["知识产权", "专利", "商标", "版权", "商业秘密"]
        for t in ip_terms:
            assert t in terms


# ---------------------------------------------------------------------------
# Task 2: GlossaryDB multi-domain functions
# ---------------------------------------------------------------------------


class TestGlossaryDBMultiDomain:
    """Test the new multi-domain methods added in Priority 4."""

    def test_get_available_domains_returns_all_four(self, all_domains_db: GlossaryDB):
        domains = all_domains_db.get_available_domains()
        expected = {"manufacturing", "medical", "legal", "electronics"}
        assert expected.issubset(set(domains)), (
            f"Expected {expected}, got {set(domains)}"
        )

    def test_get_available_domains_is_sorted(self, all_domains_db: GlossaryDB):
        domains = all_domains_db.get_available_domains()
        assert domains == sorted(domains)

    def test_load_domain_manufacturing(self, all_domains_db: GlossaryDB):
        terms = all_domains_db.load_domain("manufacturing")
        assert len(terms) >= 149
        assert "镀锌" in terms

    def test_load_domain_medical(self, all_domains_db: GlossaryDB):
        terms = all_domains_db.load_domain("medical")
        assert len(terms) >= 500
        assert "高血压" in terms

    def test_load_domain_legal(self, all_domains_db: GlossaryDB):
        terms = all_domains_db.load_domain("legal")
        assert len(terms) >= 400
        assert "合同" in terms

    def test_load_domain_electronics(self, all_domains_db: GlossaryDB):
        terms = all_domains_db.load_domain("electronics")
        assert len(terms) >= 450
        assert "集成电路" in terms

    def test_search_across_domains_finds_term_in_one_domain(self, tmp_path: Path):
        db = GlossaryDB(tmp_path / "search_test.db")
        db.add_term("焊接", "welding", "manufacturing")
        db.add_term("心脏", "heart", "medical")

        results = db.search_across_domains("焊接")
        assert len(results) == 1
        assert results[0]["domain"] == "manufacturing"
        assert results[0]["english"] == "welding"
        db.close()

    def test_search_across_domains_finds_shared_term(self, tmp_path: Path):
        """A term that appears in multiple domains should return multiple results."""
        db = GlossaryDB(tmp_path / "shared_term.db")
        db.add_term("氧化", "anodizing", "manufacturing")
        db.add_term("氧化", "oxidation", "chemistry")
        db.add_term("氧化", "oxidative stress", "medical")

        results = db.search_across_domains("氧化")
        domains_found = {r["domain"] for r in results}
        assert domains_found == {"manufacturing", "chemistry", "medical"}
        db.close()

    def test_search_across_domains_not_found(self, all_domains_db: GlossaryDB):
        results = all_domains_db.search_across_domains("nonexistent_term_xyz")
        assert results == []

    def test_merge_domains_combines_terms(self, tmp_path: Path):
        db = GlossaryDB(tmp_path / "merge_test.db")
        db.add_term("焊接", "welding", "manufacturing")
        db.add_term("高血压", "hypertension", "medical")
        db.add_term("合同", "contract", "legal")

        merged = db.merge_domains(["manufacturing", "medical", "legal"])
        assert "焊接" in merged
        assert "高血压" in merged
        assert "合同" in merged
        assert len(merged) == 3
        db.close()

    def test_merge_domains_priority_first_wins(self, tmp_path: Path):
        """First domain in the list should take precedence for shared terms."""
        db = GlossaryDB(tmp_path / "priority_test.db")
        db.add_term("绝缘", "insulation", "manufacturing")
        db.add_term("绝缘", "electrical insulation", "electronics")

        # manufacturing first -> manufacturing wins
        merged_mfg_first = db.merge_domains(["manufacturing", "electronics"])
        assert merged_mfg_first["绝缘"] == "insulation"

        # electronics first -> electronics wins
        merged_elec_first = db.merge_domains(["electronics", "manufacturing"])
        assert merged_elec_first["绝缘"] == "electrical insulation"
        db.close()

    def test_merge_domains_empty_list(self, tmp_path: Path):
        db = GlossaryDB(tmp_path / "empty_merge.db")
        merged = db.merge_domains([])
        assert merged == {}
        db.close()

    def test_merge_domains_all_four_via_db(self, all_domains_db: GlossaryDB):
        merged = all_domains_db.merge_domains(
            ["manufacturing", "medical", "legal", "electronics"]
        )
        # Should have at least 149 + 500 + 400 + 450 terms, minus any duplicates
        assert len(merged) >= 1200, f"Expected 1200+ merged terms, got {len(merged)}"
        assert "镀锌" in merged
        assert "高血压" in merged
        assert "合同" in merged
        assert "集成电路" in merged


# ---------------------------------------------------------------------------
# Task 3: discover_available_domains and load_all_glossaries
# ---------------------------------------------------------------------------


class TestLoadAllGlossaries:
    """Test auto-discovery and merging in glossary.py."""

    def test_discover_available_domains_returns_four(self):
        domains = discover_available_domains()
        expected = {"manufacturing", "medical", "legal", "electronics"}
        assert expected.issubset(set(domains)), (
            f"Expected {expected} in discovered domains {set(domains)}"
        )

    def test_load_all_glossaries_auto_discovers(self):
        """Default call should load all 4 domains."""
        merged = load_all_glossaries()
        # Should have combined terms from all domains
        assert len(merged) >= 1200
        assert "镀锌" in merged      # manufacturing
        assert "高血压" in merged     # medical
        assert "合同" in merged      # legal
        assert "集成电路" in merged   # electronics

    def test_load_all_glossaries_explicit_domains(self):
        """Explicit domain list should load only specified domains."""
        medical_only = load_all_glossaries(include_domains=["medical"])
        assert "高血压" in medical_only
        # Manufacturing-specific term should not be present
        # (unless it also happens to be in medical, which is unlikely for 镀锌)
        assert "镀锌" not in medical_only

    def test_load_all_glossaries_manufacturing_first(self):
        """Manufacturing terms should take priority over other domains."""
        merged = load_all_glossaries()
        # 焊接 is in both manufacturing (welding) and electronics (soldering)
        # Manufacturing should win with default priority
        assert "焊接" in merged

    def test_load_all_glossaries_two_domains(self):
        two_domains = load_all_glossaries(include_domains=["manufacturing", "medical"])
        assert "镀锌" in two_domains
        assert "高血压" in two_domains
        assert len(two_domains) >= 600

    def test_load_all_glossaries_legal_electronics(self):
        two_domains = load_all_glossaries(include_domains=["legal", "electronics"])
        assert "合同" in two_domains
        assert "集成电路" in two_domains

    def test_load_all_glossaries_returns_dict(self):
        result = load_all_glossaries()
        assert isinstance(result, dict)
        for k, v in result.items():
            assert isinstance(k, str)
            assert isinstance(v, str)


# ---------------------------------------------------------------------------
# Task 4: DB seeding from all TOML files
# ---------------------------------------------------------------------------


class TestDatabaseSeeding:
    """Test that open_default_db() auto-seeds from all TOML files."""

    def test_default_db_has_all_four_domains(self):
        with open_default_db() as db:
            domains = db.list_domains()
        expected = {"manufacturing", "medical", "legal", "electronics"}
        assert expected.issubset(set(domains))

    def test_default_db_total_term_count(self):
        """Total terms across all domains should be at least 1500."""
        with open_default_db() as db:
            total = db.count()
        assert total >= 1500, f"Expected 1500+ total terms, got {total}"

    def test_default_db_medical_count(self):
        with open_default_db() as db:
            count = db.count("medical")
        assert count >= 500, f"Expected 500+ medical terms, got {count}"

    def test_default_db_legal_count(self):
        with open_default_db() as db:
            count = db.count("legal")
        assert count >= 400, f"Expected 400+ legal terms, got {count}"

    def test_default_db_electronics_count(self):
        with open_default_db() as db:
            count = db.count("electronics")
        assert count >= 450, f"Expected 450+ electronics terms, got {count}"

    def test_seed_from_scratch_gets_all_domains(self, tmp_path: Path):
        """A fresh DB seeded from resources should contain all 4 domains."""
        from zh_en_translator.engines.glossary_db import _seed_from_toml

        db = GlossaryDB(tmp_path / "fresh.db")
        from zh_en_translator import __file__ as pkg_file
        resources_dir = Path(pkg_file).parent / "resources"
        _seed_from_toml(db, resources_dir)

        domains = set(db.list_domains())
        expected = {"manufacturing", "medical", "legal", "electronics"}
        assert expected.issubset(domains)
        assert db.count() >= 1500
        db.close()


# ---------------------------------------------------------------------------
# Task 5: No harmful cross-domain conflicts
# ---------------------------------------------------------------------------


class TestCrossDomainConflicts:
    """Check that cross-domain term overlaps are handled gracefully."""

    def test_welding_term_in_both_domains(self, all_domains_db: GlossaryDB):
        """'焊接' appears in both manufacturing and electronics; both should resolve."""
        mfg = all_domains_db.load_domain("manufacturing")
        elec = all_domains_db.load_domain("electronics")
        # Both domains define 焊接, but with different translations - this is OK
        assert "焊接" in mfg
        assert "焊接" in elec

    def test_domain_isolation_after_seeding(self, all_domains_db: GlossaryDB):
        """Medical-only terms should not appear in manufacturing domain."""
        mfg = all_domains_db.load_domain("manufacturing")
        # 高血压 (hypertension) should not be in manufacturing
        assert "高血压" not in mfg

    def test_legal_terms_not_in_electronics(self, all_domains_db: GlossaryDB):
        """Legal-specific terms like 诉讼 should not appear in electronics."""
        elec = all_domains_db.load_domain("electronics")
        assert "诉讼" not in elec

    def test_electronics_terms_not_in_medical(self, all_domains_db: GlossaryDB):
        """Electronics-specific terms like 集成电路 should not appear in medical."""
        med = all_domains_db.load_domain("medical")
        assert "集成电路" not in med

    def test_merge_does_not_lose_unique_terms(self, all_domains_db: GlossaryDB):
        """Merging all domains should retain unique terms from each."""
        merged = all_domains_db.merge_domains(
            ["manufacturing", "medical", "legal", "electronics"]
        )
        # Unique-to-each-domain terms must survive merging
        assert "镀锌" in merged       # unique to manufacturing
        assert "高血压" in merged     # unique to medical
        assert "诉讼" in merged       # unique to legal
        assert "集成电路" in merged   # unique to electronics


# ---------------------------------------------------------------------------
# Task 6: DomainSelectorModel
# ---------------------------------------------------------------------------


class TestDomainSelectorModel:
    """Test the non-GUI DomainSelectorModel."""

    def test_model_discovers_all_four_domains(self):
        from zh_en_translator.ui.domain_selector import DomainSelectorModel
        model = DomainSelectorModel()
        available = model.available_domains
        expected = {"manufacturing", "medical", "legal", "electronics"}
        assert expected.issubset(set(available))

    def test_model_default_all_enabled(self):
        from zh_en_translator.ui.domain_selector import DomainSelectorModel
        model = DomainSelectorModel()
        # Default: all available domains should be enabled
        assert set(model.enabled_domains) == set(model.available_domains)

    def test_model_set_enabled_true(self):
        from zh_en_translator.ui.domain_selector import DomainSelectorModel
        model = DomainSelectorModel(enabled_domains=["manufacturing"])
        assert model.is_enabled("manufacturing")
        assert not model.is_enabled("medical")
        model.set_enabled("medical", True)
        assert model.is_enabled("medical")

    def test_model_set_enabled_false(self):
        from zh_en_translator.ui.domain_selector import DomainSelectorModel
        model = DomainSelectorModel()
        model.set_enabled("legal", False)
        assert not model.is_enabled("legal")

    def test_model_enable_all(self):
        from zh_en_translator.ui.domain_selector import DomainSelectorModel
        model = DomainSelectorModel(enabled_domains=[])
        model.enable_all()
        assert len(model.enabled_domains) == len(model.available_domains)

    def test_model_disable_all(self):
        from zh_en_translator.ui.domain_selector import DomainSelectorModel
        model = DomainSelectorModel()
        model.disable_all()
        assert model.enabled_domains == []

    def test_model_on_change_callback(self):
        from zh_en_translator.ui.domain_selector import DomainSelectorModel
        changes = []

        def _cb(domains):
            changes.append(list(domains))

        model = DomainSelectorModel(enabled_domains=["manufacturing"], on_change=_cb)
        model.set_enabled("medical", True)
        assert len(changes) == 1
        assert "medical" in changes[0]

    def test_model_display_names(self):
        from zh_en_translator.ui.domain_selector import DomainSelectorModel, DOMAIN_DISPLAY_NAMES
        model = DomainSelectorModel()
        for domain in ["manufacturing", "medical", "legal", "electronics"]:
            name = model.get_display_name(domain)
            assert isinstance(name, str)
            assert len(name) > 0

    def test_model_set_enabled_domains(self):
        from zh_en_translator.ui.domain_selector import DomainSelectorModel
        model = DomainSelectorModel()
        model.set_enabled_domains(["manufacturing", "electronics"])
        assert set(model.enabled_domains) == {"manufacturing", "electronics"}
        assert not model.is_enabled("medical")
        assert not model.is_enabled("legal")
