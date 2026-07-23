# AGENTS.md

Instructions for Claude Code, Codex, and other coding agents working in this repository.

## Product identity

MeantByMe is a **consent-first communication agent**. It helps a patient complete an expression but must never convert an AI guess into the patient’s authorized speech without explicit confirmation.

It is not:

- a medical diagnosis system;
- a treatment decision system;
- a mind-reading system;
- a generic autonomous voice assistant;
- a chatbot that may speak on behalf of the patient without consent.

## Non-negotiable invariants

1. No unconfirmed candidate may use the patient’s personal voice.
2. No AI-generated suggestion may be written into verified patient memory without explicit patient confirmation.
3. Silence, timeout, no response, caregiver action, model confidence, or earbud presence are never consent.
4. The LLM may propose candidates but may not grant voice authorization.
5. The LLM may not directly write Gold memory.
6. Rejected candidates must not become patient preferences.
7. Caregiver context remains distinguishable from patient-confirmed intent.
8. High-risk medical, legal, financial, or relationship expressions require stricter confirmation.
9. Every expression must be traceable to evidence, AI completion, confirmation method, and authorization state.
10. Stop, Back, None of these, and Switch input method must remain available.

## Architecture rule

Use a **deterministic shell around probabilistic services**.

```text
PySide6 UI
→ MeantByMe Runtime
→ state machine and policies
→ provider interfaces
→ ASR / LLM / TTS / embedding adapters
```

Models sit behind adapters. Core modules must not import provider-specific SDKs.

## Dependency direction

Allowed:

```text
UI → Core Runtime → Provider Protocols → Adapters
Backend → Core Schemas
Tests → Core Runtime and Adapters
```

Forbidden:

```text
Core Runtime → PySide6
Core Runtime → MLX
Core Runtime → StepFun SDK
Core Runtime → viaim SDK
Frontend → direct personal TTS
LLM Adapter → authorization mutation
```

## Coding conventions

- Python 3.11.
- Type hints on public APIs.
- Pydantic models for cross-module data.
- `StrEnum` for state and command values.
- `Protocol` or abstract interfaces for providers.
- Explicit state transitions.
- Structured runtime events for every meaningful step.
- External calls require timeout, cancellation, retry policy, and failure status.
- Provider outputs must be validated before entering the runtime.
- Do not log secrets, raw patient audio, or full personal memory by default.

## Required tests

```text
unconfirmed candidate cannot speak
silence cannot confirm
caregiver cannot authorize patient voice
rejected candidate cannot enter Gold memory
LLM cannot skip final confirmation
high-risk expression follows strict confirmation
memory retrieval never auto-selects a candidate
TTS failure does not mark expression as spoken
cross-patient retrieval is impossible
session retry does not duplicate memory writes
```

## Mock-first policy

Every external integration must have a deterministic mock implementation.

```yaml
mock:
  asr: fixture
  intent: fixture
  tts: cached

cloud:
  asr: viaim
  secondary_asr: remote
  intent: stepfun
  tts: stepaudio

fallback:
  asr: local_whisper
  intent: template_or_local_small_llm
  tts: system_or_cache
```

## Scope control

Do not add during the three-day MVP:

- online fine-tuning;
- autonomous multi-agent planning;
- medical diagnosis;
- automatic disease-stage prediction;
- direct phone call injection;
- unverified earbud touch assumptions;
- cloud vector databases;
- universal macOS binaries;
- large CUDA-first local models on Mac.

## Definition of done

A feature is done only when:

- its state transition is explicit;
- failure behavior is defined;
- the UI can explain it through structured trace;
- it preserves consent and memory rules;
- tests cover success and rejection paths;
- it works in mock mode.
