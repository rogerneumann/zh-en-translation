"""Fine-tuning infrastructure for domain-specific model adaptation.

Provides configuration, data preparation, training scaffold, and evaluation
utilities for fine-tuning the Argos zh->en model on manufacturing corpora.

GPU training is NOT performed here -- this module provides the planning
scaffolding and data pipeline.  Implement ``FineTuneTrainer.train()`` in
the dedicated GPU training session.

Entry points:
    FineTuningConfig    -- training hyperparameters & paths (implemented)
    FineTuneTrainer     -- trainer scaffold (train() stub, GPU session fills in)
    load_corpus         -- load a JSONL corpus via CorpusManager
    split_train_val     -- 90/10 train/validation split
    prepare_training_data  -- format corpus entries as (src, tgt) pairs
"""

from zh_en_translator.finetuning.config import FineTuningConfig
from zh_en_translator.finetuning.trainer import FineTuneTrainer
from zh_en_translator.finetuning.data_preparation import (
    load_corpus,
    split_train_val,
    prepare_training_data,
    build_vocabulary,
)

__all__ = [
    "FineTuningConfig",
    "FineTuneTrainer",
    "load_corpus",
    "split_train_val",
    "prepare_training_data",
    "build_vocabulary",
]
