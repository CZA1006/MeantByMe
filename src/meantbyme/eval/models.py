from __future__ import annotations

import json
from enum import StrEnum
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from meantbyme.core.domain import RiskLevel, UncertaintyBand, VerificationLevel
from meantbyme.eval.text import normalize_for_eval


class EvalModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ExpectedBehavior(StrEnum):
    CANDIDATES = "candidates"
    CATEGORY_CLARIFICATION = "category_clarification"
    FINAL_REVIEW = "final_review"
    SWITCH_INPUT = "switch_input"


class EvaluationMode(StrEnum):
    MOCK = "mock"
    CLOUD = "cloud"
    REPLAY = "replay"


class ASRFixture(EvalModel):
    provider: str
    transcript: str
    status: Literal["success", "failed", "timeout"]
    language: str | None = None
    segments: list[dict[str, Any]] = Field(default_factory=list)
    latency_ms: int | None = None
    error: str | None = None


class SeedMemory(EvalModel):
    text: str
    verification_level: Literal[
        VerificationLevel.GOLD, VerificationLevel.SILVER
    ]
    context: dict[str, Any] = Field(default_factory=dict)
    confirmations: int = Field(default=0, ge=0)
    language: str | None = None


class EvaluationSample(EvalModel):
    sample_id: str
    simulated: Literal[True]
    language: str
    category: str
    patient_id: str
    pair_id: str | None = None
    intended_expression: str
    stable_fragments: list[str] = Field(min_length=1)
    situation: str
    acceptable_candidates: list[str] = Field(min_length=1)
    required_meaning: dict[str, list[str]] = Field(default_factory=dict)
    forbidden_changes: list[str] = Field(default_factory=list)
    risk_level: RiskLevel
    asr_fixture: list[ASRFixture] = Field(min_length=1)
    seed_memories: list[SeedMemory] = Field(default_factory=list)
    memory_expected_to_help: bool
    expected_band: UncertaintyBand
    expected_behavior: ExpectedBehavior

    @field_validator(
        "sample_id",
        "language",
        "category",
        "patient_id",
        "intended_expression",
        "situation",
    )
    @classmethod
    def require_nonempty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("value must not be blank")
        return value

    @model_validator(mode="after")
    def intended_expression_must_be_acceptable(self) -> "EvaluationSample":
        intended = normalize_for_eval(self.intended_expression)
        acceptable = {
            normalize_for_eval(item) for item in self.acceptable_candidates
        }
        if intended not in acceptable:
            raise ValueError(
                "intended_expression must be one of acceptable_candidates"
            )
        if len(acceptable) != len(self.acceptable_candidates):
            raise ValueError("acceptable_candidates must be distinct")
        for slot, alternatives in self.required_meaning.items():
            if not slot.strip():
                raise ValueError("required_meaning slot names must not be blank")
            if not alternatives or any(
                not alternative.strip() for alternative in alternatives
            ):
                raise ValueError(
                    "required_meaning alternatives must be non-empty strings"
                )
        if any(not phrase.strip() for phrase in self.forbidden_changes):
            raise ValueError(
                "forbidden_changes entries must be non-empty strings"
            )
        return self


def load_dataset(path: str | Path) -> list[EvaluationSample]:
    dataset_path = Path(path)
    samples: list[EvaluationSample] = []
    for line_number, raw_line in enumerate(
        dataset_path.read_text(encoding="utf-8").splitlines(), start=1
    ):
        if not raw_line.strip():
            continue
        try:
            samples.append(EvaluationSample.model_validate_json(raw_line))
        except (json.JSONDecodeError, ValueError) as error:
            raise ValueError(
                f"Invalid evaluation sample at line {line_number}: {error}"
            ) from error

    if not samples:
        raise ValueError("Evaluation dataset is empty")
    sample_ids = [sample.sample_id for sample in samples]
    if len(sample_ids) != len(set(sample_ids)):
        raise ValueError("Evaluation sample_id values must be unique")

    pairs: dict[str, list[EvaluationSample]] = {}
    for sample in samples:
        if sample.pair_id:
            pairs.setdefault(sample.pair_id, []).append(sample)
    invalid_pairs = {
        pair_id: len(members)
        for pair_id, members in pairs.items()
        if len(members) != 2
    }
    if invalid_pairs:
        raise ValueError(
            f"Each pair_id must identify exactly two samples: {invalid_pairs}"
        )
    return samples
