# Fine-Tuning Architecture Plan

Domain-specific fine-tuning of the Argos zh->en translation model on manufacturing text.

**Status:** Planning complete (2026-04-24) -- GPU training session pending  
**Branch:** `claude/fix-translation-completeness-8L9yn`  
**Expected gain:** +4-8 BLEU points on manufacturing/technical text

---

## 1. Objective

The base Argos model (Helsinki-NLP/opus-mt-zh-en via CTranslate2) is trained on general parallel corpora. It under-performs on:
- Manufacturing-specific vocabulary (e.g., 形位公差, 渗碳淬火, 阳极氧化)
- Technical standard citations (GB/T, ISO, JB/T)
- Specification-style sentences with numeric tolerances

Priority 3 fine-tunes the model on a curated manufacturing corpus to close this gap, without degrading general-domain quality.

---

## 2. Approach: Mixed Fine-Tuning

### 2.1 Data Mix
- **30% in-domain:** Manufacturing parallel sentences (`manufacturing_samples.jsonl`, expanded to 100+)
- **70% general:** Sample from the original Argos training corpus (opus-100 zh-en subset)

This ratio prevents catastrophic forgetting while giving the model enough in-domain signal.

### 2.2 Framework: OpenNMT-py

Argos Translate packages use CTranslate2 models (derived from OpenNMT-py). We fine-tune the underlying Transformer at the OpenNMT-py level, then convert back to CTranslate2 format for deployment.

Pipeline:
```
manufacturing_samples.jsonl (in-domain)
        +
opus-100 general sample (70%)
        |
        v
OpenNMT-py data preparation (tokenize, BPE, vocab)
        |
        v
Fine-tune from Argos base checkpoint
        |
        v
ct2-opennmt-py-converter  ->  CTranslate2 model
        |
        v
Drop into Argos package directory  ->  use in translator
```

### 2.3 Base Model
The Argos zh->en model is located at:
```
~/.local/share/argos-translate/packages/translate-zh_en-1.9/
  model/                     <- CTranslate2 model
  sentencepiece.model        <- tokenizer
```

Convert to OpenNMT-py checkpoint before fine-tuning with `ct2-to-opennmt-py` (or fine-tune at the CTranslate2 level using `ctranslate2.converters`).

---

## 3. Data Preparation

### 3.1 Input Corpus
- **File:** `src/zh_en_translator/corpus/examples/manufacturing_samples.jsonl`
- **Current size:** 20 verified sentence pairs
- **Target size:** 100+ sentence pairs (expand before training session)
- **Fields used:** `chinese` (source), `english` (target), `verified`

### 3.2 Preprocessing Steps
1. Load JSONL via `CorpusManager`
2. Filter `verified=True` for training; include `verified=False` with lower weight
3. Apply SentencePiece tokenizer (same vocab as Argos base model)
4. Encode BPE subwords using the model's existing `sentencepiece.model`
5. Build training triplets: `(src_tokens, tgt_tokens, domain_tag)`
6. Split 90/10 train/validation

### 3.3 Mixed Corpus Construction
```python
# Pseudocode for mixing
in_domain = load_corpus("manufacturing_samples.jsonl")  # ~100 pairs
general = sample_general_corpus(n=int(len(in_domain) * 70 / 30))  # ~233 pairs
mixed = in_domain + general
shuffle(mixed, seed=42)
```

### 3.4 Augmentation (Priority 4 - not now)
Back-translation: translate English manufacturing texts back to Chinese to create synthetic pairs, 3-5x data expansion.

---

## 4. Training Configuration

### 4.1 Hyperparameters (Recommended Starting Point)

| Parameter | Value | Rationale |
|---|---|---|
| `batch_size` | 32 | Standard for Transformer fine-tuning on single GPU |
| `learning_rate` | 1e-4 | Conservative; base model weights are pre-trained |
| `optimizer` | Adam (beta1=0.9, beta2=0.998) | OpenNMT default |
| `epochs` | 20 | With early stopping; small corpus trains fast |
| `warmup_steps` | 500 | ~10% of total steps for smooth convergence |
| `dropout` | 0.1 | Regularization against overfitting on small corpus |
| `label_smoothing` | 0.1 | Reduces overconfidence on rare manufacturing terms |
| `in_domain_ratio` | 0.3 | 30% manufacturing, 70% general |
| `validation_split` | 0.1 | 10% held out for early stopping |
| `seed` | 42 | Reproducibility |

### 4.2 Early Stopping
- Monitor validation BLEU every 500 steps
- Stop if no improvement for 5 consecutive checks (2500 steps)
- Save best checkpoint by validation BLEU

### 4.3 Expected Training Time
- Hardware: RTX 3090 (24 GB VRAM) or equivalent
- Corpus: ~330 sentence pairs (100 in-domain + 233 general)
- Estimated: **2-4 hours** for 20 epochs
- On CPU: not recommended (estimated 10-20x slower)

---

## 5. Evaluation Protocol

### 5.1 Test Set
- Hold out 10-15 manufacturing sentences (not used in training)
- Include sentences covering: tolerances, surface treatment, heat treatment, standards
- Reference translations verified by domain knowledge

### 5.2 Metrics
1. **BLEU** (primary): Compare baseline Argos vs. fine-tuned model on test set
2. **CER** (secondary): Character Error Rate for spot-checking
3. **Glossary coverage**: Fraction of manufacturing terms correctly translated
4. **Manual review**: 5-10 sentences reviewed by a manufacturing domain expert (or native speaker familiar with technical text)

### 5.3 Expected Outcomes

| Metric | Baseline | Fine-tuned | Expected Delta |
|---|---|---|---|
| BLEU (manufacturing) | ~0.35 | ~0.43-0.50 | +8-15 BLEU pts (absolute) |
| Glossary coverage | ~0.60 | ~0.80-0.90 | +20-30% |
| CER | ~0.30 | ~0.20-0.25 | -5-10% |

Note: BLEU is reported on a 0-1 scale internally; multiply by 100 for standard BLEU scores.

### 5.4 Integration Test
After fine-tuning, run the full A/B test harness:
```python
from zh_en_translator.evaluation import ABTestRunner, ABTestConfig

config_baseline = ABTestConfig(name="argos_base", ...)
config_finetuned = ABTestConfig(name="argos_finetuned", ...)
runner = ABTestRunner(manufacturing_test_sentences)
results = runner.run([config_baseline, config_finetuned])
```

---

## 6. Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Catastrophic forgetting | Medium | High | 70% general data mix; early stopping |
| Overfitting (small corpus) | High | Medium | Dropout=0.1, label smoothing, validation monitoring |
| Corpus too small (<100 pairs) | High | Medium | Back-translation augmentation (Priority 4) |
| BPE vocab mismatch | Low | High | Reuse Argos sentencepiece.model exactly |
| CTranslate2 conversion errors | Low | High | Test conversion on base model first (dry run) |
| VRAM OOM (16GB GPU) | Medium | Low | Reduce batch_size to 16; use gradient accumulation |

---

## 7. Deployment

After fine-tuning:
1. Convert CTranslate2: `ct2-opennmt-py-converter --model_path finetuned/ --output_dir ct2_finetuned/`
2. Replace model directory in Argos package path
3. Keep original model as fallback: `model_base/`
4. Add config option: `translation_model = "base" | "finetuned"` (default: finetuned if present)

---

## 8. Priority 4 Preview (Back-Translation)

After Priority 3 fine-tuning succeeds:
- Use the fine-tuned model to back-translate English manufacturing documentation
- Generate 3-5x synthetic Chinese-English pairs
- Re-fine-tune with the augmented corpus for another +2-4 BLEU improvement

---

## 9. File Map

```
src/zh_en_translator/finetuning/
    __init__.py                 -- module exports
    config.py                   -- FineTuningConfig dataclass (implemented)
    data_preparation.py         -- corpus loading & splitting pipeline (implemented)
    trainer.py                  -- FineTuneTrainer scaffold (GPU session implements train())
    evaluation.py               -- BLEU improvement metrics (scaffold)

tests/
    test_finetuning_prep.py     -- 15+ tests for config + data pipeline (no GPU needed)

FINETUNING_PLAN.md              -- this file
FINETUNING_SETUP.md             -- prerequisites & quick-start for GPU session
```
