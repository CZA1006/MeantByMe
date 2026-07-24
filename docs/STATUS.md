# Project Status — done / not done

Living progress tracker. Legend: ✅ done · 🟡 partial · ⬜ not started · ⏸️ deferred.
Last updated: 2026-07-24. Branch of record: `develop` (= `nick/runtime`).

## Infrastructure & process
- ✅ Git repo + remote + branch model (`main` / `develop` / `nick/runtime` / `jiayi/backend` / `an/frontend`)
- ✅ Python 3.11.8 `.venv` (isolated from system Anaconda)
- ✅ `pyproject.toml`, `.gitignore`, `.env` (git-ignored) / `.env.example` (placeholders)
- ✅ Frozen decisions **D1–D17** ([DECISIONS.md](../DECISIONS.md))
- ✅ Secrets policy enforced (no keys in tracked files; verified by scans)

## Core runtime — Milestone 1 (deterministic shell) ✅
- ✅ Domain schemas (Pydantic, `StrEnum`, `frozen`/`extra=forbid`)
- ✅ State machine (whitelisted transitions) + command handler
- ✅ Uncertainty router (D10) + memory band downgrade (D11)
- ✅ Progressive clarification, `None of these`, partial correction via `ConfirmedContext` (D13)
- ✅ Candidate ranker — Gold > Silver weighting (D14/D17), never auto-selects
- ✅ Authorization policy — two-layer consent (D15), `AuthorizedExpression` type-gate
- ✅ Risk gate deterministic (D5) + high-risk strict confirmation (D16)
- ✅ Expression Receipt + verified-memory writeback (idempotent, D8)
- ✅ Runtime event trace
- ✅ SQLite storage with safety constraints (D4): patient-scoped, Gold CHECK, cross-patient blocked
- ✅ Mock adapters (ASR / intent / cached TTS) + demo profile + fixtures
- ✅ Safety test suite (unconfirmed-can't-speak, silence-can't-confirm, caregiver-can't-authorize, cross-patient-blocked, no-double-write, TTS-fail≠spoken, core-no-forbidden-imports, …)

## Cloud integration — Milestone 2 (self-hosted gateway) ✅
- ✅ FastAPI gateway (`services/gateway`) holding secrets, timeout/retry/backoff, redacted logs
- ✅ Desktop gateway adapters (thin HTTP clients) behind the existing ports; `core/` unchanged except one optional `situation` field
- ✅ `AudioStore` (mic / WAV file → 16 kHz mono), no earbud dependency
- ✅ **Real StepFun Step Plan stack verified live (free ¥199 credit):**
  - ✅ ASR — `stepaudio-2.5-asr` via `/audio/asr/sse` (SSE, base64 PCM)
  - ✅ Intent + completion — `step-explore` via `/messages`
  - ✅ TTS — `stepaudio-2.5-tts` via `/audio/speech` (official voice)
- ✅ **Situational context** threaded end-to-end → memory-based disambiguation of fragments (verified)
- ✅ Deterministic template fallback when the LLM fails; graceful degradation
- ✅ Stub-gateway tests for mapping + failure paths; manual `scripts/smoke_cloud.py`
- 🟡 OpenAgents fallback wired but its demo endpoint is too slow for candidate JSON (kept as fallback only)

## Memory & personalization ✅
- ✅ Gold / Silver / Unverified tiers; patient-scoped retrieval
- ✅ Retrieval → ranking influence (Gold-match floats correct candidate to #1) — verified live
- ✅ Writeback increments usage_count (self-evolution) — verified live (usage 2→3)
- ✅ Rejected candidates as negative feedback, never preferences
- 🟡 `memory.context` persisted; **situational-context capture is per-session via `--situation`** — no structured Context-Memory store yet
- ⬜ Local embeddings / phonetic search (P1) — currently keyword/token overlap
- ⬜ Acoustic phrase prototypes / voice-stage weighting (P1)

## Voice output
- ✅ Neutral + personal TTS via gateway (official voice)
- 🟡 **Personal voice cloning** — flag-gated (`ENABLE_VOICE_CLONING`); the file-upload step needs standard-account balance (~¥49 top-up). Demo uses an official voice; auth safety identical either way.

## Model backend / sponsors ✅
- ✅ StepFun Step Plan (free ¥199) covers ASR + intent + TTS; keys in `.env`
- ✅ OpenAgents key (fallback); billing/base-URL fully mapped ([MODEL_BACKEND_PLAN.md](MODEL_BACKEND_PLAN.md))
- ⏸️ HyperAI GPU / Zeabur claimed but not yet used (self-deploy ASR/LLM not needed; Zeabur = future gateway host)

## Frontend (An's track) ⬜
- ⬜ PySide6 patient UI (large buttons, one-decision screens)
- ⬜ Memory & Decision Trace view
- ⬜ Candidate cards / final review / Receipt UI
- ⬜ Accessibility (keyboard, scanning, timeouts) + Generic-vs-Personalized toggle
- ⬜ QThread worker model (D7)

## Backend / deploy (Jiayi's track)
- ✅ Gateway built (currently we own it, localhost) — Jiayi to harden/deploy
- ⬜ Gateway deployment to Zeabur (Dockerfile + env secrets)
- ⏸️ iFLYBUDS Air 2 / viaim earbud capture + private playback
- ⬜ Remote persistence / backup, production reliability

## Evaluation & testing
- ✅ pytest: **65 passing** (unit / safety / integration / gateway contracts / eval); mock+fallback golden paths green, UAR 0
- ✅ Eval harness **spec** ([EVAL_HARNESS.md](EVAL_HARNESS.md)) + **implementation** (`src/meantbyme/eval`) with `mock` / `replay` / `cloud` modes, hard gates, high-risk redaction
- ✅ 26-sample EN/ZH dataset with paired situational samples (`demo/eval/dataset.jsonl`)
- ✅ **Live baseline (Step Plan, `step-explore`): Situation Sensitivity = 1.00 (2/2)** — identical fragments + differing `situation` each selected their own expected expression, no cross-contamination, EN and ZH
- ⚠️ **Mock-mode metrics are ~1.0 by construction** (the fixture seeds each sample's own `intended_expression` and ignores evidence/situation). Mock = plumbing regression only; quality claims must come from `cloud` mode. Documented in `src/meantbyme/eval/README.md`.
- ⬜ Full 26-sample **cloud** baseline (needs one WAV per sample; consumes free credit)

## Known follow-ups (backlog)

### ✅ Resolved 2026-07-24 — Chinese (CJK) tokenization gap in `core/`
`core/personalization/text.py::tokenize` splits on whitespace, so a Chinese
sentence becomes **one token**; `core/policies/uncertainty.py` matches against
**English-only** predicate/time/function word sets. Measured 2026-07-24:

| Behaviour | English | Chinese |
|---|---|---|
| `tokenize("我不想明天出门。")` | — | `['我不想明天出门']` (single token) |
| `core_slots_present(...)` | `True` | **`False`** → never reaches LOW band, always an extra clarification round |
| locked-token subset check | passes | **fails** (`{'明天'} ⊄ {'我不想明天出门'}`) |
| memory token-overlap similarity | works | **empty intersection** → `similarity_band` never `high` |

**Impact:** after `CONFIRM_HEARD_CONTENT` locks fragments, `GatewayIntentAdapter._validate_contract`
rejects otherwise-valid Chinese candidates as "dropped confirmed tokens" and the
session **degrades to template fallback**. Memory-based reranking and the D11
band downgrade also never fire for Chinese. Note the LLM itself (`step-explore`)
handles Chinese correctly — the gap is purely in the deterministic core.

**Resolution:** D18 adds language-aware tokenization (CJK → per-character,
Latin → unchanged whole words), tokenizes both sides of locked-token checks,
and uses CJK predicate/time phrase matching for core slots. Matching Chinese
Memory now reaches `similarity_band=high`; complete Chinese evidence can reach
LOW without an unnecessary clarification round. `normalize()` and
`expression_hash()` remain unchanged.

### Other
- ⬜ Add a structured `situation`/Context-Memory capture path (not just per-run `--situation`)
- ⬜ Ed25519 receipt signing (D3 — P0 ships unsigned)
- ⬜ `audioop` deprecation (removed in Python 3.13) — revisit before any 3.13 upgrade
- ⬜ Real end-to-end demo dataset + backup demo video
