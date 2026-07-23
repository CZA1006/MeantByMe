from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Sequence

from meantbyme.adapters.asr import MockASRAdapter
from meantbyme.adapters.intent import MockIntentAdapter
from meantbyme.adapters.storage import SQLiteRepository
from meantbyme.adapters.tts import CachedTTSAdapter
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


def run_mock(database: str = ":memory:") -> dict:
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
    repository.grant_voice_consent(
        patient["id"],
        profile["voice_consent"]["authorization_id"],
        profile["voice_consent"]["consent_session_id"],
        profile["voice_consent"]["voice_profile_id"],
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

    _command(runtime, PatientCommandType.START_CAPTURE)
    _command(
        runtime,
        PatientCommandType.STOP_CAPTURE,
        payload={"audio_id": fixture["audio_id"]},
    )
    _command(runtime, PatientCommandType.CONFIRM_HEARD_CONTENT)
    if runtime.session.stage is SessionStage.CATEGORY_CLARIFICATION:
        _command(
            runtime,
            PatientCommandType.SELECT_CATEGORY,
            payload={"category": "plan"},
        )

    target_text = fixture["intended_expression"]
    selected = next(
        candidate
        for candidate in runtime.session.candidates
        if candidate.text == target_text
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

    receipt = repository.get_receipt(
        patient["id"], runtime.session.session_id
    )
    result = {
        "mode": "mock",
        "patient_id": patient["id"],
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
    repository.close()
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the MeantByMe mock runtime")
    parser.add_argument(
        "--mode",
        choices=["mock"],
        default="mock",
        help="Milestone 1 supports deterministic mock mode only",
    )
    parser.add_argument(
        "--database",
        default=":memory:",
        help="SQLite path; defaults to an in-memory demo database",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = run_mock(args.database)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["final_stage"] == SessionStage.COMPLETED.value else 1
