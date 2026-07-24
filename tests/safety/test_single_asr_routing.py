from conftest import AUDIO_ID, drive_to_route, make_harness
from meantbyme.core.domain import RuntimeEventType, SessionStage


def test_content_rich_single_asr_skips_generic_category_but_never_selects() -> None:
    harness = make_harness(
        with_memory=False,
        session_id="single-asr-rich",
        asr_fixtures={
            AUDIO_ID: [
                {
                    "provider": "single_primary",
                    "transcript": (
                        "Hi we help stroke survivors communicate their needs "
                        "and speak only after confirmation"
                    ),
                    "language": "en",
                    "status": "success",
                }
            ]
        },
    )

    drive_to_route(harness)

    assert harness.runtime.session.stage is SessionStage.CANDIDATE_SELECTION
    assert harness.runtime.session.evidence is not None
    assert harness.runtime.session.evidence.stable_fragments == []
    assert harness.runtime.session.selected_candidate_id is None
    assert harness.runtime.session.patient_confirmed is False
    assert harness.runtime.session.voice_authorized is False
    assert harness.tts.personal_calls == 0
    assert not any(
        event.event_type is RuntimeEventType.CLARIFICATION_REQUESTED
        for event in harness.runtime.events
    )
