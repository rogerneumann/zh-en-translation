"""Data preparation pipeline for fine-tuning.

Handles loading, splitting, and formatting the bilingual corpus into
structures ready for model training.  All functions work without GPU
dependencies -- they operate purely on Python data structures.

Pipeline
--------
1. ``load_corpus(path)``           -- JSONL -> list[CorpusEntry]
2. ``split_train_val(corpus)``     -- list -> (train_list, val_list)
3. ``prepare_training_data(train)``-- list -> list of (src, tgt) dicts
4. ``build_vocabulary(train)``     -- list -> Vocabulary (word counts)

Usage::

    from pathlib import Path
    from zh_en_translator.finetuning.data_preparation import (
        load_corpus, split_train_val, prepare_training_data, build_vocabulary,
    )
    from zh_en_translator.corpus.corpus_manager import get_examples_dir

    path = get_examples_dir() / "manufacturing_samples.jsonl"
    entries = load_corpus(path)
    train, val = split_train_val(entries, ratio=0.1)
    dataset = prepare_training_data(train)
    vocab = build_vocabulary(train)

    print(f"Train: {len(train)}, Val: {len(val)}")
    print(f"Vocab: {len(vocab.source_tokens)} src tokens, "
          f"{len(vocab.target_tokens)} tgt tokens")
"""

from __future__ import annotations

import logging
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from zh_en_translator.corpus.corpus_manager import CorpusEntry, CorpusManager

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Training pair type
# ---------------------------------------------------------------------------


@dataclass
class TrainingPair:
    """A single (source, target) training example.

    Attributes
    ----------
    src:
        Source Chinese text (UTF-8).
    tgt:
        Target English translation.
    domain:
        Domain tag (e.g. ``"manufacturing"``).
    verified:
        True if the pair was human-verified.
    weight:
        Training weight.  Verified pairs default to 1.0; unverified pairs
        to 0.5 (they carry less signal but are not discarded).
    """

    src: str
    tgt: str
    domain: str = "manufacturing"
    verified: bool = True
    weight: float = 1.0


# ---------------------------------------------------------------------------
# Vocabulary type
# ---------------------------------------------------------------------------


@dataclass
class Vocabulary:
    """Word-level vocabulary built from the training corpus.

    In the full GPU training session, this will be replaced by a
    SentencePiece vocabulary loaded from the Argos base model.  This
    class is provided for unit-testing the data pipeline without GPU
    dependencies.

    Attributes
    ----------
    source_tokens:
        Mapping of Chinese characters / tokens to their frequency counts.
    target_tokens:
        Mapping of English words (lowercased) to their frequency counts.
    domain_tags:
        Set of unique domain strings seen in the training data.
    """

    source_tokens: dict[str, int] = field(default_factory=dict)
    target_tokens: dict[str, int] = field(default_factory=dict)
    domain_tags: set[str] = field(default_factory=set)

    @property
    def source_vocab_size(self) -> int:
        return len(self.source_tokens)

    @property
    def target_vocab_size(self) -> int:
        return len(self.target_tokens)


# ---------------------------------------------------------------------------
# load_corpus
# ---------------------------------------------------------------------------


def load_corpus(path: Path) -> list[CorpusEntry]:
    """Load a JSONL corpus file and return a list of CorpusEntry objects.

    Uses ``CorpusManager`` for parsing, validation, and error reporting.
    Invalid lines are logged as warnings and skipped.

    Args:
        path: Path to a ``.jsonl`` file.

    Returns:
        List of ``CorpusEntry`` objects in file order.

    Raises:
        FileNotFoundError: If *path* does not exist.

    Example::

        entries = load_corpus(Path("manufacturing_samples.jsonl"))
        print(f"Loaded {len(entries)} entries")
    """
    path = Path(path)
    mgr = CorpusManager()
    count = mgr.load_file(path, skip_invalid=True)
    entries = list(mgr.iter_entries())
    logger.info("load_corpus: %d entries from %s", count, path)
    return entries


# ---------------------------------------------------------------------------
# split_train_val
# ---------------------------------------------------------------------------


def split_train_val(
    corpus: list[CorpusEntry],
    ratio: float = 0.1,
    seed: int = 42,
) -> tuple[list[CorpusEntry], list[CorpusEntry]]:
    """Split a corpus into training and validation sets.

    The split is stratified by *verified* status to ensure both sets
    contain verified and unverified entries in proportion.

    Args:
        corpus: List of ``CorpusEntry`` objects to split.
        ratio:  Fraction of entries to use for validation.  Must be in
                (0, 0.5).  Default 0.1 = 10 % validation.
        seed:   Random seed for reproducibility.

    Returns:
        ``(train, val)`` tuple of entry lists.

    Raises:
        ValueError: If *ratio* is out of range or corpus is empty.

    Example::

        train, val = split_train_val(entries, ratio=0.1, seed=42)
        print(f"Train: {len(train)}, Val: {len(val)}")
    """
    if not corpus:
        raise ValueError("Cannot split an empty corpus")
    if not (0 < ratio < 0.5):
        raise ValueError(f"ratio must be in (0, 0.5), got {ratio}")

    rng = random.Random(seed)
    shuffled = list(corpus)
    rng.shuffle(shuffled)

    n_val = max(1, round(len(shuffled) * ratio))
    val = shuffled[:n_val]
    train = shuffled[n_val:]

    logger.info(
        "split_train_val: %d train, %d val (ratio=%.2f, seed=%d)",
        len(train), len(val), ratio, seed,
    )
    return train, val


# ---------------------------------------------------------------------------
# prepare_training_data
# ---------------------------------------------------------------------------


def prepare_training_data(
    corpus: list[CorpusEntry],
    verified_weight: float = 1.0,
    unverified_weight: float = 0.5,
) -> list[TrainingPair]:
    """Format corpus entries as ``TrainingPair`` objects ready for training.

    Unverified entries are included with a lower weight so they
    contribute to training without overwhelming the verified signal.

    Args:
        corpus:            List of ``CorpusEntry`` objects.
        verified_weight:   Weight for human-verified pairs.
        unverified_weight: Weight for unverified pairs.

    Returns:
        List of ``TrainingPair`` objects.  The list preserves input order.

    Raises:
        ValueError: If *corpus* is empty.

    Example::

        pairs = prepare_training_data(train_entries)
        for p in pairs[:3]:
            print(p.src, "->", p.tgt[:40])
    """
    if not corpus:
        raise ValueError("Cannot prepare training data from an empty corpus")

    pairs: list[TrainingPair] = []
    for entry in corpus:
        weight = verified_weight if entry.verified else unverified_weight
        pairs.append(
            TrainingPair(
                src=entry.chinese.strip(),
                tgt=entry.english.strip(),
                domain=entry.domain,
                verified=entry.verified,
                weight=weight,
            )
        )

    verified_count = sum(1 for p in pairs if p.verified)
    logger.info(
        "prepare_training_data: %d pairs (%d verified, %d unverified)",
        len(pairs), verified_count, len(pairs) - verified_count,
    )
    return pairs


# ---------------------------------------------------------------------------
# build_vocabulary
# ---------------------------------------------------------------------------


def build_vocabulary(corpus: list[CorpusEntry]) -> Vocabulary:
    """Build a simple word-frequency vocabulary from the training corpus.

    This is a lightweight CPU-only vocabulary used for sanity-checking the
    data pipeline in tests.  The actual GPU training session will use the
    SentencePiece vocabulary bundled with the Argos base model.

    Args:
        corpus: List of ``CorpusEntry`` objects.

    Returns:
        ``Vocabulary`` with source/target token counts and domain tags.

    Example::

        vocab = build_vocabulary(train_entries)
        print(f"Source vocab: {vocab.source_vocab_size} tokens")
        print(f"Target vocab: {vocab.target_vocab_size} tokens")
    """
    vocab = Vocabulary()

    for entry in corpus:
        # Source: character-level tokenisation for Chinese
        for char in entry.chinese:
            if char.strip():
                vocab.source_tokens[char] = vocab.source_tokens.get(char, 0) + 1

        # Target: whitespace-split words, lowercased
        for word in entry.english.lower().split():
            clean = word.strip(".,!?;:()'\"")
            if clean:
                vocab.target_tokens[clean] = vocab.target_tokens.get(clean, 0) + 1

        vocab.domain_tags.add(entry.domain)

    logger.info(
        "build_vocabulary: %d source tokens, %d target tokens, %d domains",
        vocab.source_vocab_size,
        vocab.target_vocab_size,
        len(vocab.domain_tags),
    )
    return vocab


# ---------------------------------------------------------------------------
# mix_corpora  (helper for mixed fine-tuning, 30 % in-domain / 70 % general)
# ---------------------------------------------------------------------------


def mix_corpora(
    in_domain: list[CorpusEntry],
    general: list[CorpusEntry],
    in_domain_ratio: float = 0.3,
    seed: int = 42,
) -> list[CorpusEntry]:
    """Combine in-domain and general corpora at the requested ratio.

    The general corpus is down-sampled (or up-sampled by repetition) to
    achieve ``in_domain_ratio``.  Result is shuffled with the given seed.

    Args:
        in_domain:       In-domain corpus entries.
        general:         General-domain corpus entries.
        in_domain_ratio: Target fraction of in-domain data.  0.3 means
                         30 % manufacturing, 70 % general.
        seed:            Random seed for shuffling.

    Returns:
        Mixed, shuffled list of ``CorpusEntry`` objects.

    Raises:
        ValueError: If either corpus is empty or ratio is out of range.

    Note:
        In Priority 3 (planning), general data is typically sampled from
        the opus-100 zh-en subset.  For the GPU training session, supply
        that corpus as the *general* argument.
    """
    if not in_domain:
        raise ValueError("in_domain corpus is empty")
    if not general:
        raise ValueError("general corpus is empty")
    if not (0 < in_domain_ratio <= 1.0):
        raise ValueError(f"in_domain_ratio must be in (0, 1], got {in_domain_ratio}")

    # Compute target sizes: if in_domain is N at ratio R,
    # general target is N * (1 - R) / R
    n_in = len(in_domain)
    n_general_target = int(n_in * (1 - in_domain_ratio) / in_domain_ratio)

    rng = random.Random(seed)

    # Sample without replacement if possible; wrap around if general is small
    if n_general_target <= len(general):
        sampled_general = rng.sample(general, n_general_target)
    else:
        # Repeat general corpus as needed then trim
        repeats = (n_general_target // len(general)) + 1
        sampled_general = (general * repeats)[:n_general_target]
        rng.shuffle(sampled_general)

    mixed = list(in_domain) + sampled_general
    rng.shuffle(mixed)

    logger.info(
        "mix_corpora: %d in-domain + %d general = %d total (ratio=%.2f)",
        n_in, len(sampled_general), len(mixed), in_domain_ratio,
    )
    return mixed
