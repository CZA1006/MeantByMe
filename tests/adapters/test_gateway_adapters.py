from __future__ import annotations

from pathlib import Path

from meantbyme.adapters.asr import GatewayASRAdapter
from meantbyme.adapters.audio import AudioStore
from meantbyme.adapters.http import GatewayHttpClient
from meantbyme.adapters.intent import GatewayIntentAdapter
from meantbyme.adapters.tts import GatewayTTSAdapter
from meantbyme.core.domain import ConfirmedContext
from meantbyme.core.runtime.evidence import build_transcript_evidence
from tests.helpers.stub_gateway import (
    StubGatewayState,
    running_stub_gateway,
    wav_bytes,
)


PATIENT_ID = "david_demo"
SESSION_ID = "adapter-test-session"
AUDIO_ID = "adapter-test-audio"


def _audio_store(tmp_path: Path) -> AudioStore:
    store = AudioStore(tmp_path / "audio")
    store.put_wav_bytes(AUDIO_ID, wav_bytes())
    return store


def _asr(
    gateway_url: str,
    store: AudioStore,
    *,
    timeout_seconds: float = 1.0,
) -> GatewayASRAdapter:
    return GatewayASRAdapter(
        client=GatewayHttpClient(
            gateway_url,
            timeout_seconds=timeout_seconds,
            max_attempts=1,
        ),
        audio_store=store,
        patient_id=PATIENT_ID,
        session_id=SESSION_ID,
    )


def test_gateway_adapter_success_mapping(tmp_path: Path) -> None:
    state = StubGatewayState(secondary_available=True)
    fallback_situation = "Construction-time fallback context."
    situation = "Auto-composed patient context."
    with running_stub_gateway(state) as gateway:
        client = GatewayHttpClient(gateway.base_url, max_attempts=1)
        store = _audio_store(tmp_path)
        results = _asr(gateway.base_url, store).transcribe(AUDIO_ID)
        evidence = build_transcript_evidence(results)
        proposal = GatewayIntentAdapter(
            client=client,
            patient_id=PATIENT_ID,
            session_id=SESSION_ID,
            situation=fallback_situation,
        ).propose(
            evidence,
            [],
            ConfirmedContext(),
            situation,
        )
        neutral = GatewayTTSAdapter(client=client).synthesize_neutral(
            proposal.candidates[0]
        )

    assert [item.provider for item in results] == [
        "stepfun_stepaudio_asr",
        "stub_secondary_asr",
    ]
    assert all(item.status == "success" for item in results)
    assert proposal.requires_confirmation is True
    assert len(proposal.candidates) == 3
    assert neutral.status == "success"
    assert neutral.media_type == "audio/wav"
    assert neutral.audio_bytes is not None
    assert state.last_intent_payload is not None
    assert state.last_intent_payload["situation"] == situation


def test_gateway_timeout_returns_failure_status(tmp_path: Path) -> None:
    state = StubGatewayState(asr_delay_seconds=0.2)
    with running_stub_gateway(state) as gateway:
        results = _asr(
            gateway.base_url,
            _audio_store(tmp_path),
            timeout_seconds=0.02,
        ).transcribe(AUDIO_ID)

    assert len(results) == 1
    assert results[0].status == "timeout"
    assert results[0].transcript == ""


def test_invalid_intent_json_uses_template_fallback(tmp_path: Path) -> None:
    state = StubGatewayState(invalid_intent_json=True)
    with running_stub_gateway(state) as gateway:
        client = GatewayHttpClient(gateway.base_url, max_attempts=1)
        evidence = build_transcript_evidence(
            _asr(gateway.base_url, _audio_store(tmp_path)).transcribe(AUDIO_ID)
        )
        proposal = GatewayIntentAdapter(
            client=client,
            patient_id=PATIENT_ID,
            session_id=SESSION_ID,
        ).propose(
            evidence,
            [],
            ConfirmedContext(
                locked_slots={"category": "plan"},
                locked_tokens=["i", "don't", "tomorrow"],
            ),
        )

    assert proposal.requires_confirmation is True
    assert proposal.candidates[0].id == "template-c1"
    assert len(proposal.candidates) == 3
    assert all(
        "plan" in candidate.text.casefold()
        and "tomorrow" in candidate.text.casefold()
        for candidate in proposal.candidates
    )


def test_intent_timeout_uses_template_fallback(tmp_path: Path) -> None:
    state = StubGatewayState(intent_delay_seconds=0.2)
    with running_stub_gateway(state) as gateway:
        store = _audio_store(tmp_path)
        evidence = build_transcript_evidence(
            _asr(gateway.base_url, store).transcribe(AUDIO_ID)
        )
        proposal = GatewayIntentAdapter(
            client=GatewayHttpClient(
                gateway.base_url,
                timeout_seconds=0.02,
                max_attempts=1,
            ),
            patient_id=PATIENT_ID,
            session_id=SESSION_ID,
            situation="A friend asked about tomorrow.",
        ).propose(evidence, [], ConfirmedContext())

    assert proposal.requires_confirmation is True
    assert proposal.candidates[0].id == "template-c1"


def test_secondary_missing_returns_single_source(tmp_path: Path) -> None:
    with running_stub_gateway() as gateway:
        results = _asr(
            gateway.base_url, _audio_store(tmp_path)
        ).transcribe(AUDIO_ID)

    assert len(results) == 1
    assert results[0].provider == "stepfun_stepaudio_asr"
    assert results[0].status == "success"
