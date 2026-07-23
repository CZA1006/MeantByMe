from __future__ import annotations

from pathlib import Path

from meantbyme.cli import run_cloud
from meantbyme.core.domain import RuntimeEventType, SessionStage
from tests.helpers.stub_gateway import (
    StubGatewayState,
    running_stub_gateway,
    wav_bytes,
)


def _write_input_wav(tmp_path: Path) -> Path:
    path = tmp_path / "input.wav"
    path.write_bytes(wav_bytes())
    return path


def test_full_cloud_golden_path_against_stub(tmp_path: Path) -> None:
    with running_stub_gateway() as gateway:
        result = run_cloud(
            gateway_url=gateway.base_url,
            audio_path=_write_input_wav(tmp_path),
            audio_store_dir=tmp_path / "audio",
            timeout_seconds=1.0,
            max_attempts=1,
        )

    assert result["final_stage"] == SessionStage.COMPLETED.value
    assert result["unauthorized_voice_rate"] == 0
    assert result["receipt"]["patient_confirmed"] is True
    event_types = [item["event_type"] for item in result["trace"]]
    assert RuntimeEventType.EXPRESSION_SPOKEN.value in event_types
    assert event_types[-1] == RuntimeEventType.SESSION_COMPLETED.value


def test_personal_tts_failure_does_not_mark_spoken(tmp_path: Path) -> None:
    state = StubGatewayState(personal_tts_failure=True)
    with running_stub_gateway(state) as gateway:
        result = run_cloud(
            gateway_url=gateway.base_url,
            audio_path=_write_input_wav(tmp_path),
            audio_store_dir=tmp_path / "audio",
            timeout_seconds=1.0,
            max_attempts=1,
        )

    assert result["final_stage"] == SessionStage.VOICE_AUTHORIZED.value
    event_types = [item["event_type"] for item in result["trace"]]
    assert RuntimeEventType.TTS_FAILED.value in event_types
    assert RuntimeEventType.EXPRESSION_SPOKEN.value not in event_types
    assert result["receipt"] is None
