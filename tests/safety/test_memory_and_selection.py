from __future__ import annotations

from datetime import UTC, datetime

import pytest

from conftest import (
    PATIENT_ID,
    drive_to_route,
    make_harness,
    send,
)
from meantbyme.core.domain import (
    ExpressionCandidate,
    MemoryItem,
    MemoryType,
    PatientCommandType,
    RiskLevel,
    SessionStage,
    VerificationLevel,
)
from meantbyme.core.personalization import (
    idempotency_key,
    normalize,
    rank_candidates,
)


def test_ranker_and_memory_never_auto_select() -> None:
    harness = make_harness(with_memory=True)
    drive_to_route(harness)

    assert harness.runtime.session.stage is SessionStage.FINAL_REVIEW
    assert harness.runtime.session.candidates[0].text == (
        "I don't want to go tomorrow."
    )
    assert harness.runtime.session.selected_candidate_id is None
    assert harness.tts.personal_calls == 0


def test_gold_outranks_silver_on_equal_text_match() -> None:
    text = "I don't want to go tomorrow."
    gold = MemoryItem(
        id="gold-memory",
        patient_id=PATIENT_ID,
        memory_type=MemoryType.SEMANTIC,
        verification_level=VerificationLevel.GOLD,
        text=text,
        confirmation_session_id="confirmed-session",
    )
    silver = MemoryItem(
        id="silver-memory",
        patient_id=PATIENT_ID,
        memory_type=MemoryType.SEMANTIC,
        verification_level=VerificationLevel.SILVER,
        text=text,
    )
    shared_candidate_fields = {
        "text": text,
        "language": "en",
        "patient_supported_spans": ["i", "don't", "tomorrow"],
        "ai_added_spans": ["want to go"],
        "ranking_reasons": [],
        "risk_level": RiskLevel.ORDINARY,
        "source_level": "L2",
    }
    silver_candidate = ExpressionCandidate(
        id="silver-candidate",
        memory_support_ids=[silver.id],
        **shared_candidate_fields,
    )
    gold_candidate = ExpressionCandidate(
        id="gold-candidate",
        memory_support_ids=[gold.id],
        **shared_candidate_fields,
    )

    ranked = rank_candidates(
        [silver_candidate, gold_candidate], [silver, gold]
    )

    assert ranked[0].id == gold_candidate.id
    assert any("gold" in reason for reason in ranked[0].ranking_reasons)


def _grounding_candidates() -> list[ExpressionCandidate]:
    shared = {
        "language": "en",
        "patient_supported_spans": ["we", "help", "stroke", "survivors"],
        "memory_support_ids": [],
        "ranking_reasons": [],
        "risk_level": RiskLevel.ORDINARY,
        "source_level": "L2",
    }
    literal = ExpressionCandidate(
        id="literal",
        text="We help stroke survivors with their needs.",
        ai_added_spans=["with", "needs"],
        **shared,
    )
    grounded = ExpressionCandidate(
        id="grounded",
        text="We help stroke survivors organize their needs.",
        ai_added_spans=["organize", "needs"],
        **shared,
    )
    return [literal, grounded]


def test_context_grounding_lifts_memory_informed_completion() -> None:
    # D21: an AI-added word that echoes the patient's own verified CONTEXT
    # memory ("organize") should overtake a bare literal completion that adds
    # nothing personal, even though both carry the same ai_added penalty.
    context = [
        MemoryItem(
            id="ctx-1",
            patient_id=PATIENT_ID,
            memory_type=MemoryType.CONTEXT,
            verification_level=VerificationLevel.GOLD,
            text="I help stroke survivors organize their appointment questions.",
            confirmation_session_id="confirmed-session",
        )
    ]
    literal, grounded = _grounding_candidates()

    baseline = rank_candidates([literal, grounded], [])
    assert baseline[0].id == "literal"  # tie broken by input order, no boost

    ranked = rank_candidates([literal, grounded], [], context)
    assert ranked[0].id == "grounded"
    assert any("context" in reason for reason in ranked[0].ranking_reasons)


def test_context_grounding_never_outranks_gold_semantic_match() -> None:
    # D21 must stay far below a Gold *semantic* (patient-confirmed) match so
    # context evidence can reorder near-ties but never override confirmed
    # phrasing, and never auto-selects.
    gold_semantic = MemoryItem(
        id="gold-phrase",
        patient_id=PATIENT_ID,
        memory_type=MemoryType.SEMANTIC,
        verification_level=VerificationLevel.GOLD,
        text="We help stroke survivors with their needs.",
        confirmation_session_id="confirmed-session",
    )
    context = [
        MemoryItem(
            id="ctx-1",
            patient_id=PATIENT_ID,
            memory_type=MemoryType.CONTEXT,
            verification_level=VerificationLevel.GOLD,
            text="I help stroke survivors organize their appointment questions.",
            confirmation_session_id="confirmed-session",
        )
    ]
    literal, grounded = _grounding_candidates()
    literal = literal.model_copy(update={"memory_support_ids": ["gold-phrase"]})

    ranked = rank_candidates([literal, grounded], [gold_semantic], context)

    assert ranked[0].id == "literal"


def test_context_grounding_supports_cjk_content_tokens() -> None:
    shared = {
        "language": "zh",
        "patient_supported_spans": ["我们", "帮助", "患者"],
        "memory_support_ids": [],
        "ranking_reasons": [],
        "risk_level": RiskLevel.ORDINARY,
        "source_level": "L2",
    }
    generic = ExpressionCandidate(
        id="generic-zh",
        text="我们帮助患者表达需求。",
        ai_added_spans=["表达需求"],
        **shared,
    )
    grounded = ExpressionCandidate(
        id="grounded-zh",
        text="我们帮助患者整理需求。",
        ai_added_spans=["整理需求"],
        **shared,
    )
    context = [
        MemoryItem(
            id="ctx-zh",
            patient_id=PATIENT_ID,
            memory_type=MemoryType.CONTEXT,
            verification_level=VerificationLevel.GOLD,
            text="我的项目帮助患者整理需求。",
            language="zh",
            confirmation_session_id="confirmed-session",
        )
    ]

    ranked = rank_candidates([generic, grounded], [], context)

    assert ranked[0].id == "grounded-zh"
    assert any(
        "gold patient context" in reason
        for reason in ranked[0].ranking_reasons
    )


def test_context_grounding_ignores_non_context_rows() -> None:
    literal, grounded = _grounding_candidates()
    semantic_passed_as_context = MemoryItem(
        id="semantic-row",
        patient_id=PATIENT_ID,
        memory_type=MemoryType.SEMANTIC,
        verification_level=VerificationLevel.GOLD,
        text="I help stroke survivors organize their appointment questions.",
        confirmation_session_id="confirmed-session",
    )

    ranked = rank_candidates(
        [literal, grounded], [], [semantic_passed_as_context]
    )

    assert ranked[0].id == "literal"
    assert not any(
        "context" in reason
        for candidate in ranked
        for reason in candidate.ranking_reasons
    )


def test_gold_semantic_support_stays_above_context_grounding() -> None:
    literal, grounded = _grounding_candidates()
    semantic = MemoryItem(
        id="gold-support",
        patient_id=PATIENT_ID,
        memory_type=MemoryType.SEMANTIC,
        verification_level=VerificationLevel.GOLD,
        text="A related patient-confirmed expression.",
        confirmation_session_id="confirmed-session",
    )
    literal = literal.model_copy(
        update={"memory_support_ids": ["gold-support"]}
    )
    context = [
        MemoryItem(
            id="ctx-1",
            patient_id=PATIENT_ID,
            memory_type=MemoryType.CONTEXT,
            verification_level=VerificationLevel.GOLD,
            text="I help stroke survivors organize their appointment questions.",
            confirmation_session_id="confirmed-session",
        )
    ]

    ranked = rank_candidates([grounded, literal], [semantic], context)

    assert ranked[0].id == "literal"


def test_generic_context_words_do_not_trigger_grounding() -> None:
    candidate = ExpressionCandidate(
        id="generic",
        text="I need help.",
        language="en",
        patient_supported_spans=["I"],
        ai_added_spans=["need", "help"],
        memory_support_ids=[],
        ranking_reasons=[],
        risk_level=RiskLevel.ORDINARY,
        source_level="L2",
    )
    context = [
        MemoryItem(
            id="ctx-generic",
            patient_id=PATIENT_ID,
            memory_type=MemoryType.CONTEXT,
            verification_level=VerificationLevel.GOLD,
            text="I sometimes need help at work.",
            confirmation_session_id="confirmed-session",
        )
    ]

    ranked = rank_candidates([candidate], [], context)

    assert not any("context" in reason for reason in ranked[0].ranking_reasons)


def test_memory_context_and_language_round_trip() -> None:
    harness = make_harness(with_memory=False)
    memory = MemoryItem(
        id="planning-memory",
        patient_id=PATIENT_ID,
        memory_type=MemoryType.SEMANTIC,
        verification_level=VerificationLevel.GOLD,
        text="I don't want to go tomorrow.",
        language="en",
        context={"topic": "planning"},
        confirmation_session_id="confirmed-session",
    )
    harness.repository.seed_verified_memory(PATIENT_ID, memory)

    retrieved = harness.repository.search_verified_memories(
        PATIENT_ID, ["tomorrow"]
    )

    assert retrieved[0].language == "en"
    assert retrieved[0].context == {"topic": "planning"}


def test_rejected_candidate_cannot_enter_gold_memory() -> None:
    harness = make_harness(with_memory=False)
    drive_to_route(harness)
    assert harness.runtime.session.stage is SessionStage.CANDIDATE_SELECTION
    before = harness.repository.count_memories(PATIENT_ID)

    send(harness.runtime, PatientCommandType.NONE_OF_THESE)

    assert harness.repository.count_memories(PATIENT_ID) == before
    assert harness.repository.count_rejections(PATIENT_ID) == 3
    assert all(
        normalize(candidate.text)
        not in {
            normalize(text)
            for text in harness.runtime.session.confirmed_context.rejected_texts
        }
        for candidate in harness.runtime.session.candidates
    )


def test_none_of_these_preserves_confirmed_context() -> None:
    harness = make_harness(with_memory=False)
    drive_to_route(harness)
    before = harness.runtime.session.confirmed_context.model_copy(deep=True)

    send(harness.runtime, PatientCommandType.NONE_OF_THESE)

    after = harness.runtime.session.confirmed_context
    assert after.locked_tokens == before.locked_tokens
    assert after.locked_slots == before.locked_slots
    assert len(after.rejected_texts) == 3
    for candidate in harness.runtime.session.candidates:
        candidate_tokens = set(normalize(candidate.text).split())
        assert set(after.locked_tokens).issubset(candidate_tokens)


def test_cross_patient_retrieval_is_impossible() -> None:
    harness = make_harness()

    assert harness.repository.search_verified_memories(
        "other_patient", ["tomorrow"]
    ) == []
    with pytest.raises(PermissionError, match="Cross-patient"):
        harness.repository.seed_verified_memory(
            "other_patient",
            MemoryItem(
                id="leak-attempt",
                patient_id=PATIENT_ID,
                memory_type=MemoryType.SEMANTIC,
                verification_level=VerificationLevel.GOLD,
                text="Private phrase",
                usage_count=1,
                confirmation_session_id="confirmed",
            ),
        )

    with pytest.raises(PermissionError, match="Cross-patient"):
        harness.repository.seed_verified_memory(
            "other_patient",
            MemoryItem(
                id="mem-david-go-tomorrow",
                patient_id="other_patient",
                memory_type=MemoryType.SEMANTIC,
                verification_level=VerificationLevel.GOLD,
                text="Overwrite attempt",
                usage_count=1,
                confirmation_session_id="confirmed",
            ),
        )
    david_memory = harness.repository.search_verified_memories(
        PATIENT_ID, ["tomorrow"]
    )[0]
    assert david_memory.text == "I don't want to go tomorrow."


def test_duplicate_retry_does_not_double_write_memory() -> None:
    harness = make_harness(with_memory=False)
    text = "I don't want to go tomorrow."
    memory = MemoryItem(
        id="retry-memory",
        patient_id=PATIENT_ID,
        memory_type=MemoryType.SEMANTIC,
        verification_level=VerificationLevel.GOLD,
        text=text,
        usage_count=0,
        last_used_at=datetime.now(UTC),
        confirmation_session_id="retry-session",
    )
    key = idempotency_key(
        "retry-session", text, "verified_semantic_expression"
    )

    first = harness.repository.write_verified_memory(PATIENT_ID, memory, key)
    second = harness.repository.write_verified_memory(PATIENT_ID, memory, key)

    assert first.written is True
    assert second.written is False
    assert first.idempotency_key == second.idempotency_key
    assert harness.repository.count_memory_writes(PATIENT_ID) == 1
    assert harness.repository.count_memories(PATIENT_ID) == 1
