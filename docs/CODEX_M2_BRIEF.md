# Codex Implementation Brief — Milestone 2: Cloud Adapters (cloud-first)

M2 交给 Codex(桌面 adapter/接线)与 Jiayi(gateway/SDK)的实现规格。核心原则:**用真实云服务替换 mock provider,而不改动 `core/` 一行**。运行时、状态机、策略、domain schema 保持 byte-for-byte 不变。边界见文末 ownership。

依赖:M1 已完成(`develop` @ M1 基线),D1–D17 冻结。

## Goal
Swap the mock providers for real cloud services **without changing `core/`**. M2 adds: desktop cloud adapters, a FastAPI secure gateway, deterministic fallback wrappers, and mode/config switching. Edge (MLX/whisper.cpp) fallback is **out of scope** — it deploys/tests on an M-Mac later.

## Non-negotiable invariants (must survive M2)
- `core/` still imports no provider SDK (the AST isolation test must stay green).
- Cloud adapters implement the **existing** `ASRPort` / `IntentPort` / `TTSPort` Protocols in `core/ports/providers.py`, returning the **existing** `ASRResult` / `IntentProposal` / `TTSResult` domain types. **The runtime is not modified.**
- `IntentProposal` keeps `extra="forbid"` — a cloud LLM response carrying any speak/authorize/write field must fail validation, not be silently accepted.
- Personal TTS still accepts only `AuthorizedExpression`; the desktop app/UI never calls it or the gateway's TTS route directly.
- **Secrets never touch the desktop bundle.** All provider API keys live only in the gateway. Desktop adapters call the gateway over HTTPS/WSS.
- **Patient memory stays local.** Only the minimal per-request retrieval result is sent to the gateway; no bulk memory upload. `patient_id` scoping preserved end-to-end.
- All D1–D17 remain frozen and untouched.

## Architecture (two layers — do not collapse them)
```
Desktop (Nick/Codex)                     Gateway service (Jiayi)
adapters/asr/viaim.py      ──HTTPS──▶    services/gateway (FastAPI)
adapters/intent/stepfun.py               ├── holds viaim/StepFun/StepAudio SDKs + secrets
adapters/tts/stepaudio.py                ├── timeout / retry / rate-limit / redacted logs
  (thin HTTP clients, no SDKs,           └── returns provider payload → desktop maps to domain
   no secrets)
```
Gateway endpoints per `docs/13_API_SCHEMAS.md`: `POST /v1/asr/primary`, `/v1/asr/secondary`, `/v1/intent/propose`, `/v1/tts/synthesize`, `GET /v1/health`.

## Key interface decisions (implement as stated)
1. **Audio flow — keep `transcribe(audio_id: str)` stable.** Capture writes the recorded WAV (16 kHz mono int16 PCM per viaim) into a local `AudioStore` keyed by `audio_id`; the ASR adapter resolves `audio_id` → bytes and posts them to the gateway. The port signature does **not** change, so mock/cloud stay swappable. Do not pass raw bytes through the runtime.
2. **Ports stay synchronous; adapters own resilience.** Each adapter internally applies timeout, bounded retry, and cancellation, and **always returns a validated result or a failure status** — it must never raise into the runtime or block indefinitely.
3. **Intent failure → deterministic template fallback.** Wrap the cloud intent adapter so that on gateway/LLM failure or schema-invalid output it returns a rule-based template `IntentProposal` (per `docs/03` "LLM unavailable → rule-based categories and templates"). The runtime must never crash or hang when StepFun is down. Risk classification stays deterministic (D5).
4. **Streaming partials are deferred.** viaim's WebSocket partial transcripts are a UI nicety; M2 uses batch final transcripts to build `TranscriptEvidence`. Do not let streaming leak into the runtime's evidence contract.

## Per-provider contracts (desktop adapter ↔ gateway)
Send a minimal request; map the gateway JSON back to the domain type; validate every field with Pydantic before it enters the runtime; on any validation failure return the type's failure form.

- **viaim primary ASR** → `POST /v1/asr/primary` `{audio_ref, language_hint, patient_id, session_id}` → `{provider, transcript, language, segments, latency_ms, status, error}` → `ASRResult`. Secondary (Qwen3-ASR remote or StepAudio ASR) via `/v1/asr/secondary`, same shape. Both become the two-element list `transcribe` returns; if secondary unavailable, single-source + reduced-evidence marker.
- **StepFun intent** → `POST /v1/intent/propose` `{evidence, memories(minimal), confirmed_context, language}` → JSON validated into `IntentProposal`. Gateway prompt enforces the candidate contract (`docs/04`): 2–3 distinct candidates, tagged `patient_supported_spans`/`ai_added_spans`, one optional clarification question, `requires_confirmation:true`, **no** speak/authorize/write fields. Desktop-side `extra="forbid"` is the backstop.
- **StepAudio TTS** → `POST /v1/tts/synthesize` `{text, voice_profile_id?, mode: "neutral"|"personal", scope}` → audio bytes + media_type → `TTSResult`. Neutral candidate readback uses a non-personal voice; personal uses the patient voice profile and is only ever called from `synthesize_personal(AuthorizedExpression)`. On failure return `TTSResult(status="failed", ...)`.

## Gateway responsibilities (Jiayi domain)
- Hold all secrets in env / macOS Keychain; `.env.example` placeholders only; secrets never in code, logs, or receipts.
- Per-route timeout, bounded retry with backoff, rate limiting, health check, **redacted logs** (no raw audio, no secrets, no full memory, no high-risk plaintext).
- Enforce `patient_id` scope on every request; accept only the minimal retrieval result, never bulk memory.
- Provider SDKs (viaim/StepFun/StepAudio) live here, translating to the JSON contract above.

## Degradation matrix (must hold)
| Failure | Behavior |
|---|---|
| viaim down | secondary or local fallback / fixture; reduced-evidence trace |
| secondary ASR down | single-source mode |
| StepFun down / invalid JSON | template `IntentProposal` fallback |
| StepAudio down | neutral: system/cache; personal: `TTSResult` failed, **session does not reach SPOKEN** |
| gateway/network down | fall back to mock/fallback mode; deterministic loop still completes |
| memory unavailable | generic candidate mode (already implemented) |

## Config / modes
Extend the existing `--mode` switch: `mock` (unchanged), `cloud` (gateway-backed adapters), `fallback` (local/degraded). Provider selection per `docs/03` runtime modes and `docs/14` config. Wiring happens in `cli.py`/config only — **not** in `core/`.

## Tests & acceptance
- All existing 26 tests stay green; `core/` isolation test stays green.
- New adapter tests use a **stubbed gateway** (local HTTP fake), not live services: success mapping, timeout → failure status, invalid-JSON → failure/fallback, secondary-missing → single-source, intent-down → template fallback, personal-TTS-fail → not SPOKEN.
- A `cloud`-mode golden path against the stubbed gateway completes with **Unauthorized Voice Rate = 0**.
- No change to any D1–D17 authorization/isolation/state-machine code (diff must show `core/` untouched except a possible new `AudioStore` port — flag it if introduced).
- Secrets scan: nothing sensitive in the desktop bundle or repo.

## Ownership & scope
- **Nick/Codex:** desktop adapters (thin HTTP clients), fallback wrappers, `AudioStore`, mode/config wiring, adapter tests against stub gateway.
- **Jiayi:** the FastAPI gateway service, real provider SDK integration, secrets, timeout/retry/rate-limit/redacted logs, deployment.
- **Out of scope for M2:** streaming partials, edge MLX/whisper.cpp (M-Mac), packaging, PySide6 UI (An's track).

Report back with: adapters added, stub-gateway test results, confirmation `core/` is unchanged, and any provider contract field that didn't map cleanly (list it — do not invent).

---

# 落地版补充(2026-07-24,provider 已验证,覆盖上文泛化部分)

Scope 收敛为**软件核心优先**:识别语言 / 识别意图 / 用户交互 / 补全 / 记忆自进化。**音频从麦克风或 WAV 文件进(不接耳机)**;耳机(viaim/Air 2)采音与私密回放**后移给 Jiayi**。**我们自己建一个最小 gateway**(先 localhost,Jiayi 后续加固/部署),持 key。

## 已验证的 provider 栈(2026-07-24 实测全部 200)

- **意图 LLM 主 — StepFun `step-explore`**(已审核通过,实测干净输出)
  - `POST https://api.stepfun.com/v1/messages`,头 `x-api-key: <key>` + `anthropic-version: 2023-06-01` + `content-type: application/json`
  - body:`model: "step-explore"`、`max_tokens`(必填)、`messages`(Anthropic 格式 role user/assistant)、`system`(顶层)、可选 `stream`
  - **禁传 `thinking`**;429 `rate_limited` → 指数退避
- **意图 LLM 备 — OpenAgents `deepseek-4-flash`**
  - `POST https://api-gateway.openagents.org/v1/chat/completions`,头 `Authorization: Bearer <key>`,OpenAI 兼容,输出干净
- **意图 LLM 兜底 — 确定性模板**(D5;LLM 全挂或 JSON 非法时)
- **ASR — StepFun `step-asr`**(中英混,实时+离线)
  - StepFun 标准 `/v1` 面,`Authorization: Bearer <key>`;音频取自 `AudioStore`(mic/文件,16k mono WAV);`stepaudio-2.5-asr` 为备选
- **中性 TTS — StepFun `step-tts-mini`**(官方音色)`POST /v1/audio/create-audio`
- **个人声音克隆 — StepFun**:先 `POST https://api.stepfun.com/v1/audio/voices`(5–10s WAV/MP3 → 返回 `voice id`),再用 `stepaudio-2.5-tts` + 该 voice id 合成;**只从 `synthesize_personal(AuthorizedExpression)` 调**
- ⚠️ **不要用 `step-3.7-flash` 做结构化候选**:它是 reasoning 模型,reasoning token 吃预算、`content` 易空

**两种 auth 并存**:StepFun 标准 `/v1/audio/*` 用 `Bearer`;`step-explore` 的 `/v1/messages` 用 `x-api-key`。gateway 内部封装,adapter 不感知。

## 结构化输出

意图 adapter 请求候选 JSON(2–3 distinct candidates + span 标注 + `requires_confirmation:true`,无 speak/authorize/write 字段),desktop 侧用 `IntentProposal`(`extra="forbid"`)校验;校验失败或超时 → OpenAgents 备用 → 仍失败 → 模板兜底。风险分级仍确定性(D5)。

## Secrets(强制)

- key 只进 gateway `.env`(已 gitignore)或 Zeabur/部署平台环境变量;**永不进 git**(仓库 public),不进日志/receipt/桌面 bundle
- `.env.example` 只放占位符
- key 若在聊天/截图明文出现过,**赛后轮换**

## 验收(在上文基础上)

- `cloud` 模式对**桩 gateway**跑通 golden path(不烧真实额度),Unauthorized Voice Rate = 0
- 一次**真实 smoke**:`step-explore` 出候选 + `step-asr` 转一段文件音频 + `step-tts-mini` 合成中性音,手动跑一遍确认
- `core/` diff 为空(除可能新增 `AudioStore`);安全测试全绿;仓库无 key

其余(不变量、degradation matrix、ownership)沿用上文。
