"""Tests for the Priority 3 fine-tuning data preparation pipeline.

All tests run without a GPU.  They cover:
- FineTuningConfig creation, validation, and serialisation
- load_corpus / split_train_val / prepare_training_data / build_vocabulary
- mix_corpora helper
- FineTuneTrainer scaffold (init, stub NotImplementedError)
- EvalResult / evaluate_finetuned_model / compute_bleu_improvement
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from zh_en_translator.corpus.corpus_manager import CorpusEntry, get_examples_dir
from zh_en_translator.finetuning.config import FineTuningConfig
from zh_en_translator.finetuning.data_preparation import (
    TrainingPair,
    Vocabulary,
    build_vocabulary,
    load_corpus,
    mix_corpora,
    prepare_training_data,
    split_train_val,
)
from zh_en_translator.finetuning.evaluation import (
    EvalResult,
    compare_models,
    compute_bleu_improvement,
    evaluate_finetuned_model,
)
from zh_en_translator.finetuning.trainer import FineTuneTrainer, TrainingHistory


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_entry(
    chinese: str = "热处理后的硬度符合标准",
    english: str = "Hardness after heat treatment meets the standard",
    domain: str = "manufacturing",
    verified: bool = True,
    source: str = "manual",
) -> CorpusEntry:
    return CorpusEntry(
        source=source,
        chinese=chinese,
        english=english,
        domain=domain,
        verified=verified,
    )


def _make_corpus(n: int = 10, verified: bool = True) -> list[CorpusEntry]:
    return [
        _make_entry(
            chinese=f"热处理句子{i}",
            english=f"Heat treatment sentence {i}",
            verified=verified,
        )
        for i in range(n)
    ]


@pytest.fixture
def manufacturing_jsonl(tmp_path: Path) -> Path:
    """A temporary JSONL file with 15 valid manufacturing entries."""
    entries = [
        {
            "source": "manual",
            "chinese": f"零件表面处理工艺{i}",
            "english": f"Part surface treatment process {i}",
            "domain": "manufacturing",
            "verified": True,
        }
        for i in range(15)
    ]
    path = tmp_path / "test_corpus.jsonl"
    with open(path, "w", encoding="utf-8") as f:
        for e in entries:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")
    return path


# ===========================================================================
# FineTuningConfig tests
# ===========================================================================


class TestFineTuningConfig:
    def test_default_config_creation(self, tmp_path: Path) -> None:
        config = FineTuningConfig()
        assert isinstance(config.corpus_path, Path)
        assert isinstance(config.output_dir, Path)
        assert config.batch_size == 32
        assert config.learning_rate == 1e-4
        assert config.epochs == 20
        assert config.in_domain_ratio == 0.3
        assert config.validation_split == 0.1
        assert config.seed == 42
        assert config.device == "cuda"

    def test_custom_config(self, tmp_path: Path) -> None:
        config = FineTuningConfig(
            corpus_path=tmp_path / "corpus.jsonl",
            output_dir=tmp_path / "output",
            device="cpu",
            epochs=5,
            batch_size=16,
            learning_rate=5e-5,
        )
        assert config.device == "cpu"
        assert config.epochs == 5
        assert config.batch_size == 16

    def test_validate_passes_on_valid_config(self) -> None:
        config = FineTuningConfig(device="cpu")
        config.validate()  # should not raise

    def test_validate_invalid_in_domain_ratio(self) -> None:
        config = FineTuningConfig(in_domain_ratio=0.0)
        with pytest.raises(ValueError, match="in_domain_ratio"):
            config.validate()

    def test_validate_in_domain_ratio_too_large(self) -> None:
        config = FineTuningConfig(in_domain_ratio=1.5)
        with pytest.raises(ValueError, match="in_domain_ratio"):
            config.validate()

    def test_validate_invalid_validation_split(self) -> None:
        config = FineTuningConfig(validation_split=0.0)
        with pytest.raises(ValueError, match="validation_split"):
            config.validate()

    def test_validate_validation_split_too_large(self) -> None:
        config = FineTuningConfig(validation_split=0.6)
        with pytest.raises(ValueError, match="validation_split"):
            config.validate()

    def test_validate_invalid_batch_size(self) -> None:
        config = FineTuningConfig(batch_size=0)
        with pytest.raises(ValueError, match="batch_size"):
            config.validate()

    def test_validate_invalid_learning_rate(self) -> None:
        config = FineTuningConfig(learning_rate=-1e-4)
        with pytest.raises(ValueError, match="learning_rate"):
            config.validate()

    def test_validate_invalid_device(self) -> None:
        config = FineTuningConfig(device="tpu")  # type: ignore
        with pytest.raises(ValueError, match="device"):
            config.validate()

    def test_validate_multiple_errors(self) -> None:
        config = FineTuningConfig(batch_size=0, learning_rate=-1.0)
        with pytest.raises(ValueError) as exc_info:
            config.validate()
        msg = str(exc_info.value)
        assert "batch_size" in msg
        assert "learning_rate" in msg

    def test_validate_paths_raises_if_missing(self, tmp_path: Path) -> None:
        config = FineTuningConfig(corpus_path=tmp_path / "does_not_exist.jsonl")
        with pytest.raises(FileNotFoundError):
            config.validate_paths()

    def test_validate_paths_passes_if_exists(self, tmp_path: Path) -> None:
        p = tmp_path / "corpus.jsonl"
        p.write_text("{}\n", encoding="utf-8")
        config = FineTuningConfig(corpus_path=p)
        config.validate_paths()  # should not raise

    def test_to_dict_roundtrip(self) -> None:
        config = FineTuningConfig(
            corpus_path=Path("/some/path/corpus.jsonl"),
            output_dir=Path("/some/output"),
            device="cpu",
            epochs=5,
        )
        d = config.to_dict()
        assert isinstance(d["corpus_path"], str)
        assert isinstance(d["output_dir"], str)

        config2 = FineTuningConfig.from_dict(d)
        assert config2.corpus_path == config.corpus_path
        assert config2.output_dir == config.output_dir
        assert config2.device == config.device
        assert config2.epochs == config.epochs

    def test_effective_batch_size(self) -> None:
        config = FineTuningConfig(batch_size=16, gradient_accumulation_steps=2)
        assert config.effective_batch_size == 32

    def test_path_coercion_from_string(self) -> None:
        config = FineTuningConfig(
            corpus_path="/some/path.jsonl",  # type: ignore -- intentional str
            output_dir="/some/output",       # type: ignore
        )
        assert isinstance(config.corpus_path, Path)
        assert isinstance(config.output_dir, Path)

    def test_repr(self) -> None:
        config = FineTuningConfig(device="cpu", epochs=5)
        r = repr(config)
        assert "cpu" in r
        assert "5" in r


# ===========================================================================
# load_corpus tests
# ===========================================================================


class TestLoadCorpus:
    def test_loads_valid_jsonl(self, manufacturing_jsonl: Path) -> None:
        entries = load_corpus(manufacturing_jsonl)
        assert len(entries) == 15

    def test_returns_corpus_entries(self, manufacturing_jsonl: Path) -> None:
        entries = load_corpus(manufacturing_jsonl)
        assert all(isinstance(e, CorpusEntry) for e in entries)

    def test_loads_bundled_examples(self) -> None:
        """Load the real manufacturing_samples.jsonl from the package."""
        examples_dir = get_examples_dir()
        jsonl_path = examples_dir / "manufacturing_samples.jsonl"
        if not jsonl_path.exists():
            pytest.skip("manufacturing_samples.jsonl not found")
        entries = load_corpus(jsonl_path)
        assert len(entries) >= 10, "Expected at least 10 bundled samples"

    def test_raises_on_missing_file(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            load_corpus(tmp_path / "nonexistent.jsonl")

    def test_skips_invalid_lines(self, tmp_path: Path) -> None:
        """Malformed lines should be skipped, not crash the loader."""
        path = tmp_path / "mixed.jsonl"
        with open(path, "w", encoding="utf-8") as f:
            f.write('{"source":"m","chinese":"你好","english":"Hello","domain":"test","verified":true}\n')
            f.write("NOT JSON\n")
            f.write('{"source":"m","chinese":"谢谢","english":"Thank you","domain":"test","verified":true}\n')
        entries = load_corpus(path)
        assert len(entries) == 2

    def test_entry_fields(self, manufacturing_jsonl: Path) -> None:
        entries = load_corpus(manufacturing_jsonl)
        e = entries[0]
        assert e.chinese
        assert e.english
        assert e.domain == "manufacturing"
        assert e.verified is True


# ===========================================================================
# split_train_val tests
# ===========================================================================


class TestSplitTrainVal:
    def test_basic_split(self) -> None:
        corpus = _make_corpus(20)
        train, val = split_train_val(corpus, ratio=0.1)
        assert len(train) + len(val) == 20

    def test_ratio_respected(self) -> None:
        corpus = _make_corpus(100)
        train, val = split_train_val(corpus, ratio=0.1)
        assert len(val) == 10
        assert len(train) == 90

    def test_at_least_one_val_entry(self) -> None:
        """Even with 5 entries and ratio=0.1, we get at least 1 val entry."""
        corpus = _make_corpus(5)
        train, val = split_train_val(corpus, ratio=0.1)
        assert len(val) >= 1
        assert len(train) >= 1

    def test_no_overlap(self) -> None:
        corpus = _make_corpus(20)
        train, val = split_train_val(corpus, ratio=0.2)
        train_ids = {id(e) for e in train}
        val_ids = {id(e) for e in val}
        assert not train_ids & val_ids

    def test_deterministic_with_seed(self) -> None:
        corpus = _make_corpus(30)
        _, val1 = split_train_val(corpus, ratio=0.2, seed=42)
        _, val2 = split_train_val(corpus, ratio=0.2, seed=42)
        assert [e.chinese for e in val1] == [e.chinese for e in val2]

    def test_different_seeds_differ(self) -> None:
        corpus = _make_corpus(50)
        _, val1 = split_train_val(corpus, ratio=0.2, seed=1)
        _, val2 = split_train_val(corpus, ratio=0.2, seed=99)
        assert [e.chinese for e in val1] != [e.chinese for e in val2]

    def test_raises_on_empty_corpus(self) -> None:
        with pytest.raises(ValueError, match="empty"):
            split_train_val([], ratio=0.1)

    def test_raises_on_bad_ratio(self) -> None:
        corpus = _make_corpus(10)
        with pytest.raises(ValueError, match="ratio"):
            split_train_val(corpus, ratio=0.0)
        with pytest.raises(ValueError, match="ratio"):
            split_train_val(corpus, ratio=0.9)


# ===========================================================================
# prepare_training_data tests
# ===========================================================================


class TestPrepareTrainingData:
    def test_returns_training_pairs(self) -> None:
        corpus = _make_corpus(5)
        pairs = prepare_training_data(corpus)
        assert all(isinstance(p, TrainingPair) for p in pairs)

    def test_correct_length(self) -> None:
        corpus = _make_corpus(10)
        pairs = prepare_training_data(corpus)
        assert len(pairs) == 10

    def test_src_tgt_content(self) -> None:
        entry = _make_entry(chinese="钢材", english="Steel material")
        pairs = prepare_training_data([entry])
        assert pairs[0].src == "钢材"
        assert pairs[0].tgt == "Steel material"

    def test_verified_weight(self) -> None:
        verified = _make_entry(verified=True)
        unverified = _make_entry(verified=False)
        pairs = prepare_training_data([verified, unverified])
        assert pairs[0].weight == 1.0
        assert pairs[1].weight == 0.5

    def test_custom_weights(self) -> None:
        entry = _make_entry(verified=False)
        pairs = prepare_training_data([entry], unverified_weight=0.8)
        assert pairs[0].weight == 0.8

    def test_raises_on_empty_corpus(self) -> None:
        with pytest.raises(ValueError, match="empty"):
            prepare_training_data([])

    def test_domain_preserved(self) -> None:
        entry = _make_entry(domain="medical")
        pairs = prepare_training_data([entry])
        assert pairs[0].domain == "medical"

    def test_whitespace_stripped(self) -> None:
        entry = _make_entry(chinese="  钢板  ", english="  Steel sheet  ")
        pairs = prepare_training_data([entry])
        assert pairs[0].src == "钢板"
        assert pairs[0].tgt == "Steel sheet"


# ===========================================================================
# build_vocabulary tests
# ===========================================================================


class TestBuildVocabulary:
    def test_returns_vocabulary(self) -> None:
        corpus = _make_corpus(5)
        vocab = build_vocabulary(corpus)
        assert isinstance(vocab, Vocabulary)

    def test_source_tokens_non_empty(self) -> None:
        corpus = _make_corpus(5)
        vocab = build_vocabulary(corpus)
        assert vocab.source_vocab_size > 0

    def test_target_tokens_non_empty(self) -> None:
        corpus = _make_corpus(5)
        vocab = build_vocabulary(corpus)
        assert vocab.target_vocab_size > 0

    def test_known_term_in_vocabulary(self) -> None:
        entry = _make_entry(chinese="硬度", english="hardness")
        vocab = build_vocabulary([entry])
        assert "hardness" in vocab.target_tokens

    def test_domain_tags(self) -> None:
        entries = [
            _make_entry(domain="manufacturing"),
            _make_entry(domain="medical"),
        ]
        vocab = build_vocabulary(entries)
        assert "manufacturing" in vocab.domain_tags
        assert "medical" in vocab.domain_tags


# ===========================================================================
# mix_corpora tests
# ===========================================================================


class TestMixCorpora:
    def test_basic_mix(self) -> None:
        in_domain = _make_corpus(10)
        general = _make_corpus(100)
        mixed = mix_corpora(in_domain, general, in_domain_ratio=0.3)
        # 10 in-domain + ~23 general = ~33 total
        assert len(mixed) > len(in_domain)

    def test_ratio_approximately_correct(self) -> None:
        in_domain = _make_corpus(30)
        general = _make_corpus(200)
        mixed = mix_corpora(in_domain, general, in_domain_ratio=0.3)
        # Expected: 30 in-domain + 70 general = 100 total
        assert abs(len(mixed) - 100) <= 2  # small rounding tolerance

    def test_raises_on_empty_in_domain(self) -> None:
        with pytest.raises(ValueError, match="in_domain"):
            mix_corpora([], _make_corpus(10))

    def test_raises_on_empty_general(self) -> None:
        with pytest.raises(ValueError, match="general"):
            mix_corpora(_make_corpus(10), [])

    def test_raises_on_bad_ratio(self) -> None:
        with pytest.raises(ValueError, match="in_domain_ratio"):
            mix_corpora(_make_corpus(10), _make_corpus(10), in_domain_ratio=0.0)


# ===========================================================================
# FineTuneTrainer scaffold tests
# ===========================================================================


class TestFineTuneTrainer:
    def test_trainer_init(self) -> None:
        config = FineTuningConfig(device="cpu")
        trainer = FineTuneTrainer(config, model=None)
        assert trainer.config is config
        assert trainer.model is None

    def test_train_raises_not_implemented(self) -> None:
        config = FineTuningConfig(device="cpu")
        trainer = FineTuneTrainer(config, model=None)
        train_data = [TrainingPair(src="你好", tgt="Hello")]
        val_data = [TrainingPair(src="谢谢", tgt="Thank you")]
        with pytest.raises(NotImplementedError):
            trainer.train(train_data, val_data)

    def test_evaluate_raises_not_implemented(self) -> None:
        config = FineTuningConfig(device="cpu")
        trainer = FineTuneTrainer(config, model=None)
        with pytest.raises(NotImplementedError):
            trainer.evaluate([])

    def test_save_model_raises_not_implemented(self, tmp_path: Path) -> None:
        config = FineTuningConfig(device="cpu")
        trainer = FineTuneTrainer(config, model=None)
        with pytest.raises(NotImplementedError):
            trainer.save_model(tmp_path / "model")

    def test_history_is_none_before_training(self) -> None:
        config = FineTuningConfig(device="cpu")
        trainer = FineTuneTrainer(config, model=None)
        assert trainer.history is None

    def test_repr(self) -> None:
        config = FineTuningConfig(device="cpu")
        trainer = FineTuneTrainer(config, model=None)
        r = repr(trainer)
        assert "FineTuneTrainer" in r

    def test_early_stopping_logic_no_stop(self) -> None:
        config = FineTuningConfig(device="cpu")
        trainer = FineTuneTrainer(config, model=None)
        # Steadily improving -- should not stop
        history = [0.10, 0.20, 0.30, 0.40, 0.50]
        assert not trainer._should_stop_early(history, patience=3)

    def test_early_stopping_logic_stops(self) -> None:
        config = FineTuningConfig(device="cpu")
        trainer = FineTuneTrainer(config, model=None)
        # Plateau after the 3rd entry -- should stop with patience=3
        history = [0.10, 0.30, 0.30, 0.30, 0.30]
        assert trainer._should_stop_early(history, patience=3)

    def test_early_stopping_not_enough_history(self) -> None:
        config = FineTuningConfig(device="cpu")
        trainer = FineTuneTrainer(config, model=None)
        history = [0.10, 0.20]
        assert not trainer._should_stop_early(history, patience=5)


# ===========================================================================
# TrainingHistory tests
# ===========================================================================


class TestTrainingHistory:
    def test_summary(self) -> None:
        h = TrainingHistory(
            train_losses=[1.0, 0.8, 0.6],
            val_bleu_scores=[0.3, 0.35, 0.38],
            best_epoch=2,
            best_val_bleu=0.38,
            total_steps=300,
            stopped_early=False,
        )
        s = h.summary()
        assert "0.3800" in s
        assert "300" in s


# ===========================================================================
# Evaluation tests
# ===========================================================================


class TestEvalResult:
    def test_summary(self) -> None:
        result = EvalResult(
            bleu=0.45,
            cer=0.20,
            glossary_coverage=0.85,
            n_sentences=15,
            model_name="argos_finetuned",
        )
        s = result.summary()
        assert "argos_finetuned" in s
        assert "0.4500" in s


class TestEvaluateFinetunedModel:
    def _make_test_data(self) -> tuple[list[str], list[CorpusEntry]]:
        corpus = [
            _make_entry(english="Hardness after heat treatment meets the standard"),
            _make_entry(english="Surface roughness Ra value in range"),
            _make_entry(english="Tensile strength shall not be less than 600 MPa"),
        ]
        translations = [
            "Hardness after heat treatment meets the standard",
            "Surface roughness Ra value in range",
            "The tensile strength is at least 600 MPa",
        ]
        return translations, corpus

    def test_basic_evaluation(self) -> None:
        translations, corpus = self._make_test_data()
        result = evaluate_finetuned_model(translations, corpus)
        assert isinstance(result, EvalResult)
        assert result.n_sentences == 3
        assert 0.0 <= result.bleu <= 1.0
        assert 0.0 <= result.cer

    def test_perfect_translation_high_bleu(self) -> None:
        entry = _make_entry(english="Steel surface treatment process")
        result = evaluate_finetuned_model(
            ["Steel surface treatment process"], [entry]
        )
        assert result.bleu > 0.9

    def test_raises_length_mismatch(self) -> None:
        corpus = _make_corpus(3)
        with pytest.raises(ValueError, match="same length"):
            evaluate_finetuned_model(["one", "two"], corpus)

    def test_raises_empty_translations(self) -> None:
        with pytest.raises(ValueError, match="empty"):
            evaluate_finetuned_model([], [])

    def test_glossary_coverage(self) -> None:
        entry = _make_entry(
            chinese="热处理硬度符合标准",
            english="Heat treatment hardness meets standard",
        )
        glossary = {"热处理": "heat treatment"}
        result = evaluate_finetuned_model(
            ["Heat treatment hardness meets standard"],
            [entry],
            glossary=glossary,
        )
        assert result.glossary_coverage == 1.0

    def test_sentence_bleus_length(self) -> None:
        translations, corpus = self._make_test_data()
        result = evaluate_finetuned_model(translations, corpus)
        assert len(result.sentence_bleus) == len(translations)


class TestComputeBleuImprovement:
    def test_positive_improvement(self) -> None:
        baseline = EvalResult(bleu=0.35, n_sentences=10)
        finetuned = EvalResult(bleu=0.43, n_sentences=10)
        delta = compute_bleu_improvement(baseline, finetuned)
        assert abs(delta - 0.08) < 1e-6

    def test_zero_improvement(self) -> None:
        baseline = EvalResult(bleu=0.40)
        finetuned = EvalResult(bleu=0.40)
        assert compute_bleu_improvement(baseline, finetuned) == 0.0

    def test_negative_regression(self) -> None:
        baseline = EvalResult(bleu=0.45)
        finetuned = EvalResult(bleu=0.40)
        delta = compute_bleu_improvement(baseline, finetuned)
        assert delta < 0.0


class TestCompareModels:
    def test_returns_both_results(self) -> None:
        corpus = [_make_entry(english="Heat treatment process")]
        results = compare_models(
            ["Heat treatment process"],
            ["Heat treatment process"],
            corpus,
        )
        assert "baseline" in results
        assert "finetuned" in results

    def test_custom_model_names(self) -> None:
        corpus = [_make_entry(english="Hello")]
        results = compare_models(
            ["Hello"], ["Hello"], corpus,
            baseline_name="argos_base",
            finetuned_name="argos_v3",
        )
        assert results["baseline"].model_name == "argos_base"
        assert results["finetuned"].model_name == "argos_v3"
