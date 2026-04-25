# Priority 3: GPU Training Implementation Guide

**Status:** Ready for implementation on GPU hardware  
**Estimated Time:** 2-4 hours on RTX 3090 (training + evaluation)  
**Expected Outcome:** +4-8 BLEU improvement on manufacturing domain

---

## Overview

This guide provides step-by-step instructions for implementing `FineTuneTrainer.train()` in `src/zh_en_translator/finetuning/trainer.py`.

The scaffold is 90% complete. You need to implement ONE method with 9 clear steps.

---

## Prerequisites

```bash
# Install GPU dependencies
pip install .[finetuning]

# Verify
python -c "import torch; print(f'PyTorch: {torch.__version__}'); print(f'CUDA: {torch.cuda.is_available()}')"
python -c "import opennmt; print(f'OpenNMT-py: {opennmt.__version__}')"
```

**Required:**
- PyTorch 2.0+ with CUDA support
- OpenNMT-py 3.0+
- CTranslate2 3.0+
- SentencePiece 0.1.99+
- 8GB+ VRAM (RTX 3090, A100, etc.)

---

## Implementation Steps

### Step 1-2: Model Conversion Utilities

Create `src/zh_en_translator/finetuning/model_conversion.py`:

```python
"""Convert between Argos CTranslate2 and OpenNMT-py model formats."""

import torch
import json
from pathlib import Path
import tempfile
from typing import Dict, Any

def argos_to_opennmt(argos_model_path: str | Path) -> Dict[str, Any]:
    """Load Argos CTranslate2 model and prepare for OpenNMT-py.
    
    Args:
        argos_model_path: Path to Argos zh->en CTranslate2 model
        
    Returns:
        Dict with model weights, vocab, config ready for OpenNMT-py
    """
    import ctranslate2
    
    # Load Argos model
    model = ctranslate2.models.Model(str(argos_model_path))
    
    # Extract vocab (from model or use SentencePiece)
    # Note: Argos uses its own tokenization; you may need to:
    # 1. Extract vocab from model metadata
    # 2. Or train new SentencePiece vocab on corpus
    
    return {
        "model": model,
        "device": "cuda" if torch.cuda.is_available() else "cpu",
    }

def opennmt_to_ctranslate2(opennmt_checkpoint: Path, output_path: Path) -> None:
    """Convert trained OpenNMT-py checkpoint back to CTranslate2 format.
    
    Args:
        opennmt_checkpoint: Path to best OpenNMT-py checkpoint
        output_path: Where to save CTranslate2 model
    """
    import opennmt
    import ctranslate2
    
    # Load OpenNMT checkpoint
    model = opennmt.models.SequenceToSequence.from_checkpoint(str(opennmt_checkpoint))
    
    # Convert to CTranslate2
    # Use ctranslate2's conversion tools
    ctranslate2.converters.OpenNMTConverter(
        str(opennmt_checkpoint),
        str(output_path),
        output_format="ctranslate2"
    ).convert()
    
    print(f"Model converted to CTranslate2 at {output_path}")
```

### Step 3-5: Dataset Preparation

Use existing `data_preparation.py` functions:

```python
from zh_en_translator.finetuning.data_preparation import (
    load_corpus,
    split_train_val,
    prepare_training_data,
)

# Load corpus
corpus = load_corpus(config.corpus_path)

# Split into train/val (90/10)
train_data, val_data = split_train_val(corpus, ratio=0.1)

# Prepare for training
train_pairs = prepare_training_data(train_data)
val_pairs = prepare_training_data(val_data)

# Tokenize with SentencePiece (or use Argos tokenizer)
import sentencepiece as spm
vocab_model = spm.SentencePieceProcessor()
# Train or load vocab: vocab_model = spm.load(existing_vocab)
```

### Step 6-7: Training Loop

```python
import opennmt
from opennmt.models import SequenceToSequence
from opennmt.config import load_config
from opennmt.runners import Runner

def create_opennmt_trainer(config, base_model_path):
    """Set up OpenNMT-py trainer with manufacturing-specific config."""
    
    # OpenNMT config (can be YAML or dict)
    opennmt_config = {
        "model": "Transformer",
        "params": {
            "num_layers": 6,
            "num_units": 512,
            "num_heads": 8,
            "ffn_inner_dim": 2048,
            "dropout": 0.1,
            "attention_dropout": 0.1,
            "ffn_dropout": 0.1,
        },
        "optimizer": "Adam",
        "optimizer_params": {
            "beta_1": 0.9,
            "beta_2": 0.998,
            "epsilon": 1e-9,
        },
        "learning_rate": 2.0,
        "learning_rate_decay": {
            "type": "exponential_decay",
            "decay_steps": 1000,
            "decay_rate": 0.98,
        },
        "label_smoothing": 0.1,
        "batch_size": 32,
        "batch_type": "tokens",
        "num_buckets": 32,
        "bucket_width": 50,
        "sample_buffer_size": 100000,
        "maximum_features_length": 150,
        "maximum_target_length": 150,
    }
    
    model = SequenceToSequence(
        "Transformer",
        num_layers=opennmt_config["params"]["num_layers"],
        num_units=opennmt_config["params"]["num_units"],
        num_heads=opennmt_config["params"]["num_heads"],
    )
    
    runner = Runner(
        model,
        dict(train=train_file, valid=val_file),
        opennmt_config["optimizer_params"],
        devices=["cuda" if torch.cuda.is_available() else "cpu"],
        model_dir="checkpoints",
        mixed_precision="float16" if torch.cuda.is_available() else None,
    )
    
    return runner

def train_with_early_stopping(runner, num_epochs=20, patience=3):
    """Train with early stopping on validation BLEU."""
    best_bleu = 0.0
    patience_counter = 0
    
    for epoch in range(1, num_epochs + 1):
        # Train one epoch
        runner.train(num_epochs=1)
        
        # Evaluate on validation set
        val_bleu = runner.evaluate(validation_data, metric="bleu")
        
        print(f"Epoch {epoch}: Val BLEU = {val_bleu:.2f}")
        
        # Early stopping
        if val_bleu > best_bleu:
            best_bleu = val_bleu
            patience_counter = 0
            runner.checkpoint()  # Save best checkpoint
        else:
            patience_counter += 1
            if patience_counter >= patience:
                print(f"Early stopping at epoch {epoch}")
                break
    
    return best_bleu
```

### Step 8-9: Integration

```python
def train(
    self,
    train_data: list["TrainingPair"],
    val_data: list["TrainingPair"],
) -> "TrainingHistory":
    """Full 9-step fine-tuning process."""
    
    # 1-2: Load and convert Argos model
    model_info = argos_to_opennmt(self.config.argos_model_path)
    
    # 3-5: Prepare corpus (already working)
    train_pairs = prepare_training_data(train_data)
    val_pairs = prepare_training_data(val_data)
    
    # Write to OpenNMT-py format files
    write_opennmt_dataset(train_pairs, "train.txt")
    write_opennmt_dataset(val_pairs, "valid.txt")
    
    # 6-7: Train with early stopping
    runner = create_opennmt_trainer(self.config, model_info["model"])
    best_bleu = train_with_early_stopping(runner, num_epochs=self.config.epochs)
    
    # 8: Save best checkpoint (done by early stopping)
    best_checkpoint = Path(runner.model_dir) / "best_checkpoint"
    
    # 9: Convert back to CTranslate2
    output_model = Path(self.config.output_dir) / "finetuned_model"
    opennmt_to_ctranslate2(best_checkpoint, output_model)
    
    # Return training history
    self._history = TrainingHistory(
        losses=[...],  # from runner training loop
        val_bleues=[best_bleu],
        best_checkpoint=best_checkpoint,
        final_model=output_model,
    )
    
    return self._history
```

---

## Running the Training

```bash
# Create config
cat > finetuning_config.yaml << EOF
corpus_path: src/zh_en_translator/corpus/examples/manufacturing_samples.jsonl
output_dir: ./finetuned_models
argos_model_path: ~/.local/share/argos-translate/packages/translate-zh_en-1.3
batch_size: 32
learning_rate: 0.001
epochs: 20
validation_split: 0.1
in_domain_ratio: 0.3
device: cuda
EOF

# Run training
python -m zh_en_translator.finetuning.train --config finetuning_config.yaml
```

---

## Expected Output

```
Epoch 1: Train Loss = 4.23, Val BLEU = 0.15
Epoch 2: Train Loss = 3.87, Val BLEU = 0.19
Epoch 3: Train Loss = 3.45, Val BLEU = 0.24
...
Epoch 15: Train Loss = 1.12, Val BLEU = 0.31
Epoch 16: Early stopping at epoch 16

Best validation BLEU: 0.31
Model saved to: ./finetuned_models/finetuned_model

Expected improvement: +4-8 BLEU on manufacturing domain
(Baseline Jieba+Glossary ≈ 0.23, Fine-tuned ≈ 0.31)
```

---

## Troubleshooting

**CUDA Out of Memory:**
- Reduce batch_size: 32 → 16 or 8
- Reduce num_units: 512 → 256
- Use mixed precision (already in config)

**Slow Training:**
- Check GPU utilization: `nvidia-smi`
- Increase batch_size if VRAM available
- Use gradient accumulation

**Low Validation BLEU:**
- Increase corpus size (currently 100 sentences)
- Adjust learning rate
- Train longer (increase epochs)

---

## Integration with Main Pipeline

After training, integrate fine-tuned model:

```python
# In translation_worker.py or app.py
from pathlib import Path

finetuned_model_path = Path("finetuned_models/finetuned_model")

if finetuned_model_path.exists():
    # Use fine-tuned model for technical domains
    result = translate_sentence_finetuned(text, finetuned_model_path)
else:
    # Fallback to Argos baseline
    result = translate_sentence_argos(text)
```

---

## Success Metrics

✅ Training completes without errors  
✅ Validation BLEU increases over epochs  
✅ Final model saves successfully  
✅ CTranslate2 conversion succeeds  
✅ +4-8 BLEU improvement on test set  
✅ Model integrates with main pipeline

---

## References

- OpenNMT-py: https://opennmt.net/
- CTranslate2: https://opennmt.net/CTranslate2/
- SentencePiece: https://github.com/google/sentencepiece
- PyTorch: https://pytorch.org/

---

**Ready to implement? Follow the 9 steps above with your GPU hardware!**
