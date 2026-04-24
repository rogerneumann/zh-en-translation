"""Corpus management for zh-en-translator domain adaptation.

Provides utilities for loading, validating, and versioning bilingual sentence
corpora used for translation quality evaluation and model fine-tuning.

Entry points:
    CorpusManager     -- load and iterate corpus files (JSONL format)
    CorpusEntry       -- typed dataclass for a single sentence pair
    CORPUS_SCHEMA     -- JSON schema fields for corpus entries
"""

from zh_en_translator.corpus.corpus_manager import (
    CorpusEntry,
    CorpusManager,
    CORPUS_SCHEMA,
)

__all__ = ["CorpusEntry", "CorpusManager", "CORPUS_SCHEMA"]
