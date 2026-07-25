from __future__ import annotations

import asyncio
import base64
import binascii
import hmac
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import (
    Depends,
    FastAPI,
    Header,
    HTTPException,
    Request,
    Response,
)
from fastapi.responses import FileResponse
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field, model_validator

from meantbyme.adapters.audio import AudioStore, AudioStoreError
from meantbyme.adapters.profile import ProfileBundleError
from meantbyme.core.domain import (
    CommandActor,
    ConfirmationMethod,
    PatientCommand,
    PatientCommandType,
)
from meantbyme.core.runtime import CommandRejected, ProviderContractError

from services.web_demo.config import WebDemoSettings
from services.web_demo.profile_storage import ProfileStorageError
from services.web_demo.sessions import (
    DemoSession,
    DemoSessionStore,
    SIMULATED_NOTICE,
)


class APIModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CreateSessionRequest(APIModel):
    language: str = Field(default="en", min_length=2, max_length=12)
    profile_ref: str = Field(default="no_profile", min_length=1, max_length=160)


class CommandRequest(APIModel):
    command: PatientCommandType
    payload: dict[str, Any] = Field(default_factory=dict)
    confirmation_method: ConfirmationMethod | None = None


class CreateProfileRequest(APIModel):
    display_name: str = Field(min_length=1, max_length=120)
    language: str = Field(default="zh", min_length=2, max_length=12)
    background: str = Field(default="", max_length=2000)
    relationships: str = Field(default="", max_length=2000)
    routines: str = Field(default="", max_length=2000)
    interests: str = Field(default="", max_length=2000)
    communication_preferences: str = Field(default="", max_length=2000)
    additional_notes: str = Field(default="", max_length=2000)

    @model_validator(mode="after")
    def require_profile_content(self) -> "CreateProfileRequest":
        fields = (
            self.background,
            self.relationships,
            self.routines,
            self.interests,
            self.communication_preferences,
            self.additional_notes,
        )
        if not any(value.strip() for value in fields):
            raise ValueError("at least one profile answer is required")
        return self


def create_app(
    *,
    settings: WebDemoSettings | None = None,
    store: DemoSessionStore | None = None,
) -> FastAPI:
    active_settings = settings or WebDemoSettings.from_env()
    active_store = store or DemoSessionStore(active_settings)
    static_root = Path(__file__).resolve().parent / "static"

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        yield
        active_store.close_all()

    application = FastAPI(
        title="MeantByMe Web Demo",
        version="0.1.0",
        docs_url=None,
        redoc_url=None,
        lifespan=lifespan,
    )
    application.mount(
        "/assets", StaticFiles(directory=static_root), name="assets"
    )

    @application.exception_handler(ProfileStorageError)
    async def profile_storage_error_handler(
        _: Request,
        __: ProfileStorageError,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=503,
            content={"detail": "profile database unavailable"},
        )

    async def require_demo_access(request: Request) -> None:
        configured = active_settings.demo_token
        if not configured:
            if active_settings.mode == "cloud":
                raise HTTPException(
                    status_code=503,
                    detail="demo token not configured",
                )
            return
        supplied = request.headers.get("X-Demo-Token", "")
        if not hmac.compare_digest(supplied, configured):
            raise HTTPException(status_code=401, detail="invalid demo token")

    def resolve_session(
        session_id: str,
        x_demo_session: str = Header(default=""),
    ) -> DemoSession:
        try:
            return active_store.get(session_id, x_demo_session)
        except KeyError as error:
            raise HTTPException(
                status_code=404, detail="demo session not found"
            ) from error

    @application.get("/")
    async def index() -> FileResponse:
        return FileResponse(static_root / "index.html")

    @application.get("/api/health")
    async def health() -> dict[str, Any]:
        return {
            "service": "MeantByMe Web Demo",
            "status": "ok",
            "mode": active_settings.mode,
            "simulated": True,
            "notice": SIMULATED_NOTICE,
            "gateway_configured": bool(active_settings.gateway_token),
            "demo_access_configured": bool(active_settings.demo_token),
            "max_audio_seconds": active_settings.max_audio_seconds,
            "viaim_earbud_api": True,
            "profile_database_backend": (
                active_settings.profile_database_backend
            ),
        }

    @application.post(
        "/api/sessions", dependencies=[Depends(require_demo_access)]
    )
    async def create_session(
        payload: CreateSessionRequest,
    ) -> dict[str, Any]:
        try:
            session = await asyncio.to_thread(
                active_store.create,
                profile_ref=payload.profile_ref,
                language=payload.language,
            )
        except (ProfileBundleError, ValueError) as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        except RuntimeError as error:
            raise HTTPException(status_code=503, detail=str(error)) from error
        response = session.response()
        response["session_token"] = session.access_token
        return response

    @application.get(
        "/api/profiles", dependencies=[Depends(require_demo_access)]
    )
    async def list_profiles() -> dict[str, Any]:
        return {
            "notice": SIMULATED_NOTICE,
            "profiles": active_store.list_profiles(),
        }

    @application.get(
        "/api/profiles/{profile_ref}",
        dependencies=[Depends(require_demo_access)],
    )
    async def get_profile(profile_ref: str) -> dict[str, Any]:
        try:
            profile = await asyncio.to_thread(
                active_store.profile_detail, profile_ref
            )
        except ProfileBundleError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        return {"notice": SIMULATED_NOTICE, "profile": profile}

    @application.post(
        "/api/profiles/questionnaire",
        dependencies=[Depends(require_demo_access)],
    )
    async def create_profile(
        payload: CreateProfileRequest,
    ) -> dict[str, Any]:
        try:
            profile = await asyncio.to_thread(
                active_store.create_profile,
                display_name=payload.display_name.strip(),
                language=payload.language,
                answers={
                    "background": payload.background,
                    "relationships": payload.relationships,
                    "routines": payload.routines,
                    "interests": payload.interests,
                    "communication_preferences": (
                        payload.communication_preferences
                    ),
                    "additional_notes": payload.additional_notes,
                },
            )
        except ProfileBundleError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        return {"notice": SIMULATED_NOTICE, "profile": profile}

    @application.post(
        "/api/profiles", dependencies=[Depends(require_demo_access)]
    )
    async def upload_profile(request: Request) -> dict[str, Any]:
        content_type = request.headers.get("content-type", "").split(";", 1)[0]
        if content_type not in {"text/markdown", "text/plain"}:
            raise HTTPException(
                status_code=415, detail="UTF-8 Markdown profile required"
            )
        body = await request.body()
        if not body or len(body) > active_settings.max_profile_bytes:
            raise HTTPException(status_code=413, detail="invalid profile size")
        try:
            markdown = body.decode("utf-8")
            profile = await asyncio.to_thread(
                active_store.register_profile, markdown
            )
        except UnicodeDecodeError as error:
            raise HTTPException(
                status_code=400, detail="profile must be UTF-8"
            ) from error
        except ProfileBundleError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        return {"notice": SIMULATED_NOTICE, "profile": profile}

    @application.post(
        "/api/sessions/{session_id}/audio",
        dependencies=[Depends(require_demo_access)],
    )
    async def upload_audio(
        request: Request,
        primary_transcript_b64: str | None = Header(
            default=None,
            alias="X-Viaim-Primary-Transcript-B64",
        ),
        session: DemoSession = Depends(resolve_session),
    ) -> dict[str, Any]:
        content_type = request.headers.get("content-type", "").split(";", 1)[0]
        if content_type not in {"audio/wav", "audio/x-wav"}:
            raise HTTPException(status_code=415, detail="WAV audio required")
        wav_bytes = await request.body()
        if not wav_bytes or len(wav_bytes) > active_settings.max_audio_bytes:
            raise HTTPException(status_code=413, detail="invalid audio size")
        try:
            duration_seconds = AudioStore.duration_seconds(wav_bytes)
            if duration_seconds > active_settings.max_audio_seconds:
                raise HTTPException(
                    status_code=413,
                    detail=(
                        "audio must be "
                        f"{active_settings.max_audio_seconds:g} "
                        "seconds or shorter"
                    ),
                )
            primary_transcript = (
                _decode_transcript_header(primary_transcript_b64)
                if primary_transcript_b64 is not None
                else None
            )
            audio_id = await asyncio.to_thread(
                session.put_audio,
                wav_bytes,
                primary_transcript=primary_transcript,
            )
        except AudioStoreError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
        return {
            "notice": SIMULATED_NOTICE,
            "audio_id": audio_id,
            "normalized": True,
        }

    @application.post(
        "/api/sessions/{session_id}/commands",
        dependencies=[Depends(require_demo_access)],
    )
    async def command(
        payload: CommandRequest,
        session: DemoSession = Depends(resolve_session),
    ) -> dict[str, Any]:
        command_payload = dict(payload.payload)
        if payload.command is PatientCommandType.STOP_CAPTURE:
            try:
                command_payload["audio_id"] = session.audio_id_for_capture()
            except ValueError as error:
                raise HTTPException(
                    status_code=409, detail=str(error)
                ) from error
        playback_commands = {
            PatientCommandType.PLAYBACK_COMPLETED,
            PatientCommandType.PLAYBACK_FAILED,
            PatientCommandType.PROCEED_WITHOUT_HEARD_CONFIRMATION,
            PatientCommandType.PREPARE_CANDIDATE_READBACK,
        }
        patient_command = PatientCommand(
            command=payload.command,
            session_id=session.runtime.session.session_id,
            payload=command_payload,
            confirmation_method=payload.confirmation_method,
            actor=(
                CommandActor.SYSTEM
                if payload.command in playback_commands
                else CommandActor.PATIENT
            ),
        )
        try:
            if (
                payload.command
                is PatientCommandType.CONFIRM_NEUTRAL_PLAYBACK
            ):
                return await asyncio.to_thread(
                    session.handle_voice_confirmation,
                    patient_command,
                )
            return await asyncio.to_thread(session.handle, patient_command)
        except CommandRejected as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        except ProviderContractError as error:
            raise HTTPException(
                status_code=502, detail="intent provider contract rejected"
            ) from error

    @application.post(
        "/api/sessions/{session_id}/earbud/interpret",
        dependencies=[Depends(require_demo_access)],
    )
    async def interpret_earbud_command(
        request: Request,
        primary_transcript_b64: str = Header(
            alias="X-Viaim-Primary-Transcript-B64"
        ),
        prompt_id: str = Header(
            min_length=1,
            max_length=128,
            alias="X-MeantByMe-Prompt-ID",
        ),
        mock_secondary_transcript_b64: str | None = Header(
            default=None,
            alias="X-Mock-Secondary-Transcript-B64",
        ),
        session: DemoSession = Depends(resolve_session),
    ) -> dict[str, Any]:
        content_type = request.headers.get("content-type", "").split(";", 1)[0]
        if content_type not in {"audio/wav", "audio/x-wav"}:
            raise HTTPException(status_code=415, detail="WAV audio required")
        wav_bytes = await request.body()
        if not wav_bytes or len(wav_bytes) > active_settings.max_audio_bytes:
            raise HTTPException(status_code=413, detail="invalid audio size")
        try:
            primary_transcript = _decode_transcript_header(
                primary_transcript_b64
            )
            mock_secondary_transcript = (
                _decode_transcript_header(mock_secondary_transcript_b64)
                if mock_secondary_transcript_b64 is not None
                else None
            )
            duration_seconds = AudioStore.duration_seconds(wav_bytes)
            if duration_seconds > active_settings.max_audio_seconds:
                raise HTTPException(
                    status_code=413,
                    detail="command audio exceeds session limit",
                )
            result = await asyncio.to_thread(
                session.interpret_earbud_command,
                wav_bytes=wav_bytes,
                primary_transcript=primary_transcript,
                prompt_id=prompt_id,
                mock_secondary_transcript=mock_secondary_transcript,
            )
        except AudioStoreError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
        return {"notice": SIMULATED_NOTICE, **result}

    @application.get(
        "/api/sessions/{session_id}/audio/{kind}",
        dependencies=[Depends(require_demo_access)],
    )
    async def get_audio(
        kind: str,
        session: DemoSession = Depends(resolve_session),
    ) -> Response:
        if kind not in {"neutral", "personal"}:
            raise HTTPException(status_code=404, detail="audio not found")
        result = session.audio(kind)
        if result is None or result.status != "success":
            raise HTTPException(status_code=404, detail="audio not available")
        if result.audio_bytes:
            return Response(
                content=result.audio_bytes,
                media_type=result.media_type or "audio/wav",
                headers={"Cache-Control": "no-store"},
            )
        if result.audio_path:
            return FileResponse(
                result.audio_path,
                media_type=result.media_type or "audio/wav",
                headers={"Cache-Control": "no-store"},
            )
        raise HTTPException(status_code=404, detail="audio not available")

    return application


def _decode_transcript_header(encoded: str) -> str:
    try:
        transcript = base64.b64decode(
            encoded, validate=True
        ).decode("utf-8").strip()
    except (binascii.Error, UnicodeDecodeError) as error:
        raise HTTPException(
            status_code=400, detail="invalid transcript evidence"
        ) from error
    if not transcript or len(transcript) > 120:
        raise HTTPException(
            status_code=400, detail="invalid transcript evidence"
        )
    return transcript


app = create_app()
