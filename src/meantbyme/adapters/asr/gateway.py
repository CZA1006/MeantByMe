from __future__ import annotations

import json

from pydantic import ValidationError

from meantbyme.adapters.audio import AudioStore
from meantbyme.adapters.http import (
    GatewayError,
    GatewayHTTPError,
    GatewayHttpClient,
    GatewayInvalidResponse,
    GatewayTimeout,
)
from meantbyme.core.domain import ASRResult


class GatewayASRAdapter:
    def __init__(
        self,
        *,
        audio_store: AudioStore,
        client: GatewayHttpClient,
        patient_id: str,
        session_id: str,
        language_hint: str | None = None,
        secondary_endpoint: str | None = "/v1/asr/secondary",
    ) -> None:
        self._audio_store = audio_store
        self._client = client
        self._patient_id = patient_id
        self._session_id = session_id
        self._language_hint = language_hint
        self._secondary_endpoint = secondary_endpoint

    def transcribe(self, audio_id: str) -> list[ASRResult]:
        try:
            wav_bytes = self._audio_store.read_wav(audio_id)
        except Exception as error:
            return [self._failure("audio_store", error)]

        headers = {
            "X-Patient-Id": self._patient_id,
            "X-Session-Id": self._session_id,
            "X-Audio-Id": audio_id,
        }
        if self._language_hint:
            headers["X-Language-Hint"] = self._language_hint

        primary = self._request_result(
            "/v1/asr/primary", wav_bytes, headers, "gateway_primary"
        )
        results = [primary]
        if primary.status != "success" or self._secondary_endpoint is None:
            return results

        try:
            secondary = self._request_result(
                self._secondary_endpoint,
                wav_bytes,
                headers,
                "gateway_secondary",
                missing_is_none=True,
            )
        except GatewayHTTPError as error:
            if error.status_code == 404:
                return results
            secondary = self._failure("gateway_secondary", error)
        if secondary is not None:
            results.append(secondary)
        return results

    def _request_result(
        self,
        path: str,
        wav_bytes: bytes,
        headers: dict[str, str],
        provider: str,
        *,
        missing_is_none: bool = False,
    ) -> ASRResult | None:
        try:
            response = self._client.post_wav(
                path, wav_bytes, headers=headers
            )
            payload = json.loads(response.body)
            if not isinstance(payload, dict):
                raise GatewayInvalidResponse("ASR JSON must be an object")
            return ASRResult.model_validate(payload)
        except GatewayHTTPError:
            if missing_is_none:
                raise
            return self._failure(provider, GatewayError("ASR HTTP failure"))
        except (
            UnicodeDecodeError,
            json.JSONDecodeError,
            ValidationError,
            GatewayError,
        ) as error:
            return self._failure(provider, error)
        except Exception as error:
            return self._failure(provider, error)

    @staticmethod
    def _failure(provider: str, error: Exception) -> ASRResult:
        status = "timeout" if isinstance(error, GatewayTimeout) else "failed"
        return ASRResult(
            provider=provider,
            transcript="",
            language=None,
            segments=[],
            latency_ms=None,
            status=status,
            error=type(error).__name__,
        )
