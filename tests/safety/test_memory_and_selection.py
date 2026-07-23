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
    MemoryItem,
    MemoryType,
    PatientCommandType,
    SessionStage,
    VerificationLevel,
)
from meantbyme.core.personalization import idempotency_key, normalize


def test_ranker_and_memory_never_auto_select() -> None:
    harness = make_harness(with_memory=True)
    drive_to_route(harness)

    assert harness.runtime.session.stage is SessionStage.FINAL_REVIEW
    assert harness.runtime.session.candidates[0].text == (
        "I don't want to go tomorrow."
    )
    assert harness.runtime.session.selected_candidate_id is None
    assert harness.tts.personal_calls == 0


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
