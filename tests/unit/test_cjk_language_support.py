from __future__ import annotations

import re

import pytest

from meantbyme.adapters.intent.gateway import GatewayIntentAdapter
from meantbyme.adapters.intent.mock import MockIntentAdapter
from meantbyme.adapters.intent.template import TemplateIntentAdapter
from meantbyme.adapters.storage import SQLiteRepository
from meantbyme.core.domain import (
    ASRResult,
    ConfirmedContext,
    ExpressionCandidate,
    IntentProposal,
    MemoryItem,
    MemoryType,
    RiskLevel,
    UncertaintyBand,
    VerificationLevel,
)
from meantbyme.core.personalization.text import (
    expression_hash,
    normalize,
    tokenize,
)
from meantbyme.core.policies.uncertainty import (
    assess_uncertainty,
    core_slots_present,
)
from meantbyme.core.runtime.evidence import build_transcript_evidence


def _asr(transcript: str) -> list[ASRResult]:
    return [
        ASRResult(provider="primary", transcript=transcript, status="success"),
        ASRResult(
            provider="secondary", transcript=transcript, status="success"
        ),
    ]


def _candidate(candidate_id: str, text: str) -> ExpressionCandidate:
    return ExpressionCandidate(
        id=candidate_id,
        text=text,
        language="zh",
        patient_supported_spans=["明天"],
        ai_added_spans=[],
        memory_support_ids=[],
        ranking_reasons=[],
        risk_level=RiskLevel.ORDINARY,
        source_level="L2",
    )


def _proposal(*candidates: ExpressionCandidate) -> IntentProposal:
    return IntentProposal(
        certain_content=["明天"],
        uncertain_content=[],
        candidates=list(candidates),
        requires_confirmation=True,
    )


def test_english_tokenization_matches_previous_word_boundary_behavior() -> None:
    examples = [
        "I don't want to go tomorrow.",
        "Hello, world!",
        "plan_2 can't wait",
        "Room 12 is ready.",
    ]

    for text in examples:
        previous = re.findall(r"\b[\w']+\b", normalize(text))
        assert tokenize(text) == previous


def test_cjk_and_mixed_text_tokenize_at_language_appropriate_granularity() -> None:
    assert tokenize("我不想明天出门。") == [
        "我",
        "不",
        "想",
        "明",
        "天",
        "出",
        "门",
    ]
    assert tokenize("我想去 hospital") == ["我", "想", "去", "hospital"]


def test_complete_and_fragmented_english_routing_is_unchanged() -> None:
    complete = build_transcript_evidence(_asr("I want water"))
    fragmented = build_transcript_evidence(_asr("I tomorrow"))

    assert core_slots_present(complete.stable_fragments) is True
    assert assess_uncertainty(complete) is UncertaintyBand.LOW
    assert core_slots_present(fragmented.stable_fragments) is False
    assert assess_uncertainty(fragmented) is UncertaintyBand.MEDIUM


def test_complete_chinese_evidence_is_low_uncertainty() -> None:
    evidence = build_transcript_evidence(_asr("我明天想回家"))

    assert core_slots_present(evidence.stable_fragments) is True
    assert evidence.missing_slots == []
    assert assess_uncertainty(evidence) is UncertaintyBand.LOW


def test_fragmented_chinese_evidence_remains_conservative() -> None:
    evidence = build_transcript_evidence(_asr("我明天"))

    assert core_slots_present(evidence.stable_fragments) is False
    assert evidence.missing_slots == ["predicate"]
    assert assess_uncertainty(evidence) is UncertaintyBand.MEDIUM


def test_gateway_locked_check_accepts_preserved_chinese_fragment() -> None:
    context = ConfirmedContext(locked_tokens=["明天"])
    proposal = _proposal(
        _candidate("valid-1", "我不想明天出门。"),
        _candidate("valid-2", "我明天想在家休息。"),
    )

    GatewayIntentAdapter._validate_contract(proposal, context)


def test_gateway_locked_check_rejects_dropped_chinese_fragment() -> None:
    context = ConfirmedContext(locked_tokens=["明天"])
    proposal = _proposal(
        _candidate("valid", "我不想明天出门。"),
        _candidate("invalid", "我现在想在家休息。"),
    )

    with pytest.raises(ValueError, match="dropped confirmed tokens"):
        GatewayIntentAdapter._validate_contract(proposal, context)


def test_gateway_english_locked_check_is_unchanged() -> None:
    context = ConfirmedContext(locked_tokens=["tomorrow"])
    valid = _proposal(
        _candidate("valid-1", "I don't want to go tomorrow."),
        _candidate("valid-2", "I want to rest tomorrow."),
    )
    invalid = _proposal(
        _candidate("valid", "I want to rest tomorrow."),
        _candidate("invalid", "I want to rest now."),
    )

    GatewayIntentAdapter._validate_contract(valid, context)
    with pytest.raises(ValueError, match="dropped confirmed tokens"):
        GatewayIntentAdapter._validate_contract(invalid, context)


@pytest.mark.parametrize(
    "assert_locked",
    [
        TemplateIntentAdapter._assert_locked,
        MockIntentAdapter._assert_confirmed_context,
    ],
)
def test_local_adapter_locked_checks_tokenize_both_sides(
    assert_locked,
) -> None:
    context = ConfirmedContext(locked_tokens=["明天"])

    assert_locked(_candidate("valid", "我不想明天出门。"), context)
    with pytest.raises(ValueError, match="dropped"):
        assert_locked(_candidate("invalid", "我现在想休息。"), context)


def test_matching_chinese_memory_reaches_high_similarity() -> None:
    repository = SQLiteRepository(":memory:")
    repository.add_patient("patient-zh", "Simulated Chinese Patient")
    repository.seed_verified_memory(
        "patient-zh",
        MemoryItem(
            id="memory-zh",
            patient_id="patient-zh",
            memory_type=MemoryType.SEMANTIC,
            verification_level=VerificationLevel.GOLD,
            text="我不想明天出门。",
            language="zh",
            confirmation_session_id="simulated-confirmation",
        ),
    )

    memories = repository.search_verified_memories(
        "patient-zh", ["我", "不想", "明天"]
    )
    repository.close()

    assert memories[0].similarity_band == "high"


def test_matching_english_memory_still_reaches_high_similarity() -> None:
    repository = SQLiteRepository(":memory:")
    repository.add_patient("patient-en", "Simulated English Patient")
    repository.seed_verified_memory(
        "patient-en",
        MemoryItem(
            id="memory-en",
            patient_id="patient-en",
            memory_type=MemoryType.SEMANTIC,
            verification_level=VerificationLevel.GOLD,
            text="I don't want to go tomorrow.",
            language="en",
            confirmation_session_id="simulated-confirmation",
        ),
    )

    memories = repository.search_verified_memories(
        "patient-en", ["i", "don't", "tomorrow"]
    )
    repository.close()

    assert memories[0].similarity_band == "high"


def test_existing_english_expression_hash_is_unchanged() -> None:
    assert expression_hash("I don't want to go tomorrow.") == (
        "0410b0292a7e52d8b2d0c99717f2cc679e4de296be18e4372d9818e4908db17f"
    )
