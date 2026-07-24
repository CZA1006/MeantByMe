from __future__ import annotations

from pathlib import Path

from conftest import send
from meantbyme.adapters.asr import MockASRAdapter
from meantbyme.adapters.intent import MockIntentAdapter
from meantbyme.adapters.profile import (
    load_profile_bundle,
    seed_profile_repository,
)
from meantbyme.adapters.storage import SQLiteRepository
from meantbyme.adapters.tts import CachedTTSAdapter
from meantbyme.core.domain import PatientCommandType, SessionStage
from meantbyme.core.runtime import MeantByMeRuntime


ROOT = Path(__file__).resolve().parents[2]
AUDIO_ID = "lin-yue-hackathon-audio"


class RecordingIntent(MockIntentAdapter):
    def __init__(self) -> None:
        self.situation: str | None = None

    def propose(
        self,
        evidence,
        memories,
        confirmed_context,
        situation=None,
    ):
        self.situation = situation
        return super().propose(
            evidence,
            memories,
            confirmed_context,
            situation,
        )


def test_profile_plus_rich_single_asr_retrieves_only_relevant_context() -> None:
    profile = load_profile_bundle(
        ROOT / "demo/profiles/lin_yue_demo.md"
    )
    repository = SQLiteRepository()
    seed_profile_repository(repository, profile)
    intent = RecordingIntent()
    runtime = MeantByMeRuntime(
        asr=MockASRAdapter(
            {
                AUDIO_ID: [
                    {
                        "provider": "single_primary",
                        "transcript": (
                            "Hi we are MeantByMe we help stroke survivors "
                            "organize their needs and speak after confirmation"
                        ),
                        "language": "en",
                        "status": "success",
                    }
                ]
            }
        ),
        intent=intent,
        tts=CachedTTSAdapter(
            ROOT / "demo/audio/neutral_candidate.cache",
            ROOT / "demo/audio/david_personal_final.cache",
        ),
        repository=repository,
    )
    runtime.create_session(
        session_id="lin-yue-profile-audio",
        patient_id=profile.patient.patient_id,
        language="en",
        voice_profile_id=profile.voice_consent.voice_profile_id,
    )

    send(runtime, PatientCommandType.START_CAPTURE)
    send(
        runtime,
        PatientCommandType.STOP_CAPTURE,
        payload={"audio_id": AUDIO_ID},
    )

    assert runtime.session.situation is not None
    assert "building MeantByMe" in runtime.session.situation
    assert "Wednesday is normally reserved for treatment" not in (
        runtime.session.situation
    )
    assert "husband reports" not in runtime.session.situation

    send(runtime, PatientCommandType.CONFIRM_HEARD_CONTENT)

    assert runtime.session.stage is SessionStage.CANDIDATE_SELECTION
    assert runtime.session.evidence is not None
    assert runtime.session.evidence.stable_fragments == []
    assert runtime.session.selected_candidate_id is None
    assert runtime.session.voice_authorized is False
    assert intent.situation == runtime.session.situation
