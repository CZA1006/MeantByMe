# 08｜数据、安全、隐私与授权

## Product boundary

MeantByMe 是沟通辅助原型，不是医疗器械、诊断系统或临床决策系统。
MIT licensing permits software reuse but does not certify the system, grant
rights to patient data or voice identity, or override third-party licenses.

## Data categories

- raw audio；
-ASR transcripts；
-patient-confirmed text；
-AI candidates；
-Memory retrieval；
-caregiver context；
-voice profile IDs；
-confirmation and authorization records；
-session events；
-Expression Receipts。

## Provenance

每条数据必须有：

```text
source
verification level
patient_id
session_id
timestamp
retention policy
allowed use
```

来源：

```text
patient_audio
asr_output
ai_candidate
patient_confirmed
caregiver_context
system_context
```

来源字段是安全边界。Branch-local profile 或 dynamic-memory 实现不得把
`caregiver_context`、`system_context` 或 `ai_candidate` 重新标记为
`patient_confirmed`，也不得通过统一的 `trusted` 标签隐藏来源。

## Consent scopes

分别授权：

- 麦克风采集；
-云 ASR；
-长期保存音频；
-Patient Memory；
-声音克隆；
-个人声音输出；
-未来训练；
-导出；
-与护理者共享。

所有授权可撤销。

Profile import、登录、耳机连接、设备配对和资料信任均不附带 personal voice
authorization。声音同意与本次表达授权是两个独立条件。

## Personal voice

> A cloned voice is not cloned consent.

存在 voice profile 不代表允许使用。

链路：

```text
selected final expression
+ patient final confirmation
+ valid voice consent
+ current-expression scope
→ AuthorizedExpression
→ TTS
```

## Local-first

优先本地保存：

- Patient Profile；
-Verified Memory；
-授权设置；
-表达历史；
-拒绝候选；
-Receipt；
-音频 archive。

云端只接收本次请求所需最小数据。

## Secrets

禁止放入：

- source code；
-frontend bundle；
-public GitHub；
-example config；
-logs；
-Receipt。

使用 gateway 环境变量和必要时 macOS Keychain。`.env.example` 只放占位符。

## Cross-patient isolation

所有 repository API 必须要求 `patient_id`。

禁止未限定患者的 list/search 和全局 embedding search。Cache key 也必须包含患者 scope。

## Retention

### Unverified

临时 session 使用，取消或超时后删除，不用于训练。

### Verified

可见、可编辑、可导出、可删除，保留来源。

### Rejected

可作为“避免重复推荐”的负反馈，但不能成为患者偏好。

## High-risk content

包括治疗、药物、法律、支付、紧急和重大关系决定。

MVP：

- 显示风险；
-完整私密读回；
-显式确认；
-不自动执行外部动作；
-生成完整 Receipt。

## Expression Receipt

```json
{
  "receipt_id": "receipt_...",
  "patient_id": "patient_...",
  "session_id": "session_...",
  "patient_supported_content": ["I", "don't", "tomorrow"],
  "ai_added_content": ["want to go"],
  "memory_ids_used": ["memory_1"],
  "expression_level": "L2",
  "selected_candidate_id": "A",
  "patient_confirmed": true,
  "confirmation_method": "large_button",
  "voice_profile_id": "voice_01",
  "authorization_scope": "this_expression",
  "output_channel": "speaker",
  "audio_input_hash": "sha256:...",
  "final_text_hash": "sha256:...",
  "created_at": "...",
  "signature": "ed25519:..."
}
```

> **注(见 [DECISIONS.md](../DECISIONS.md) D3):** 时间字段统一为 `created_at`(与 [13_API_SCHEMAS.md](13_API_SCHEMAS.md) 一致)。P0 阶段 `signature` 可为 `null`(发不签名 receipt);Ed25519 签名与密钥管理推迟至 P1。

## Logging

记录：

- event type；
-latency；
-provider status；
-error category；
-session state；
-redacted IDs。

不记录：

- raw audio；
-secrets；
-full Memory；
-high-risk expression plain text；
-voice enrollment audio。

## Demo declaration

所有 Demo Patient 数据标记 simulated。禁止暗示真实患者验证、临床准确率、医疗批准或临床级眼动。

Branch test counts only describe automated contract checks. They are not user
study results, clinical evidence, accessibility validation, or production
security certification.
