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
