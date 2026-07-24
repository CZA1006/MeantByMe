from meantbyme.core.domain import ExpressionCandidate, RiskLevel
from meantbyme.eval.models import load_dataset
from meantbyme.eval.runner import _best_match_rank
from meantbyme.eval.semantic import evaluate_meaning, meaning_matches


ACCEPTABLE = [
    (
        "Hi, we are MeantByMe. We help stroke survivors organize their "
        "needs, and we speak only after confirmation."
    )
]
REQUIRED = {
    "speaker": ["we are MeantByMe", "we're MeantByMe"],
    "beneficiary": ["stroke survivors"],
    "action": ["organize their needs"],
    "speech_policy": [
        "we speak only after confirmation",
        "we only speak after confirmation",
        "speak only after confirmation",
    ],
}
FORBIDDEN = [
    "meet their needs",
    "communicate their needs",
    "speak before confirmation",
    "they speak",
    "he speaks",
    "she speaks",
]


def _matches(text: str) -> bool:
    return meaning_matches(
        text,
        acceptable_candidates=ACCEPTABLE,
        required_meaning=REQUIRED,
        forbidden_changes=FORBIDDEN,
    )


def test_semantic_match_accepts_safe_paraphrase() -> None:
    assert _matches(
        "Hi, we're MeantByMe. We help stroke survivors organize their "
        "needs. We only speak after confirmation."
    )


def test_semantic_match_accepts_inherited_subject() -> None:
    assert _matches(
        "Hi, we are MeantByMe. We help stroke survivors organize their "
        "needs and speak only after confirmation."
    )


def test_semantic_match_rejects_wrong_actor() -> None:
    assert not _matches(
        "Hi, they are MeantByMe. We help stroke survivors organize their "
        "needs, and we speak only after confirmation."
    )


def test_semantic_match_rejects_changed_action() -> None:
    result = evaluate_meaning(
        (
            "Hi, we are MeantByMe. We help stroke survivors meet their "
            "needs, and we speak only after confirmation."
        ),
        acceptable_candidates=ACCEPTABLE,
        required_meaning=REQUIRED,
        forbidden_changes=FORBIDDEN,
    )

    assert result.matched is False
    assert "action" in result.missing_slots
    assert "meet their needs" in result.forbidden_matches


def test_semantic_match_rejects_reversed_confirmation_timing() -> None:
    assert not _matches(
        "Hi, we are MeantByMe. We help stroke survivors organize their "
        "needs, and we speak before confirmation."
    )


def test_semantic_match_preserves_english_and_chinese_negation() -> None:
    assert meaning_matches(
        "I do not want to go tomorrow.",
        acceptable_candidates=["I don't want to go tomorrow."],
        required_meaning={
            "actor": ["I"],
            "negated_action": ["not want to go", "don't want to go"],
            "time": ["tomorrow"],
        },
        forbidden_changes=[],
    )
    assert not meaning_matches(
        "I want to go tomorrow.",
        acceptable_candidates=["I don't want to go tomorrow."],
        required_meaning={
            "actor": ["I"],
            "negated_action": ["not want to go", "don't want to go"],
            "time": ["tomorrow"],
        },
        forbidden_changes=[],
    )
    assert meaning_matches(
        "我不想明天出门。",
        acceptable_candidates=["我不想明天出门。"],
        required_meaning={
            "actor": ["我"],
            "negation": ["不想"],
            "action": ["出门"],
            "time": ["明天"],
        },
        forbidden_changes=[],
    )


def test_runner_rank_uses_semantic_slots_not_exact_text() -> None:
    base = load_dataset("demo/eval/dataset.jsonl")[0]
    sample = base.model_copy(
        update={
            "acceptable_candidates": ACCEPTABLE,
            "required_meaning": REQUIRED,
            "forbidden_changes": FORBIDDEN,
        }
    )
    candidate = ExpressionCandidate(
        id="semantic-paraphrase",
        text=(
            "Hi, we're MeantByMe. We help stroke survivors organize their "
            "needs. We only speak after confirmation."
        ),
        language="en",
        patient_supported_spans=["we", "help", "stroke survivors"],
        ai_added_spans=["organize", "confirmation"],
        memory_support_ids=[],
        ranking_reasons=[],
        risk_level=RiskLevel.ORDINARY,
        source_level="L2",
    )

    assert _best_match_rank([candidate], sample) == 1
