# MeantByMe｜意由我

> **Completed with AI. Meant by me.**  
> AI 可以帮助补全表达，但意思必须由本人确认。

MeantByMe is a **patient-bound, consent-first communication agent** for people whose cognition and communicative intent remain relatively clear, but whose speech production is impaired, fragmented, slow, or temporarily unavailable.

## Core principle

> **The Agent may complete the sentence, but it must never decide the meaning.**

MeantByMe treats ASR, language models, patient memory, and context as **evidence rather than authority**. It captures fragmented speech, retrieves verified patient-specific memory, proposes a small number of possible expressions, and speaks in the patient’s authorized voice only after explicit confirmation.

## Hackathon MVP

A native macOS desktop application with:

- iFLYBUDS Air 2 as microphone and private audio output;
- primary and secondary ASR evidence;
- stable / uncertain fragment extraction;
- patient-bound verified memory;
- progressive clarification;
- 2–3 expression candidates plus “None of these”;
- final private readback;
- deterministic personal-voice authorization;
- StepAudio personal TTS;
- Memory & Decision Trace;
- verified memory writeback;
- mock, cloud, and fallback modes.

## Golden path

```text
Fragmented speech
→ ASR evidence
→ stable / uncertain fragments
→ verified patient memory retrieval
→ clarification or candidates
→ patient selection
→ final private readback
→ explicit authorization
→ personal-voice output
→ expression receipt
→ verified memory update
```

## Why this is different

Most voice agents optimize for autonomous completion. MeantByMe optimizes for **safe recovery when the model is wrong**.

The system separates:

- what the patient directly expressed;
- what ASR inferred;
- what AI completed;
- what memory influenced;
- what the patient confirmed;
- what the system was authorized to speak.

## Development environment

The team develops with Claude Code and Codex on:

- two Apple Silicon Macs;
- one Intel Mac.

Heavy models are cloud- or remote-GPU-first. The Mac application owns interaction, state, memory, authorization, trace, and fallback behavior.

## Implementation status

- **Milestone 1 — deterministic mock runtime (done).** Headless vertical slice:
  fixture ASR, verified SQLite memory, deterministic candidates, cached TTS, no
  network. Full state machine + policies + Expression Receipt + memory writeback,
  with the safety invariants (D1–D17) enforced by types, DB constraints, and tests.
- **Milestone 2 — real cloud stack via a self-hosted gateway (done, verified live).**
  A local FastAPI gateway runs the whole probabilistic layer on StepFun **Step Plan**
  free credit: ASR (`stepaudio-2.5-asr`, SSE), intent + completion (`step-explore`),
  neutral/personal TTS (`stepaudio-2.5-tts`). Situational context is threaded into
  candidate generation for memory-based disambiguation. `core/` stays provider- and
  platform-independent; secrets live only in a git-ignored `.env`.
- **Viaim iOS hardware track (implemented, awaiting signed-device test).**
  The native iOS 15 client uses the supplied Viaim SDK for 16 kHz PCM and
  primary text, ends an expression after 8 seconds without speech, performs
  candidate readback only on an active earbud route, and reuses the Web Demo
  BFF/Runtime/Gateway flow. After the private readback, the app records a short
  patient response: natural affirmations such as “是/嗯/没错” confirm, while
  “不是/不对/换一个” rejects the candidate. Two ASR/model interpretations
  must agree before an affirmation can trigger public playback. Public output
  uses only system-neutral audio.

See [docs/STATUS.md](docs/STATUS.md) for the full done / not-done breakdown.

## Running

```bash
# install
./.venv/bin/python -m pip install -e '.[test]'

# tests (mock/stub only — no network, no credits)
./.venv/bin/python -m pytest

# deterministic mock golden path (headless, no network)
./.venv/bin/python -m meantbyme --mode mock

# real cloud path (needs a local .env with StepFun Step Plan key; free credit)
./.venv/bin/python -m services.gateway            # start the gateway (localhost:8000)
./.venv/bin/python -m meantbyme --mode cloud \
    --audio path/to/speech.wav \
    --situation "A friend asked if he wants to go out tomorrow. Tomorrow is Sunday."

# browser interaction demo (mock by default; no network)
./.venv/bin/python -m services.web_demo
# open http://127.0.0.1:8081
```

Modes: `mock` (deterministic fixtures), `cloud` (gateway-backed StepFun), `fallback`
(degraded/local). Every mode ends at `completed` with **Unauthorized Voice Rate = 0**.

The browser demo is a server-side Runtime facade, not a static client that calls
the model gateway directly. See
[services/web_demo/README.md](services/web_demo/README.md) for its security
boundary and Zeabur deployment.

The native headset client is under
[ios/MeantByMeHeadset](ios/MeantByMeHeadset/README.md). Its backend protocol and
deployment boundary are documented in
[docs/VIAIM_IOS_INTEGRATION.md](docs/VIAIM_IOS_INTEGRATION.md).

## Documentation

- [Product vision](docs/01_PRODUCT_VISION.md)
- [Storytelling and demo](docs/02_STORYTELLING_AND_DEMO.md)
- [Technical architecture](docs/03_TECHNICAL_ARCHITECTURE.md)
- [Agent runtime](docs/04_AGENT_RUNTIME.md)
- [Memory and personalization](docs/05_MEMORY_AND_PERSONALIZATION.md)
- [Interaction and accessibility](docs/06_INTERACTION_AND_ACCESSIBILITY.md)
- [Models and integrations](docs/07_MODELS_AND_INTEGRATIONS.md)
- [Security and consent](docs/08_SECURITY_AND_CONSENT.md)
- [Development plan](docs/09_DEVELOPMENT_PLAN.md)
- [Team ownership](docs/10_TEAM_OWNERSHIP.md)
- [Evaluation and testing](docs/11_EVALUATION_AND_TESTING.md)
- [Research references](docs/12_RESEARCH_REFERENCES.md)
- [API schemas](docs/13_API_SCHEMAS.md)
- [Repository structure](docs/14_REPO_STRUCTURE.md)

### Working documents

- [Frozen decisions D1–D19](DECISIONS.md) — the single source of truth for architecture/behavior decisions
- [Project status (done / not done)](docs/STATUS.md)
- [Model backend plan (sponsor coverage + billing)](docs/MODEL_BACKEND_PLAN.md)
- [Milestone 1 brief](docs/CODEX_IMPLEMENTATION_BRIEF.md) · [Milestone 2 brief](docs/CODEX_M2_BRIEF.md) · [Step Plan gateway spec](docs/CODEX_GATEWAY_STEPPLAN_SPEC.md)
- [Evaluation harness spec](docs/EVAL_HARNESS.md)
