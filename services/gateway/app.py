from __future__ import annotations

import asyncio
import io
import logging
import wave
from typing import Any, Literal

from fastapi import FastAPI, Header, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field

from services.gateway.config import GatewaySettings
from services.gateway.providers import (
    CloudProviderService,
    ProviderContractError,
)
from services.gateway.provider_http import ProviderRequestError


logger = logging.getLogger("meantbyme.gateway")
MAX_AUDIO_BYTES = 32 * 1024 * 1024


class GatewayModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class IntentRequest(GatewayModel):
    patient_id: str = Field(min_length=1)
    session_id: str = Field(min_length=1)
    language: str | None = None
    evidence: dict[str, Any]
    memories: list[dict[str, Any]] = Field(default_factory=list, max_length=20)
    confirmed_context: dict[str, Any]


class TTSRequest(GatewayModel):
    text: str = Field(min_length=1, max_length=1_000)
    mode: Literal["neutral", "personal"]
    scope: str
    voice_profile_id: str | None = None
    patient_id: str | None = None
    session_id: str | None = None


def create_app(
    *,
    settings: GatewaySettings | None = None,
    providers: CloudProviderService | None = None,
) -> FastAPI:
    active_settings = settings or GatewaySettings.from_env()
    active_providers = providers or CloudProviderService(active_settings)
    application = FastAPI(title="MeantByMe Gateway", version="0.2.0")

    async def run_provider(callable_, *args, **kwargs):
        try:
            return await asyncio.wait_for(
                asyncio.to_thread(callable_, *args, **kwargs),
                timeout=active_settings.route_timeout_seconds,
            )
        except TimeoutError as error:
            raise HTTPException(
                status_code=504, detail="provider timeout"
            ) from error
        except (ProviderRequestError, ProviderContractError) as error:
            logger.warning(
                "provider request failed type=%s",
                type(error).__name__,
            )
            raise HTTPException(
                status_code=502, detail="provider unavailable"
            ) from error

    @application.middleware("http")
    async def redacted_access_log(request: Request, call_next):
        response = await call_next(request)
        logger.info(
            "request method=%s path=%s status=%s",
            request.method,
            request.url.path,
            response.status_code,
        )
        return response

    @application.get("/v1/health")
    async def health() -> dict[str, Any]:
        return {
            "status": "ok",
            "intent_provider": active_settings.intent_provider,
            "intent_model": active_settings.intent_model,
            "asr_model": "step-asr",
            "neutral_tts_model": "step-tts-mini",
            "personal_tts_model": "stepaudio-2.5-tts",
            "stepfun_configured": bool(active_settings.stepfun_api_key),
            "openagents_configured": bool(
                active_settings.openagents_api_key
            ),
        }

    @application.post("/v1/asr/primary")
    async def asr_primary(
        request: Request,
        x_patient_id: str = Header(...),
        x_session_id: str = Header(...),
        x_language_hint: str | None = Header(default=None),
    ) -> dict[str, Any]:
        del x_patient_id, x_session_id
        wav_bytes = await request.body()
        _validate_audio(wav_bytes)
        return await run_provider(
            active_providers.transcribe,
            wav_bytes,
            language_hint=x_language_hint,
        )

    @application.post("/v1/intent/propose")
    async def intent_propose(payload: IntentRequest) -> dict[str, Any]:
        return await run_provider(
            active_providers.propose_intent,
            payload.model_dump(mode="json"),
        )

    @application.post("/v1/tts/synthesize")
    async def tts_synthesize(payload: TTSRequest) -> Response:
        if payload.mode == "personal":
            if (
                payload.scope != "this_expression"
                or not payload.patient_id
                or not payload.session_id
            ):
                raise HTTPException(
                    status_code=400,
                    detail="personal TTS requires expression scope",
                )
        audio, media_type = await run_provider(
            active_providers.synthesize,
            text=payload.text,
            mode=payload.mode,
            voice_profile_id=payload.voice_profile_id,
        )
        return Response(content=audio, media_type=media_type)

    @application.post("/v1/tts/enroll-voice")
    async def enroll_voice(
        request: Request,
        x_patient_id: str = Header(...),
        x_session_id: str = Header(...),
    ) -> dict[str, str]:
        del x_patient_id, x_session_id
        wav_bytes = await request.body()
        _validate_audio(wav_bytes)
        _validate_voice_sample(wav_bytes)
        voice_id = await run_provider(
            active_providers.enroll_voice, wav_bytes
        )
        return {"voice_id": voice_id}

    return application


def _validate_audio(wav_bytes: bytes) -> None:
    if not wav_bytes or len(wav_bytes) > MAX_AUDIO_BYTES:
        raise HTTPException(status_code=413, detail="invalid audio size")
    if not wav_bytes.startswith(b"RIFF"):
        raise HTTPException(status_code=400, detail="WAV audio required")


def _validate_voice_sample(wav_bytes: bytes) -> None:
    try:
        with wave.open(io.BytesIO(wav_bytes), "rb") as reader:
            duration = reader.getnframes() / reader.getframerate()
    except (EOFError, wave.Error, ZeroDivisionError) as error:
        raise HTTPException(status_code=400, detail="invalid WAV audio") from error
    if duration < 5 or duration > 10:
        raise HTTPException(
            status_code=400,
            detail="voice sample must be between 5 and 10 seconds",
        )


app = create_app()
