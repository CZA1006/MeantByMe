# 04｜Agent Runtime 与 Workflow

## Why a domain runtime

通用 Agent 通常：

```text
goal → plan → tool → observe → continue
```

MeantByMe 必须：

```text
evidence → propose → stop → patient confirms → authorize → act
```

核心能力不是“自主执行”，而是“在关键节点可靠停止”。

## Runtime responsibilities

- 表达会话状态；
-模型服务编排；
-不确定性路由；
-Memory 检索；
-候选生成和重排；
-渐进式澄清；
-患者命令处理；
-声音授权；
-Verified Memory 写入资格；
-事件和 Receipt。

LLM 不负责选择候选、跳过确认、授权声音、写 Gold Memory 或解释无反应。

## State machine

```text
READY
→ CAPTURING
→ AUDIO_CAPTURED
→ TRANSCRIBING
→ EVIDENCE_EXTRACTED
→ MEMORY_RETRIEVING
→ HEARD_CONTENT_REVIEW
→ UNCERTAINTY_ASSESSED
   ├─ LOW → FINAL_REVIEW
   ├─ MEDIUM → CANDIDATE_SELECTION
   └─ HIGH → CATEGORY_CLARIFICATION
→ FINAL_REVIEW
→ PATIENT_CONFIRMED
→ VOICE_AUTHORIZED
→ SPOKEN
→ MEMORY_UPDATED
→ COMPLETED
```

> **状态 vs 事件(见 [DECISIONS.md](../DECISIONS.md) D1):** 写记忆的**状态**为 `MEMORY_UPDATED`(与 [13_API_SCHEMAS.md](13_API_SCHEMAS.md) 的 `SessionStage` 一致);`VERIFIED_MEMORY_WRITTEN` 仅作 `RuntimeEvent.event_type`。状态名与事件名分属两套命名空间,禁止复用。

Global commands:

```text
STOP
CANCEL
GO_BACK
SWITCH_INPUT_METHOD
REQUEST_HELP
```

## Expression levels

### L1 — Direct expression

输入基本完整。若系统改写文本，仍需最终 review。

### L2 — AI-assisted completion

患者片段 + AI 补全。个人声音前必须显式最终确认。

### L3 — Agent suggestion

主动建议，不能默认使用患者声音，需更严格确认。

## Invariants

```python
assert not personal_voice_used_without_confirmation
assert not gold_memory_written_without_confirmation
assert silence_is_not_consent
assert caregiver_context_is_not_patient_confirmation
assert rejected_candidate_is_not_preference
assert llm_cannot_change_authorization_state
```

## Commands

```text
START_CAPTURE
STOP_CAPTURE
CONFIRM_HEARD_CONTENT
REJECT_HEARD_CONTENT
SELECT_CATEGORY
SELECT_CANDIDATE
NONE_OF_THESE
FINAL_CONFIRM
EDIT_COMPLETION
GO_BACK
STOP
SWITCH_INPUT_METHOD
REQUEST_HELP
```

只有 Runtime command handler 可改变 session 状态。

## Uncertainty routing

不要显示伪精确概率，使用 evidence bands。

### Low uncertainty

ASR 基本一致、句子核心完整、无关键槽位缺失。进入最终句确认。

### Medium uncertainty

存在稳定意图片段，但缺一个关键槽位或 ASR 冲突。展示 2–3 个候选。

### High uncertainty

ASR 严重冲突、只剩少量词、候选跨主题。先问类别或切换 AAC 输入。

## Clarification design

每个问题：

1. 只问一个维度；
2. 至少排除一个候选；
3. 不诱导；
4. 不增加新决定；
5. 只需一个简单动作；
6. 保留已确认内容。

## Candidate contract

```json
{
  "certain_content": [],
  "uncertain_content": [],
  "candidates": [
    {
      "text": "",
      "patient_supported_spans": [],
      "ai_added_spans": [],
      "memory_support_ids": [],
      "risk_level": "ordinary"
    }
  ],
  "clarification_question": null,
  "requires_confirmation": true
}
```

LLM 输出不包含 `speak_now`、`voice_authorized` 或 `write_memory`。

## Candidate ranker

```text
score =
audio support
+ ASR agreement
+ verified semantic memory
+ acoustic phrase match
+ context
+ frequency
+ recency
- unsupported completion
- risk penalty
```

分数是排序启发式，不是概率。

## Authorization

Personal TTS 只接受 `AuthorizedExpression` 类型，而不是普通字符串。

```python
def can_use_personal_voice(session) -> bool:
    return (
        session.patient_confirmed
        and session.stage == "voice_authorized"
        and session.authorization_scope == "this_expression"
    )
```

## Memory writeback

仅在患者确认、完成输出或明确保存且通过幂等检查后写入。

幂等键：

```text
session_id + expression_hash + update_type
```

## Runtime events

```text
SESSION_STARTED
AUDIO_CAPTURED
ASR_RESULT_RECEIVED
EVIDENCE_EXTRACTED
MEMORY_RETRIEVED
UNCERTAINTY_ASSESSED
CLARIFICATION_REQUESTED
CANDIDATES_GENERATED
CANDIDATES_RERANKED
PATIENT_SELECTION_RECEIVED
FINAL_CONFIRMATION_RECEIVED
VOICE_AUTHORIZATION_GRANTED
VOICE_AUTHORIZATION_BLOCKED
EXPRESSION_SPOKEN
VERIFIED_MEMORY_WRITTEN
SESSION_COMPLETED
```

这些事件驱动 UI Trace、调试、持久化、评测和 Receipt。
