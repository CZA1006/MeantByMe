from __future__ import annotations

from datetime import UTC, datetime

import pytest

from conftest import PATIENT_ID, drive_to_route, make_harness
from meantbyme.adapters.intent import MockIntentAdapter
from meantbyme.cli import _seed_demo_repository
from meantbyme.core.domain import (
    MemoryItem,
    MemoryType,
    RuntimeEventType,
    SessionStage,
    VerificationLevel,
)
from meantbyme.core.personalization import compose_situation, expression_hash


FIXED_NOW = datetime(2026, 7, 26, 10, 0, tzinfo=UTC)


class RecordingIntentAdapter(MockIntentAdapter):
    def __init__(self) -> None:
        self.last_situation: str | None = None

    def propose(
        self,
        evidence,
        memories,
        confirmed_context,
        situation=None,
    ):
        self.last_situation = situation
        return super().propose(
            evidence,
            memories,
            confirmed_context,
            situation,
        )


def _context_memory(
    *,
    memory_id: str,
    patient_id: str = PATIENT_ID,
    text: str,
    level: VerificationLevel,
    source: str,
    last_used_at: datetime | None = None,
    confirmation_session_id: str | None = None,
) -> MemoryItem:
    return MemoryItem(
        id=memory_id,
        patient_id=patient_id,
        memory_type=MemoryType.CONTEXT,
        verification_level=level,
        text=text,
        language="en",
        context={
            "kind": "routine",
            "detail": text,
            "source": source,
        },
        last_used_at=last_used_at,
        confirmation_session_id=confirmation_session_id,
    )


def test_context_storage_is_patient_scoped_and_gold_precedes_silver() -> None:
    harness = make_harness(with_memory=False)
    gold = _context_memory(
        memory_id="context-gold",
        text="Sees the doctor every Sunday morning.",
        level=VerificationLevel.GOLD,
        source="patient",
        last_used_at=datetime(2026, 7, 20, tzinfo=UTC),
        confirmation_session_id="patient-context-confirmation",
    )
    silver = _context_memory(
        memory_id="context-silver",
        text="Prefers the living-room window open.",
        level=VerificationLevel.SILVER,
        source="caregiver",
        last_used_at=datetime(2026, 7, 25, tzinfo=UTC),
    )

    harness.repository.add_context_memory(PATIENT_ID, silver)
    harness.repository.add_context_memory(PATIENT_ID, gold)

    assert [
        memory.id
        for memory in harness.repository.search_context_memories(PATIENT_ID)
    ] == ["context-gold", "context-silver"]
    assert harness.repository.search_context_memories("other_patient") == []
    with pytest.raises(PermissionError, match="Cross-patient"):
        harness.repository.add_context_memory("other_patient", gold)


def test_caregiver_context_stays_silver_and_gold_requires_confirmation() -> None:
    harness = make_harness(with_memory=False)
    caregiver = _context_memory(
        memory_id="caregiver-context",
        text="Likes tea in the afternoon.",
        level=VerificationLevel.SILVER,
        source="caregiver",
    )
    harness.repository.add_context_memory(PATIENT_ID, caregiver)

    with pytest.raises(ValueError, match="Caregiver context"):
        harness.repository.add_context_memory(
            PATIENT_ID,
            caregiver.model_copy(
                update={
                    "id": "invalid-caregiver-gold",
                    "verification_level": VerificationLevel.GOLD,
                    "confirmation_session_id": "not-patient-confirmed",
                }
            ),
        )
    with pytest.raises(ValueError, match="Gold memory requires"):
        harness.repository.add_context_memory(
            PATIENT_ID,
            _context_memory(
                memory_id="missing-confirmation",
                text="Daughter Mia visits on weekends.",
                level=VerificationLevel.GOLD,
                source="patient",
            ),
        )
    with pytest.raises(ValueError, match="enter Gold"):
        harness.repository.add_context_memory(
            PATIENT_ID,
            _context_memory(
                memory_id="ai-gold",
                text="Inferred routine.",
                level=VerificationLevel.GOLD,
                source="ai",
                confirmation_session_id="forged-confirmation",
            ),
        )
    with pytest.raises(ValueError, match="cannot change automatically"):
        harness.repository.add_context_memory(
            PATIENT_ID,
            caregiver.model_copy(
                update={
                    "verification_level": VerificationLevel.GOLD,
                    "context": {
                        **caregiver.context,
                        "source": "patient",
                    },
                    "confirmation_session_id": "later-confirmation",
                }
            ),
        )
    with pytest.raises(ValueError, match="semantic verified writeback"):
        harness.repository.write_verified_memory(
            PATIENT_ID,
            _context_memory(
                memory_id="runtime-context-write",
                text="AI attempted context write.",
                level=VerificationLevel.GOLD,
                source="patient",
                confirmation_session_id="runtime-session",
            ),
            "runtime-context-write-idempotency-key",
        )

    stored = harness.repository.search_context_memories(PATIENT_ID)
    assert len(stored) == 1
    assert stored[0].verification_level is VerificationLevel.SILVER


def test_semantic_search_never_returns_context_rows() -> None:
    harness = make_harness(with_memory=True)
    context = _context_memory(
        memory_id="context-same-words",
        text="I don't want to go tomorrow.",
        level=VerificationLevel.GOLD,
        source="patient",
        confirmation_session_id="context-confirmation",
    )
    harness.repository.add_context_memory(PATIENT_ID, context)

    semantic = harness.repository.search_verified_memories(
        PATIENT_ID, ["i", "don't", "tomorrow"]
    )
    contexts = harness.repository.search_context_memories(PATIENT_ID)

    assert {memory.memory_type for memory in semantic} == {
        MemoryType.SEMANTIC
    }
    assert context.id not in {memory.id for memory in semantic}
    assert [memory.id for memory in contexts] == [context.id]


def test_compose_situation_is_deterministic_and_tags_silver() -> None:
    gold = _context_memory(
        memory_id="context-gold",
        text="Sees the doctor every Sunday morning.",
        level=VerificationLevel.GOLD,
        source="patient",
        confirmation_session_id="patient-context-confirmation",
    )
    silver = _context_memory(
        memory_id="context-silver-zh",
        text="女儿周末来访。",
        level=VerificationLevel.SILVER,
        source="caregiver",
    )

    assert compose_situation([], now=FIXED_NOW, override=None) is None
    assert (
        compose_situation(
            [gold, silver],
            now=FIXED_NOW,
            override="Manual situation wins.",
        )
        == "Manual situation wins."
    )
    assert compose_situation(
        [gold, silver], now=FIXED_NOW, override=None
    ) == (
        "Today is Sunday 2026-07-26. Known patient context: "
        "Sees the doctor every Sunday morning.; "
        "女儿周末来访。 (caregiver-provided)"
    )


def test_runtime_auto_recalls_context_without_authorizing_or_ranking_it() -> None:
    intent = RecordingIntentAdapter()
    harness = make_harness(
        with_memory=False,
        intent=intent,
        clock=lambda: FIXED_NOW,
        session_id="context-runtime",
    )
    context = _context_memory(
        memory_id="runtime-context",
        text="Plans tomorrow with daughter Mia.",
        level=VerificationLevel.GOLD,
        source="patient",
        confirmation_session_id="patient-context-confirmation",
    )
    harness.repository.add_context_memory(PATIENT_ID, context)

    drive_to_route(harness)

    assert harness.runtime.session.situation == (
        "Today is Sunday 2026-07-26. Known patient context: "
        "Plans tomorrow with daughter Mia."
    )
    assert intent.last_situation == harness.runtime.session.situation
    context_event = next(
        event
        for event in harness.runtime.events
        if event.event_type is RuntimeEventType.CONTEXT_RETRIEVED
    )
    assert context_event.payload == {
        "count": 1,
        "memory_ids": ["runtime-context"],
        "sources": ["patient"],
    }
    assert harness.runtime.session.stage is SessionStage.CANDIDATE_SELECTION
    assert context.id not in {
        support_id
        for candidate in harness.runtime.session.candidates
        for support_id in candidate.memory_support_ids
    }
    assert all(
        candidate.text != context.text
        for candidate in harness.runtime.session.candidates
    )
    assert harness.runtime.session.selected_candidate_id is None
    assert harness.runtime.session.voice_authorized is False
    assert harness.tts.personal_calls == 0


def test_runtime_context_retrieval_excludes_irrelevant_rows_and_limits_results() -> None:
    harness = make_harness(with_memory=False, session_id="context-relevance")
    relevant = [
        _context_memory(
            memory_id=f"relevant-{index}",
            text=f"Tomorrow planning detail {index}.",
            level=VerificationLevel.GOLD,
            source="patient",
            confirmation_session_id=f"context-confirmation-{index}",
        )
        for index in range(7)
    ]
    irrelevant = _context_memory(
        memory_id="irrelevant-window",
        text="Prefers the window open in the afternoon.",
        level=VerificationLevel.SILVER,
        source="caregiver",
    )
    for memory in [*relevant, irrelevant]:
        harness.repository.add_context_memory(PATIENT_ID, memory)

    drive_to_route(harness)

    event = next(
        item
        for item in harness.runtime.events
        if item.event_type is RuntimeEventType.CONTEXT_RETRIEVED
    )
    assert event.payload["count"] == 5
    assert "irrelevant-window" not in event.payload["memory_ids"]
    assert harness.runtime.session.situation is not None
    assert "window open" not in harness.runtime.session.situation


def test_demo_profile_seeds_gold_and_caregiver_silver_context() -> None:
    repository, patient, _, _, _ = _seed_demo_repository(":memory:")

    context_memories = repository.search_context_memories(patient["id"])
    repository.close()

    assert len(context_memories) == 3
    assert [
        memory.verification_level for memory in context_memories
    ] == [
        VerificationLevel.GOLD,
        VerificationLevel.GOLD,
        VerificationLevel.SILVER,
    ]
    caregiver = context_memories[-1]
    assert caregiver.context["source"] == "caregiver"
    assert caregiver.confirmation_session_id is None


def test_context_memory_does_not_change_expression_hash() -> None:
    assert expression_hash("I don't want to go tomorrow.") == (
        "0410b0292a7e52d8b2d0c99717f2cc679e4de296be18e4372d9818e4908db17f"
    )
