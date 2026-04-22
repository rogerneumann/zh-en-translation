# Next Session: Priority 1 - Domain-Specific Refinement

## Quick Context

You're continuing work on the zh-en-translator project. The translation completeness initiative (v4) is **complete and pushed**. Now implementing **Priority 1: Domain-Specific Improvements** to boost technical/manufacturing translation accuracy by +2-7%.

**Current branch:** `claude/fix-translation-completeness-8hpL2`  
**Status:** Ready for Priority 1 implementation

---

## What to Do This Session

Implement **Priority 1: Immediate Actions** from `DOMAIN_IMPROVEMENTS.md`:

### Task 1: Switch Word Segmenter (Jieba → PKUSEG or HanLP)

**Files to Modify:**
- `src/zh_en_translator/engines/segmentation.py` — Main segmentation module
- `tests/test_segmentation.py` — Segmentation tests

**Steps:**
1. Read current `segmentation.py` to understand the `segment()` function signature
2. Evaluate PKUSEG vs. HanLP:
   - PKUSEG: 82.34% F1, multi-domain models available
   - HanLP: 87.8% F1, better out-of-the-box, deep learning-based
3. **Implement both as options** with a config flag to choose which one
4. Create benchmarking tests comparing jieba vs. PKUSEG vs. HanLP
5. Update `config.py` to add `segmenter = "jieba" | "pkuseg" | "hanlp"`

**Expected:** Switch to PKUSEG or HanLP improves technical term accuracy by 2-3%

**Test on:** Sample manufacturing text (available in `DOMAIN_IMPROVEMENTS.md` examples)

---

### Task 2: Create Manufacturing Glossary

**Files to Create/Modify:**
- `src/zh_en_translator/resources/glossary_manufacturing.toml` — NEW glossary database
- `src/zh_en_translator/engines/glossary.py` — Update to support domain glossaries
- `src/zh_en_translator/engines/pipeline.py` — Integrate glossary lookup

**Steps:**
1. Create manufacturing glossary with 500-1000 terms (template in `DOMAIN_IMPROVEMENTS.md`)
2. Format: TOML or CSV with fields: [Chinese, Pinyin, English_Primary, English_Alt, Context, Notes]
3. Start with high-priority terms:
   - Materials: 钢, 铝, 铜, 塑料 (with alloy specifics)
   - Processes: 镀锌, 表面处理, 氧化, 热处理, 硬化
   - Components: 零件, 组件
   - Compliance: 公差, 精度, 防火, 接地

4. Integrate into translation pipeline:
   - Before dictionary lookup, check glossary for exact match
   - If found, use glossary translation (takes precedence)
   - Fall back to dictionary if not in glossary

5. Create tests for glossary lookup and pipeline integration

**Expected:** Glossary on ~20% of technical terms improves accuracy by 5-7% on glossary-covered words

**Resources:** 
- ProZ.com manufacturing glossaries (free)
- CJK Institute Technical Dictionary
- DOMAIN_IMPROVEMENTS.md has examples

---

### Task 3: Benchmark Results

**What to Do:**
1. Run tests on sample manufacturing sentences before/after changes
2. Compare segmenter accuracy: jieba vs. PKUSEG vs. HanLP
3. Measure glossary impact: with/without glossary
4. Document results in `BENCHMARKS.md` or section in `progress.md`

**Success Criteria:**
- ✅ PKUSEG/HanLP shows 5-6% better F1 than jieba on technical text
- ✅ Glossary correctly handles 95%+ of known manufacturing terms
- ✅ End-to-end translation improves by 2-7% on sample technical text
- ✅ All tests passing

---

## Session Prompt to Use

Copy this and use as your starting prompt in the next session:

```
You're implementing Priority 1 from DOMAIN_IMPROVEMENTS.md for the zh-en-translator project.

## What to Implement

Priority 1 has 2 components (both should be done this session):

### 1. Switch Segmenter: Jieba → PKUSEG or HanLP
- Current segmenter: jieba (81.6% F1 accuracy)
- Target: PKUSEG (82.34%) or HanLP (87.8%)
- Modify: src/zh_en_translator/engines/segmentation.py
- Add config option: segmenter = "jieba" | "pkuseg" | "hanlp"
- Create benchmarking tests comparing all three
- Update tests in tests/test_segmentation.py

### 2. Create Manufacturing Glossary
- Create: src/zh_en_translator/resources/glossary_manufacturing.toml
- Content: 500-1000 technical/manufacturing terms (see DOMAIN_IMPROVEMENTS.md for examples)
- Format: TOML with fields [chinese, pinyin, english_primary, english_alt, context, notes]
- Integrate into pipeline.py: glossary lookup before dictionary
- Update glossary.py to support domain-specific glossaries
- Create/update tests for glossary integration

## Expected Outcomes
- +2-3% accuracy from better segmentation
- +5-7% accuracy on glossary-covered terms
- Total Priority 1 gain: +2-7% on technical text
- All tests passing

## Key Files
- DOMAIN_IMPROVEMENTS.md — Full implementation guide with manufacturing terminology
- src/zh_en_translator/engines/segmentation.py — Current segmentation logic
- src/zh_en_translator/engines/glossary.py — Glossary management
- src/zh_en_translator/engines/pipeline.py — Translation pipeline
- config.py — Configuration system

## Branch
- Work on: claude/fix-translation-completeness-8hpL2
- Commit with clear messages
- Push when complete

## Success Criteria
✅ Segmenter switch complete with benchmarks showing improvement
✅ Glossary created and integrated into pipeline
✅ All tests passing (existing + new)
✅ Manufacturing terminology handled correctly
✅ Committed and pushed to remote
```

---

## Quick Reference

### Key Files in This Session
```
src/zh_en_translator/
├── engines/
│   ├── segmentation.py        ← MODIFY: Add PKUSEG/HanLP support
│   ├── glossary.py            ← MODIFY: Support domain glossaries
│   └── pipeline.py            ← MODIFY: Integrate glossary lookup
├── resources/
│   └── glossary_manufacturing.toml  ← CREATE: Manufacturing terms (500-1000)
└── config.py                  ← MODIFY: Add segmenter option

tests/
├── test_segmentation.py       ← UPDATE: Benchmark jieba vs PKUSEG vs HanLP
└── test_glossary.py           ← UPDATE: Test glossary integration
```

### Manufacturing Terminology Examples (Start Here)
From DOMAIN_IMPROVEMENTS.md:
- 镀锌 → "galvanized" / "zinc-plated"
- 表面处理 → "surface treatment" (not "surface processing")
- 氧化 → Context-dependent (anodizing vs. black oxide vs. oxidation)
- 热处理 → "heat treatment" with process specification
- 零件 → "component" (consistent usage)
- 精度 → "tolerance" / "precision" (context-dependent)

### Installation Commands Needed
```bash
pip install pkuseg    # For PKUSEG segmenter
# OR
pip install hanlp     # For HanLP segmenter
```

---

## Checklist for Session Completion

- [ ] Read DOMAIN_IMPROVEMENTS.md (priority 1 section)
- [ ] Install PKUSEG (or HanLP)
- [ ] Implement segmenter switch in segmentation.py
- [ ] Create manufacturing glossary (500-1000 terms)
- [ ] Integrate glossary into pipeline
- [ ] Create/update tests for both components
- [ ] Benchmark: measure improvement from segmenter + glossary
- [ ] Verify all existing tests still pass
- [ ] Commit with clear messages
- [ ] Push to claude/fix-translation-completeness-8hpL2
- [ ] Update progress.md with results

---

## Resources & Documentation

**In This Repo:**
- `DOMAIN_IMPROVEMENTS.md` — Full research and implementation guide (82+ sources)
- `v4_completeness.md` — Translation completeness initiative (complete reference)
- `progress.md` — Project status and milestones
- `PLAN.md`, `plan-v2.md`, `plan-v3.md` — Architecture and design

**External Resources:**
- ProZ.com: Manufacturing glossaries (free, community-maintained)
- CJK Institute: Technical Dictionary (professional-grade)
- CSET-ETO: Chinese Technical Glossary (free, regularly updated)
- CETERM: 2.9M+ technical terms database

---

## Estimated Token Usage

This session should use ~50,000-76,000 tokens:
- Reading code: ~8,000
- Segmenter implementation: ~20,000
- Glossary creation + integration: ~18,000
- Testing + benchmarking: ~15,000
- Commits + documentation: ~5,000

With fresh token budget, should complete comfortably.

---

## Done in Previous Session

✅ v4 Translation Completeness Initiative (All 3 phases complete)
  - Phase 1: Post-processing validation & recovery (48 tests)
  - Phase 2: Clause-level translation fallback (47 tests)
  - Phase 3: Adaptive orchestration (44 tests)
  - Total: 110+ tests, all passing

✅ Research Validation
  - Approach validated against 21+ academic sources
  - BLEU improvements documented (2.94-5.43 points)

✅ Domain-Specific Research (Priority 1-4 roadmap created)
  - Identified bottlenecks (jieba segmentation, CC-CEDICT gaps)
  - Research-backed solutions (PKUSEG, HanLP, glossaries, fine-tuning)
  - Total potential improvement: 12-25% across all priorities

---

**Everything is clean, committed, and ready to go. Good luck with Priority 1!**
