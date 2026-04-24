"""Tests for glossary loading and integration."""

import pytest
from pathlib import Path
from zh_en_translator.engines.glossary import (
    load_glossary,
    load_domain_glossary,
    load_all_glossaries,
    save_glossary,
    get_glossary_path,
)


class TestUserGlossary:
    """Test user glossary CSV loading and saving."""

    def test_load_empty_glossary_when_no_file(self):
        """Should return empty dict when glossary file doesn't exist."""
        # Create a non-existent path
        fake_path = Path("/tmp/nonexistent_glossary.csv")
        glossary = load_glossary(fake_path)
        assert glossary == {}

    def test_save_and_load_glossary(self, tmp_path):
        """Should save and load glossary CSV correctly."""
        glossary_path = tmp_path / "test_glossary.csv"
        terms = {
            "镀锌": "galvanized",
            "表面处理": "surface treatment",
            "热处理": "heat treatment",
        }

        # Save
        save_glossary(terms, glossary_path)
        assert glossary_path.exists()

        # Load
        loaded = load_glossary(glossary_path)
        assert loaded == terms

    def test_save_glossary_creates_parent_dirs(self, tmp_path):
        """Should create parent directories if they don't exist."""
        glossary_path = tmp_path / "deep" / "nested" / "glossary.csv"
        terms = {"test": "测试"}

        save_glossary(terms, glossary_path)
        assert glossary_path.exists()


class TestDomainGlossary:
    """Test domain-specific glossary loading."""

    def test_load_manufacturing_glossary(self):
        """Should load manufacturing glossary from resources."""
        glossary = load_domain_glossary("manufacturing")
        assert len(glossary) > 0, "Manufacturing glossary should not be empty"
        assert "镀锌" in glossary
        assert glossary["镀锌"] == "galvanized / zinc-plated"

    def test_load_nonexistent_domain_glossary(self):
        """Should return empty dict for non-existent domain."""
        glossary = load_domain_glossary("nonexistent_domain")
        assert glossary == {}

    def test_manufacturing_glossary_has_key_terms(self):
        """Should contain essential manufacturing terminology."""
        glossary = load_domain_glossary("manufacturing")
        key_terms = [
            "镀锌",      # galvanized
            "表面处理",   # surface treatment
            "氧化",      # oxidation/anodizing
            "热处理",    # heat treatment
            "零件",      # component
            "精度",      # tolerance/precision
            "公差",      # tolerance
        ]
        for term in key_terms:
            assert term in glossary, f"Manufacturing glossary missing key term: {term}"

    def test_manufacturing_glossary_has_sections(self):
        """Verify glossary covers multiple domains within manufacturing."""
        glossary = load_domain_glossary("manufacturing")

        # Sample from different sections
        materials = ["钢", "铝", "铜"]           # materials section
        processes = ["镀锌", "焊接", "铸造"]     # processes section
        components = ["轴", "齿轮", "螺栓"]    # components section
        standards = ["防火", "接地", "RoHS"]    # standards section

        for term in materials + processes + components + standards:
            assert term in glossary, f"Missing term from glossary: {term}"


class TestMergedGlossaries:
    """Test merging user and domain glossaries."""

    def test_load_all_glossaries_includes_manufacturing(self):
        """Should include manufacturing domain by default."""
        glossary = load_all_glossaries()
        assert len(glossary) > 0
        # Check that manufacturing terms are present
        assert "镀锌" in glossary
        assert "热处理" in glossary

    def test_load_all_glossaries_user_overrides_domain(self, tmp_path):
        """User glossary should override domain glossary."""
        # Create a user glossary with an override
        user_glossary_path = tmp_path / "glossary.csv"
        user_terms = {
            "镀锌": "CUSTOM_GALVANIZED",
        }
        save_glossary(user_terms, user_glossary_path)

        # Mock the glossary path lookup
        import zh_en_translator.engines.glossary as glossary_module
        original_get_glossary_path = glossary_module.get_glossary_path

        def mock_get_glossary_path():
            return user_glossary_path

        glossary_module.get_glossary_path = mock_get_glossary_path
        try:
            merged = load_all_glossaries()
            # User glossary should override manufacturing glossary
            assert merged["镀锌"] == "CUSTOM_GALVANIZED"
        finally:
            glossary_module.get_glossary_path = original_get_glossary_path

    def test_load_all_glossaries_accepts_domain_list(self):
        """Should accept list of domains to load."""
        # Since we only have manufacturing, this tests the parameter
        glossary = load_all_glossaries(include_domains=["manufacturing"])
        assert len(glossary) > 0
        assert "镀锌" in glossary

    def test_load_all_glossaries_default_manufacturing(self):
        """Default should include manufacturing domain."""
        glossary = load_all_glossaries(include_domains=["manufacturing"])
        glossary_default = load_all_glossaries()
        # Default should at least have manufacturing
        assert "镀锌" in glossary_default


class TestGlossaryIntegration:
    """Test glossary integration with translation pipeline."""

    def test_glossary_used_in_pipeline(self):
        """Verify glossary is properly integrated in pipeline.translate."""
        pytest.importorskip("platformdirs")
        from zh_en_translator.engines.pipeline import translate
        from zh_en_translator.engines.dictionary import Dictionary, ensure_cedict

        # Prepare dictionary and glossary
        cedict_path = ensure_cedict()
        db_path = cedict_path.with_suffix(".db")
        if not db_path.exists():
            Dictionary.build_from_cedict(cedict_path, db_path)
        dictionary = Dictionary(db_path)

        try:
            # Create a simple glossary
            glossary = {
                "镀锌": "galvanized",
                "热处理": "heat treatment",
            }

            # Test with glossary
            results = translate("镀锌和热处理", dictionary, glossary=glossary)

            # Check that first token matches glossary
            assert results[0].token == "镀锌"
            assert glossary["镀锌"] in results[0].glosses

        finally:
            dictionary.close()

    def test_glossary_precedence_over_dictionary(self):
        """Glossary should take precedence over dictionary lookups."""
        pytest.importorskip("platformdirs")
        from zh_en_translator.engines.pipeline import translate
        from zh_en_translator.engines.dictionary import Dictionary, ensure_cedict

        cedict_path = ensure_cedict()
        db_path = cedict_path.with_suffix(".db")
        if not db_path.exists():
            Dictionary.build_from_cedict(cedict_path, db_path)
        dictionary = Dictionary(db_path)

        try:
            # Use a glossary with different translation than dictionary
            glossary = {
                "零件": "manufacturing_component",
            }

            results = translate("零件", dictionary, glossary=glossary)

            # Glossary entry should be in results
            assert results[0].glosses == ["manufacturing_component"]

        finally:
            dictionary.close()


class TestGlossaryContent:
    """Test the actual content and coverage of manufacturing glossary."""

    def test_glossary_covers_materials(self):
        """Manufacturing glossary should cover common materials."""
        glossary = load_domain_glossary("manufacturing")
        materials = ["钢", "铝", "铜", "塑料"]
        for material in materials:
            assert material in glossary, f"Missing material: {material}"

    def test_glossary_covers_processes(self):
        """Manufacturing glossary should cover surface treatment processes."""
        glossary = load_domain_glossary("manufacturing")
        processes = ["镀锌", "表面处理", "氧化", "热处理", "焊接"]
        for process in processes:
            assert process in glossary, f"Missing process: {process}"

    def test_glossary_covers_components(self):
        """Manufacturing glossary should cover common components."""
        glossary = load_domain_glossary("manufacturing")
        components = ["零件", "螺栓", "螺母", "轴", "齿轮"]
        for component in components:
            assert component in glossary, f"Missing component: {component}"

    def test_glossary_covers_quality_standards(self):
        """Manufacturing glossary should cover quality and standards."""
        glossary = load_domain_glossary("manufacturing")
        standards = ["精度", "公差", "防火", "接地", "认证"]
        for standard in standards:
            assert standard in glossary, f"Missing standard: {standard}"

    def test_glossary_entries_have_translations(self):
        """All glossary entries should have non-empty English translations."""
        glossary = load_domain_glossary("manufacturing")
        for zh, en in glossary.items():
            assert zh, "Chinese term should not be empty"
            assert en, f"English translation for '{zh}' should not be empty"
            assert isinstance(en, str), f"Translation should be string, got {type(en)}"

    def test_glossary_size(self):
        """Manufacturing glossary should contain substantial number of terms."""
        glossary = load_domain_glossary("manufacturing")
        # Expecting 145+ terms minimum (substantial initial coverage)
        assert len(glossary) >= 145, f"Glossary too small: {len(glossary)} terms"

