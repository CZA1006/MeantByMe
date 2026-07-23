from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from meantbyme.adapters.asr import MockASRAdapter
from meantbyme.adapters.intent import MockIntentAdapter
from meantbyme.adapters.storage import SQLiteRepository
from meantbyme.adapters.tts import CachedTTSAdapter
from meantbyme.core.domain import (
    ConfirmationMethod,
    MemoryItem,
    MemoryType,
    PatientCommand,
    PatientCommandType,
    SessionStage,
    VerificationLevel,
)
from meantbyme.core.ports import IntentPort
from meantbyme.core.runtime import MeantByMeRuntime


ROOT = Path(__file__).resolve().parents[1]
PATIENT_ID = "david_demo"
VOICE_PROFILE_ID = "voice-david-demo"
AUDIO_ID = "david_fragment_001"


@dataclass
class Harness:
    runtime: MeantByMeRuntime
    repository: SQLiteRepository
    tts: CachedTTSAdapter


def make_harness(
    *,
    with_memory: bool = True,
    fail_personal_tts: bool = False,
    intent: IntentPort | None = None,
    repository: SQLiteRepository | None = None,
    session_id: str = "test-session-001",
    situation: str | None = None,
    asr_fixtures: dict[str, list[dict[str, Any]]] | None = None,
) -> Harness:
    repo = repository or SQLiteRepository()
    repo.add_patient(PATIENT_ID, "David")
    repo.add_patient("other_patient", "Other")
    if with_memory:
        repo.seed_verified_memory(
            PATIENT_ID,
            MemoryItem(
                id="mem-david-go-tomorrow",
                patient_id=PATIENT_ID,
                memory_type=MemoryType.SEMANTIC,
                verification_level=VerificationLevel.GOLD,
                text="I don't want to go tomorrow.",
                language="en",
                context={"topic": "planning"},
                usage_count=2,
                last_used_at=datetime.now(UTC),
                confirmation_session_id="historical-confirmation",
            ),
        )
    repo.grant_voice_consent(
        PATIENT_ID,
        "voice-consent-david",
        "voice-enrollment-david",
        VOICE_PROFILE_ID,
    )
    fixtures = asr_fixtures or {
        AUDIO_ID: [
            {
                "provider": "mock_primary",
                "transcript": "I don't tomorrow",
                "language": "en",
                "segments": [],
                "latency_ms": 1,
                "status": "success",
            },
            {
                "provider": "mock_secondary",
                "transcript": "I don't want tomorrow",
                "language": "en",
                "segments": [],
                "latency_ms": 2,
                "status": "success",
            },
        ]
    }
    tts = CachedTTSAdapter(
        ROOT / "demo/audio/neutral_candidate.cache",
        ROOT / "demo/audio/david_personal_final.cache",
        fail_personal=fail_personal_tts,
    )
    runtime = MeantByMeRuntime(
        asr=MockASRAdapter(fixtures),
        intent=intent or MockIntentAdapter(),
        tts=tts,
        repository=repo,
    )
    runtime.create_session(
        session_id=session_id,
        patient_id=PATIENT_ID,
        language="en",
        voice_profile_id=VOICE_PROFILE_ID,
        situation=situation,
    )
    return Harness(runtime=runtime, repository=repo, tts=tts)


def send(
    runtime: MeantByMeRuntime,
    command: PatientCommandType,
    *,
    payload: dict[str, Any] | None = None,
    confirmation_method: ConfirmationMethod | None = None,
    **command_updates: Any,
) -> None:
    runtime.handle(
        PatientCommand(
            command=command,
            session_id=runtime.session.session_id,
            payload=payload or {},
            confirmation_method=confirmation_method,
            **command_updates,
        )
    )


def drive_to_route(harness: Harness) -> None:
    send(harness.runtime, PatientCommandType.START_CAPTURE)
    send(
        harness.runtime,
        PatientCommandType.STOP_CAPTURE,
        payload={"audio_id": AUDIO_ID},
    )
    send(harness.runtime, PatientCommandType.CONFIRM_HEARD_CONTENT)


def drive_to_final_review(harness: Harness) -> None:
    drive_to_route(harness)
    if harness.runtime.session.stage is SessionStage.CATEGORY_CLARIFICATION:
        send(
            harness.runtime,
            PatientCommandType.SELECT_CATEGORY,
            payload={"category": "plan"},
        )
    candidate = harness.runtime.session.candidates[0]
    send(
        harness.runtime,
        PatientCommandType.SELECT_CANDIDATE,
        payload={"candidate_id": candidate.id},
    )
    assert harness.runtime.session.stage is SessionStage.FINAL_REVIEW


def final_confirm(
    harness: Harness, *, strict: bool | None = None
) -> None:
    payload = {"private_readback_completed": True}
    if strict is not None:
        payload["strict_confirmation"] = strict
    send(
        harness.runtime,
        PatientCommandType.FINAL_CONFIRM,
        payload=payload,
        confirmation_method=ConfirmationMethod.LARGE_BUTTON,
    )
