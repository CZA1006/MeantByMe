from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class DomainModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SessionStage(StrEnum):
    READY = "ready"
    CAPTURING = "capturing"
    AUDIO_CAPTURED = "audio_captured"
    TRANSCRIBING = "transcribing"
    EVIDENCE_EXTRACTED = "evidence_extracted"
    MEMORY_RETRIEVING = "memory_retrieving"
    HEARD_CONTENT_REVIEW = "heard_content_review"
    UNCERTAINTY_ASSESSED = "uncertainty_assessed"
    CATEGORY_CLARIFICATION = "category_clarification"
    CANDIDATE_SELECTION = "candidate_selection"
    FINAL_REVIEW = "final_review"
    PATIENT_CONFIRMED = "patient_confirmed"
    VOICE_AUTHORIZED = "voice_authorized"
    SPOKEN = "spoken"
    MEMORY_UPDATED = "memory_updated"
    COMPLETED = "completed"
    STOPPED = "stopped"


class ConfirmationMethod(StrEnum):
    LARGE_BUTTON = "large_button"
    KEYBOARD = "keyboard"
    SCANNING = "scanning"
    DWELL = "dwell"
    SECOND_METHOD = "second_method"


class CommandActor(StrEnum):
    PATIENT = "patient"
    CAREGIVER = "caregiver"
    SYSTEM = "system"


class PatientCommandType(StrEnum):
    START_CAPTURE = "start_capture"
    STOP_CAPTURE = "stop_capture"
    CONFIRM_HEARD_CONTENT = "confirm_heard_content"
    REJECT_HEARD_CONTENT = "reject_heard_content"
    SELECT_CATEGORY = "select_category"
    SELECT_CANDIDATE = "select_candidate"
    NONE_OF_THESE = "none_of_these"
    FINAL_CONFIRM = "final_confirm"
    EDIT_COMPLETION = "edit_completion"
    GO_BACK = "go_back"
    STOP = "stop"
    SWITCH_INPUT_METHOD = "switch_input_method"
    REQUEST_HELP = "request_help"


class MemoryType(StrEnum):
    SEMANTIC = "semantic"
    ACOUSTIC = "acoustic"
    CONTEXT = "context"
    LANGUAGE = "language"
    INTERACTION = "interaction"


class VerificationLevel(StrEnum):
    GOLD = "gold"
    SILVER = "silver"
    UNVERIFIED = "unverified"


class RiskLevel(StrEnum):
    ORDINARY = "ordinary"
    SENSITIVE = "sensitive"
    HIGH_RISK = "high_risk"


class UncertaintyBand(StrEnum):
    LOW = "low_uncertainty"
    MEDIUM = "medium_uncertainty"
    HIGH = "high_uncertainty"


class RuntimeEventType(StrEnum):
    SESSION_STARTED = "SESSION_STARTED"
    AUDIO_CAPTURED = "AUDIO_CAPTURED"
    ASR_RESULT_RECEIVED = "ASR_RESULT_RECEIVED"
    EVIDENCE_EXTRACTED = "EVIDENCE_EXTRACTED"
    MEMORY_RETRIEVED = "MEMORY_RETRIEVED"
    MEMORY_RETRIEVAL_FAILED = "MEMORY_RETRIEVAL_FAILED"
    CONTEXT_RETRIEVED = "CONTEXT_RETRIEVED"
    UNCERTAINTY_ASSESSED = "UNCERTAINTY_ASSESSED"
    CLARIFICATION_REQUESTED = "CLARIFICATION_REQUESTED"
    CANDIDATES_GENERATED = "CANDIDATES_GENERATED"
    CANDIDATES_RERANKED = "CANDIDATES_RERANKED"
    PATIENT_SELECTION_RECEIVED = "PATIENT_SELECTION_RECEIVED"
    PRIVATE_READBACK_READY = "PRIVATE_READBACK_READY"
    FINAL_CONFIRMATION_RECEIVED = "FINAL_CONFIRMATION_RECEIVED"
    VOICE_AUTHORIZATION_GRANTED = "VOICE_AUTHORIZATION_GRANTED"
    VOICE_AUTHORIZATION_BLOCKED = "VOICE_AUTHORIZATION_BLOCKED"
    TTS_FAILED = "TTS_FAILED"
    EXPRESSION_SPOKEN = "EXPRESSION_SPOKEN"
    EXPRESSION_RECEIPT_CREATED = "EXPRESSION_RECEIPT_CREATED"
    EXPRESSION_RECEIPT_FAILED = "EXPRESSION_RECEIPT_FAILED"
    VERIFIED_MEMORY_WRITTEN = "VERIFIED_MEMORY_WRITTEN"
    MEMORY_WRITE_FAILED = "MEMORY_WRITE_FAILED"
    SESSION_COMPLETED = "SESSION_COMPLETED"
    SESSION_STOPPED = "SESSION_STOPPED"
    COMMAND_REJECTED = "COMMAND_REJECTED"
    INPUT_METHOD_SWITCH_REQUESTED = "INPUT_METHOD_SWITCH_REQUESTED"
    HELP_REQUESTED = "HELP_REQUESTED"


class ASRResult(DomainModel):
    provider: str
    transcript: str
    language: str | None = None
    segments: list[dict[str, Any]] = Field(default_factory=list)
    latency_ms: int | None = None
    status: Literal["success", "failed", "timeout"]
    error: str | None = None


class TranscriptEvidence(DomainModel):
    results: list[ASRResult]
    stable_fragments: list[str]
    uncertain_fragments: list[str]
    conflicts: list[list[str]]
    missing_slots: list[str]
    evidence_band: UncertaintyBand


class MemoryItem(DomainModel):
    id: str
    patient_id: str
    memory_type: MemoryType
    verification_level: VerificationLevel
    text: str | None = None
    language: str | None = None
    context: dict[str, Any] = Field(default_factory=dict)
    usage_count: int = 0
    last_used_at: datetime | None = None
    similarity_band: Literal["high", "medium", "low"] | None = None
    confirmation_session_id: str | None = None


class ExpressionCandidate(DomainModel):
    id: str
    text: str
    language: str
    patient_supported_spans: list[str]
    ai_added_spans: list[str]
    memory_support_ids: list[str]
    ranking_reasons: list[str]
    risk_level: RiskLevel
    source_level: Literal["L1", "L2", "L3"]


class IntentProposal(DomainModel):
    certain_content: list[str]
    uncertain_content: list[str]
    candidates: list[ExpressionCandidate]
    clarification_question: str | None = None
    clarification_options: list[str] = Field(default_factory=list)
    requires_confirmation: bool = True


class ConfirmedContext(DomainModel):
    locked_slots: dict[str, str] = Field(default_factory=dict)
    locked_tokens: list[str] = Field(default_factory=list)
    rejected_texts: list[str] = Field(default_factory=list)


class AuthorizedExpression(DomainModel):
    session_id: str
    patient_id: str
    final_text: str
    language: str
    voice_profile_id: str
    authorization_scope: Literal["this_expression"]
    confirmation_method: ConfirmationMethod
    authorized_at: datetime


class ExpressionReceipt(DomainModel):
    receipt_id: str
    session_id: str
    patient_id: str
    patient_supported_content: list[str]
    ai_added_content: list[str]
    memory_ids_used: list[str]
    expression_level: Literal["L1", "L2", "L3"]
    selected_candidate_id: str
    patient_confirmed: bool
    confirmation_method: ConfirmationMethod
    voice_profile_id: str | None
    authorization_scope: Literal["this_expression"] | None
    output_channel: str
    audio_input_hash: str
    final_text_hash: str
    created_at: datetime
    signature: str | None = None


class ExpressionSession(DomainModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    session_id: str
    patient_id: str
    stage: SessionStage = SessionStage.READY
    language: str | None = None
    situation: str | None = None
    voice_profile_id: str
    evidence: TranscriptEvidence | None = None
    retrieved_memories: list[MemoryItem] = Field(default_factory=list)
    retrieved_context: list[MemoryItem] = Field(default_factory=list)
    candidates: list[ExpressionCandidate] = Field(default_factory=list)
    selected_candidate_id: str | None = None
    patient_confirmed: bool = False
    confirmation_method: ConfirmationMethod | None = None
    voice_authorized: bool = False
    authorization_scope: Literal["this_expression"] | None = None
    risk_level: RiskLevel = RiskLevel.ORDINARY
    strict: bool = False
    confirmed_context: ConfirmedContext = Field(default_factory=ConfirmedContext)
    previous_stage: SessionStage | None = None
    audio_id: str | None = None
    audio_input_hash: str | None = None
    neutral_readback_path: str | None = None
    authorized_expression: AuthorizedExpression | None = None
    receipt_id: str | None = None
    failure_status: str | None = None

    def selected_candidate(self) -> ExpressionCandidate | None:
        if self.selected_candidate_id is None:
            return None
        return next(
            (
                candidate
                for candidate in self.candidates
                if candidate.id == self.selected_candidate_id
            ),
            None,
        )


class PatientCommand(DomainModel):
    command: PatientCommandType
    session_id: str
    payload: dict[str, Any] = Field(default_factory=dict)
    confirmation_method: ConfirmationMethod | None = None
    actor: CommandActor = CommandActor.PATIENT


class RuntimeEvent(DomainModel):
    event_id: str
    event_type: RuntimeEventType
    session_id: str
    patient_id: str
    timestamp: datetime
    payload: dict[str, Any] = Field(default_factory=dict)


class TTSResult(DomainModel):
    status: Literal["success", "failed"]
    audio_path: str | None = None
    audio_bytes: bytes | None = None
    media_type: str | None = None
    error: str | None = None


class MemoryWriteResult(DomainModel):
    memory: MemoryItem
    written: bool
    idempotency_key: str


class SessionViewModel(DomainModel):
    session_id: str
    stage: SessionStage
    headline: str
    heard_stable: list[str]
    heard_uncertain: list[str]
    clarification_question: str | None
    clarification_options: list[str]
    candidates: list[ExpressionCandidate]
    allowed_actions: list[PatientCommandType]
    trace_items: list[dict[str, Any]]
    personal_voice_status: Literal[
        "blocked", "awaiting_confirmation", "authorized", "used"
    ]
