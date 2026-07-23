from __future__ import annotations

import json

from meantbyme.adapters.audio import AudioStore
from meantbyme.adapters.http import GatewayError, GatewayHttpClient
from meantbyme.core.domain import (
    AuthorizedExpression,
    ExpressionCandidate,
    TTSResult,
)


class GatewayTTSAdapter:
    def __init__(
        self,
        *,
        client: GatewayHttpClient,
        audio_store: AudioStore | None = None,
    ) -> None:
        self._client = client
        self._audio_store = audio_store
        self._consumed_authorizations: set[tuple[str, str]] = set()

    def synthesize_neutral(
        self, candidate: ExpressionCandidate
    ) -> TTSResult:
        return self._synthesize(
            {
                "text": candidate.text,
                "mode": "neutral",
                "scope": "preview",
            }
        )

    def synthesize_personal(
        self, expression: AuthorizedExpression
    ) -> TTSResult:
        if not isinstance(expression, AuthorizedExpression):
            raise TypeError(
                "Personal TTS requires an AuthorizedExpression object"
            )
        authorization_key = (
            expression.session_id,
            expression.authorized_at.isoformat(),
        )
        if authorization_key in self._consumed_authorizations:
            return TTSResult(
                status="failed", error="authorization already consumed"
            )
        result = self._synthesize(
            {
                "text": expression.final_text,
                "voice_profile_id": expression.voice_profile_id,
                "mode": "personal",
                "scope": expression.authorization_scope,
                "patient_id": expression.patient_id,
                "session_id": expression.session_id,
            }
        )
        if result.status == "success":
            self._consumed_authorizations.add(authorization_key)
        return result

    def enroll_voice(
        self,
        *,
        audio_id: str,
        patient_id: str,
        session_id: str,
    ) -> str | None:
        if self._audio_store is None:
            return None
        try:
            response = self._client.post_wav(
                "/v1/tts/enroll-voice",
                self._audio_store.read_wav(audio_id),
                headers={
                    "X-Patient-Id": patient_id,
                    "X-Session-Id": session_id,
                    "X-Audio-Id": audio_id,
                },
            )
            payload = json.loads(response.body)
            voice_id = payload.get("voice_id")
            return voice_id if isinstance(voice_id, str) else None
        except (GatewayError, ValueError, TypeError):
            return None

    def _synthesize(self, payload: dict) -> TTSResult:
        try:
            response = self._client.request(
                "POST",
                "/v1/tts/synthesize",
                body=json.dumps(payload, separators=(",", ":")).encode(
                    "utf-8"
                ),
                headers={
                    "Content-Type": "application/json",
                    "Accept": "audio/*",
                },
            )
            if not response.body:
                raise ValueError("Gateway returned empty audio")
            return TTSResult(
                status="success",
                audio_bytes=response.body,
                media_type=response.headers.get(
                    "content-type", "audio/wav"
                ).split(";", 1)[0],
            )
        except (GatewayError, ValueError, TypeError) as error:
            return TTSResult(
                status="failed", error=type(error).__name__
            )
