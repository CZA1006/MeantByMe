from __future__ import annotations

import hashlib
import json
import shutil
import threading
from dataclasses import dataclass, field
from pathlib import Path
from secrets import token_urlsafe
from typing import Any
from uuid import uuid4

from meantbyme.adapters.asr import (
    GatewayASRAdapter,
    HeadsetPrimaryASRAdapter,
    MockASRAdapter,
)
from meantbyme.adapters.audio import AudioStore
from meantbyme.adapters.command import (
    GatewayCommandIntentAdapter,
    MockCommandIntentAdapter,
)
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
    CommandIntent,
    ExpressionCandidate,
    PatientCommand,
    RuntimeEventType,
    TTSResult,
)
from meantbyme.core.ports import ASRPort, CommandIntentPort, TTSPort
from meantbyme.core.runtime import CommandRejected, MeantByMeRuntime

from services.web_demo.config import WebDemoSettings
from services.web_demo.profile_storage import (
    MySQLProfileStore,
    SQLiteProfileStore,
)
from services.web_demo.profiles import DemoProfileRegistry


SIMULATED_NOTICE = "Simulated data. Not a clinical accuracy claim."


@dataclass(frozen=True)
class VoiceInterpretationRecord:
    interpretation_id: str
    stage: str
    candidate_id: str | None
    prompt_id: str
    intent: CommandIntent
    consensus: bool
    audio_hash: str


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
    asr: HeadsetPrimaryASRAdapter
    command_intent: CommandIntentPort
    mode: str
    storage_root: Path
    profile: ProfileBundle
    profile_import: ProfileImportResult
    access_token: str = field(default_factory=lambda: token_urlsafe(32))
    pending_audio_id: str | None = None
    fixture_audio_id: str = "david_fragment_001"
    lock: threading.RLock = field(default_factory=threading.RLock)
    voice_interpretations: dict[str, VoiceInterpretationRecord] = field(
        default_factory=dict
    )

    def close(self) -> None:
        self.repository.close()
        shutil.rmtree(self.storage_root, ignore_errors=True)

    def put_audio(
        self,
        wav_bytes: bytes,
        *,
        primary_transcript: str | None = None,
    ) -> str:
        with self.lock:
            audio_id = (
                self.fixture_audio_id
                if self.mode == "mock"
                else f"web-audio-{uuid4().hex}"
            )
            self.audio_store.put_wav_bytes(audio_id, wav_bytes)
            if primary_transcript:
                self.asr.submit_primary(
                    audio_id,
                    primary_transcript,
                    language=self.runtime.session.language,
                )
            self.pending_audio_id = audio_id
            return audio_id

    def interpret_earbud_command(
        self,
        *,
        wav_bytes: bytes,
        primary_transcript: str,
        prompt_id: str,
        mock_secondary_transcript: str | None = None,
    ) -> dict[str, Any]:
        """Interpret command evidence without mutating Runtime authorization."""
        with self.lock:
            audio_id = f"earbud-command-{uuid4().hex}"
            self.audio_store.put_wav_bytes(audio_id, wav_bytes)
            try:
                if self.mode == "mock":
                    secondary_transcript = (
                        mock_secondary_transcript
                        if mock_secondary_transcript is not None
                        else primary_transcript
                    )
                    secondary_provider = "mock_secondary_command_asr"
                else:
                    results = self.asr.transcribe(audio_id)
                    secondary = next(
                        (
                            result
                            for result in results
                            if result.status == "success"
                            and result.transcript.strip()
                        ),
                        None,
                    )
                    secondary_transcript = (
                        secondary.transcript if secondary else ""
                    )
                    secondary_provider = (
                        secondary.provider
                        if secondary
                        else "secondary_command_asr_missing"
                    )
            finally:
                self.audio_store.delete(audio_id)

            stage = self.runtime.session.stage.value
            language = self.runtime.session.language
            primary = self.command_intent.interpret(
                primary_transcript,
                stage=stage,
                language=language,
            )
            secondary = self.command_intent.interpret(
                secondary_transcript,
                stage=stage,
                language=language,
            )
            if CommandIntent.STOP in {primary.intent, secondary.intent}:
                resolved = CommandIntent.STOP
                consensus = primary.intent is secondary.intent
            elif primary.intent is secondary.intent and primary.intent in {
                CommandIntent.AFFIRM,
                CommandIntent.REJECT,
                CommandIntent.REPEAT,
                CommandIntent.BACK,
            }:
                resolved = primary.intent
                consensus = True
            else:
                resolved = CommandIntent.UNKNOWN
                consensus = False
            interpretation_id = f"voice-interpretation-{uuid4().hex}"
            audio_hash = hashlib.sha256(wav_bytes).hexdigest()
            self.voice_interpretations[interpretation_id] = (
                VoiceInterpretationRecord(
                    interpretation_id=interpretation_id,
                    stage=stage,
                    candidate_id=self.runtime.session.selected_candidate_id,
                    prompt_id=prompt_id,
                    intent=resolved,
                    consensus=consensus,
                    audio_hash=audio_hash,
                )
            )
            while len(self.voice_interpretations) > 12:
                oldest_id = next(iter(self.voice_interpretations))
                self.voice_interpretations.pop(oldest_id, None)
            return {
                "interpretation_id": interpretation_id,
                "intent": resolved.value,
                "consensus": consensus,
                "stage": stage,
                "prompt_id": prompt_id,
                "audio_input_hash": audio_hash,
                "primary": {
                    "provider": primary.provider,
                    "intent": primary.intent.value,
                    "status": primary.status,
                },
                "secondary": {
                    "provider": secondary_provider,
                    "intent_provider": secondary.provider,
                    "intent": secondary.intent.value,
                    "status": secondary.status,
                },
            }

    def handle_voice_confirmation(
        self,
        command: PatientCommand,
    ) -> dict[str, Any]:
        """Bind Runtime confirmation to server-issued command evidence."""
        with self.lock:
            raw_ids = command.payload.get("voice_interpretation_ids")
            if (
                not isinstance(raw_ids, list)
                or not raw_ids
                or any(not isinstance(item, str) for item in raw_ids)
                or len(set(raw_ids)) != len(raw_ids)
            ):
                raise CommandRejected(
                    "Voice confirmation requires server-issued "
                    "interpretation IDs"
                )
            candidate = self.runtime.session.selected_candidate()
            if candidate is None:
                raise CommandRejected(
                    "No privately reviewed candidate is active"
                )
            required_count = (
                2
                if self.runtime.session.strict
                or candidate.source_level == "L3"
                else 1
            )
            if len(raw_ids) != required_count:
                raise CommandRejected(
                    f"Voice confirmation requires {required_count} "
                    "interpretation record(s)"
                )
            records: list[VoiceInterpretationRecord] = []
            for interpretation_id in raw_ids:
                record = self.voice_interpretations.get(interpretation_id)
                if record is None:
                    raise CommandRejected(
                        "Voice interpretation is missing, expired, or reused"
                    )
                if (
                    record.stage != self.runtime.session.stage.value
                    or record.candidate_id != candidate.id
                    or record.intent is not CommandIntent.AFFIRM
                    or not record.consensus
                ):
                    raise CommandRejected(
                        "Voice interpretation does not match the active "
                        "candidate"
                    )
                records.append(record)

            latest = records[-1]
            evidence: dict[str, Any] = {
                "prompt_id": latest.prompt_id,
                "audio_hash": latest.audio_hash,
                "intent": latest.intent.value,
                "consensus": latest.consensus,
            }
            if len(records) == 2:
                evidence.update(
                    {
                        "first_prompt_id": records[0].prompt_id,
                        "second_prompt_id": records[1].prompt_id,
                        "first_audio_hash": records[0].audio_hash,
                        "second_audio_hash": records[1].audio_hash,
                    }
                )
            trusted_payload = dict(command.payload)
            trusted_payload.pop("voice_interpretation_ids", None)
            trusted_payload["voice_confirmation_evidence"] = evidence
            trusted_payload["additional_voice_confirmation"] = (
                len(records) == 2
            )
            trusted_command = command.model_copy(
                update={"payload": trusted_payload}
            )
            self.runtime.handle(trusted_command)
            for interpretation_id in raw_ids:
                self.voice_interpretations.pop(interpretation_id, None)
            return self.response()

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
        if spoken and session.voice_authorized:
            view_payload["personal_voice_status"] = "used"
        return {
            "notice": (
                SIMULATED_NOTICE
                if self.profile.simulated
                else "User profile data; not a clinical accuracy claim."
            ),
            "simulated": self.profile.simulated,
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
        if settings.profile_database_backend == "mysql":
            profile_store = MySQLProfileStore(
                host=settings.mysql_host,
                port=settings.mysql_port,
                user=settings.mysql_user,
                password=settings.mysql_password,
                database=settings.mysql_database,
                connect_timeout_seconds=(
                    settings.mysql_connect_timeout_seconds
                ),
                ssl_ca=settings.mysql_ssl_ca,
                auto_create_schema=settings.mysql_auto_create_schema,
            )
        else:
            profile_store = SQLiteProfileStore(
                settings.profile_database_path
                or settings.audio_store_root / "profiles.sqlite3"
            )
        self._profiles = DemoProfileRegistry(
            root / "demo/profiles",
            max_profile_bytes=settings.max_profile_bytes,
            max_uploaded_profiles=settings.max_uploaded_profiles,
            cloud_mode=settings.mode == "cloud",
            store=profile_store,
        )

    def list_profiles(self) -> list[dict[str, Any]]:
        return self._profiles.list_profiles()

    def register_profile(self, markdown: str) -> dict[str, Any]:
        return self._profiles.register_upload(markdown)

    def create_profile(
        self,
        *,
        display_name: str,
        language: str,
        answers: dict[str, str],
    ) -> dict[str, Any]:
        return self._profiles.create_from_questionnaire(
            display_name=display_name,
            language=language,
            answers=answers,
        )

    def profile_detail(self, profile_ref: str) -> dict[str, Any]:
        return self._profiles.detail(profile_ref)

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
        self._profiles.close()


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
        profile_voice_id = (
            profile.voice_consent.voice_profile_id
            if profile.voice_consent is not None
            else None
        )
        voice_profile_id = (
            settings.voice_profile_id if profile_voice_id else None
        )
        if (
            voice_profile_id is not None
            and voice_profile_id != profile_voice_id
        ):
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
        base_asr: ASRPort = GatewayASRAdapter(
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
        command_intent: CommandIntentPort = GatewayCommandIntentAdapter(client)
    else:
        voice_profile_id = (
            profile.voice_consent.voice_profile_id
            if profile.voice_consent is not None
            else None
        )
        base_asr = MockASRAdapter.from_json(fixture_path)
        intent = MockIntentAdapter()
        command_intent = MockCommandIntentAdapter()
        delegate_tts = CachedTTSAdapter(
            root / fixture["tts"]["neutral_cache"],
            root / fixture["tts"]["personal_cache"],
        )

    asr = HeadsetPrimaryASRAdapter(base_asr)
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
        asr=asr,
        command_intent=command_intent,
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
