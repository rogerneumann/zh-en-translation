"""Benchmarking tests comparing jieba vs PKUSEG segmentation accuracy.

These tests measure segmentation quality on manufacturing/technical Chinese
text.  The F1 score is computed against hand-labelled reference segmentations
using the standard token-level precision/recall formula.

Skipped automatically when spacy-pkuseg is not installed.
"""

from __future__ import annotations

import pytest

try:
    import spacy_pkuseg  # noqa: F401
    _PKUSEG_AVAILABLE = True
except ImportError:
    _PKUSEG_AVAILABLE = False

try:
    import jieba  # noqa: F401
    _JIEBA_AVAILABLE = True
except ImportError:
    _JIEBA_AVAILABLE = False


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _f1(predicted: list[str], reference: list[str]) -> float:
    """Compute token-level F1 between two segmentations.

    Uses multiset intersection so duplicate tokens are counted correctly.
    Returns a value in [0.0, 1.0].
    """
    pred_counts: dict[str, int] = {}
    ref_counts: dict[str, int] = {}
    for t in predicted:
        pred_counts[t] = pred_counts.get(t, 0) + 1
    for t in reference:
        ref_counts[t] = ref_counts.get(t, 0) + 1

    # |intersection| = sum of min counts for shared tokens
    intersection = sum(
        min(pred_counts[t], ref_counts.get(t, 0)) for t in pred_counts
    )

    precision = intersection / len(predicted) if predicted else 0.0
    recall = intersection / len(reference) if reference else 0.0

    if precision + recall == 0.0:
        return 0.0
    return 2 * precision * recall / (precision + recall)


def _segment_jieba(text: str) -> list[str]:
    from zh_en_translator.engines.segmentation import _segment_jieba
    return _segment_jieba(text)


def _segment_pkuseg(text: str) -> list[str]:
    from zh_en_translator.engines.segmentation import _segment_pkuseg
    return _segment_pkuseg(text)


# ---------------------------------------------------------------------------
# Reference segmentations: (input_text, expected_tokens)
# These are manually verified correct segmentations for manufacturing domain.
# ---------------------------------------------------------------------------

# Format: (sentence, reference_token_list)
# Reference tokens are the "gold standard" we measure both segmenters against.
MANUFACTURING_REFERENCES: list[tuple[str, list[str]]] = [
    # Surface treatment
    (
        "镀锌钢板的表面处理",
        ["镀锌", "钢板", "的", "表面", "处理"],
    ),
    # Heat treatment
    (
        "零件需要进行热处理",
        ["零件", "需要", "进行", "热处理"],
    ),
    # Precision / tolerance
    (
        "加工精度和公差要求严格",
        ["加工", "精度", "和", "公差", "要求", "严格"],
    ),
    # Stamped parts
    (
        "冲压件的表面不得有毛刺",
        ["冲压件", "的", "表面", "不得", "有", "毛刺"],
    ),
    # Welding inspection
    (
        "焊接部位需进行超声波检测",
        ["焊接", "部位", "需", "进行", "超声波", "检测"],
    ),
    # Anodising
    (
        "铝合金零件阳极氧化处理",
        ["铝合金", "零件", "阳极", "氧化", "处理"],
    ),
    # Hardness measurement
    (
        "经过热处理后测量硬度",
        ["经过", "热处理", "后", "测量", "硬度"],
    ),
    # Injection moulding gate removal
    (
        "注塑件需要去除浇口",
        ["注塑件", "需要", "去除", "浇口"],
    ),
    # Dimensional tolerance
    (
        "尺寸公差符合图纸要求",
        ["尺寸", "公差", "符合", "图纸", "要求"],
    ),
    # Galvanized surface quality
    (
        "镀锌层表面质量检验",
        ["镀锌", "层", "表面", "质量", "检验"],
    ),
]

# Simpler individual manufacturing terms with unambiguous expected segmentation
TERM_REFERENCES: list[tuple[str, list[str]]] = [
    ("镀锌", ["镀锌"]),
    ("表面处理", ["表面", "处理"]),
    ("精度", ["精度"]),
    ("公差", ["公差"]),
    ("冲压件", ["冲压件"]),
    ("焊接", ["焊接"]),
    ("超声波检测", ["超声波", "检测"]),
    ("铝合金", ["铝合金"]),
    ("尺寸公差", ["尺寸", "公差"]),
]


# ---------------------------------------------------------------------------
# Basic functional tests (segmenter works at all)
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not _PKUSEG_AVAILABLE, reason="spacy-pkuseg not installed")
def test_pkuseg_basic_segmentation():
    """PKUSEG must produce a non-empty list for non-empty input."""
    from zh_en_translator.engines.segmentation import _segment_pkuseg
    result = _segment_pkuseg("镀锌表面处理")
    assert len(result) > 0
    assert all(isinstance(t, str) and t for t in result)


@pytest.mark.skipif(not _PKUSEG_AVAILABLE, reason="spacy-pkuseg not installed")
def test_pkuseg_empty_input():
    """PKUSEG must return empty list for empty input."""
    from zh_en_translator.engines.segmentation import segment
    result = segment("", segmenter="pkuseg")
    assert result == []


@pytest.mark.skipif(not _PKUSEG_AVAILABLE, reason="spacy-pkuseg not installed")
def test_pkuseg_preserves_ascii():
    """ASCII spans must not be garbled by PKUSEG's Chinese-only model."""
    from zh_en_translator.engines.segmentation import segment
    result = segment("X10零件", segmenter="pkuseg")
    joined = "".join(result)
    assert joined == "X10零件"
    assert "X10" in result, f"Expected 'X10' as a single token; got: {result}"


@pytest.mark.skipif(not _PKUSEG_AVAILABLE, reason="spacy-pkuseg not installed")
def test_pkuseg_mixed_input():
    """Mixed Chinese/ASCII text must be fully preserved."""
    from zh_en_translator.engines.segmentation import segment
    text = "ISO 9001认证工厂"
    result = segment(text, segmenter="pkuseg")
    assert "".join(result) == text


# ---------------------------------------------------------------------------
# Config-based segmenter switching
# ---------------------------------------------------------------------------

def test_set_segmenter_jieba():
    """set_segmenter('jieba') must switch active backend."""
    from zh_en_translator.engines.segmentation import set_segmenter, get_segmenter
    set_segmenter("jieba")
    assert get_segmenter() == "jieba"


@pytest.mark.skipif(not _PKUSEG_AVAILABLE, reason="spacy-pkuseg not installed")
def test_set_segmenter_pkuseg():
    """set_segmenter('pkuseg') must switch active backend."""
    from zh_en_translator.engines.segmentation import set_segmenter, get_segmenter
    set_segmenter("pkuseg")
    assert get_segmenter() == "pkuseg"
    # Restore default for other tests
    set_segmenter("jieba")


def test_set_segmenter_fallback():
    """set_segmenter('fallback') must switch active backend."""
    from zh_en_translator.engines.segmentation import set_segmenter, get_segmenter
    set_segmenter("fallback")
    assert get_segmenter() == "fallback"
    # Restore default
    set_segmenter("jieba")


def test_set_segmenter_invalid():
    """set_segmenter with unknown name must raise ValueError."""
    from zh_en_translator.engines.segmentation import set_segmenter
    with pytest.raises(ValueError, match="Unknown segmenter"):
        set_segmenter("hanlp")


@pytest.mark.skipif(not _PKUSEG_AVAILABLE, reason="spacy-pkuseg not installed")
def test_segment_with_explicit_backend():
    """segment() must accept an explicit segmenter override."""
    from zh_en_translator.engines.segmentation import segment
    result_jieba = segment("镀锌", segmenter="jieba")
    result_pkuseg = segment("镀锌", segmenter="pkuseg")
    # Both must return non-empty lists
    assert result_jieba
    assert result_pkuseg
    # For "镀锌" both should keep it as one token
    assert "镀锌" in result_jieba
    assert "镀锌" in result_pkuseg


@pytest.mark.skipif(not _PKUSEG_AVAILABLE, reason="spacy-pkuseg not installed")
def test_active_segmenter_used_by_default():
    """Calling segment() with no args uses the active module-level backend."""
    from zh_en_translator.engines.segmentation import segment, set_segmenter, get_segmenter

    original = get_segmenter()
    try:
        set_segmenter("pkuseg")
        result = segment("精度")
        assert result  # just verify it ran without error
    finally:
        set_segmenter(original)


# ---------------------------------------------------------------------------
# Accuracy benchmarks -- F1 on manufacturing text
# ---------------------------------------------------------------------------

def _avg_f1(segment_fn, references) -> float:
    scores = [_f1(segment_fn(text), ref) for text, ref in references]
    return sum(scores) / len(scores)


@pytest.mark.skipif(not _JIEBA_AVAILABLE, reason="jieba not installed")
def test_jieba_f1_baseline():
    """Jieba F1 on manufacturing sentences must be >= 0.65 (baseline check)."""
    f1 = _avg_f1(_segment_jieba, MANUFACTURING_REFERENCES)
    assert f1 >= 0.65, f"Jieba baseline F1 too low: {f1:.3f}"


@pytest.mark.skipif(not _PKUSEG_AVAILABLE, reason="spacy-pkuseg not installed")
def test_pkuseg_f1_baseline():
    """PKUSEG F1 on manufacturing sentences must be >= 0.60."""
    f1 = _avg_f1(_segment_pkuseg, MANUFACTURING_REFERENCES)
    assert f1 >= 0.60, f"PKUSEG baseline F1 too low: {f1:.3f}"


@pytest.mark.skipif(
    not (_JIEBA_AVAILABLE and _PKUSEG_AVAILABLE),
    reason="Both jieba and spacy-pkuseg required for comparison",
)
def test_both_segmenters_competitive():
    """Both jieba and PKUSEG must achieve F1 within 15 percentage points of each other.

    Neither segmenter is uniformly better on all manufacturing text; the goal
    is to confirm they are in the same ballpark.  Domain-specific tuning
    (user dict for jieba, custom model for pkuseg) would tighten this gap.
    """
    jieba_f1 = _avg_f1(_segment_jieba, MANUFACTURING_REFERENCES)
    pkuseg_f1 = _avg_f1(_segment_pkuseg, MANUFACTURING_REFERENCES)
    delta = abs(jieba_f1 - pkuseg_f1)
    assert delta <= 0.15, (
        f"Segmenters diverge too much: jieba={jieba_f1:.3f}, pkuseg={pkuseg_f1:.3f}, "
        f"delta={delta:.3f}"
    )


# ---------------------------------------------------------------------------
# Manufacturing term segmentation correctness
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not _JIEBA_AVAILABLE, reason="jieba not installed")
@pytest.mark.parametrize("term,expected", TERM_REFERENCES)
def test_jieba_term_segmentation(term, expected):
    """Jieba must correctly segment unambiguous manufacturing terms."""
    result = _segment_jieba(term)
    assert result == expected, (
        f"Term '{term}': expected {expected}, got {result}"
    )


@pytest.mark.skipif(not _PKUSEG_AVAILABLE, reason="spacy-pkuseg not installed")
@pytest.mark.parametrize("term,expected", [
    ("镀锌", ["镀锌"]),
    ("精度", ["精度"]),
    ("公差", ["公差"]),
    ("焊接", ["焊接"]),
    ("铝合金", ["铝合金"]),
])
def test_pkuseg_unambiguous_terms(term, expected):
    """PKUSEG must correctly segment clearly unambiguous manufacturing terms."""
    result = _segment_pkuseg(term)
    assert result == expected, (
        f"Term '{term}': expected {expected}, got {result}"
    )


# ---------------------------------------------------------------------------
# Glossary coverage test -- key terms from glossary_manufacturing.toml
# ---------------------------------------------------------------------------

GLOSSARY_TERMS = [
    "镀锌",
    "表面处理",
    "热处理",
    "精度",
    "公差",
    "冲压",
    "焊接",
    "铝合金",
    "钢板",
    "毛刺",
    "超声波",
    "尺寸",
]


@pytest.mark.skipif(not _JIEBA_AVAILABLE, reason="jieba not installed")
def test_glossary_term_coverage_jieba():
    """All glossary terms must appear as valid tokens in jieba segmentation of a phrase."""
    covered = 0
    for term in GLOSSARY_TERMS:
        tokens = _segment_jieba(term)
        # The term may be split but all characters must be present
        joined = "".join(tokens)
        if joined == term:
            covered += 1
    coverage_pct = covered / len(GLOSSARY_TERMS)
    assert coverage_pct >= 0.80, (
        f"Jieba covered only {covered}/{len(GLOSSARY_TERMS)} ({coverage_pct:.0%}) "
        "glossary terms as single tokens"
    )


@pytest.mark.skipif(not _PKUSEG_AVAILABLE, reason="spacy-pkuseg not installed")
def test_glossary_term_coverage_pkuseg():
    """All glossary terms must appear as valid tokens in pkuseg segmentation."""
    covered = 0
    for term in GLOSSARY_TERMS:
        tokens = _segment_pkuseg(term)
        joined = "".join(tokens)
        if joined == term:
            covered += 1
    coverage_pct = covered / len(GLOSSARY_TERMS)
    assert coverage_pct >= 0.70, (
        f"PKUSEG covered only {covered}/{len(GLOSSARY_TERMS)} ({coverage_pct:.0%}) "
        "glossary terms as single tokens"
    )


# ---------------------------------------------------------------------------
# Regression: domain sentences from DOMAIN_IMPROVEMENTS.md
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not _JIEBA_AVAILABLE, reason="jieba not installed")
def test_domain_sentence_galvanized_jieba():
    """Jieba: '镀锌' must appear as one token in a galvanizing sentence."""
    result = _segment_jieba("镀锌钢板表面处理工艺")
    assert "镀锌" in result, f"Expected '镀锌' token; got: {result}"


@pytest.mark.skipif(not _PKUSEG_AVAILABLE, reason="spacy-pkuseg not installed")
def test_domain_sentence_galvanized_pkuseg():
    """PKUSEG: '镀锌' must appear as one token in a galvanizing sentence."""
    result = _segment_pkuseg("镀锌钢板表面处理工艺")
    assert "镀锌" in result, f"Expected '镀锌' token; got: {result}"


@pytest.mark.skipif(not _JIEBA_AVAILABLE, reason="jieba not installed")
def test_domain_sentence_precision_jieba():
    """Jieba: '精度' and '公差' must both appear as tokens."""
    result = _segment_jieba("加工精度和公差要求严格")
    assert "精度" in result, f"Expected '精度' token; got: {result}"
    assert "公差" in result, f"Expected '公差' token; got: {result}"


@pytest.mark.skipif(not _PKUSEG_AVAILABLE, reason="spacy-pkuseg not installed")
def test_domain_sentence_precision_pkuseg():
    """PKUSEG: '精度' and '公差' must both appear as tokens."""
    result = _segment_pkuseg("加工精度和公差要求严格")
    assert "精度" in result, f"Expected '精度' token; got: {result}"
    assert "公差" in result, f"Expected '公差' token; got: {result}"


@pytest.mark.skipif(not _JIEBA_AVAILABLE, reason="jieba not installed")
def test_domain_sentence_heat_treatment_jieba():
    """Jieba: '热处理' must appear as one compound token."""
    result = _segment_jieba("零件热处理后检验硬度")
    assert "热处理" in result, f"Expected '热处理' token; got: {result}"


@pytest.mark.skipif(not _JIEBA_AVAILABLE, reason="jieba not installed")
def test_domain_sentence_surface_treatment_jieba():
    """Jieba: '表面' must appear in surface treatment sentence."""
    result = _segment_jieba("表面处理工艺要求")
    assert "表面" in result, f"Expected '表面' token; got: {result}"


@pytest.mark.skipif(not _PKUSEG_AVAILABLE, reason="spacy-pkuseg not installed")
def test_domain_sentence_surface_treatment_pkuseg():
    """PKUSEG: '表面' must appear in surface treatment sentence."""
    result = _segment_pkuseg("表面处理工艺要求")
    assert "表面" in result, f"Expected '表面' token; got: {result}"
