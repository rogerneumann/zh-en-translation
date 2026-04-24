# Fine-Tuning Setup Guide

Quick-start for the GPU fine-tuning session (Priority 3 execution).

**Pre-reading:** See `FINETUNING_PLAN.md` for full architecture design.  
**Status:** Scaffolding complete. Implement `trainer.py::FineTuneTrainer.train()` in the GPU session.

---

## Prerequisites

### Hardware
- NVIDIA GPU with **8 GB+ VRAM** (tested target: RTX 3090 24 GB)
- 16 GB+ system RAM
- 20 GB+ free disk space (model checkpoints, training data)

### Software
- Python 3.11+ (matches project requirement)
- CUDA 11.8+ (`nvidia-smi` should show driver >= 520)
- cuDNN 8.6+ (bundled with PyTorch wheels, no separate install needed)
- PyTorch 2.0+ with CUDA support
- OpenNMT-py 3.0+
- CTranslate2 3.0+ (for model conversion)

### Verify CUDA setup
```bash
python -c "import torch; print(torch.cuda.is_available(), torch.version.cuda)"
# Expected: True  11.8  (or 12.x)

nvidia-smi
# Should show GPU name, driver version, CUDA version
```

---

## Installation

### 1. Install finetuning extras
```bash
cd /path/to/zh-en-translation
pip install -e ".[finetuning]"
```

This installs: `opennmt-py>=3.0`, `ctranslate2>=3.0`, `sentencepiece>=0.1.99`, `torch>=2.0`.

### 2. Verify the finetuning module loads
```bash
python -c "from zh_en_translator.finetuning import FineTuningConfig, FineTuneTrainer; print('OK')"
```

### 3. Run the data-pipeline tests (no GPU needed)
```bash
pytest tests/test_finetuning_prep.py -v
# All 15+ tests should pass
```

---

## Preparing the Corpus

### Step 1: Expand manufacturing samples to 100+ sentences

The current corpus has 20 verified pairs. Before training, expand to at least 100:

```bash
# Check current count
python -c "
from zh_en_translator.corpus import CorpusManager
from zh_en_translator.corpus.corpus_manager import get_examples_dir
mgr = CorpusManager()
mgr.load_directory(get_examples_dir())
print(mgr.stats())
"
```

Add new entries to:
`src/zh_en_translator/corpus/examples/manufacturing_samples.jsonl`

Each line is a JSON object with fields: `source`, `chinese`, `english`, `domain`, `verified`.

### Step 2: Verify data pipeline

```bash
python -c "
from zh_en_translator.finetuning.data_preparation import load_corpus, split_train_val, prepare_training_data
from zh_en_translator.corpus.corpus_manager import get_examples_dir

corpus_path = get_examples_dir() / 'manufacturing_samples.jsonl'
entries = load_corpus(corpus_path)
train, val = split_train_val(entries, ratio=0.1)
dataset = prepare_training_data(train)
print(f'Train: {len(train)}, Val: {len(val)}, Pairs: {len(dataset)}')
"
```

---

## Running Fine-Tuning

### Quick Start

```python
from pathlib import Path
from zh_en_translator.finetuning.config import FineTuningConfig
from zh_en_translator.finetuning.trainer import FineTuneTrainer
from zh_en_translator.finetuning.data_preparation import (
    load_corpus, split_train_val, prepare_training_data
)
from zh_en_translator.corpus.corpus_manager import get_examples_dir

# 1. Configure
config = FineTuningConfig(
    corpus_path=get_examples_dir() / "manufacturing_samples.jsonl",
    output_dir=Path("finetuning_output"),
    device="cuda",           # or "cpu" for testing
    epochs=20,
    batch_size=32,
    learning_rate=1e-4,
)
config.validate()

# 2. Load data
entries = load_corpus(config.corpus_path)
train_entries, val_entries = split_train_val(entries, ratio=config.validation_split)
train_data = prepare_training_data(train_entries)
val_data = prepare_training_data(val_entries)

# 3. Train  (implement trainer.py::FineTuneTrainer.train() first)
trainer = FineTuneTrainer(config, model=None)  # pass your loaded model
history = trainer.train(train_data, val_data)
trainer.save_model(config.output_dir / "finetuned_model")

print(history)
```

### What to implement in the GPU session

The only file that needs GPU-specific implementation is:
`src/zh_en_translator/finetuning/trainer.py`

The key method stub is `FineTuneTrainer.train()`. See the file's docstring for the expected contract.

The data pipeline (`data_preparation.py`) and configuration (`config.py`) are already fully working.

---

## Expected Outputs

After a successful training run, `finetuning_output/` will contain:

```
finetuning_output/
    finetuned_model/           <- CTranslate2 model directory
        model.bin
        source_vocabulary.json
        target_vocabulary.json
    checkpoints/               <- OpenNMT-py checkpoints (optional, large)
        step_500.pt
        step_1000.pt
        ...
    training_history.json      <- Loss + BLEU by epoch
    eval_results.json          <- BLEU improvement vs. baseline
```

### Expected BLEU gains
- Manufacturing test set (10-15 held-out sentences): **+4-8 BLEU points**
- General Chinese text: **no degradation** (or < 1 BLEU point loss)

---

## Evaluating the Fine-Tuned Model

```python
from zh_en_translator.finetuning.evaluation import (
    evaluate_finetuned_model,
    compute_bleu_improvement,
)

# After loading both models and the test corpus:
improvement = compute_bleu_improvement(baseline_results, finetuned_results)
print(f"BLEU improvement: +{improvement:.2f} points")
```

---

## Integrating the Fine-Tuned Model

Once you have a fine-tuned CTranslate2 model:

1. Copy the `finetuned_model/` directory to the Argos package path:
   - Linux: `~/.local/share/argos-translate/packages/translate-zh_en-1.9/model_finetuned/`
   - Windows: `%APPDATA%\argos-translate\packages\translate-zh_en-1.9\model_finetuned\`

2. In `src/zh_en_translator/engines/argos.py`, add model selection:
   ```python
   model_path = finetuned_path if finetuned_path.exists() else base_path
   ```

3. Add a config toggle: `use_finetuned_model = true` in the app config.

---

## Troubleshooting

### CUDA out of memory
Reduce `batch_size` from 32 to 16, or use gradient accumulation:
```python
config = FineTuningConfig(..., batch_size=16, gradient_accumulation_steps=2)
```

### OpenNMT-py version mismatch
```bash
pip install "opennmt-py>=3.0,<4.0"
python -c "import onmt; print(onmt.__version__)"
```

### CTranslate2 conversion errors
Ensure you are using the same sentencepiece vocabulary as the Argos base model.
The vocabulary file is at the Argos package path (`sentencepiece.model`).

### Validation BLEU not improving
- Check that `val_data` includes diverse manufacturing sentences
- Verify the general corpus mix ratio (should be ~70%)
- Try lowering learning rate to 5e-5

---

## References

- OpenNMT-py fine-tuning guide: https://opennmt.net/OpenNMT-py/options/train.html
- CTranslate2 model conversion: https://opennmt.net/CTranslate2/conversion.html
- Argos Translate model format: https://github.com/argosopentech/argos-translate
- SentencePiece tokenization: https://github.com/google/sentencepiece
