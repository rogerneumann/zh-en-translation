# Translation Completeness Enhancement (v4)

**Status:** Planning ✅ | Phase 1 (In Progress) | Phase 2 (Pending) | Phase 3 (Pending)  
**Last Updated:** 2026-04-22 (Initial planning complete)

This plan addresses a critical gap in the current translation pipeline: **missing details and clauses** from the original Chinese in the final translation.

---

## Problem Statement

The app's sentence-level translation (via Argos/ctranslate2) drops clauses and details on complex Chinese sentences.

**Example:**
```
Original Chinese:    "NADCC氯片 200ppm 150ppm 100ppm浓度狗骨头浸泡测试已完成 实验室今天提供给@杨中宝"

Current output:      "NADCC chlorine tablets 200 ppm 150 ppm 100 ppm dog bone immersion test completed."

Missing:             "The laboratory provided the results to @YangZhongbao today."

Completeness rate:   ~60% (loses second clause entirely)
```

**Root Cause:**
Neural MT models (ctranslate2) can drop information on complex run-on sentences where:
- Multiple clauses lack explicit structural markers
- Chinese relies on implicit relationships (no conjunctions like "and")
- Sentences don't end with terminal punctuation (。)

The model treats the input as a single complex sequence and compresses content, losing less-salient clauses.

---

## Solution: Three-Phase Hybrid Approach

### Phase 1: Post-Processing Validation & Recovery (HIGHEST ROI)

**Objective:** After Argos translates, detect missing content and recover it using the word-by-word dictionary pipeline.

**How it works:**
1. Extract key content tokens from source Chinese (nouns, verbs, key terms)
2. Check if their English equivalents appear in the Argos output
3. For missing tokens, look up in CC-CEDICT + user glossary
4. Insert recovered translations intelligently into output

**Implementation files:**
- **NEW:** `src/zh_en_translator/engines/validation.py`
  - `extract_content_tokens(text, dictionary)` — Extract meaningful tokens using jieba POS tagging
  - `is_translation_complete(source_tokens, translation, dictionary)` — Check if all key content covered
  - `recover_missing_content(source, translation, missing_tokens, dictionary)` — Insert recovered terms
- **MODIFY:** `src/zh_en_translator/engines/translation_worker.py`
  - Integrate validation into `TranslationWorker.run()` after Argos translation
- **MODIFY:** `src/zh_en_translator/config.py`
  - Add `validation_enabled: bool = True`
  - Add `validation_completeness_threshold: float = 0.7`

**Performance:**
- Speed: 1.2x (single Argos call + validation analysis)
- Completeness gain: +30-50%
- Complexity: Medium
- Risk: Low (purely additive, fallback behavior)

**Example result:**
```
Input:   "NADCC氯片... 实验室今天提供给@杨中宝"
Current: "NADCC chlorine tablets... test completed."
Phase 1: "NADCC chlorine tablets... test completed. The laboratory provided the results to @YangZhongbao today."
```

---

### Phase 2: Clause-Level Translation (COMPLEX CASES)

**Objective:** For sentences where Phase 1 recovery doesn't suffice, split into clauses and translate each independently.

**How it works:**
1. Split Chinese by clause-ending punctuation (。！？；)
2. Protect patterns (URLs, emails, numbers like "200ppm")
3. Translate each clause with separate Argos call
4. Intelligently recombine with conjunctions and punctuation

**Implementation files:**
- **ENHANCE:** `src/zh_en_translator/engines/argos.py`
  - `split_into_clauses(text, max_clause_length=60)` — Split with protection for edge cases
  - `translate_with_clause_fallback(text)` — Fallback to clause-level if needed
  - `_recombine_translations(original, clauses, translations)` — Recombine with proper structure
- **MODIFY:** `src/zh_en_translator/engines/translation_worker.py`
  - Add conditional fallback: if Phase 1 incomplete, try Phase 2

**Performance:**
- Speed: 3-5x on complex sentences (multiple Argos calls) BUT only affects ~20% of input
- Completeness gain: +20-30% additional (50-70% total with Phase 1)
- Complexity: High (regex tuning for Chinese edge cases)
- Risk: Medium (performance on complex input, regex correctness)

**Example result:**
```
Input:   "测试已完成。实验室今天提供给@杨中宝。"
Phase 1: Handles first clause; misses second
Phase 2: Clause 1 (translated separately) + Clause 2 (translated separately) = "Test completed. The laboratory provided results to @YangZhongbao today."
```

---

### Phase 3: Adaptive Orchestration & Heuristics (OPTIMIZATION)

**Objective:** Decide per-sentence whether to use validation-only (fast) or clause-level (thorough) based on complexity.

**How it works:**
1. Heuristics detect sentence complexity (length, clause count, token count)
2. Simple sentences: Use Phase 1 only (1.2x speed)
3. Complex sentences: Use Phase 1 + Phase 2 (3-5x speed but better results)
4. Result: Adaptive 1.5x average speed with 50-70% completeness

**Implementation files:**
- **REFACTOR:** `src/zh_en_translator/engines/translation_worker.py`
  - `_should_use_clause_fallback(text, validation_result)` — Decide which path
  - Orchestrate validation + optional clause-level in `TranslationWorker.run()`

**Performance:**
- Speed: 1.5x average (adaptive)
- Completeness gain: 50-70% (final)
- Complexity: Medium (decision logic)
- Risk: Low (orchestration only, both phases tested independently)

---

## Implementation Sequence & Effort

| Phase | Effort | Speed Impact | Completeness Gain | Status |
|-------|--------|--------------|-------------------|--------|
| Phase 1 | 2-3 hrs | 1.2x | +30-50% | ⏳ In Progress |
| Phase 2 | 3-4 hrs | 3-5x (complex only) | +20-30% (total 50-70%) | 📅 Pending |
| Phase 3 | 2 hrs | 1.5x avg | — (optimization only) | 📅 Pending |
| **Total** | **7-9 hrs** | **1.5x avg** | **50-70%** | |

---

## Testing Strategy

### Phase 1 Tests
- `tests/test_validation.py` (NEW)
  - `test_extract_content_tokens()` — Extraction of meaningful tokens
  - `test_is_translation_complete()` — Detection of missing content
  - `test_recover_missing_content()` — Recovery and insertion logic

### Phase 2 Tests
- `tests/test_clause_translation.py` (NEW)
  - `test_split_into_clauses()` — Clause splitting with edge case protection
  - `test_translate_with_clause_fallback()` — Clause-level translation
  - `test_recombine_translations()` — Intelligent recombination

### Phase 3 Tests
- Integration tests verifying adaptive fallback decisions

---

## Expected Outcomes

### Completeness Metrics

| Metric | Current | Phase 1 | Phase 1+2 | Phase 1+2+3 |
|--------|---------|---------|-----------|-------------|
| Simple sentences (< 100 chars) | 95% | 98% | 98% | 98% |
| Complex sentences (100-200 chars) | 60% | 85% | 95% | 95% |
| Very complex (> 200 chars) | 40% | 60% | 90% | 90% |
| **Overall average** | **60%** | **85%** | **95%** | **95%** |

### Performance Impact

| Metric | Current | Phase 1 | Phase 1+2 | Phase 1+2+3 |
|--------|---------|---------|-----------|-------------|
| Avg. translation time | 1x | 1.2x | 2.5x* | 1.5x* |
| Max time (complex) | ~3s | ~3.5s | ~15s | ~4s |

*Phase 1+2: slower because all complex sentences use both paths  
*Phase 1+2+3: adaptive, avoids unnecessary clause-level on simple input

---

## Risk Mitigation

| Risk | Mitigation |
|------|-----------|
| Clause detection misses edge cases (numbers, URLs) | Comprehensive regex with protection patterns; test suite covers edge cases |
| Dictionary-based recovery inserts awkward phrasing | Context-aware insertion (sentence-end preferred, intelligent conjunctions) |
| Performance degradation on very long text | Phase 3 heuristics prevent unnecessary fallback; max text length cutoff |
| Recombination loses original punctuation semantics | Preserve original clause boundary punctuation (。→., ，→,) |

---

## Related Documentation

- **PLAN.md** — Core app architecture and v1 milestones
- **plan-v2.md** — v2 enhancements (history, DeepL, UI refresh)
- **plan-v3.md** — v3 improvements (quality, Tesseract, bundling, glossary)
- **progress.md** — Execution status and milestone tracking

---

## Notes

- All phases are **non-breaking** — app continues to work if validation/fallback disabled
- Validation/recovery can be feature-gated via `config.toml` for A/B testing
- Clause-level fallback only triggers on complex sentences (adaptive)
- Integration points minimize disruption to existing pipeline
