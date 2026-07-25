import pytest

from conftest import AUDIO_ID, PATIENT_ID, make_harness, send
from meantbyme.adapters.intent import MockIntentAdapter
from meantbyme.core.domain import (
    CommandActor,
    ConfirmationMethod,
    IntentProposal,
    PatientCommandType,
    RuntimeEventType,
    SessionStage,
)
from meantbyme.core.runtime import CommandRejected


def drive_to_private_voice_review(harness):
    send(harness.runtime, PatientCommandType.START_CAPTURE)
    send(
        harness.runtime,
        PatientCommandType.STOP_CAPTURE,
        payload={"audio_id": AUDIO_ID},
    )
    send(
        harness.runtime,
        PatientCommandType.PROCEED_WITHOUT_HEARD_CONFIRMATION,
        actor=CommandActor.SYSTEM,
    )
    candidate = harness.runtime.session.candidates[0]
    send(
        harness.runtime,
        PatientCommandType.PREPARE_CANDIDATE_READBACK,
        payload={"candidate_id": candidate.id},
        actor=CommandActor.SYSTEM,
    )
    return candidate


def affirmation_evidence() -> dict:
    return {
        "prompt_id": "prompt-one",
        "audio_hash": "audio-one",
        "intent": "affirm",
        "consensus": True,
    }


class L3IntentAdapter(MockIntentAdapter):
    def propose(self, *args, **kwargs) -> IntentProposal:
        proposal = super().propose(*args, **kwargs)
        candidates = list(proposal.candidates)
        candidates[0] = candidates[0].model_copy(
            update={"source_level": "L3"}
        )
        return proposal.model_copy(update={"candidates": candidates})


def test_agreed_voice_affirmation_uses_only_neutral_audio() -> None:
    harness = make_harness()
    candidate = drive_to_private_voice_review(harness)

    assert harness.runtime.session.stage is SessionStage.FINAL_REVIEW
    assert harness.runtime.session.patient_confirmed is False
    assert harness.runtime.session.confirmed_context.locked_tokens == []
    assert harness.tts.personal_calls == 0
    assert not any(
        event.event_type is RuntimeEventType.PATIENT_SELECTION_RECEIVED
        for event in harness.runtime.events
    )

    send(
        harness.runtime,
        PatientCommandType.CONFIRM_NEUTRAL_PLAYBACK,
        payload={
            "private_readback_completed": True,
            "voice_confirmation_evidence": affirmation_evidence(),
        },
        confirmation_method=ConfirmationMethod.VOICE_SEMANTIC,
    )

    assert harness.runtime.session.stage is SessionStage.PATIENT_CONFIRMED
    assert harness.runtime.session.selected_candidate_id == candidate.id
    assert harness.runtime.session.voice_authorized is False
    assert harness.runtime.session.authorized_expression is None
    assert harness.tts.personal_calls == 0

    send(
        harness.runtime,
        PatientCommandType.PLAYBACK_COMPLETED,
        payload={
            "playback_id": "neutral-playback-1",
            "output_channel": "iphone_speaker",
        },
        actor=CommandActor.SYSTEM,
    )

    assert harness.runtime.session.stage is SessionStage.COMPLETED
    receipt = harness.repository.get_receipt(
        PATIENT_ID, harness.runtime.session.session_id
    )
    assert receipt is not None
    assert receipt.confirmation_method is ConfirmationMethod.VOICE_SEMANTIC
    assert receipt.voice_profile_id is None
    assert receipt.authorization_scope is None
    assert receipt.output_channel == "iphone_speaker"
    assert harness.tts.personal_calls == 0


def test_voice_rejection_removes_only_current_candidate() -> None:
    harness = make_harness()
    rejected = drive_to_private_voice_review(harness)

    send(
        harness.runtime,
        PatientCommandType.REJECT_CURRENT_CANDIDATE,
    )

    assert harness.runtime.session.stage is SessionStage.CANDIDATE_SELECTION
    assert harness.runtime.session.selected_candidate_id is None
    assert rejected.text in harness.runtime.session.confirmed_context.rejected_texts
    assert all(
        candidate.id != rejected.id
        for candidate in harness.runtime.session.candidates
    )
    assert harness.runtime.session.patient_confirmed is False
    assert harness.tts.personal_calls == 0
    assert harness.repository.count_memory_writes(PATIENT_ID) == 0


@pytest.mark.parametrize(
    "evidence",
    [
        {
            "prompt_id": "prompt-one",
            "audio_hash": "audio-one",
            "intent": "unknown",
            "consensus": True,
        },
        {
            "prompt_id": "prompt-one",
            "audio_hash": "audio-one",
            "intent": "affirm",
            "consensus": False,
        },
    ],
)
def test_unknown_or_disagreed_voice_cannot_confirm(evidence: dict) -> None:
    harness = make_harness()
    drive_to_private_voice_review(harness)

    with pytest.raises(CommandRejected, match="agreed affirmation"):
        send(
            harness.runtime,
            PatientCommandType.CONFIRM_NEUTRAL_PLAYBACK,
            payload={
                "private_readback_completed": True,
                "voice_confirmation_evidence": evidence,
            },
            confirmation_method=ConfirmationMethod.VOICE_SEMANTIC,
        )

    assert harness.runtime.session.stage is SessionStage.FINAL_REVIEW
    assert harness.runtime.session.patient_confirmed is False
    assert harness.tts.personal_calls == 0


def test_wrong_method_or_incomplete_readback_cannot_confirm() -> None:
    harness = make_harness()
    drive_to_private_voice_review(harness)

    with pytest.raises(CommandRejected, match="semantic voice"):
        send(
            harness.runtime,
            PatientCommandType.CONFIRM_NEUTRAL_PLAYBACK,
            payload={
                "private_readback_completed": True,
                "voice_confirmation_evidence": affirmation_evidence(),
            },
            confirmation_method=ConfirmationMethod.LARGE_BUTTON,
        )
    with pytest.raises(CommandRejected, match="readback"):
        send(
            harness.runtime,
            PatientCommandType.CONFIRM_NEUTRAL_PLAYBACK,
            payload={
                "private_readback_completed": False,
                "voice_confirmation_evidence": affirmation_evidence(),
            },
            confirmation_method=ConfirmationMethod.VOICE_SEMANTIC,
        )

    assert harness.runtime.session.stage is SessionStage.FINAL_REVIEW
    assert harness.runtime.session.patient_confirmed is False
    assert harness.tts.personal_calls == 0


def test_l3_neutral_playback_requires_two_distinct_voice_confirmations() -> None:
    harness = make_harness(intent=L3IntentAdapter())
    drive_to_private_voice_review(harness)

    with pytest.raises(CommandRejected, match="another voice confirmation"):
        send(
            harness.runtime,
            PatientCommandType.CONFIRM_NEUTRAL_PLAYBACK,
            payload={
                "private_readback_completed": True,
                "voice_confirmation_evidence": affirmation_evidence(),
            },
            confirmation_method=ConfirmationMethod.VOICE_SEMANTIC,
        )

    send(
        harness.runtime,
        PatientCommandType.CONFIRM_NEUTRAL_PLAYBACK,
        payload={
            "private_readback_completed": True,
            "additional_voice_confirmation": True,
            "voice_confirmation_evidence": {
                **affirmation_evidence(),
                "prompt_id": "prompt-two",
                "audio_hash": "audio-two",
                "first_prompt_id": "prompt-one",
                "second_prompt_id": "prompt-two",
                "first_audio_hash": "audio-one",
                "second_audio_hash": "audio-two",
            },
        },
        confirmation_method=ConfirmationMethod.VOICE_SEMANTIC,
    )

    assert harness.runtime.session.stage is SessionStage.PATIENT_CONFIRMED
    assert harness.runtime.session.voice_authorized is False
    assert harness.tts.personal_calls == 0
