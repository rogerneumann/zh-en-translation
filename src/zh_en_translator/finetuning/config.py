"""Fine-tuning configuration dataclass.

Encapsulates all hyperparameters and path settings needed to run a fine-tuning
session.  Instances are serialisable to/from plain dicts for reproducibility.

Usage::

    from zh_en_translator.finetuning.config import FineTuningConfig
    from zh_en_translator.corpus.corpus_manager import get_examples_dir

    config = FineTuningConfig(
        corpus_path=get_examples_dir() / "manufacturing_samples.jsonl",
        output_dir=Path("finetuning_output"),
        device="cuda",
    )
    config.validate()          # raises ValueError on bad config
    d = config.to_dict()       # serialise
    config2 = FineTuningConfig.from_dict(d)  # deserialise
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Literal


@dataclass
class FineTuningConfig:
    """All parameters for a fine-tuning run.

    Attributes
    ----------
    corpus_path:
        Path to the in-domain JSONL corpus
        (e.g. ``manufacturing_samples.jsonl``).
    output_dir:
        Directory where the fine-tuned model, checkpoints, and training
        logs will be written.  Created if it does not exist.
    model_name:
        Identifier for the base model.  Default matches the Argos zh->en
        package distributed with this project.
    batch_size:
        Training batch size.  Reduce to 16 if VRAM < 16 GB.
    learning_rate:
        Initial learning rate.  1e-4 is conservative for fine-tuning
        pre-trained weights; try 5e-5 if BLEU plateaus early.
    epochs:
        Maximum training epochs.  Early stopping may terminate before this.
    warmup_steps:
        Linear LR warmup steps (~10 % of total steps is a good heuristic).
    dropout:
        Dropout probability applied during training for regularisation.
    label_smoothing:
        Label-smoothing epsilon to reduce overconfidence on rare terms.
    in_domain_ratio:
        Fraction of training data drawn from the in-domain corpus.
        0.3 = 30 % manufacturing, 70 % general.  Must be in (0, 1].
    validation_split:
        Fraction of the in-domain corpus held out for validation /
        early stopping.  Must be in (0, 0.5).
    seed:
        Random seed for shuffling and splitting.
    device:
        ``"cuda"`` for GPU training, ``"cpu"`` for CPU (slow but functional
        for smoke tests).
    gradient_accumulation_steps:
        Simulate a larger batch by accumulating gradients.  Useful when
        VRAM is limited (e.g. set batch_size=16, gradient_accumulation=2
        to match effective batch_size=32).
    save_every_n_steps:
        Checkpoint interval.  Set to 0 to disable intermediate checkpoints.
    early_stopping_patience:
        Number of consecutive validation checks without improvement before
        training stops.
    """

    # -- Paths --
    corpus_path: Path = field(default_factory=lambda: Path("manufacturing_samples.jsonl"))
    output_dir: Path = field(default_factory=lambda: Path("finetuning_output"))
    model_name: str = "Helsinki-NLP/opus-mt-zh-en"

    # -- Core hyperparameters --
    batch_size: int = 32
    learning_rate: float = 1e-4
    epochs: int = 20
    warmup_steps: int = 500
    dropout: float = 0.1
    label_smoothing: float = 0.1

    # -- Data mix --
    in_domain_ratio: float = 0.3   # 30 % in-domain, 70 % general
    validation_split: float = 0.1  # 10 % of in-domain for validation

    # -- Reproducibility --
    seed: int = 42

    # -- Hardware --
    device: Literal["cuda", "cpu"] = "cuda"
    gradient_accumulation_steps: int = 1

    # -- Checkpointing --
    save_every_n_steps: int = 500
    early_stopping_patience: int = 5

    # ------------------------------------------------------------------
    # Post-init coercion
    # ------------------------------------------------------------------

    def __post_init__(self) -> None:
        """Coerce string paths to Path objects after construction."""
        self.corpus_path = Path(self.corpus_path)
        self.output_dir = Path(self.output_dir)

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def validate(self) -> None:
        """Raise ``ValueError`` if any parameter is out of range.

        Does NOT require the corpus file to exist so that configs can be
        created speculatively.  Call ``validate(require_files=True)`` to
        also check paths.
        """
        errors: list[str] = []

        if not (0 < self.in_domain_ratio <= 1.0):
            errors.append(
                f"in_domain_ratio must be in (0, 1], got {self.in_domain_ratio}"
            )
        if not (0 < self.validation_split < 0.5):
            errors.append(
                f"validation_split must be in (0, 0.5), got {self.validation_split}"
            )
        if self.batch_size < 1:
            errors.append(f"batch_size must be >= 1, got {self.batch_size}")
        if self.learning_rate <= 0:
            errors.append(f"learning_rate must be > 0, got {self.learning_rate}")
        if self.epochs < 1:
            errors.append(f"epochs must be >= 1, got {self.epochs}")
        if self.warmup_steps < 0:
            errors.append(f"warmup_steps must be >= 0, got {self.warmup_steps}")
        if not (0.0 <= self.dropout < 1.0):
            errors.append(f"dropout must be in [0, 1), got {self.dropout}")
        if not (0.0 <= self.label_smoothing < 1.0):
            errors.append(
                f"label_smoothing must be in [0, 1), got {self.label_smoothing}"
            )
        if self.gradient_accumulation_steps < 1:
            errors.append(
                f"gradient_accumulation_steps must be >= 1, "
                f"got {self.gradient_accumulation_steps}"
            )
        if self.device not in ("cuda", "cpu"):
            errors.append(f"device must be 'cuda' or 'cpu', got {self.device!r}")

        if errors:
            raise ValueError("FineTuningConfig validation failed:\n" + "\n".join(errors))

    def validate_paths(self) -> None:
        """Raise ``FileNotFoundError`` if corpus_path does not exist."""
        if not self.corpus_path.exists():
            raise FileNotFoundError(
                f"Corpus file not found: {self.corpus_path}"
            )

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    def to_dict(self) -> dict:
        """Serialise to a JSON-compatible plain dict."""
        d = asdict(self)
        # Convert Path objects to strings for JSON serialisability
        d["corpus_path"] = str(self.corpus_path)
        d["output_dir"] = str(self.output_dir)
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "FineTuningConfig":
        """Deserialise from a plain dict (e.g. loaded from JSON)."""
        kwargs = dict(d)
        kwargs["corpus_path"] = Path(d["corpus_path"])
        kwargs["output_dir"] = Path(d["output_dir"])
        return cls(**kwargs)

    # ------------------------------------------------------------------
    # Convenience
    # ------------------------------------------------------------------

    @property
    def effective_batch_size(self) -> int:
        """Batch size after gradient accumulation."""
        return self.batch_size * self.gradient_accumulation_steps

    def is_cuda_available(self) -> bool:
        """Return True if a CUDA device is available at runtime.

        This is a lightweight check; it does NOT import torch to keep the
        module importable without GPU dependencies installed.
        """
        try:
            import torch  # type: ignore[import]
            return torch.cuda.is_available()
        except ImportError:
            return False

    def __repr__(self) -> str:
        return (
            f"FineTuningConfig("
            f"corpus={self.corpus_path.name}, "
            f"device={self.device}, "
            f"epochs={self.epochs}, "
            f"batch={self.batch_size}, "
            f"lr={self.learning_rate})"
        )
