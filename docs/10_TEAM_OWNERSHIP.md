# 10｜团队分工与接口契约

早期按人名划分 frontend/backend/runtime 已经与实际代码分支不一致。本项目改用
组件 ownership；具体 reviewer 可由仓库维护者在 GitHub CODEOWNERS 中另行
指定。

## Component ownership

| Area | Owns | Must not own |
|---|---|---|
| Product and consent | Invariants, confirmation language, risk flow, provenance | Provider implementation details |
| Core runtime | Domain schemas, state machine, policies, trace, ports | PySide6, Swift, FastAPI, vendor SDKs |
| Personalization | Patient-scoped retrieval, ranking, writeback, provenance | Authorization or automatic selection |
| Gateway | Provider credentials, validation, timeout, retry, rate limits | Patient consent decisions |
| Web BFF | Session boundary, runtime commands, browser-safe view models | Direct personal TTS or browser secrets |
| Web UI | Accessible presentation and explicit controls | State mutation outside commands |
| iOS/headset | Capture, audio routing, device UX, protocol adapters | Treating device events as consent |
| Evaluation | Fixtures, metrics, audit declarations | Clinical or real-patient claims without evidence |
| Release/docs | Canonical docs, license, Pages, releases, changelog | Silently promoting branch experiments |

## Interface contracts

### UI → Runtime

UI sends a typed `PatientCommand` and displays a `SessionViewModel`. It never
selects a candidate based on rank score, writes verified memory, or invokes
personal TTS directly.

### Runtime → Providers

Runtime depends on `Protocol` interfaces. Adapters validate provider output and
return bounded failures. Providers cannot mutate authorization or memory.

### Runtime → Storage

Every query and write is patient scoped. Gold writes require explicit patient
confirmation and an idempotency key. Rejected candidates remain negative
session evidence, not patient preference.

### Gateway → Cloud

Gateway owns secrets, request validation, timeouts, cancellation, bounded
retries, error mapping and redacted logs. Frontends do not receive provider
credentials.

### Device → Runtime

Headset audio and gestures are input evidence only. Earbud presence, silence,
timeout, volume action, touch, caregiver input, and model confidence never
authorize the patient's voice.

## Review requirements

Changes crossing two or more areas require reviewers for both contracts. The
following always require consent/safety review:

- state transitions and `PatientCommand`;
- memory verification or ranking;
- personal TTS and audio routing;
- high-risk detection or confirmation;
- profile import/export;
- patient identity and storage;
- retry, idempotency, receipt, and audit behavior.

## Branch responsibility

Branches do not confer ownership. `frontend` and `develop` currently point to
the same integrated snapshot; `feature/earPhones` contains changes across nearly
all areas. New work must use component-scoped branches and pull requests.

See [BRANCH_AUDIT.md](BRANCH_AUDIT.md) and
[09_DEVELOPMENT_PLAN.md](09_DEVELOPMENT_PLAN.md).
