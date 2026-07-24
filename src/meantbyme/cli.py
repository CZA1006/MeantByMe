from __future__ import annotations

import argparse
import json
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Sequence
from uuid import uuid4

from meantbyme.adapters.asr import GatewayASRAdapter, MockASRAdapter
from meantbyme.adapters.audio import AudioStore
from meantbyme.adapters.http import GatewayHttpClient
from meantbyme.adapters.intent import GatewayIntentAdapter, MockIntentAdapter
from meantbyme.adapters.storage import SQLiteRepository
from meantbyme.adapters.tts import CachedTTSAdapter, GatewayTTSAdapter
from meantbyme.config import DesktopSettings
from meantbyme.core.domain import (
    ConfirmationMethod,
    MemoryItem,
    MemoryType,
    PatientCommand,
    PatientCommandType,
    SessionStage,
    VerificationLevel,
)
from meantbyme.core.runtime import MeantByMeRuntime


def _repository_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _command(
    runtime: MeantByMeRuntime,
    command: PatientCommandType,
    *,
    payload: dict | None = None,
    confirmation_method: ConfirmationMethod | None = None,
) -> None:
    runtime.handle(
        PatientCommand(
            command=command,
            session_id=runtime.session.session_id,
            payload=payload or {},
            confirmation_method=confirmation_method,
        )
    )


def _seed_demo_repository(
    database: str,
) -> tuple[SQLiteRepository, dict, dict, dict, Path]:
    root = _repository_root()
    profile = _load_json(root / "demo/profiles/david_demo.json")
    fixture_path = root / "demo/fixtures/golden_path.json"
    fixture = _load_json(fixture_path)
    repository = SQLiteRepository(database)
    patient = profile["patient"]
    repository.add_patient(patient["id"], patient["display_name"])
    for item in patient["verified_phrases"]:
        repository.seed_verified_memory(
            patient["id"],
            MemoryItem(
                id=item["id"],
                patient_id=patient["id"],
                memory_type=MemoryType.SEMANTIC,
                verification_level=VerificationLevel.GOLD,
                text=item["text"],
                language=item["language"],
                context=item["context"],
                usage_count=item["confirmations"],
                last_used_at=datetime.now(UTC),
                confirmation_session_id=item["confirmation_session_id"],
            ),
        )
    for item in patient.get("context_memories", []):
        repository.add_context_memory(
            patient["id"],
            MemoryItem(
                id=item["id"],
                patient_id=patient["id"],
                memory_type=MemoryType.CONTEXT,
                verification_level=VerificationLevel(
                    item["verification_level"]
                ),
                text=item["text"],
                language=item["language"],
                context=item["context"],
                usage_count=item["confirmations"],
                last_used_at=datetime.now(UTC),
                confirmation_session_id=item["confirmation_session_id"],
            ),
        )
    repository.grant_voice_consent(
        patient["id"],
        profile["voice_consent"]["authorization_id"],
        profile["voice_consent"]["consent_session_id"],
        profile["voice_consent"]["voice_profile_id"],
    )
    return repository, patient, profile, fixture, fixture_path


def _drive_golden_path(
    runtime: MeantByMeRuntime,
    *,
    audio_id: str,
    intended_expression: str,
) -> None:
    _command(runtime, PatientCommandType.START_CAPTURE)
    _command(
        runtime,
        PatientCommandType.STOP_CAPTURE,
        payload={"audio_id": audio_id},
    )
    _command(runtime, PatientCommandType.CONFIRM_HEARD_CONTENT)
    if runtime.session.stage is SessionStage.CATEGORY_CLARIFICATION:
        _command(
            runtime,
            PatientCommandType.SELECT_CATEGORY,
            payload={"category": "plan"},
        )

    selected = next(
        (
            candidate
            for candidate in runtime.session.candidates
            if candidate.text == intended_expression
        ),
        runtime.session.candidates[0],
    )
    _command(
        runtime,
        PatientCommandType.SELECT_CANDIDATE,
        payload={"candidate_id": selected.id},
    )
    _command(
        runtime,
        PatientCommandType.FINAL_CONFIRM,
        payload={
            "private_readback_completed": True,
            "strict_confirmation": runtime.session.strict,
        },
        confirmation_method=ConfirmationMethod.LARGE_BUTTON,
    )


def _result(
    runtime: MeantByMeRuntime,
    repository: SQLiteRepository,
    *,
    mode: str,
) -> dict:
    receipt = repository.get_receipt(
        runtime.session.patient_id, runtime.session.session_id
    )
    return {
        "mode": mode,
        "patient_id": runtime.session.patient_id,
        "simulated_profile": True,
        "session_id": runtime.session.session_id,
        "final_stage": runtime.session.stage.value,
        "unauthorized_voice_rate": 0,
        "receipt": (
            receipt.model_dump(mode="json") if receipt is not None else None
        ),
        "trace": [
            event.model_dump(mode="json") for event in runtime.events
        ],
    }


def run_mock(database: str = ":memory:") -> dict:
    root = _repository_root()
    repository, patient, profile, fixture, fixture_path = (
        _seed_demo_repository(database)
    )
    tts = CachedTTSAdapter(
        root / fixture["tts"]["neutral_cache"],
        root / fixture["tts"]["personal_cache"],
    )
    runtime = MeantByMeRuntime(
        asr=MockASRAdapter.from_json(fixture_path),
        intent=MockIntentAdapter(),
        tts=tts,
        repository=repository,
    )
    runtime.create_session(
        session_id=fixture["session_id"],
        patient_id=patient["id"],
        language=fixture["language"],
        voice_profile_id=profile["voice_consent"]["voice_profile_id"],
    )
    _drive_golden_path(
        runtime,
        audio_id=fixture["audio_id"],
        intended_expression=fixture["intended_expression"],
    )
    result = _result(runtime, repository, mode="mock")
    repository.close()
    return result


def run_cloud(
    *,
    gateway_url: str,
    audio_path: Path | None = None,
    microphone_seconds: float | None = None,
    audio_device: int | str | None = None,
    database: str = ":memory:",
    audio_store_dir: Path | None = None,
    timeout_seconds: float = 20.0,
    max_attempts: int = 2,
    gateway_token: str = "",
    situation: str | None = None,
    voice_profile_id: str = "cixingnansheng",
) -> dict:
    repository, patient, profile, fixture, _ = _seed_demo_repository(database)
    store_root = audio_store_dir or (
        Path(tempfile.gettempdir()) / "meantbyme-audio"
    )
    audio_store = AudioStore(store_root)
    audio_id = fixture["audio_id"]
    if audio_path is not None:
        audio_store.import_wav(audio_path, audio_id=audio_id)
    elif microphone_seconds is not None:
        audio_store.capture_microphone(
            audio_id=audio_id,
            duration_seconds=microphone_seconds,
            device=audio_device,
        )
    else:
        repository.close()
        raise ValueError("cloud mode requires a WAV file or microphone duration")

    session_id = f"cloud-{uuid4().hex}"
    if voice_profile_id != profile["voice_consent"]["voice_profile_id"]:
        repository.grant_voice_consent(
            patient["id"],
            (
                f"{profile['voice_consent']['authorization_id']}"
                f"-{voice_profile_id}"
            ),
            profile["voice_consent"]["consent_session_id"],
            voice_profile_id,
        )
    client = GatewayHttpClient(
        gateway_url,
        timeout_seconds=timeout_seconds,
        max_attempts=max_attempts,
        token=gateway_token,
    )
    runtime = MeantByMeRuntime(
        asr=GatewayASRAdapter(
            client=client,
            audio_store=audio_store,
            patient_id=patient["id"],
            session_id=session_id,
        ),
        intent=GatewayIntentAdapter(
            client=client,
            patient_id=patient["id"],
            session_id=session_id,
            situation=situation,
        ),
        tts=GatewayTTSAdapter(
            client=client,
            audio_store=audio_store,
        ),
        repository=repository,
    )
    runtime.create_session(
        session_id=session_id,
        patient_id=patient["id"],
        language=fixture["language"],
        voice_profile_id=voice_profile_id,
        situation=situation,
    )
    _drive_golden_path(
        runtime,
        audio_id=audio_id,
        intended_expression=fixture["intended_expression"],
    )
    result = _result(runtime, repository, mode="cloud")
    repository.close()
    return result


def run_fallback(database: str = ":memory:") -> dict:
    result = run_mock(database)
    result["mode"] = "fallback"
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the MeantByMe runtime")
    parser.add_argument(
        "--mode",
        choices=["mock", "cloud", "fallback"],
        default="mock",
        help="Provider mode; cloud routes through the local gateway",
    )
    parser.add_argument(
        "--database",
        default=":memory:",
        help="SQLite path; defaults to an in-memory demo database",
    )
    parser.add_argument("--audio", type=Path, help="WAV input for cloud mode")
    parser.add_argument(
        "--microphone-seconds",
        type=float,
        help="Capture this many seconds from the microphone in cloud mode",
    )
    parser.add_argument(
        "--audio-device",
        help="Optional sounddevice input device id or name",
    )
    parser.add_argument(
        "--gateway-url",
        help="Gateway base URL; defaults to GATEWAY_URL",
    )
    parser.add_argument(
        "--audio-store-dir",
        type=Path,
        help="Directory for private normalized WAV files",
    )
    parser.add_argument(
        "--situation",
        help="Current situational evidence for intent disambiguation",
    )
    parser.add_argument(
        "--voice-profile-id",
        default="cixingnansheng",
        help="Official or enrolled StepFun voice for confirmed output",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.mode == "cloud":
        if (args.audio is None) == (args.microphone_seconds is None):
            parser.error(
                "cloud mode requires exactly one of --audio or "
                "--microphone-seconds"
            )
        settings = DesktopSettings.from_env()
        device: int | str | None = args.audio_device
        if isinstance(device, str) and device.isdigit():
            device = int(device)
        result = run_cloud(
            gateway_url=args.gateway_url or settings.gateway_url,
            audio_path=args.audio,
            microphone_seconds=args.microphone_seconds,
            audio_device=device,
            database=args.database,
            audio_store_dir=args.audio_store_dir or settings.audio_store_dir,
            timeout_seconds=settings.gateway_timeout_seconds,
            max_attempts=settings.gateway_max_attempts,
            gateway_token=settings.gateway_token,
            situation=args.situation,
            voice_profile_id=args.voice_profile_id,
        )
    elif args.mode == "fallback":
        result = run_fallback(args.database)
    else:
        result = run_mock(args.database)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["final_stage"] == SessionStage.COMPLETED.value else 1
