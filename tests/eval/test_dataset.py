from pathlib import Path

from meantbyme.eval.models import load_dataset


DATASET = Path("demo/eval/dataset.jsonl")


def test_dataset_loads_and_validates_against_schema() -> None:
    samples = load_dataset(DATASET)

    assert 20 <= len(samples) <= 30
    assert all(sample.simulated is True for sample in samples)
    assert {sample.language for sample in samples} == {"en", "zh"}
    assert {
        "complete_speech",
        "fragmented",
        "long_pauses",
        "repetition",
        "low_volume",
        "missing_predicate",
        "missing_object",
        "conflicting_asr",
        "known_personal_phrase",
        "unknown_phrase",
        "high_risk",
    }.issubset({sample.category for sample in samples})


def test_flagship_situation_pairs_only_change_context_and_answer() -> None:
    samples = load_dataset(DATASET)
    by_pair = {
        pair_id: [sample for sample in samples if sample.pair_id == pair_id]
        for pair_id in {"tomorrow_ambiguity", "tomorrow_ambiguity_zh"}
    }

    for members in by_pair.values():
        assert len(members) == 2
        left, right = members
        assert left.stable_fragments == right.stable_fragments
        assert left.asr_fixture == right.asr_fixture
        assert left.seed_memories == right.seed_memories
        assert left.situation != right.situation
        assert left.intended_expression != right.intended_expression
