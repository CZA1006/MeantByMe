from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal, Protocol

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    model_validator,
)

from meantbyme.core.domain import (
    MemoryItem,
    MemoryType,
    RiskLevel,
    VerificationLevel,
)


_PROFILE_BLOCK = re.compile(
    r"```meantbyme-profile\s*\n(?P<body>.*?)\n```",
    flags=re.DOTALL,
)


class ProfileBundleError(ValueError):
    pass


class ProfileModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ProfilePatient(ProfileModel):
    patient_id: str = Field(min_length=1, max_length=80)
    display_name: str = Field(min_length=1, max_length=120)
    languages: list[str] = Field(min_length=1)
    default_language: str = Field(min_length=2, max_length=12)


class ProfileConsent(ProfileModel):
    scope: Literal["demo_testing", "app_personalization"]
    cloud_processing_allowed: bool


class ProfileVoiceConsent(ProfileModel):
    authorization_id: str = Field(min_length=1, max_length=160)
    consent_session_id: str = Field(min_length=1, max_length=160)
    voice_profile_id: str = Field(min_length=1, max_length=160)


class ProfileMemory(ProfileModel):
    simulated: bool
    id: str = Field(min_length=1, max_length=160)
    memory_type: Literal["semantic", "context"]
    verification_level: VerificationLevel
    source: Literal[
        "user_input",
        "confirmed_expression",
        "patient",
        "caregiver",
        "research_fixture",
    ]
    text: str = Field(min_length=1, max_length=1000)
    language: str = Field(min_length=2, max_length=12)
    context: dict[str, Any] = Field(default_factory=dict)
    usage_count: int = Field(default=0, ge=0)
    confirmation_session_id: str | None = None
    sensitivity: RiskLevel = RiskLevel.ORDINARY
    prompt_eligible: bool

    @model_validator(mode="after")
    def enforce_provenance(self) -> "ProfileMemory":
        if (
            self.verification_level is VerificationLevel.UNVERIFIED
            and self.prompt_eligible
        ):
            raise ValueError("unverified memory cannot be prompt eligible")
        return self


class ProfileBundle(ProfileModel):
    schema_version: Literal[1]
    simulated: bool
    profile_id: str = Field(min_length=1, max_length=80)
    label: str = Field(min_length=1, max_length=160)
    patient: ProfilePatient
    consent: ProfileConsent
    voice_consent: ProfileVoiceConsent | None = None
    memories: list[ProfileMemory] = Field(default_factory=list)

    @model_validator(mode="after")
    def require_consistent_patient(self) -> "ProfileBundle":
        if self.profile_id != self.patient.patient_id:
            raise ValueError("profile_id must equal patient.patient_id")
        if self.simulated and self.consent.scope != "demo_testing":
            raise ValueError("simulated profile requires demo_testing scope")
        if not self.simulated and self.consent.scope != "app_personalization":
            raise ValueError(
                "non-simulated profile requires app_personalization scope"
            )
        memory_ids: set[str] = set()
        for memory in self.memories:
            if memory.simulated != self.simulated:
                raise ValueError("memory simulated flag must match profile")
            if memory.id in memory_ids:
                raise ValueError(f"duplicate profile memory id: {memory.id}")
            memory_ids.add(memory.id)
        return self


class ProfileImportResult(ProfileModel):
    patient_id: str
    semantic_count: int
    context_count: int
    skipped_memory_ids: list[str]


class ProfileRepositoryPort(Protocol):
    def add_patient(self, patient_id: str, display_name: str) -> None: ...

    def add_context_memory(
        self, patient_id: str, memory: MemoryItem
    ) -> None: ...

    def seed_verified_memory(
        self, patient_id: str, memory: MemoryItem
    ) -> None: ...

    def grant_voice_consent(
        self,
        patient_id: str,
        authorization_id: str,
        consent_session_id: str,
        voice_profile_id: str,
    ) -> None: ...


def parse_profile_markdown(
    text: str,
    *,
    max_bytes: int = 64 * 1024,
) -> ProfileBundle:
    if len(text.encode("utf-8")) > max_bytes:
        raise ProfileBundleError("profile document is too large")
    matches = list(_PROFILE_BLOCK.finditer(text))
    if len(matches) != 1:
        raise ProfileBundleError(
            "profile Markdown must contain exactly one "
            "meantbyme-profile JSON block"
        )
    try:
        payload = json.loads(matches[0].group("body"))
        return ProfileBundle.model_validate(payload)
    except json.JSONDecodeError as error:
        raise ProfileBundleError(f"invalid profile bundle: {error}") from error
    except ValidationError as error:
        details = "; ".join(
            (
                ".".join(str(part) for part in issue["loc"])
                + ": "
                + issue["msg"]
            )
            for issue in error.errors(include_input=False)
        )
        raise ProfileBundleError(
            f"invalid profile bundle: {details}"
        ) from error


def load_profile_bundle(
    path: str | Path,
    *,
    max_bytes: int = 64 * 1024,
) -> ProfileBundle:
    source = Path(path)
    try:
        text = source.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as error:
        raise ProfileBundleError("profile document must be UTF-8 Markdown") from error
    return parse_profile_markdown(text, max_bytes=max_bytes)


def seed_profile_repository(
    repository: ProfileRepositoryPort,
    profile: ProfileBundle,
    *,
    now: datetime | None = None,
) -> ProfileImportResult:
    timestamp = now or datetime.now(UTC)
    patient_id = profile.patient.patient_id
    repository.add_patient(patient_id, profile.patient.display_name)
    semantic_count = 0
    context_count = 0
    skipped: list[str] = []

    for item in profile.memories:
        if (
            not item.prompt_eligible
            or item.verification_level is VerificationLevel.UNVERIFIED
        ):
            skipped.append(item.id)
            continue
        context = {
            **item.context,
            "source": item.source,
            "sensitivity": item.sensitivity.value,
            "prompt_eligible": item.prompt_eligible,
        }
        trusted_level = (
            VerificationLevel.UNVERIFIED
            if item.verification_level is VerificationLevel.UNVERIFIED
            else VerificationLevel.GOLD
        )
        memory = MemoryItem(
            id=item.id,
            patient_id=patient_id,
            memory_type=MemoryType(item.memory_type),
            verification_level=trusted_level,
            text=item.text,
            language=item.language,
            context=context,
            usage_count=item.usage_count,
            last_used_at=timestamp,
            confirmation_session_id=(
                item.confirmation_session_id
                or f"explicit-profile-input:{item.id}"
            ),
        )
        if memory.memory_type is MemoryType.CONTEXT:
            repository.add_context_memory(patient_id, memory)
            context_count += 1
        else:
            repository.seed_verified_memory(patient_id, memory)
            semantic_count += 1

    voice = profile.voice_consent
    if voice is not None:
        repository.grant_voice_consent(
            patient_id,
            voice.authorization_id,
            voice.consent_session_id,
            voice.voice_profile_id,
        )
    return ProfileImportResult(
        patient_id=patient_id,
        semantic_count=semantic_count,
        context_count=context_count,
        skipped_memory_ids=skipped,
    )
