# 13｜核心 API 与 Domain Schemas

建议使用 Python 3.11 + Pydantic。

> **注:** 本文档的 schema 为单一事实源。字段/枚举冲突的裁决见 [DECISIONS.md](../DECISIONS.md)(D1 状态枚举、D2 记忆类型、D3 receipt 字段、D9 confirmation_method)。

## SessionStage

```python
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
```

## ConfirmationMethod

`confirmation_method` 收敛为枚举(见 [DECISIONS.md](../DECISIONS.md) D9),不使用自由字符串。

```python
class ConfirmationMethod(StrEnum):
    LARGE_BUTTON = "large_button"
    KEYBOARD = "keyboard"
    SCANNING = "scanning"
    DWELL = "dwell"
    SECOND_METHOD = "second_method"
```

## ASR and evidence

```python
class ASRResult(BaseModel):
    provider: str
    transcript: str
    language: str | None
    segments: list[dict]
    latency_ms: int | None
    status: Literal["success", "failed", "timeout"]
    error: str | None = None

class TranscriptEvidence(BaseModel):
    results: list[ASRResult]
    stable_fragments: list[str]
    uncertain_fragments: list[str]
    conflicts: list[list[str]]
    missing_slots: list[str]
    evidence_band: Literal[
        "low_uncertainty",
        "medium_uncertainty",
        "high_uncertainty"
    ]
```

## Memory

```python
class MemoryItem(BaseModel):
    id: str
    patient_id: str
    memory_type: Literal[
        "semantic", "acoustic", "context",
        "language", "interaction"
    ]
    # gold/silver are legacy storage values; both map to trusted
    verification_level: Literal["gold", "silver", "unverified"]
    text: str | None
    language: str | None
    context: dict
    usage_count: int
    last_used_at: datetime | None
    similarity_band: Literal["high", "medium", "low"] | None
```

## Candidate

```python
class ExpressionCandidate(BaseModel):
    id: str
    text: str
    language: str
    patient_supported_spans: list[str]
    ai_added_spans: list[str]
    memory_support_ids: list[str]
    ranking_reasons: list[str]
    risk_level: Literal["ordinary", "sensitive", "high_risk"]
    source_level: Literal["L1", "L2", "L3"]
```

## IntentProposal

```python
class IntentProposal(BaseModel):
    certain_content: list[str]
    uncertain_content: list[str]
    candidates: list[ExpressionCandidate]
    clarification_question: str | None
    clarification_options: list[str]
    requires_confirmation: bool = True
```

禁止任何 speak、authorization 或 memory-write 字段。

## ExpressionSession

```python
class ExpressionSession(BaseModel):
    session_id: str
    patient_id: str
    stage: SessionStage
    language: str | None
    evidence: TranscriptEvidence | None
    retrieved_memories: list[MemoryItem]
    candidates: list[ExpressionCandidate]
    selected_candidate_id: str | None
    patient_confirmed: bool
    confirmation_method: str | None
    voice_authorized: bool
    authorization_scope: str | None
    risk_level: str
```

## PatientCommand

```python
class PatientCommand(BaseModel):
    command: Literal[
        "start_capture",
        "stop_capture",
        "confirm_heard_content",
        "reject_heard_content",
        "select_category",
        "select_candidate",
        "none_of_these",
        "final_confirm",
        "edit_completion",
        "go_back",
        "cancel_expression",
        "stop",
        "switch_input_method",
        "request_help"
    ]
    session_id: str
    payload: dict
    confirmation_method: str | None
```

## AuthorizedExpression

```python
class AuthorizedExpression(BaseModel):
    session_id: str
    patient_id: str
    final_text: str
    language: str
    voice_profile_id: str
    authorization_scope: Literal["this_expression"]
    confirmation_method: str
    authorized_at: datetime
```

个人 TTS 接口只接受该类型。

## RuntimeEvent

```python
class RuntimeEvent(BaseModel):
    event_id: str
    event_type: str
    session_id: str
    patient_id: str
    timestamp: datetime
    payload: dict
```

## SessionViewModel

```python
class SessionViewModel(BaseModel):
    session_id: str
    stage: SessionStage
    headline: str
    heard_stable: list[str]
    heard_uncertain: list[str]
    clarification_question: str | None
    clarification_options: list[str]
    candidates: list[ExpressionCandidate]
    allowed_actions: list[str]
    trace_items: list[dict]
    personal_voice_status: Literal[
        "blocked", "awaiting_confirmation",
        "authorized", "used"
    ]
```

## ExpressionReceipt

```python
class ExpressionReceipt(BaseModel):
    receipt_id: str
    session_id: str
    patient_id: str
    patient_supported_content: list[str]
    ai_added_content: list[str]
    memory_ids_used: list[str]
    expression_level: Literal["L1", "L2", "L3"]
    selected_candidate_id: str
    patient_confirmed: bool
    confirmation_method: str
    voice_profile_id: str | None
    authorization_scope: str | None
    output_channel: str
    audio_input_hash: str
    final_text_hash: str
    created_at: datetime
    signature: str | None
```

## Gateway endpoints

```text
POST /v1/asr/primary
POST /v1/asr/secondary
POST /v1/intent/propose
POST /v1/tts/synthesize
GET  /v1/health
```

Memory 默认本地。若暴露接口：

```text
POST /v1/memory/search
POST /v1/memory/write-verified
```

必须 enforce patient scope 和 authorization。

## Profile evolution

不增加独立的 Profile Update 确认接口。已有 session command 同时提供反馈：

```text
final_confirm / confirm_neutral_playback → positive feedback
reject_current_candidate / none_of_these / edit_completion → negative feedback
```

响应中的 `dynamic_memory.feedback_status` 表示后台反馈是否成功，
`requires_extra_confirmation` 固定为 `false`。服务端把反馈聚合为
`ExpressionMapping(input_text, intent_text, embedding, confidence,
positive_count, negative_count)`；写入按 session、profile ref 和 patient /
profile id 限定并幂等。
