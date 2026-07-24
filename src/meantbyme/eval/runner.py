from __future__ import annotations

import json
import os
import tempfile
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from meantbyme.adapters.asr.gateway import GatewayASRAdapter
from meantbyme.adapters.asr.mock import MockASRAdapter
from meantbyme.adapters.audio import AudioStore
from meantbyme.adapters.http import GatewayHttpClient
from meantbyme.adapters.intent.gateway import GatewayIntentAdapter
from meantbyme.adapters.storage.sqlite import SQLiteRepository
from meantbyme.adapters.tts.cached import CachedTTSAdapter
from meantbyme.adapters.tts.gateway import GatewayTTSAdapter
from meantbyme.core.domain import (
    CommandActor,
    ConfirmationMethod,
    ExpressionCandidate,
    MemoryItem,
    MemoryType,
    PatientCommand,
    PatientCommandType,
    RiskLevel,
    RuntimeEventType,
    SessionStage,
    VerificationLevel,
)
from meantbyme.core.policies import classify_risk
from meantbyme.core.runtime import MeantByMeRuntime
from meantbyme.eval.metrics import compute_aggregate
from meantbyme.eval.models import (
    EvaluationMode,
    EvaluationSample,
    ExpectedBehavior,
    load_dataset,
)
from meantbyme.eval.providers import (
    EvaluationIntentAdapter,
    ReplayASRAdapter,
    ReplayIntentAdapter,
)
from meantbyme.eval.text import eval_tokens, normalize_for_eval, text_matches


DISCLAIMER = "Simulated data. Not a clinical accuracy claim."
OFFICIAL_VOICE = "cixingnansheng"
PROJECT_ROOT = Path(__file__).resolve().parents[3]


@dataclass
class ProfileRun:
    candidates: list[ExpressionCandidate]
    actual_band: str
    actual_behavior: str
    selected: ExpressionCandidate | None
    selected_text: str | None
    final_text: str | None
    final_stage: str
    spoken: bool
    authorization_granted: bool
    patient_confirmed: bool
    receipt_created: bool
    memory_write_count: int
    gold_memory_count: int
    valid_gold_memory_count: int
    clarification_rounds: int
    final_risk_level: RiskLevel
    strict_confirmation: bool
    elapsed_seconds: float | None


def _command(
    runtime: MeantByMeRuntime,
    command: PatientCommandType,
    *,
    payload: dict[str, Any] | None = None,
    confirmation_method: ConfirmationMethod | None = None,
) -> None:
    runtime.handle(
        PatientCommand(
            command=command,
            session_id=runtime.session.session_id,
            payload=payload or {},
            confirmation_method=confirmation_method,
            actor=CommandActor.PATIENT,
        )
    )


def _seed_repository(
    repository: SQLiteRepository,
    sample: EvaluationSample,
    *,
    include_memories: bool,
) -> None:
    repository.add_patient(sample.patient_id, f"Simulated {sample.patient_id}")
    if include_memories:
        for index, seed in enumerate(sample.seed_memories):
            level = VerificationLevel(seed.verification_level)
            repository.seed_verified_memory(
                sample.patient_id,
                MemoryItem(
                    id=f"eval-{sample.sample_id}-memory-{index + 1}",
                    patient_id=sample.patient_id,
                    memory_type=MemoryType.SEMANTIC,
                    verification_level=level,
                    text=seed.text,
                    language=seed.language or sample.language,
                    context=seed.context,
                    usage_count=seed.confirmations,
                    last_used_at=datetime(2026, 7, 24, tzinfo=UTC),
                    confirmation_session_id=(
                        f"simulated-seed-confirmation-{sample.sample_id}-{index + 1}"
                        if level is VerificationLevel.GOLD
                        else None
                    ),
                ),
            )
    repository.grant_voice_consent(
        sample.patient_id,
        f"simulated-consent-{sample.sample_id}",
        f"simulated-consent-session-{sample.sample_id}",
        OFFICIAL_VOICE,
    )


def _build_providers(
    *,
    mode: EvaluationMode,
    sample: EvaluationSample,
    dataset_path: Path,
    session_id: str,
    temporary_root: Path,
    gateway_url: str | None,
) -> tuple[Any, Any, Any]:
    tts_cache = CachedTTSAdapter(
        PROJECT_ROOT / "demo/audio/neutral_candidate.cache",
        PROJECT_ROOT / "demo/audio/david_personal_final.cache",
    )
    if mode is EvaluationMode.MOCK:
        fixture = [
            item.model_copy(
                update={"language": item.language or sample.language}
            ).model_dump(mode="json")
            for item in sample.asr_fixture
        ]
        return (
            MockASRAdapter({sample.sample_id: fixture}),
            EvaluationIntentAdapter(sample),
            tts_cache,
        )

    if mode is EvaluationMode.REPLAY:
        recording_path = (
            dataset_path.parent / "recordings" / f"{sample.sample_id}.json"
        )
        if not recording_path.is_file():
            raise FileNotFoundError(
                f"Replay fixture not found: {recording_path}"
            )
        return (
            ReplayASRAdapter(recording_path),
            ReplayIntentAdapter(recording_path),
            tts_cache,
        )

    base_url = gateway_url or os.getenv(
        "GATEWAY_URL", "http://127.0.0.1:8000"
    )
    audio_path = dataset_path.parent / "audio" / f"{sample.sample_id}.wav"
    if not audio_path.is_file():
        raise FileNotFoundError(
            "Cloud evaluation requires a simulated WAV at "
            f"{audio_path}; raw audio is not written to reports"
        )
    audio_store = AudioStore(temporary_root / "audio")
    audio_store.import_wav(audio_path, audio_id=sample.sample_id)
    client = GatewayHttpClient(
        base_url,
        timeout_seconds=20.0,
        max_attempts=3,
        backoff_seconds=0.25,
    )
    return (
        GatewayASRAdapter(
            audio_store=audio_store,
            client=client,
            patient_id=sample.patient_id,
            session_id=session_id,
            language_hint=sample.language,
            secondary_endpoint=None,
        ),
        GatewayIntentAdapter(
            client=client,
            patient_id=sample.patient_id,
            session_id=session_id,
            situation=sample.situation,
        ),
        GatewayTTSAdapter(client=client, audio_store=audio_store),
    )


def _initial_behavior(
    stage: SessionStage, *, switched_input: bool
) -> str:
    if switched_input:
        return ExpectedBehavior.SWITCH_INPUT.value
    if stage is SessionStage.CATEGORY_CLARIFICATION:
        return ExpectedBehavior.CATEGORY_CLARIFICATION.value
    if stage is SessionStage.FINAL_REVIEW:
        return ExpectedBehavior.FINAL_REVIEW.value
    return ExpectedBehavior.CANDIDATES.value


def _run_profile(
    sample: EvaluationSample,
    *,
    mode: EvaluationMode,
    dataset_path: Path,
    profile: Literal["coverage", "full-loop"],
    include_memories: bool,
    gateway_url: str | None,
) -> ProfileRun:
    repository = SQLiteRepository(":memory:")
    _seed_repository(
        repository, sample, include_memories=include_memories
    )
    suffix = "memory" if include_memories else "no-memory"
    session_id = f"eval-{sample.sample_id}-{profile}-{suffix}"
    started_at = time.monotonic()
    try:
        with tempfile.TemporaryDirectory(prefix="meantbyme-eval-") as temp:
            asr, intent, tts = _build_providers(
                mode=mode,
                sample=sample,
                dataset_path=dataset_path,
                session_id=session_id,
                temporary_root=Path(temp),
                gateway_url=gateway_url,
            )
            runtime = MeantByMeRuntime(
                asr=asr,
                intent=intent,
                tts=tts,
                repository=repository,
            )
            runtime.create_session(
                session_id=session_id,
                patient_id=sample.patient_id,
                language=sample.language,
                voice_profile_id=OFFICIAL_VOICE,
                situation=sample.situation,
            )
            _command(runtime, PatientCommandType.START_CAPTURE)
            _command(
                runtime,
                PatientCommandType.STOP_CAPTURE,
                payload={"audio_id": sample.sample_id},
            )
            _command(runtime, PatientCommandType.CONFIRM_HEARD_CONTENT)

            route_stage = runtime.session.stage
            switched_input = False
            if route_stage is SessionStage.CATEGORY_CLARIFICATION:
                if (
                    sample.expected_behavior
                    is ExpectedBehavior.SWITCH_INPUT
                ):
                    _command(
                        runtime, PatientCommandType.SWITCH_INPUT_METHOD
                    )
                    switched_input = True
                _command(
                    runtime,
                    PatientCommandType.SELECT_CATEGORY,
                    payload={"category": sample.category},
                )
            actual_behavior = _initial_behavior(
                route_stage, switched_input=switched_input
            )
            candidates = list(runtime.session.candidates)
            evidence = runtime.session.evidence
            actual_band = (
                evidence.evidence_band.value if evidence else "unknown"
            )

            selected: ExpressionCandidate | None = None
            if profile == "coverage":
                _command(runtime, PatientCommandType.STOP)
            else:
                selected = next(
                    (
                        candidate
                        for candidate in candidates
                        if text_matches(
                            candidate.text, sample.acceptable_candidates
                        )
                    ),
                    None,
                )
                if selected is None:
                    _command(runtime, PatientCommandType.NONE_OF_THESE)
                    _command(runtime, PatientCommandType.STOP)
                else:
                    _command(
                        runtime,
                        PatientCommandType.SELECT_CANDIDATE,
                        payload={"candidate_id": selected.id},
                    )
                    payload = {
                        "private_readback_completed": True,
                        "strict_confirmation": runtime.session.strict,
                        "l3_confirmation": selected.source_level == "L3",
                    }
                    _command(
                        runtime,
                        PatientCommandType.FINAL_CONFIRM,
                        payload=payload,
                        confirmation_method=ConfirmationMethod.LARGE_BUTTON,
                    )

            session = runtime.session
            events = runtime.events
            event_types = [event.event_type for event in events]
            memories = repository.search_verified_memories(
                sample.patient_id, []
            )
            gold = [
                memory
                for memory in memories
                if memory.verification_level is VerificationLevel.GOLD
            ]
            elapsed = (
                time.monotonic() - started_at
                if mode is EvaluationMode.CLOUD
                else None
            )
            return ProfileRun(
                candidates=candidates,
                actual_band=actual_band,
                actual_behavior=actual_behavior,
                selected=selected,
                selected_text=selected.text if selected else None,
                final_text=(
                    session.authorized_expression.final_text
                    if session.authorized_expression
                    else None
                ),
                final_stage=session.stage.value,
                spoken=RuntimeEventType.EXPRESSION_SPOKEN in event_types,
                authorization_granted=(
                    RuntimeEventType.VOICE_AUTHORIZATION_GRANTED
                    in event_types
                ),
                patient_confirmed=session.patient_confirmed,
                receipt_created=(
                    repository.get_receipt(
                        sample.patient_id, session_id
                    )
                    is not None
                ),
                memory_write_count=repository.count_memory_writes(
                    sample.patient_id
                ),
                gold_memory_count=len(gold),
                valid_gold_memory_count=sum(
                    bool(memory.confirmation_session_id) for memory in gold
                ),
                clarification_rounds=sum(
                    event_type
                    in {
                        RuntimeEventType.CLARIFICATION_REQUESTED,
                        RuntimeEventType.PATIENT_SELECTION_RECEIVED,
                    }
                    for event_type in event_types
                ),
                final_risk_level=session.risk_level,
                strict_confirmation=session.strict,
                elapsed_seconds=elapsed,
            )
    finally:
        repository.close()


def _best_match_rank(
    candidates: list[ExpressionCandidate], acceptable: list[str]
) -> int | None:
    for rank, candidate in enumerate(candidates, start=1):
        if text_matches(candidate.text, acceptable):
            return rank
    return None


def _fragment_recall(sample: EvaluationSample, final_text: str | None) -> float:
    if final_text is None:
        return 0.0
    final_tokens = set(eval_tokens(final_text))
    fragment_tokens = [
        token
        for fragment in sample.stable_fragments
        for token in eval_tokens(fragment)
    ]
    if not fragment_tokens:
        return 1.0
    return sum(token in final_tokens for token in fragment_tokens) / len(
        fragment_tokens
    )


def _unsupported_counts(
    sample: EvaluationSample, selected: ExpressionCandidate | None
) -> tuple[int, int]:
    if selected is None:
        return 0, 0
    sources = [
        sample.situation,
        *(
            fixture.transcript
            for fixture in sample.asr_fixture
            if fixture.status == "success"
        ),
        *(memory.text for memory in sample.seed_memories),
    ]
    source_tokens = {
        token for source in sources for token in eval_tokens(source)
    }
    unsupported = 0
    for span in selected.ai_added_spans:
        tokens = set(eval_tokens(span))
        if tokens and not tokens.issubset(source_tokens):
            unsupported += 1
    return unsupported, len(selected.ai_added_spans)


def _candidate_report(
    candidates: list[ExpressionCandidate], *, redact: bool
) -> list[dict[str, Any]]:
    return [
        {
            "rank": rank,
            "candidate_id": candidate.id,
            "text": "[REDACTED]" if redact else candidate.text,
            "source_level": candidate.source_level,
        }
        for rank, candidate in enumerate(candidates, start=1)
    ]


def _evaluate_sample(
    sample: EvaluationSample,
    *,
    mode: EvaluationMode,
    dataset_path: Path,
    gateway_url: str | None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    coverage = _run_profile(
        sample,
        mode=mode,
        dataset_path=dataset_path,
        profile="coverage",
        include_memories=True,
        gateway_url=gateway_url,
    )
    full = _run_profile(
        sample,
        mode=mode,
        dataset_path=dataset_path,
        profile="full-loop",
        include_memories=True,
        gateway_url=gateway_url,
    )
    rank_with = _best_match_rank(
        coverage.candidates, sample.acceptable_candidates
    )
    rank_without: int | None = None
    if sample.memory_expected_to_help:
        no_memory = _run_profile(
            sample,
            mode=mode,
            dataset_path=dataset_path,
            profile="coverage",
            include_memories=False,
            gateway_url=gateway_url,
        )
        rank_without = _best_match_rank(
            no_memory.candidates, sample.acceptable_candidates
        )
    missing_rank = len(coverage.candidates) + 1
    improvement = (
        (rank_without or missing_rank) - (rank_with or missing_rank)
        if sample.memory_expected_to_help
        else 0
    )
    unsupported, ai_added = _unsupported_counts(sample, full.selected)
    top3_hit = rank_with is not None and rank_with <= 3
    redact_final = full.final_risk_level is RiskLevel.HIGH_RISK
    redact_candidates = any(
        classify_risk(candidate.text, candidate.risk_level)
        is RiskLevel.HIGH_RISK
        for candidate in coverage.candidates
    )

    metric_record = {
        "sample_id": sample.sample_id,
        "pair_id": sample.pair_id,
        "acceptable_candidates": sample.acceptable_candidates,
        "selected_text": full.selected_text,
        "spoken": full.spoken,
        "authorization_granted": full.authorization_granted,
        "patient_confirmed": full.patient_confirmed,
        "gold_memory_count": full.gold_memory_count,
        "valid_gold_memory_count": full.valid_gold_memory_count,
        "top3_hit": top3_hit,
        "fragment_recall": _fragment_recall(sample, full.final_text),
        "unsupported_span_count": unsupported,
        "ai_added_span_count": ai_added,
        "expected_band": sample.expected_band.value,
        "expected_behavior": sample.expected_behavior.value,
        "actual_behavior": coverage.actual_behavior,
        "clarification_rounds": full.clarification_rounds,
        "memory_expected_to_help": sample.memory_expected_to_help,
        "memory_rank_improvement": improvement,
        "time_to_expression_seconds": full.elapsed_seconds,
    }
    report_record = {
        "sample_id": sample.sample_id,
        "simulated": True,
        "language": sample.language,
        "category": sample.category,
        "pair_id": sample.pair_id,
        "expected_band": sample.expected_band.value,
        "actual_band": coverage.actual_band,
        "expected_behavior": sample.expected_behavior.value,
        "actual_behavior": coverage.actual_behavior,
        "candidates": _candidate_report(
            coverage.candidates, redact=redact_candidates
        ),
        "top3_hit": top3_hit,
        "best_match_rank": rank_with,
        "selected_match": text_matches(
            full.selected_text, sample.acceptable_candidates
        ),
        "final_expression": (
            "[REDACTED]"
            if redact_final and full.final_text
            else full.final_text
        ),
        "final_stage": full.final_stage,
        "strict_confirmation": full.strict_confirmation,
        "receipt_created": full.receipt_created,
        "memory_write_count": full.memory_write_count,
        "fragment_recall": metric_record["fragment_recall"],
        "unsupported_completion_rate": (
            unsupported / ai_added if ai_added else 0.0
        ),
        "clarification_rounds": full.clarification_rounds,
        "memory_rank_with": rank_with,
        "memory_rank_without": rank_without,
        "memory_rank_improvement": improvement,
        "high_risk_plaintext_redacted": (
            redact_final or redact_candidates
        ),
    }
    return metric_record, report_record


def run_evaluation(
    *,
    dataset: str | Path,
    mode: str | EvaluationMode = EvaluationMode.MOCK,
    report: str | Path | None = None,
    gateway_url: str | None = None,
) -> dict[str, Any]:
    dataset_path = Path(dataset)
    selected_mode = EvaluationMode(mode)
    samples = load_dataset(dataset_path)
    metric_records: list[dict[str, Any]] = []
    report_records: list[dict[str, Any]] = []
    for sample in samples:
        metric_record, report_record = _evaluate_sample(
            sample,
            mode=selected_mode,
            dataset_path=dataset_path,
            gateway_url=gateway_url,
        )
        metric_records.append(metric_record)
        report_records.append(report_record)

    aggregate = compute_aggregate(
        metric_records, mode=selected_mode.value
    )
    hard_gates_passed = (
        aggregate["unauthorized_voice_rate"] == 0.0
        and aggregate["verified_memory_integrity"] == 1.0
    )
    result = {
        "disclaimer": DISCLAIMER,
        "mode": selected_mode.value,
        "dataset": str(dataset),
        "n_samples": len(samples),
        "aggregate": aggregate,
        "hard_gates_passed": hard_gates_passed,
        "per_sample": report_records,
    }
    if report is not None:
        report_path = Path(report)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    return result
