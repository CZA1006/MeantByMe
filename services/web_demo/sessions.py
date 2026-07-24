from __future__ import annotations

import json
import shutil
import threading
from dataclasses import dataclass, field
from pathlib import Path
from secrets import token_urlsafe
from typing import Any
from uuid import uuid4

from meantbyme.adapters.asr import GatewayASRAdapter, MockASRAdapter
from meantbyme.adapters.audio import AudioStore
from meantbyme.adapters.http import GatewayHttpClient
from meantbyme.adapters.intent import GatewayIntentAdapter, MockIntentAdapter
from meantbyme.adapters.profile import (
    ProfileBundle,
    ProfileImportResult,
    seed_profile_repository,
)
from meantbyme.adapters.storage import SQLiteRepository
from meantbyme.adapters.tts import CachedTTSAdapter, GatewayTTSAdapter
from meantbyme.core.domain import (
    AuthorizedExpression,
    ExpressionCandidate,
    PatientCommand,
    RuntimeEventType,
    TTSResult,
)
from meantbyme.core.ports import TTSPort
from meantbyme.core.runtime import MeantByMeRuntime

from services.web_demo.config import WebDemoSettings
from services.web_demo.profiles import DemoProfileRegistry


SIMULATED_NOTICE = "Simulated data. Not a clinical accuracy claim."


class CapturingTTSAdapter:
    """Captures runtime-authorized audio so the browser can fetch it later."""

    def __init__(self, delegate: TTSPort) -> None:
        self._delegate = delegate
        self.neutral_result: TTSResult | None = None
        self.personal_result: TTSResult | None = None

    def synthesize_neutral(
        self, candidate: ExpressionCandidate
    ) -> TTSResult:
        result = self._delegate.synthesize_neutral(candidate)
        self.neutral_result = result
        return result

    def synthesize_personal(
        self, expression: AuthorizedExpression
    ) -> TTSResult:
        result = self._delegate.synthesize_personal(expression)
        self.personal_result = result
        return result


@dataclass
class DemoSession:
    runtime: MeantByMeRuntime
    repository: SQLiteRepository
    audio_store: AudioStore
    tts: CapturingTTSAdapter
    mode: str
    storage_root: Path
    profile: ProfileBundle
    profile_import: ProfileImportResult
    access_token: str = field(default_factory=lambda: token_urlsafe(32))
    pending_audio_id: str | None = None
    fixture_audio_id: str = "david_fragment_001"
    lock: threading.RLock = field(default_factory=threading.RLock)

    def close(self) -> None:
        self.repository.close()
        shutil.rmtree(self.storage_root, ignore_errors=True)

    def put_audio(self, wav_bytes: bytes) -> str:
        with self.lock:
            audio_id = (
                self.fixture_audio_id
                if self.mode == "mock"
                else f"web-audio-{uuid4().hex}"
            )
            self.audio_store.put_wav_bytes(audio_id, wav_bytes)
            self.pending_audio_id = audio_id
            return audio_id

    def audio_id_for_capture(self) -> str:
        if self.pending_audio_id is not None:
            return self.pending_audio_id
        if self.mode == "mock":
            return self.fixture_audio_id
        raise ValueError("Cloud mode requires recorded or uploaded WAV audio")

    def handle(self, command: PatientCommand) -> dict[str, Any]:
        with self.lock:
            self.runtime.handle(command)
            return self.response()

    def response(self) -> dict[str, Any]:
        session = self.runtime.session
        view = self.runtime.view_model()
        receipt = self.repository.get_receipt(
            session.patient_id, session.session_id
        )
        selected = session.selected_candidate()
        spoken = any(
            event.event_type is RuntimeEventType.EXPRESSION_SPOKEN
            for event in self.runtime.events
        )
        view_payload = view.model_dump(mode="json")
        if spoken:
            view_payload["personal_voice_status"] = "used"
        return {
            "notice": SIMULATED_NOTICE,
            "simulated": True,
            "mode": self.mode,
            "profile": {
                "profile_id": self.profile.profile_id,
                "label": self.profile.label,
                "semantic_count": self.profile_import.semantic_count,
                "context_count": self.profile_import.context_count,
                "skipped_count": len(
                    self.profile_import.skipped_memory_ids
                ),
            },
            "session": view_payload,
            "selected_candidate_id": session.selected_candidate_id,
            "selected_candidate": (
                selected.model_dump(mode="json") if selected else None
            ),
            "strict": session.strict,
            "risk_level": session.risk_level.value,
            "failure_status": session.failure_status,
            "situation_present": bool(session.situation),
            "confirmed_context": session.confirmed_context.model_dump(
                mode="json"
            ),
            "audio": {
                "neutral_available": _audio_available(
                    self.tts.neutral_result
                ),
                "personal_available": (
                    session.voice_authorized
                    and _audio_available(self.tts.personal_result)
                ),
            },
            "receipt": (
                receipt.model_dump(mode="json") if receipt else None
            ),
        }

    def audio(self, kind: str) -> TTSResult | None:
        if kind == "neutral":
            return self.tts.neutral_result
        if kind == "personal" and self.runtime.session.voice_authorized:
            return self.tts.personal_result
        return None


class DemoSessionStore:
    def __init__(self, settings: WebDemoSettings) -> None:
        self._settings = settings
        self._sessions: dict[str, DemoSession] = {}
        self._lock = threading.RLock()
        root = Path(__file__).resolve().parents[2]
        self._profiles = DemoProfileRegistry(
            root / "demo/profiles",
            max_profile_bytes=settings.max_profile_bytes,
            max_uploaded_profiles=settings.max_uploaded_profiles,
            cloud_mode=settings.mode == "cloud",
        )

    def list_profiles(self) -> list[dict[str, Any]]:
        return self._profiles.list_profiles()

    def register_profile(self, markdown: str) -> dict[str, Any]:
        return self._profiles.register_upload(markdown)

    def create(
        self,
        *,
        profile_ref: str = "no_profile",
        language: str = "en",
    ) -> DemoSession:
        with self._lock:
            if len(self._sessions) >= self._settings.max_sessions:
                raise RuntimeError("Demo session capacity reached")
            profile = self._profiles.resolve(profile_ref)
            if language not in profile.patient.languages:
                raise ValueError("language is not enabled for this profile")
            if self._settings.mode == "mock" and language != "en":
                raise ValueError("mock Web Demo fixture supports English only")
            session = _build_session(
                self._settings,
                profile=profile,
                language=language,
            )
            self._sessions[session.runtime.session.session_id] = session
            return session

    def get(self, session_id: str, access_token: str) -> DemoSession:
        with self._lock:
            session = self._sessions.get(session_id)
        if session is None or not access_token:
            raise KeyError("Demo session not found")
        from hmac import compare_digest

        if not compare_digest(access_token, session.access_token):
            raise KeyError("Demo session not found")
        return session

    def close_all(self) -> None:
        with self._lock:
            sessions = list(self._sessions.values())
            self._sessions.clear()
        for session in sessions:
            session.close()


def _build_session(
    settings: WebDemoSettings,
    *,
    profile: ProfileBundle,
    language: str,
) -> DemoSession:
    root = Path(__file__).resolve().parents[2]
    fixture_path = root / "demo/fixtures/golden_path.json"
    fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
    patient = profile.patient
    session_id = f"web-{uuid4().hex}"
    session_root = settings.audio_store_root / session_id
    audio_store = AudioStore(session_root)
    repository = SQLiteRepository(check_same_thread=False)
    profile_import = seed_profile_repository(repository, profile)

    if settings.mode == "cloud":
        if not settings.gateway_token:
            repository.close()
            raise RuntimeError("Cloud demo requires GATEWAY_TOKEN")
        voice_profile_id = settings.voice_profile_id
        if voice_profile_id != profile.voice_consent.voice_profile_id:
            repository.grant_voice_consent(
                patient.patient_id,
                f"web-voice-consent-{voice_profile_id}",
                "web-demo-official-voice-consent",
                voice_profile_id,
            )
        client = GatewayHttpClient(
            settings.gateway_url,
            timeout_seconds=settings.gateway_timeout_seconds,
            max_attempts=settings.gateway_max_attempts,
            token=settings.gateway_token,
        )
        asr = GatewayASRAdapter(
            client=client,
            audio_store=audio_store,
            patient_id=patient.patient_id,
            session_id=session_id,
        )
        intent = GatewayIntentAdapter(
            client=client,
            patient_id=patient.patient_id,
            session_id=session_id,
        )
        delegate_tts: TTSPort = GatewayTTSAdapter(
            client=client,
            audio_store=audio_store,
        )
    else:
        voice_profile_id = profile.voice_consent.voice_profile_id
        asr = MockASRAdapter.from_json(fixture_path)
        intent = MockIntentAdapter()
        delegate_tts = CachedTTSAdapter(
            root / fixture["tts"]["neutral_cache"],
            root / fixture["tts"]["personal_cache"],
        )

    tts = CapturingTTSAdapter(delegate_tts)
    runtime = MeantByMeRuntime(
        asr=asr,
        intent=intent,
        tts=tts,
        repository=repository,
    )
    runtime.create_session(
        session_id=session_id,
        patient_id=patient.patient_id,
        language=language,
        voice_profile_id=voice_profile_id,
    )
    return DemoSession(
        runtime=runtime,
        repository=repository,
        audio_store=audio_store,
        tts=tts,
        mode=settings.mode,
        storage_root=session_root,
        profile=profile,
        profile_import=profile_import,
        fixture_audio_id=fixture["audio_id"],
    )


def _audio_available(result: TTSResult | None) -> bool:
    return bool(
        result
        and result.status == "success"
        and (result.audio_bytes or result.audio_path)
    )
