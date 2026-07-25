# Codex Implementation Brief — Milestone 1

> **Historical brief:** This file records the instructions used to create the
> original deterministic mock slice. The work is complete and the named branch,
> test count, and D1–D16 scope are historical. For current work, use
> [STATUS.md](STATUS.md), [09_DEVELOPMENT_PLAN.md](09_DEVELOPMENT_PLAN.md),
> [../AGENTS.md](../AGENTS.md), and the canonical D1–D21 registry in
> [../DECISIONS.md](../DECISIONS.md). Do not execute the branch or “do not push”
> instructions below as current repository policy.

本文件是交给 Codex 的实现任务规格。它把已冻结的决策([../DECISIONS.md](../DECISIONS.md) D1–D16)和规格文档打包成一份自包含任务,使 Codex 无需重新决策即可落地代码。范围严格限定在**里程碑 1 的 mock 垂直切片**:headless、不涉及 PySide6/云/打包,在 Intel Mac 上即可跑通。

审查者:Nick(agent/runtime owner)。Codex 完成后应对照 D1–D16 与安全不变量审查产出。

---

## Task for Codex

You are implementing **Milestone 1** of the MeantByMe project. Work in the
existing repository root on branch `nick/runtime` (create it from `main` if not
checked out). **Do not push**; leave commits local for review.

### Read first (authoritative — do not re-decide anything they settle)
- `AGENTS.md` — architecture rules, forbidden dependencies, required tests, definition of done
- `DECISIONS.md` — **frozen decisions D1–D16**; every one is binding
- `docs/13_API_SCHEMAS.md` — domain schemas (reconciled by D1/D2/D3/D9)
- `docs/04_AGENT_RUNTIME.md` — state machine, commands, events, candidate contract, authorization gate
- `docs/14_REPO_STRUCTURE.md` — repo layout and the `core/` isolation rule

### Scope — Milestone 1 ONLY: the deterministic mock golden path
Build the vertical slice: **fixture audio → mock ASR evidence → mock memory retrieval → candidate generation → patient confirmation → authorization → cached TTS → verified memory writeback → visible trace**, running entirely in **mock mode, headless, no network**.

**In scope:** `core/domain`, `core/ports`, `core/runtime`, `core/policies`, `core/personalization`, mock adapters (`adapters/asr/mock.py`, `adapters/intent/mock.py`, `adapters/tts/cached.py`, `adapters/storage/sqlite.py`), tests, `pyproject.toml`.

**Explicitly OUT of scope (do NOT build):** PySide6 UI, FastAPI gateway, real viaim/StepFun/StepAudio/whisper adapters, embeddings, packaging, MLX. Leave `ASRPort`/`IntentPort`/`TTSPort` cleanly abstracted so cloud adapters can be added later, but implement only the mocks now.

### Environment
- Use the existing venv: `./.venv/bin/python` (Python 3.11.8). **Do not use bare `pip`/`python3`** (system default is Anaconda 3.7 — wrong). Install deps into `.venv` only.
- Milestone-1 dependencies: `pydantic>=2`, `pytest`. Nothing else.
- This is an Intel x86_64 Mac; everything here must run headless without Apple-Silicon-only packages.

### Hard architectural rules (from AGENTS.md — enforce, don't just follow)
- `core/` MUST NOT import PySide6, mlx, sounddevice, FastAPI, or any provider SDK. Add a test in `tests/safety/` that asserts this.
- Providers sit behind `Protocol` interfaces in `core/ports`. Adapters translate provider payloads → shared schema.
- Only the runtime command handler mutates session state.
- Personal TTS accepts **only** an `AuthorizedExpression` object, never a raw string.
- The frontend/UI layer (not built here) must never be able to call personal TTS or write memory — keep those paths reachable only through the runtime.

### Behavior constraints from frozen decisions (implement exactly)
- **D1:** use the reconciled `SessionStage` enum (includes `UNCERTAINTY_ASSESSED`; write stage is `MEMORY_UPDATED`). State names and event-type names are separate namespaces.
- **D2:** `MemoryType = {semantic, acoustic, context, language, interaction}`; authorization lives in a separate `authorizations` table, not a memory_type.
- **D4:** create the SQLite schema exactly as specified (patients, memories, rejected_candidates, memory_writes, authorizations, sessions, events, receipts). Every table carries `patient_id`. Gold rows require `confirmation_session_id` (enforce with CHECK). Repository methods MUST require `patient_id`; provide no unscoped list/search.
- **D5 + D16:** risk classification gate is deterministic (keyword lexicon in `core/policies/risk.py`); LLM/mocks may only raise severity, never lower it. High-risk sets `strict=true` on FINAL_REVIEW (no new state); risk is evaluated on the selected candidate's final text before minting `AuthorizedExpression`.
- **D8:** idempotency key = `f"{session_id}:{sha256(normalize(final_text))}:{update_type}"`, stored as `memory_writes.idempotency_key` (PK) so retries never double-write.
- **D10:** uncertainty band is computed from `TranscriptEvidence` only, before candidates. HIGH if both ASR failed OR `len(stable_fragments) < 2` OR (core slot missing AND conflicts non-empty). LOW if no conflicts AND no missing_slots AND core slots present. MEDIUM otherwise. Core slot = predicate + (object or time) present in stable_fragments.
- **D11:** strong verified-memory match may downgrade band by one level (HIGH→MEDIUM, MEDIUM→straight to FINAL_REVIEW) but NEVER to auto-select; always reach FINAL_REVIEW for patient confirmation.
- **D12:** `GO_BACK` is linear single-step with the reversibility map in DECISIONS.md; nothing is reversible after `VOICE_AUTHORIZED`/`SPOKEN`.
- **D13:** add a `ConfirmedContext` domain object (`locked_slots: dict[str,str]`, `locked_tokens: list[str]`, `rejected_texts: list[str]`) on the session; pass it as a hard constraint into each candidate-generation round; `NONE_OF_THESE` preserves it and only re-generates the uncertain/AI-added portion.
- **D14:** ranker score is ordering-only. `select_candidate` may originate ONLY from a `PatientCommand`. Add a runtime assertion and a safety test that the ranker can never auto-select, even when top-1 dominates.
- **D15:** two-layer consent. `can_use_personal_voice(session)` returns true only if: patient_confirmed for THIS expression ∧ stage is voice-authorized ∧ a valid, non-revoked long-term voice-clone consent exists in `authorizations`. Revoking the long-term consent must immediately block all subsequent expressions.

### Mock adapter specs
- `adapters/asr/mock.py`: return two `ASRResult`s from a fixture keyed by audio id (e.g. primary `"I don't tomorrow"`, secondary `"I don't want tomorrow"`), with `status="success"`.
- `adapters/intent/mock.py`: return a deterministic `IntentProposal` with 2–3 distinct candidates + ranking_reasons, tagging `patient_supported_spans` vs `ai_added_spans`. Output MUST NOT contain any speak/authorize/write fields.
- `adapters/tts/cached.py`: return a path/bytes of pre-rendered audio for candidates (neutral voice) and for the final `AuthorizedExpression`; on simulated failure, return a failure status and DO NOT let the session reach `SPOKEN`.
- Ship a fixture for the demo profile `david_demo` and the golden-path session (see `docs/02_STORYTELLING_AND_DEMO.md`).

### Required tests (`tests/safety/` unless noted) — from AGENTS.md + docs/11
unconfirmed candidate cannot speak · silence/timeout cannot confirm · caregiver cannot authorize · rejected candidate cannot enter Gold · LLM/mock cannot skip final confirmation · ranker/memory never auto-selects (D14) · TTS failure does not mark SPOKEN · cross-patient retrieval is impossible (D4) · duplicate/retry does not double-write memory (D8) · None-of-these preserves ConfirmedContext (D13) · GO_BACK reverses only reversible state (D12) · high-risk sets strict confirmation (D16) · revoking voice consent blocks personal voice (D15) · `core/` imports no forbidden packages. Plus one integration test in `tests/integration/` running the full mock golden path end-to-end.

### Receipt & writeback ordering
On `SPOKEN` (TTS success): build the `ExpressionReceipt` FIRST (P0: `signature` may be null per D3), THEN perform the idempotent verified-memory write, THEN `COMPLETED`. Emit the runtime events listed in `docs/04_AGENT_RUNTIME.md`.

### Definition of done (per AGENTS.md)
- The mock golden path runs headless: `./.venv/bin/python -m meantbyme --mode mock` (or an equivalent documented entrypoint/script) drives fixture → … → memory write → prints/returns the structured trace.
- `./.venv/bin/python -m pytest` passes, including every safety test above.
- Every state transition is explicit; failure paths defined; runs entirely in mock mode with **Unauthorized Voice Rate = 0**.
- `core/` contains no forbidden imports (enforced by test).
- Conventional commits on `nick/runtime`; do not push.

Report back with: the file tree you created, how to run the app and tests, and any place where a doc/DECISIONS item was ambiguous (list it — do not silently invent a resolution).
