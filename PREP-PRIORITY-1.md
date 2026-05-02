# Priority 1 Implementation Prep

**Status:** Framework prepared, ready for Sonnet agent implementation  
**Branch:** `claude/fix-translation-completeness-8hpL2`  
**Session Date:** 2026-04-22 (Prep), Next session (Implementation)

---

## Current Architecture

### Segmentation Pipeline (segmentation.py)
- **Current:** `segment(text) -> list[str]` uses jieba if available, falls back to char-run grouping
- **Dependencies:** jieba (optional, gracefully degrades)
- **Supporting functions:** `load_user_dict()`, `add_custom_words()`

### Config System (config.py)
- **Pattern:** TOML-based with `@dataclass Config` and load/save functions
- **Existing translation section:**
  ```
  [translation]
  traditional_to_simplified = true
  validation_enabled = true
  validation_completeness_threshold = 0.7
  ```
- **To add:** `segmenter = "jieba" | "pkuseg" | "hanlp"`

### Glossary System (glossary.py - existing)
- **Current:** Loads user glossary from CSV at `%APPDATA%\zh-en-translator\glossary.csv`
- **Integration:** Checked in pipeline.py before dictionary lookup
- **Pattern:** Can be extended to support domain-specific glossaries

---

## Task 1: Segmenter Switch Implementation

### Files to Modify
- **segmentation.py** — Add PKUSEG/HanLP support as config-switchable options
- **config.py** — Add `segmenter: str = "jieba"` field to Config dataclass
- **tests/test_segmentation.py** — Add benchmarking tests

### Implementation Plan
1. Add try-except blocks for PKUSEG and HanLP imports (optional, like jieba)
2. Modify `segment()` function with config-based dispatch:
   ```python
   def segment(text: str, segmenter: str = "jieba") -> list[str]:
       if segmenter == "pkuseg":
           return _segment_pkuseg(text)
       elif segmenter == "hanlp":
           return _segment_hanlp(text)
       elif segmenter == "jieba":
           return _segment_jieba(text)
       else:
           return _segment_fallback(text)
   ```
3. Thread through config system to use selected segmenter at runtime
4. Create benchmark tests comparing accuracy on technical text

### Expected Outcome
- Drop-in replacement of segmenter via config
- 2-3% accuracy improvement on technical terms (87.8% F1 from HanLP vs. 81.6% from jieba)
- Graceful fallback if library not installed

---

## Task 2: Manufacturing Glossary Creation

### Files to Create/Modify
- **NEW:** `src/zh_en_translator/resources/glossary_manufacturing.toml` — 500-1000 manufacturing terms
- **MODIFY:** `glossary.py` — Support domain-specific glossaries (optional, may already support)
- **MODIFY:** `pipeline.py` — Integrate manufacturing glossary lookup before generic dictionary

### Glossary Structure (TOML Format)
```toml
[manufacturing_general]
"镀锌" = { pinyin = "dù xīn", english_primary = "galvanized", english_alt = ["zinc-plated"], context = "metals, coatings", notes = "hot-dip vs. electroplating distinction" }
"表面处理" = { pinyin = "biǎo miàn chǔ lǐ", english_primary = "surface treatment", english_alt = ["surface finishing"], context = "manufacturing processes", notes = "electroplating, anodizing, powder coating, polishing" }

[manufacturing_processes]
"热处理" = { pinyin = "rè chǔ lǐ", english_primary = "heat treatment", english_alt = [], context = "metallurgy", notes = "hardening, tempering, annealing" }
"硬化" = { pinyin = "yìng huà", english_primary = "case-hardening", english_alt = ["surface-hardening"], context = "metallurgy", notes = "process-specific, not generic hardening" }

[manufacturing_components]
"零件" = { pinyin = "líng jiàn", english_primary = "component", english_alt = ["part"], context = "engineering", notes = "consistent usage in technical docs" }

[manufacturing_standards]
"公差" = { pinyin = "gōng chà", english_primary = "tolerance", english_alt = [], context = "specifications", notes = "not error or margin" }
"精度" = { pinyin = "jīng dù", english_primary = "precision", english_alt = ["tolerance"], context = "measurements", notes = "accuracy vs precision context-dependent" }
```

### Content Priority
Start with **high-ROI terms** from DOMAIN_IMPROVEMENTS.md:
- **Materials:** 钢, 铝, 铜, 塑料 (with alloy specifics)
- **Processes:** 镀锌, 表面处理, 氧化, 热处理, 硬化
- **Components:** 零件, 组件
- **Compliance:** 公差, 精度, 防火, 接地

### Integration Points
1. Load glossary at startup (like current user glossary)
2. Check glossary before dictionary lookup in pipeline
3. Glossary match takes precedence over generic dictionary

### Expected Outcome
- Consistent terminology across manufacturing documents
- 5-7% accuracy improvement on glossary-covered terms
- ~20% of technical text has glossary coverage

---

## Task 3: Benchmarking & Validation

### Test Scope
- Segmenter accuracy: jieba vs. PKUSEG vs. HanLP on sample technical text
- Glossary coverage: Does it handle 95%+ of known manufacturing terms?
- End-to-end: Translation quality improvement on sample manufacturing sentences

### Sample Test Cases (from DOMAIN_IMPROVEMENTS.md)
```
Simple compound: "镀锌钢板" (galvanized steel plate)
  Expected segmentation: 镀锌 + 钢板 (not mis-segment as 镀 + 锌 + 钢 + 板)

Process description: "表面处理后需要喷粉"
  Expected: recognizes "表面处理" as single term, not "表 + 面 + 处 + 理"

Technical spec: "公差控制在±0.5mm"
  Expected: Glossary maps "公差" → "tolerance", not "error margin"
```

### Metrics to Track
- **F1 score** on technical term recognition (jieba vs. alternatives)
- **BLEU score** on sample manufacturing translations (before/after)
- **Glossary hit rate** (% of technical terms found in glossary)

---

## Dependencies to Install (Next Session)

For agent to install when implementing:
```bash
pip install pkuseg     # ~10 MB, multi-domain support
# OR
pip install hanlp      # ~5 MB, better out-of-the-box performance (87.8% F1)
```

Recommendation: Test both, choose the better performer on technical text.

---

## Integration Points Identified

### segmentation.py
- `segment()` function signature stays compatible
- Config-based dispatch added internally
- No breaking changes to callers

### config.py
- Add `[translation]` section field: `segmenter = "jieba" | "pkuseg" | "hanlp"`
- Default to "jieba" for backward compatibility
- Load/save functions handle new field automatically

### glossary.py / pipeline.py
- Load manufacturing glossary alongside user glossary at startup
- Glossary lookup order: manufacturing → user → dictionary (longest-match first)
- No structural changes needed, just priority reordering

### tests/
- **test_segmentation.py** — Add benchmark tests
- **test_glossary.py** — Add manufacturing glossary tests (or expand existing)
- **test_pipeline.py** — Add integration tests for glossary precedence

---

## Files Ready for Next Session

1. ✅ **PREP-PRIORITY-1.md** (this file) — Framework, architecture, integration points
2. ✅ **segmentation.py** — Analyzed, implementation plan clear
3. ✅ **config.py** — Analyzed, config field identified
4. ✅ **glossary.py/pipeline.py** — Integration points mapped
5. 📋 **glossary_manufacturing.toml** — Draft template (to be expanded in next session)

---

## Session Handoff Checklist

For Sonnet agent in next session:
- [ ] Read this file (PREP-PRIORITY-1.md) for architecture and integration points
- [ ] Read DOMAIN_IMPROVEMENTS.md Priority 1 section for business context
- [ ] Install PKUSEG and HanLP via pip
- [ ] Implement segmenter switch in segmentation.py
- [ ] Expand manufacturing glossary with 500-1000 terms (can start with 100-200 high-priority)
- [ ] Integrate glossary into pipeline
- [ ] Create benchmarking tests
- [ ] Run all tests, verify no regressions
- [ ] Commit with clear messages
- [ ] Push to branch when complete

**Estimated Time:** 2-3 hours for Sonnet agent

---

## Key Decision Points for Agent

1. **PKUSEG vs. HanLP:** Test both, choose better performer on technical text (likely HanLP for F1 score)
2. **Glossary size:** Start with 100-200 high-priority terms, can expand to 500-1000 in next phase
3. **Glossary scope:** Manufacturing-focused first, can add other domains in Priority 4
4. **Integration:** Glossary checked before dictionary (not after) to ensure domain terms take precedence

---

**Status:** Ready for implementation | **Dependencies:** PKUSEG/HanLP pip packages | **Complexity:** Medium | **Risk:** Low (additive, fallback behavior)
