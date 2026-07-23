from __future__ import annotations

import base64
import json
from typing import Any

import pytest
from pydantic import ValidationError

from services.gateway.app import IntentRequest
from services.gateway.config import GatewaySettings
from services.gateway.provider_http import (
    ProviderRequestError,
    ProviderResponse,
)
from services.gateway.providers import CloudProviderService
from tests.helpers.stub_gateway import asr_sse_bytes, wav_bytes


class RecordingProviderClient:
    def __init__(self, responses: list[ProviderResponse]) -> None:
        self.responses = list(responses)
        self.calls: list[dict[str, Any]] = []

    def request(
        self, url: str, *, body: bytes, headers: dict[str, str]
    ) -> ProviderResponse:
        self.calls.append(
            {
                "kind": "request",
                "url": url,
                "body": body,
                "headers": headers,
            }
        )
        return self.responses.pop(0)

    def post_json(
        self,
        url: str,
        payload: dict[str, Any],
        *,
        headers: dict[str, str],
    ) -> ProviderResponse:
        self.calls.append(
            {
                "kind": "json",
                "url": url,
                "payload": payload,
                "headers": headers,
            }
        )
        return self.responses.pop(0)


def _json_response(payload: dict) -> ProviderResponse:
    return ProviderResponse(
        status_code=200,
        body=json.dumps(payload).encode("utf-8"),
        content_type="application/json",
    )


def _sse_response(transcript: str = " hello") -> ProviderResponse:
    return ProviderResponse(
        status_code=200,
        body=asr_sse_bytes(transcript),
        # StepFun returns the ASR SSE stream as text/plain (verified live).
        content_type="text/plain",
    )


def _proposal() -> dict:
    candidates = []
    for index, text in enumerate(
        [
            "I don't want to go tomorrow.",
            "I don't want to call tomorrow.",
        ],
        start=1,
    ):
        candidates.append(
            {
                "id": f"provider-c{index}",
                "text": text,
                "language": "en",
                "patient_supported_spans": ["i", "don't", "tomorrow"],
                "ai_added_spans": ["want"],
                "memory_support_ids": [],
                "ranking_reasons": ["provider evidence"],
                "risk_level": "ordinary",
                "source_level": "L2",
            }
        )
    return {
        "certain_content": ["i", "don't", "tomorrow"],
        "uncertain_content": ["want"],
        "candidates": candidates,
        "clarification_question": None,
        "clarification_options": [],
        "requires_confirmation": True,
    }


def test_stepfun_messages_uses_anthropic_shape_without_thinking() -> None:
    response = _json_response(
        {
            "content": [
                {"type": "text", "text": json.dumps(_proposal())}
            ]
        }
    )
    client = RecordingProviderClient([response])
    service = CloudProviderService(
        GatewaySettings(
            stepfun_api_key="test-key",
            intent_provider="stepfun",
            intent_model="step-explore",
        ),
        client=client,
    )

    result = service.propose_intent(
        {
            "evidence": {},
            "memories": [],
            "confirmed_context": {},
            "language": "en",
            "situation": "A friend asked about tomorrow.",
        }
    )

    call = client.calls[0]
    assert call["url"].endswith("/messages")
    assert call["headers"]["x-api-key"] == "test-key"
    assert call["headers"]["anthropic-version"] == "2023-06-01"
    assert call["payload"]["max_tokens"] == 2_048
    assert "thinking" not in call["payload"]
    user_content = json.loads(call["payload"]["messages"][0]["content"])
    assert user_content["situation"] == "A friend asked about tomorrow."
    assert result["requires_confirmation"] is True


def test_stepfun_audio_requests_map_documented_fields() -> None:
    client = RecordingProviderClient(
        [
            _sse_response(" hello"),
            ProviderResponse(200, b"WAV", "audio/wav"),
            ProviderResponse(200, b"PERSONAL", "audio/wav"),
        ]
    )
    service = CloudProviderService(
        GatewaySettings(stepfun_api_key="test-key"),
        client=client,
    )

    asr = service.transcribe(wav_bytes(), language_hint="en")
    audio, media_type = service.synthesize(
        text="hello",
        mode="neutral",
        voice_profile_id=None,
    )
    personal_audio, _ = service.synthesize(
        text="confirmed",
        mode="personal",
        voice_profile_id="official-voice",
    )
    voice_id = service.enroll_voice(b"RIFFvoice")

    assert asr["transcript"] == "hello"
    assert asr["language"] == "en"
    assert asr["provider"] == "stepfun_stepaudio_asr"
    assert client.calls[0]["url"].endswith("/audio/asr/sse")
    assert client.calls[0]["headers"]["Accept"] == "text/event-stream"
    assert "User-Agent" in client.calls[0]["headers"]
    transcription = client.calls[0]["payload"]["audio"]["input"][
        "transcription"
    ]
    audio_format = client.calls[0]["payload"]["audio"]["input"]["format"]
    pcm = base64.b64decode(client.calls[0]["payload"]["audio"]["data"])
    assert transcription == {
        "model": "stepaudio-2.5-asr",
        "language": "en",
        "enable_itn": True,
    }
    assert audio_format == {
        "type": "pcm",
        "codec": "pcm_s16le",
        "rate": 16_000,
        "bits": 16,
        "channel": 1,
    }
    assert pcm and not pcm.startswith(b"RIFF")
    assert client.calls[1]["url"].endswith("/audio/speech")
    assert client.calls[1]["payload"] == {
        "model": "stepaudio-2.5-tts",
        "input": "hello",
        "voice": "cixingnansheng",
        "response_format": "wav",
    }
    assert audio == b"WAV"
    assert media_type == "audio/wav"
    assert client.calls[2]["payload"] == {
        "model": "stepaudio-2.5-tts",
        "input": "confirmed",
        "voice": "official-voice",
        "response_format": "wav",
    }
    assert personal_audio == b"PERSONAL"
    assert voice_id is None
    assert len(client.calls) == 3


@pytest.mark.parametrize(
    "body",
    [
        b'data: {"type":"transcript.text.done","text":""}\n',
        b'data: {"type":"error","error":{"message":"overloaded"}}\n',
    ],
)
def test_empty_or_error_asr_sse_returns_failure_status(body: bytes) -> None:
    client = RecordingProviderClient(
        [
            ProviderResponse(
                200,
                body,
                "text/event-stream",
            )
        ]
    )
    service = CloudProviderService(
        GatewaySettings(stepfun_api_key="test-key"),
        client=client,
    )

    result = service.transcribe(wav_bytes(), language_hint="en")

    assert result["status"] == "failed"
    assert result["transcript"] == ""


def test_asr_sse_falls_back_to_accumulated_deltas() -> None:
    client = RecordingProviderClient(
        [
            ProviderResponse(
                200,
                (
                    b'data: {"type":"transcript.text.delta","delta":" hello"}\n\n'
                    b'data: {"type":"transcript.text.delta","delta":" world"}\n'
                ),
                "text/event-stream",
            )
        ]
    )
    service = CloudProviderService(
        GatewaySettings(stepfun_api_key="test-key"),
        client=client,
    )

    result = service.transcribe(wav_bytes(), language_hint="en")

    assert result["status"] == "success"
    assert result["transcript"] == "hello world"


def test_voice_cloning_uses_standard_upload_when_enabled() -> None:
    client = RecordingProviderClient(
        [
            _json_response({"id": "file-test"}),
            _json_response({"id": "voice-test"}),
        ]
    )
    service = CloudProviderService(
        GatewaySettings(
            stepfun_api_key="test-key",
            enable_voice_cloning=True,
        ),
        client=client,
    )

    voice_id = service.enroll_voice(b"RIFFvoice")

    assert client.calls[0]["url"] == "https://api.stepfun.com/v1/files"
    assert b"storage" in client.calls[0]["body"]
    assert client.calls[1]["url"].endswith("/audio/voices")
    assert client.calls[1]["payload"] == {
        "file_id": "file-test",
        "model": "stepaudio-2.5-tts",
    }
    assert voice_id == "voice-test"


def test_voice_cloning_402_returns_none() -> None:
    class InsufficientBalanceClient(RecordingProviderClient):
        def request(
            self, url: str, *, body: bytes, headers: dict[str, str]
        ) -> ProviderResponse:
            raise ProviderRequestError(
                "provider_http_402", status_code=402
            )

    service = CloudProviderService(
        GatewaySettings(
            stepfun_api_key="test-key",
            enable_voice_cloning=True,
        ),
        client=InsufficientBalanceClient([]),
    )

    assert service.enroll_voice(b"RIFFvoice") is None


def test_openagents_uses_openai_chat_completions_shape() -> None:
    client = RecordingProviderClient(
        [
            _json_response(
                {
                    "choices": [
                        {
                            "message": {
                                "content": json.dumps(_proposal())
                            }
                        }
                    ]
                }
            )
        ]
    )
    service = CloudProviderService(
        GatewaySettings(
            openagents_api_key="test-key",
            intent_provider="openagents",
            intent_model="deepseek-v4-pro",
        ),
        client=client,
    )

    service.propose_intent(
        {
            "evidence": {},
            "memories": [],
            "confirmed_context": {},
            "language": "en",
        }
    )

    call = client.calls[0]
    assert call["url"].endswith("/chat/completions")
    assert call["payload"]["model"] == "deepseek-v4-pro"
    assert call["headers"]["Authorization"] == "Bearer test-key"


def test_step_plan_config_defaults_and_attempt_floor(monkeypatch) -> None:
    for name in [
        "INTENT_PROVIDER",
        "INTENT_MODEL",
        "STEPFUN_BASE_URL",
        "ENABLE_VOICE_CLONING",
    ]:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("PROVIDER_MAX_ATTEMPTS", "1")

    settings = GatewaySettings.from_env(load_local_env=False)

    assert settings.intent_provider == "stepfun"
    assert settings.intent_model == "step-explore"
    assert settings.stepfun_base_url == (
        "https://api.stepfun.com/step_plan/v1"
    )
    assert settings.provider_max_attempts == 3
    assert settings.enable_voice_cloning is False


def test_gateway_intent_request_accepts_situation_and_forbids_extra() -> None:
    request = IntentRequest(
        patient_id="david_demo",
        session_id="session-1",
        language="en",
        situation="A friend asked about tomorrow.",
        evidence={},
        memories=[],
        confirmed_context={},
    )

    assert request.situation == "A friend asked about tomorrow."
    with pytest.raises(ValidationError):
        IntentRequest(
            patient_id="david_demo",
            session_id="session-1",
            evidence={},
            memories=[],
            confirmed_context={},
            speak=True,
        )
