from __future__ import annotations

import json
from typing import Any

from services.gateway.config import GatewaySettings
from services.gateway.provider_http import ProviderResponse
from services.gateway.providers import CloudProviderService


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
        }
    )

    call = client.calls[0]
    assert call["url"].endswith("/messages")
    assert call["headers"]["x-api-key"] == "test-key"
    assert call["headers"]["anthropic-version"] == "2023-06-01"
    assert call["payload"]["max_tokens"] == 2_048
    assert "thinking" not in call["payload"]
    assert result["requires_confirmation"] is True


def test_stepfun_audio_requests_map_documented_fields() -> None:
    client = RecordingProviderClient(
        [
            _json_response({"text": "hello"}),
            ProviderResponse(200, b"WAV", "audio/wav"),
            _json_response({"id": "file-test"}),
            _json_response({"id": "voice-test"}),
        ]
    )
    service = CloudProviderService(
        GatewaySettings(stepfun_api_key="test-key"),
        client=client,
    )

    asr = service.transcribe(b"RIFFtest", language_hint="en")
    audio, media_type = service.synthesize(
        text="hello",
        mode="neutral",
        voice_profile_id=None,
    )
    voice_id = service.enroll_voice(b"RIFFvoice")

    assert asr["transcript"] == "hello"
    assert asr["language"] == "en"
    assert b'name="response_format"' in client.calls[0]["body"]
    assert b"json" in client.calls[0]["body"]
    assert client.calls[1]["url"].endswith("/audio/create-audio")
    assert client.calls[1]["payload"]["model"] == "step-tts-mini"
    assert audio == b"WAV"
    assert media_type == "audio/wav"
    assert client.calls[2]["url"].endswith("/files")
    assert b"storage" in client.calls[2]["body"]
    assert client.calls[3]["url"].endswith("/audio/voices")
    assert client.calls[3]["payload"]["file_id"] == "file-test"
    assert voice_id == "voice-test"


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
