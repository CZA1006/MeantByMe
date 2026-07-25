from __future__ import annotations

import pytest

from conftest import (
    drive_to_final_review,
    drive_to_route,
    final_confirm,
    make_harness,
    playback_completed,
    send,
)
from meantbyme.adapters.intent import MockIntentAdapter
from meantbyme.adapters.storage import SQLiteRepository
from meantbyme.core.domain import (
    CommandActor,
    ExpressionCandidate,
    PatientCommandType,
    RiskLevel,
    RuntimeEventType,
    SessionStage,
)
from meantbyme.core.runtime import CommandRejected


def test_go_back_reverses_only_reversible_stages() -> None:
    harness = make_harness(with_memory=False)
    drive_to_final_review(harness)

    send(harness.runtime, PatientCommandType.GO_BACK)
    assert harness.runtime.session.stage is SessionStage.CANDIDATE_SELECTION
    assert harness.runtime.session.selected_candidate_id is None

    send(harness.runtime, PatientCommandType.GO_BACK)
    assert harness.runtime.session.stage is SessionStage.HEARD_CONTENT_REVIEW
    assert harness.runtime.session.candidates == []

    blocked = make_harness(
        with_memory=False,
        fail_personal_tts=True,
        session_id="authorized-session",
    )
    drive_to_final_review(blocked)
    final_confirm(blocked)
    assert blocked.runtime.session.stage is SessionStage.VOICE_AUTHORIZED
    with pytest.raises(CommandRejected, match="Nothing is reversible"):
        send(blocked.runtime, PatientCommandType.GO_BACK)


def test_cancel_expression_discards_round_without_speaking_or_memory() -> None:
    harness = make_harness(with_memory=False)
    drive_to_final_review(harness)
    selected_text = harness.runtime.session.selected_candidate().text
    assert (
        PatientCommandType.CANCEL_EXPRESSION
        in harness.runtime.view_model().allowed_actions
    )

    send(
        harness.runtime,
        PatientCommandType.CANCEL_EXPRESSION,
        actor=CommandActor.CAREGIVER,
    )

    session = harness.runtime.session
    assert session.stage is SessionStage.EXPRESSION_CANCELLED
    assert session.evidence is None
    assert session.candidates == []
    assert session.selected_candidate_id is None
    assert session.patient_confirmed is False
    assert session.voice_authorized is False
    assert session.authorized_expression is None
    assert harness.tts.personal_calls == 0
    assert harness.repository.count_memory_writes("david_demo") == 0
    assert harness.repository.get_receipt(
        "david_demo", session.session_id
    ) is None
    cancelled = next(
        event
        for event in harness.runtime.events
        if event.event_type is RuntimeEventType.EXPRESSION_CANCELLED
    )
    assert cancelled.payload == {
        "actor": "caregiver",
        "cancelled_from": "final_review",
        "authorized_output_blocked": True,
        "memory_write_blocked": True,
    }
    assert selected_text not in session.confirmed_context.rejected_texts


def test_cancel_after_authorization_revokes_this_expression_scope() -> None:
    harness = make_harness(with_memory=False)
    drive_to_final_review(harness)
    final_confirm(harness)
    assert harness.runtime.session.stage is SessionStage.VOICE_AUTHORIZED

    send(harness.runtime, PatientCommandType.CANCEL_EXPRESSION)

    assert harness.runtime.session.stage is SessionStage.EXPRESSION_CANCELLED
    assert harness.runtime.session.patient_confirmed is False
    assert harness.runtime.session.voice_authorized is False
    assert harness.runtime.session.authorization_scope is None
    assert harness.runtime.session.authorized_expression is None
    assert harness.repository.count_memory_writes("david_demo") == 0


def test_completed_expression_cannot_be_cancelled_retroactively() -> None:
    harness = make_harness(with_memory=False)
    drive_to_final_review(harness)
    final_confirm(harness)
    playback_completed(harness)
    assert harness.runtime.session.stage is SessionStage.COMPLETED

    with pytest.raises(CommandRejected, match="unspoken active expression"):
        send(harness.runtime, PatientCommandType.CANCEL_EXPRESSION)

    assert harness.runtime.session.stage is SessionStage.COMPLETED
    assert harness.repository.count_memory_writes("david_demo") == 1


class HighRiskIntent(MockIntentAdapter):
    def propose(
        self, evidence, memories, confirmed_context, situation=None
    ):
        proposal = super().propose(
            evidence, memories, confirmed_context, situation
        )
        high_risk = ExpressionCandidate(
            id="high-risk-candidate",
            text="I don't want to transfer money tomorrow.",
            language="en",
            patient_supported_spans=list(confirmed_context.locked_tokens),
            ai_added_spans=["want to transfer money"],
            memory_support_ids=[],
            ranking_reasons=["fragment support"],
            risk_level=RiskLevel.ORDINARY,
            source_level="L2",
        )
        return proposal.model_copy(
            update={"candidates": [high_risk, *proposal.candidates[:2]]}
        )


class ChineseMedicalIntent(MockIntentAdapter):
    def propose(
        self, evidence, memories, confirmed_context, situation=None
    ):
        proposal = super().propose(
            evidence, memories, confirmed_context, situation
        )
        medical = ExpressionCandidate(
            id="chinese-medical-candidate",
            text="我想预约明天的治疗。",
            language="zh",
            patient_supported_spans=[],
            ai_added_spans=["预约明天的治疗"],
            memory_support_ids=[],
            ranking_reasons=["simulated Chinese medical expression"],
            risk_level=RiskLevel.ORDINARY,
            source_level="L2",
        )
        return proposal.model_copy(
            update={"candidates": [medical, *proposal.candidates[:2]]}
        )


def test_high_risk_expression_sets_strict_final_review() -> None:
    harness = make_harness(with_memory=False, intent=HighRiskIntent())
    drive_to_route(harness)
    candidate = next(
        item
        for item in harness.runtime.session.candidates
        if item.id == "high-risk-candidate"
    )
    send(
        harness.runtime,
        PatientCommandType.SELECT_CANDIDATE,
        payload={"candidate_id": candidate.id},
    )

    assert harness.runtime.session.stage is SessionStage.FINAL_REVIEW
    assert harness.runtime.session.risk_level is RiskLevel.HIGH_RISK
    assert harness.runtime.session.strict is True
    with pytest.raises(CommandRejected, match="strict confirmation"):
        final_confirm(harness)
    final_confirm(harness, strict=True)
    assert harness.runtime.session.stage is SessionStage.VOICE_AUTHORIZED
    playback_completed(harness)
    assert harness.runtime.session.stage is SessionStage.COMPLETED


def test_chinese_medical_expression_sets_strict_final_review() -> None:
    harness = make_harness(
        with_memory=False,
        intent=ChineseMedicalIntent(),
    )
    drive_to_route(harness)
    send(
        harness.runtime,
        PatientCommandType.SELECT_CANDIDATE,
        payload={"candidate_id": "chinese-medical-candidate"},
    )

    assert harness.runtime.session.risk_level is RiskLevel.HIGH_RISK
    assert harness.runtime.session.strict is True
    with pytest.raises(CommandRejected, match="strict confirmation"):
        final_confirm(harness)


class FailingSearchRepository(SQLiteRepository):
    def search_verified_memories(self, patient_id, fragments):
        raise TimeoutError("simulated memory timeout")


def test_memory_failure_falls_back_to_generic_mode() -> None:
    repository = FailingSearchRepository()
    harness = make_harness(with_memory=False, repository=repository)
    send(harness.runtime, PatientCommandType.START_CAPTURE)
    send(
        harness.runtime,
        PatientCommandType.STOP_CAPTURE,
        payload={"audio_id": "david_fragment_001"},
    )

    assert harness.runtime.session.stage is SessionStage.HEARD_CONTENT_REVIEW
    assert harness.runtime.session.retrieved_memories == []
    assert RuntimeEventType.MEMORY_RETRIEVAL_FAILED in {
        event.event_type for event in harness.runtime.events
    }


class FailingContextRepository(SQLiteRepository):
    def search_context_memories(
        self, patient_id, fragments=None, *, limit=None
    ):
        del patient_id, fragments, limit
        raise TimeoutError("simulated context timeout")


def test_context_failure_preserves_semantic_memory_path() -> None:
    repository = FailingContextRepository()
    harness = make_harness(repository=repository)
    send(harness.runtime, PatientCommandType.START_CAPTURE)
    send(
        harness.runtime,
        PatientCommandType.STOP_CAPTURE,
        payload={"audio_id": "david_fragment_001"},
    )

    assert harness.runtime.session.stage is SessionStage.HEARD_CONTENT_REVIEW
    assert harness.runtime.session.retrieved_memories
    assert harness.runtime.session.situation is None
    context_event = next(
        event
        for event in harness.runtime.events
        if event.event_type is RuntimeEventType.CONTEXT_RETRIEVED
    )
    assert context_event.payload == {
        "count": 0,
        "memory_ids": [],
        "sources": [],
    }


def test_session_snapshot_cannot_mutate_runtime_state() -> None:
    harness = make_harness(with_memory=False)
    snapshot = harness.runtime.session
    snapshot.confirmed_context.locked_tokens.append("forged")

    assert "forged" not in harness.runtime.session.confirmed_context.locked_tokens


class FailingReceiptRepository(SQLiteRepository):
    def store_receipt(self, patient_id, receipt):
        raise OSError("simulated receipt storage failure")


def test_receipt_failure_prevents_verified_memory_write() -> None:
    repository = FailingReceiptRepository()
    harness = make_harness(with_memory=False, repository=repository)
    drive_to_final_review(harness)
    final_confirm(harness)
    playback_completed(harness)

    assert harness.runtime.session.stage is SessionStage.SPOKEN
    assert harness.runtime.session.failure_status == "receipt_write_failed"
    assert harness.repository.count_memory_writes("david_demo") == 0
    assert RuntimeEventType.EXPRESSION_RECEIPT_FAILED in {
        event.event_type for event in harness.runtime.events
    }


def test_playback_failure_cannot_mark_spoken_or_write_memory() -> None:
    harness = make_harness(with_memory=False)
    drive_to_final_review(harness)
    final_confirm(harness)

    send(
        harness.runtime,
        PatientCommandType.PLAYBACK_FAILED,
        payload={
            "playback_id": "failed-playback-001",
            "output_channel": "iphone_speaker",
        },
        actor=CommandActor.SYSTEM,
    )

    assert harness.runtime.session.stage is SessionStage.VOICE_AUTHORIZED
    assert harness.runtime.session.failure_status == "playback_failed"
    assert harness.repository.get_receipt(
        "david_demo", harness.runtime.session.session_id
    ) is None
    assert harness.repository.count_memory_writes("david_demo") == 0
    assert RuntimeEventType.EXPRESSION_SPOKEN not in {
        event.event_type for event in harness.runtime.events
    }


def test_playback_callback_requires_system_actor_and_is_idempotent() -> None:
    harness = make_harness(with_memory=False)
    drive_to_final_review(harness)
    final_confirm(harness)

    with pytest.raises(CommandRejected, match="authenticated playback"):
        send(
            harness.runtime,
            PatientCommandType.PLAYBACK_COMPLETED,
            payload={
                "playback_id": "device-playback-001",
                "output_channel": "iphone_speaker",
            },
        )

    playback_completed(harness, playback_id="device-playback-001")
    first_event_count = len(harness.runtime.events)
    first_memory_count = harness.repository.count_memory_writes("david_demo")
    playback_completed(harness, playback_id="device-playback-001")

    assert harness.runtime.session.stage is SessionStage.COMPLETED
    assert len(harness.runtime.events) == first_event_count
    assert harness.repository.count_memory_writes(
        "david_demo"
    ) == first_memory_count
