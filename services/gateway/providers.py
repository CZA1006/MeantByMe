from __future__ import annotations

import base64
import json
import time
from typing import Any
from uuid import uuid4

from pydantic import ValidationError

from meantbyme.core.domain import IntentProposal
from services.gateway.config import GatewaySettings
from services.gateway.prompts import INTENT_SYSTEM_PROMPT
from services.gateway.provider_http import (
    ProviderHttpClient,
    ProviderRequestError,
    ProviderResponse,
)


class ProviderContractError(RuntimeError):
    pass


class CloudProviderService:
    def __init__(
        self,
        settings: GatewaySettings,
        client: ProviderHttpClient | None = None,
    ) -> None:
        self.settings = settings
        self._client = client or ProviderHttpClient(
            timeout_seconds=settings.provider_timeout_seconds,
            max_attempts=settings.provider_max_attempts,
            backoff_seconds=settings.retry_backoff_seconds,
        )

    def transcribe(
        self, wav_bytes: bytes, *, language_hint: str | None
    ) -> dict[str, Any]:
        self._require_secret(self.settings.stepfun_api_key, "StepFun")
        started = time.monotonic()
        body, content_type = _multipart(
            fields={
                "model": "step-asr",
                "response_format": "json",
            },
            file_field="file",
            filename="audio.wav",
            file_content_type="audio/wav",
            file_bytes=wav_bytes,
        )
        response = self._client.request(
            f"{self.settings.stepfun_base_url}/audio/transcriptions",
            body=body,
            headers={
                "Authorization": f"Bearer {self.settings.stepfun_api_key}",
                "Content-Type": content_type,
                "Accept": "application/json",
            },
        )
        payload = _json_object(response)
        transcript = payload.get("text") or payload.get("transcript")
        if not isinstance(transcript, str):
            raise ProviderContractError("ASR response has no transcript text")
        return {
            "provider": "stepfun_step_asr",
            "transcript": transcript,
            "language": payload.get("language") or language_hint,
            "segments": (
                payload.get("segments")
                if isinstance(payload.get("segments"), list)
                else []
            ),
            "latency_ms": int((time.monotonic() - started) * 1000),
            "status": "success",
            "error": None,
        }

    def propose_intent(self, request_payload: dict[str, Any]) -> dict[str, Any]:
        user_content = json.dumps(
            {
                "evidence": request_payload["evidence"],
                "memories": request_payload["memories"],
                "confirmed_context": request_payload["confirmed_context"],
                "language": request_payload.get("language"),
            },
            separators=(",", ":"),
            ensure_ascii=False,
        )
        if self.settings.intent_provider == "stepfun":
            text = self._stepfun_intent(user_content)
        else:
            text = self._openagents_intent(user_content)
        proposal_payload = _extract_json_text(text)
        try:
            proposal = IntentProposal.model_validate(proposal_payload)
        except ValidationError as error:
            raise ProviderContractError(
                "Intent response failed domain validation"
            ) from error
        if not proposal.requires_confirmation:
            raise ProviderContractError("Intent response skipped confirmation")
        if not 2 <= len(proposal.candidates) <= 3:
            raise ProviderContractError("Intent response candidate count invalid")
        return proposal.model_dump(mode="json")

    def synthesize(
        self,
        *,
        text: str,
        mode: str,
        voice_profile_id: str | None,
    ) -> tuple[bytes, str]:
        self._require_secret(self.settings.stepfun_api_key, "StepFun")
        if mode == "personal" and not voice_profile_id:
            raise ProviderContractError(
                "Personal synthesis requires voice_profile_id"
            )
        payload = {
            "model": (
                "stepaudio-2.5-tts"
                if mode == "personal"
                else "step-tts-mini"
            ),
            "input": text,
            "voice": (
                voice_profile_id
                if mode == "personal"
                else self.settings.neutral_voice
            ),
            "response_format": "wav",
        }
        response = self._client.post_json(
            f"{self.settings.stepfun_base_url}/audio/create-audio",
            payload,
            headers={
                "Authorization": f"Bearer {self.settings.stepfun_api_key}",
                "Accept": "audio/wav",
            },
        )
        return _audio_response(response)

    def enroll_voice(self, wav_bytes: bytes) -> str:
        self._require_secret(self.settings.stepfun_api_key, "StepFun")
        body, content_type = _multipart(
            fields={"purpose": "storage"},
            file_field="file",
            filename="voice.wav",
            file_content_type="audio/wav",
            file_bytes=wav_bytes,
        )
        upload_response = self._client.request(
            f"{self.settings.stepfun_base_url}/files",
            body=body,
            headers={
                "Authorization": f"Bearer {self.settings.stepfun_api_key}",
                "Content-Type": content_type,
                "Accept": "application/json",
            },
        )
        upload_payload = _json_object(upload_response)
        file_id = upload_payload.get("id")
        if not isinstance(file_id, str):
            raise ProviderContractError("Voice sample upload returned no file_id")
        response = self._client.post_json(
            f"{self.settings.stepfun_base_url}/audio/voices",
            {
                "file_id": file_id,
                "model": "stepaudio-2.5-tts",
            },
            headers={
                "Authorization": f"Bearer {self.settings.stepfun_api_key}",
                "Accept": "application/json",
            },
        )
        payload = _json_object(response)
        voice_id = payload.get("voice_id") or payload.get("id")
        if not isinstance(voice_id, str) and isinstance(
            payload.get("data"), dict
        ):
            voice_id = payload["data"].get("voice_id") or payload["data"].get(
                "id"
            )
        if not isinstance(voice_id, str):
            raise ProviderContractError("Voice enrollment returned no voice_id")
        return voice_id

    def _openagents_intent(self, user_content: str) -> str:
        self._require_secret(self.settings.openagents_api_key, "OpenAgents")
        response = self._client.post_json(
            f"{self.settings.openagents_base_url}/chat/completions",
            {
                "model": self.settings.intent_model,
                "messages": [
                    {"role": "system", "content": INTENT_SYSTEM_PROMPT},
                    {"role": "user", "content": user_content},
                ],
                "temperature": 0,
                "response_format": {"type": "json_object"},
            },
            headers={
                "Authorization": (
                    f"Bearer {self.settings.openagents_api_key}"
                ),
                "Accept": "application/json",
            },
        )
        payload = _json_object(response)
        try:
            content = payload["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as error:
            raise ProviderContractError(
                "OpenAgents response has no message content"
            ) from error
        return _text_content(content)

    def _stepfun_intent(self, user_content: str) -> str:
        self._require_secret(self.settings.stepfun_api_key, "StepFun")
        response = self._client.post_json(
            f"{self.settings.stepfun_base_url}/messages",
            {
                "model": self.settings.intent_model,
                "max_tokens": 2_048,
                "system": INTENT_SYSTEM_PROMPT,
                "messages": [{"role": "user", "content": user_content}],
            },
            headers={
                "x-api-key": self.settings.stepfun_api_key,
                "anthropic-version": "2023-06-01",
                "Accept": "application/json",
            },
        )
        payload = _json_object(response)
        content = payload.get("content")
        if not isinstance(content, list):
            raise ProviderContractError(
                "StepFun response has no content blocks"
            )
        text_blocks = [
            block.get("text")
            for block in content
            if isinstance(block, dict)
            and block.get("type") == "text"
            and isinstance(block.get("text"), str)
        ]
        if not text_blocks:
            raise ProviderContractError("StepFun response text is empty")
        return "".join(text_blocks)

    @staticmethod
    def _require_secret(secret: str, provider: str) -> None:
        if not secret:
            raise ProviderRequestError(f"{provider.casefold()}_key_missing")


def _json_object(response: ProviderResponse) -> dict[str, Any]:
    try:
        payload = json.loads(response.body)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ProviderContractError("Provider returned invalid JSON") from error
    if not isinstance(payload, dict):
        raise ProviderContractError("Provider JSON must be an object")
    return payload


def _extract_json_text(text: str) -> dict[str, Any]:
    stripped = text.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        stripped = "\n".join(lines)
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start < 0 or end < start:
        raise ProviderContractError("Intent response contains no JSON object")
    try:
        payload = json.loads(stripped[start : end + 1])
    except json.JSONDecodeError as error:
        raise ProviderContractError("Intent response JSON is invalid") from error
    if not isinstance(payload, dict):
        raise ProviderContractError("Intent response JSON must be an object")
    return payload


def _text_content(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        texts = [
            block.get("text")
            for block in content
            if isinstance(block, dict) and isinstance(block.get("text"), str)
        ]
        if texts:
            return "".join(texts)
    raise ProviderContractError("Provider content is not text")


def _audio_response(response: ProviderResponse) -> tuple[bytes, str]:
    if response.content_type.startswith("audio/"):
        return response.body, response.content_type
    payload = _json_object(response)
    encoded = payload.get("audio") or payload.get("data")
    if isinstance(encoded, dict):
        encoded = encoded.get("audio") or encoded.get("data")
    if not isinstance(encoded, str):
        raise ProviderContractError("TTS response contains no audio bytes")
    try:
        return base64.b64decode(encoded, validate=True), "audio/wav"
    except ValueError as error:
        raise ProviderContractError("TTS audio base64 is invalid") from error


def _multipart(
    *,
    fields: dict[str, str],
    file_field: str,
    filename: str,
    file_content_type: str,
    file_bytes: bytes,
) -> tuple[bytes, str]:
    boundary = f"----MeantByMe{uuid4().hex}"
    chunks: list[bytes] = []
    for name, value in fields.items():
        chunks.extend(
            [
                f"--{boundary}\r\n".encode(),
                (
                    f'Content-Disposition: form-data; name="{name}"\r\n\r\n'
                ).encode(),
                value.encode(),
                b"\r\n",
            ]
        )
    chunks.extend(
        [
            f"--{boundary}\r\n".encode(),
            (
                "Content-Disposition: form-data; "
                f'name="{file_field}"; filename="{filename}"\r\n'
            ).encode(),
            f"Content-Type: {file_content_type}\r\n\r\n".encode(),
            file_bytes,
            b"\r\n",
            f"--{boundary}--\r\n".encode(),
        ]
    )
    return b"".join(chunks), f"multipart/form-data; boundary={boundary}"
