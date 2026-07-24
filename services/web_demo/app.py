from __future__ import annotations

import asyncio
import hmac
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException, Request, Response
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field

from meantbyme.adapters.audio import AudioStoreError
from meantbyme.core.domain import (
    ConfirmationMethod,
    PatientCommand,
    PatientCommandType,
)
from meantbyme.core.runtime import CommandRejected, ProviderContractError

from services.web_demo.config import WebDemoSettings
from services.web_demo.sessions import (
    DemoSession,
    DemoSessionStore,
    SIMULATED_NOTICE,
)


class APIModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CreateSessionRequest(APIModel):
    language: str = Field(default="en", min_length=2, max_length=12)


class CommandRequest(APIModel):
    command: PatientCommandType
    payload: dict[str, Any] = Field(default_factory=dict)
    confirmation_method: ConfirmationMethod | None = None


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
        }

    @application.post(
        "/api/sessions", dependencies=[Depends(require_demo_access)]
    )
    async def create_session(
        payload: CreateSessionRequest,
    ) -> dict[str, Any]:
        if payload.language != "en":
            raise HTTPException(
                status_code=400,
                detail="The current simulated profile uses English fixtures",
            )
        try:
            session = await asyncio.to_thread(active_store.create)
        except RuntimeError as error:
            raise HTTPException(status_code=503, detail=str(error)) from error
        response = session.response()
        response["session_token"] = session.access_token
        return response

    @application.post(
        "/api/sessions/{session_id}/audio",
        dependencies=[Depends(require_demo_access)],
    )
    async def upload_audio(
        request: Request,
        session: DemoSession = Depends(resolve_session),
    ) -> dict[str, Any]:
        content_type = request.headers.get("content-type", "").split(";", 1)[0]
        if content_type not in {"audio/wav", "audio/x-wav"}:
            raise HTTPException(status_code=415, detail="WAV audio required")
        wav_bytes = await request.body()
        if not wav_bytes or len(wav_bytes) > active_settings.max_audio_bytes:
            raise HTTPException(status_code=413, detail="invalid audio size")
        try:
            audio_id = await asyncio.to_thread(session.put_audio, wav_bytes)
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
        patient_command = PatientCommand(
            command=payload.command,
            session_id=session.runtime.session.session_id,
            payload=command_payload,
            confirmation_method=payload.confirmation_method,
        )
        try:
            return await asyncio.to_thread(session.handle, patient_command)
        except CommandRejected as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        except ProviderContractError as error:
            raise HTTPException(
                status_code=502, detail="intent provider contract rejected"
            ) from error

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


app = create_app()
