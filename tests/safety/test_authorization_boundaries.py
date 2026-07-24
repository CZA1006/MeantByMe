from __future__ import annotations

import pytest
from pydantic import ValidationError

from conftest import (
    PATIENT_ID,
    VOICE_PROFILE_ID,
    drive_to_final_review,
    final_confirm,
    make_harness,
    send,
)
from meantbyme.adapters.intent import MockIntentAdapter
from meantbyme.core.domain import (
    CommandActor,
    ConfirmationMethod,
    IntentProposal,
    ExpressionCandidate,
    PatientCommand,
    PatientCommandType,
    RuntimeEventType,
    SessionStage,
    RiskLevel,
)
from meantbyme.core.runtime import CommandRejected, ProviderContractError


def test_unconfirmed_candidate_cannot_speak() -> None:
    harness = make_harness()
    drive_to_final_review(harness)

    assert harness.tts.personal_calls == 0
    assert harness.runtime.session.voice_authorized is False
    neutral_result = harness.tts.synthesize_neutral(
        harness.runtime.session.candidates[0]
    )
    assert neutral_result.audio_bytes is not None
    assert neutral_result.audio_bytes.startswith(b"RIFF")
    with pytest.raises(TypeError):
        harness.tts.synthesize_personal("raw candidate")  # type: ignore[arg-type]


def test_silence_or_timeout_cannot_confirm() -> None:
    harness = make_harness()
    drive_to_final_review(harness)

    with pytest.raises(CommandRejected, match="Silence"):
        send(
            harness.runtime,
            PatientCommandType.FINAL_CONFIRM,
            payload={"private_readback_completed": True},
        )
    with pytest.raises(ValidationError):
        PatientCommand(
            command=PatientCommandType.FINAL_CONFIRM,
            session_id=harness.runtime.session.session_id,
            confirmation_method="timeout",  # type: ignore[arg-type]
        )
    assert harness.tts.personal_calls == 0
    assert harness.runtime.session.stage is SessionStage.FINAL_REVIEW


def test_caregiver_cannot_authorize_patient_voice() -> None:
    harness = make_harness()
    drive_to_final_review(harness)

    with pytest.raises(CommandRejected, match="explicit patient command"):
        send(
            harness.runtime,
            PatientCommandType.FINAL_CONFIRM,
            payload={"private_readback_completed": True},
            confirmation_method=ConfirmationMethod.LARGE_BUTTON,
            actor=CommandActor.CAREGIVER,
        )
    assert harness.tts.personal_calls == 0
    assert harness.runtime.session.patient_confirmed is False


class NonConfirmingIntent(MockIntentAdapter):
    def propose(
        self, evidence, memories, confirmed_context, situation=None
    ) -> IntentProposal:
        proposal = super().propose(
            evidence, memories, confirmed_context, situation
        )
        return proposal.model_copy(update={"requires_confirmation": False})


def test_intent_provider_cannot_skip_final_confirmation() -> None:
    harness = make_harness(intent=NonConfirmingIntent())
    send(harness.runtime, PatientCommandType.START_CAPTURE)
    send(
        harness.runtime,
        PatientCommandType.STOP_CAPTURE,
        payload={"audio_id": "david_fragment_001"},
    )

    with pytest.raises(ProviderContractError, match="skip"):
        send(
            harness.runtime,
            PatientCommandType.CONFIRM_HEARD_CONTENT,
        )
    assert harness.runtime.session.stage is SessionStage.UNCERTAINTY_ASSESSED
    assert harness.tts.personal_calls == 0


def test_tts_failure_does_not_mark_expression_spoken() -> None:
    harness = make_harness(fail_personal_tts=True)
    drive_to_final_review(harness)
    final_confirm(harness)

    assert harness.runtime.session.stage is SessionStage.VOICE_AUTHORIZED
    assert harness.runtime.session.failure_status == "personal_tts_failed"
    assert harness.repository.get_receipt(
        PATIENT_ID, harness.runtime.session.session_id
    ) is None
    assert harness.repository.count_memory_writes(PATIENT_ID) == 0
    assert RuntimeEventType.EXPRESSION_SPOKEN not in {
        event.event_type for event in harness.runtime.events
    }


def test_revoked_long_term_consent_blocks_personal_voice() -> None:
    harness = make_harness()
    drive_to_final_review(harness)
    harness.repository.revoke_voice_consent(PATIENT_ID, VOICE_PROFILE_ID)

    final_confirm(harness)

    assert harness.runtime.session.stage is SessionStage.PATIENT_CONFIRMED
    assert harness.runtime.session.voice_authorized is False
    assert harness.tts.personal_calls == 0
    assert RuntimeEventType.VOICE_AUTHORIZATION_BLOCKED in {
        event.event_type for event in harness.runtime.events
    }


class L3Intent(MockIntentAdapter):
    def propose(
        self, evidence, memories, confirmed_context, situation=None
    ) -> IntentProposal:
        proposal = super().propose(
            evidence, memories, confirmed_context, situation
        )
        suggestion = ExpressionCandidate(
            id="l3-suggestion",
            text="I don't want to reschedule tomorrow.",
            language="en",
            patient_supported_spans=list(confirmed_context.locked_tokens),
            ai_added_spans=["want to reschedule"],
            memory_support_ids=[],
            ranking_reasons=["agent suggestion"],
            risk_level=RiskLevel.ORDINARY,
            source_level="L3",
        )
        return proposal.model_copy(
            update={"candidates": [suggestion, *proposal.candidates[:2]]}
        )


def test_l3_cannot_speak_without_additional_confirmation() -> None:
    harness = make_harness(with_memory=False, intent=L3Intent())
    send(harness.runtime, PatientCommandType.START_CAPTURE)
    send(
        harness.runtime,
        PatientCommandType.STOP_CAPTURE,
        payload={"audio_id": "david_fragment_001"},
    )
    send(harness.runtime, PatientCommandType.CONFIRM_HEARD_CONTENT)
    send(
        harness.runtime,
        PatientCommandType.SELECT_CANDIDATE,
        payload={"candidate_id": "l3-suggestion"},
    )

    with pytest.raises(CommandRejected, match="L3 suggestion"):
        send(
            harness.runtime,
            PatientCommandType.FINAL_CONFIRM,
            payload={"private_readback_completed": True},
            confirmation_method=ConfirmationMethod.LARGE_BUTTON,
        )
    assert harness.tts.personal_calls == 0
    assert harness.runtime.session.stage is SessionStage.FINAL_REVIEW
