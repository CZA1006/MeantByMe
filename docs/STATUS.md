# Project Status — done / not done

Living progress tracker. Legend: ✅ done · 🟡 partial · ⬜ not started · ⏸️ deferred.
Last updated: 2026-07-24. Branch of record: `develop` (= `nick/runtime`).

## Infrastructure & process
- ✅ Git repo + remote + branch model (`main` / `develop` / `nick/runtime` / `jiayi/backend` / `an/frontend`)
- ✅ Python 3.11.8 `.venv` (isolated from system Anaconda)
- ✅ `pyproject.toml`, `.gitignore`, `.env` (git-ignored) / `.env.example` (placeholders)
- ✅ Frozen decisions **D1–D20** ([DECISIONS.md](../DECISIONS.md))
- ✅ Secrets policy enforced (no keys in tracked files; verified by scans)

## Core runtime — Milestone 1 (deterministic shell) ✅
- ✅ Domain schemas (Pydantic, `StrEnum`, `frozen`/`extra=forbid`)
- ✅ State machine (whitelisted transitions) + command handler
- ✅ Uncertainty router (D10) + memory band downgrade (D11)
- ✅ Progressive clarification, `None of these`, partial correction via `ConfirmedContext` (D13)
- ✅ Candidate ranker — Gold > Silver weighting (D14/D17), never auto-selects
- ✅ Authorization policy — two-layer consent (D15), `AuthorizedExpression` type-gate
- ✅ Risk gate deterministic (D5) + high-risk strict confirmation (D16); **bilingual** — CJK high-risk lexicon (医生/治疗/药物/自杀/转账/合同/律师… ) + emergency codes (110/120), still raise-only
- ✅ Single-source ASR routing: rich single-ASR evidence routes to MEDIUM (candidates) instead of forcing a generic category question — still requires confirmation, never auto-selects
- ✅ Expression Receipt + verified-memory writeback (idempotent, D8)
- ✅ Runtime event trace
- ✅ SQLite storage with safety constraints (D4): patient-scoped, Gold CHECK, cross-patient blocked
- ✅ Mock adapters (ASR / intent / cached TTS) + demo profile + fixtures
- ✅ Safety test suite (unconfirmed-can't-speak, silence-can't-confirm, caregiver-can't-authorize, cross-patient-blocked, no-double-write, TTS-fail≠spoken, core-no-forbidden-imports, …)

## Cloud integration — Milestone 2 (self-hosted gateway) ✅
- ✅ FastAPI gateway (`services/gateway`) holding secrets, timeout/retry/backoff, redacted logs
- ✅ Desktop gateway adapters (thin HTTP clients) behind provider-independent ports
- ✅ `AudioStore` (mic / WAV file → 16 kHz mono), no earbud dependency
- ✅ **Real StepFun Step Plan stack verified live (free ¥199 credit):**
  - ✅ ASR — `stepaudio-2.5-asr` via `/audio/asr/sse` (SSE, base64 PCM)
  - ✅ Intent + completion — `step-explore` via `/messages`
  - ✅ TTS — `stepaudio-2.5-tts` via `/audio/speech` (official voice)
- ✅ **Situational context** threaded end-to-end; persistent Context-Memory auto-recall added in D19
- ✅ Deterministic template fallback when the LLM fails; graceful degradation
- ✅ Stub-gateway tests for mapping + failure paths; manual `scripts/smoke_cloud.py`
- 🟡 OpenAgents fallback wired but its demo endpoint is too slow for candidate JSON (kept as fallback only)

## Memory & personalization ✅
- ✅ Gold / Silver / Unverified tiers; patient-scoped retrieval
- ✅ Retrieval → ranking influence (Gold-match floats correct candidate to #1) — verified live
- ✅ Writeback increments usage_count (self-evolution) — verified live (usage 2→3)
- ✅ Rejected candidates as negative feedback, never preferences
- ✅ Structured Context-Memory stored per patient; Gold patient/seed context and caregiver Silver remain distinguishable
- ⬜ Local embeddings / phonetic search (P1) — currently keyword/token overlap
- ⬜ Acoustic phrase prototypes / voice-stage weighting (P1)

## Voice output
- ✅ Neutral + personal TTS via gateway (official voice)
- 🟡 **Personal voice cloning** — flag-gated (`ENABLE_VOICE_CLONING`); the file-upload step needs standard-account balance (~¥49 top-up). Demo uses an official voice; auth safety identical either way.

## Model backend / sponsors ✅
- ✅ StepFun Step Plan (free ¥199) covers ASR + intent + TTS; keys in `.env`
- ✅ OpenAgents key (fallback); billing/base-URL fully mapped ([MODEL_BACKEND_PLAN.md](MODEL_BACKEND_PLAN.md))
- ✅ Zeabur gateway deployed and health-checked at `meantbyme.zeabur.app`
- ⏸️ HyperAI GPU claimed but not used (self-deploy ASR/LLM not currently needed)

## Frontend
- ✅ Browser interaction demo (`services/web_demo`) with a server-side Runtime/BFF boundary
- ✅ Heard-content review, candidates, None of these, Back, final private readback, explicit confirmation, authorized audio, Receipt
- ✅ Visible Memory & Decision Trace with patient-supported vs AI-added provenance
- 🟡 Web accessibility baseline: large targets, keyboard reachability, reduced motion, responsive mobile layout; scanning and adjustable timeouts remain P1
- ⬜ Production web identity, encrypted cloud memory consent, durable patient store
- ⬜ PySide6 patient UI (large buttons, one-decision screens)
- ⬜ QThread worker model (D7)

## Backend / deploy (Jiayi's track)
- ✅ Gateway deployed to Zeabur with caller token, rate limit, env secrets, and public health route
- ✅ Dedicated Web Demo BFF/service entry (`Dockerfile.meantbyme-demo`)
- ✅ Web Demo deployed as a second Zeabur service at `meantbyme-demo.zeabur.app`
- ✅ Structured simulated profile bundles, no-profile control, process-local
  Markdown upload, relevant Context-Memory Top-5, and same-audio A/B rerun (D20)
- ⏸️ iFLYBUDS Air 2 / viaim earbud capture + private playback
- ⬜ Remote persistence / backup, production reliability

## Evaluation & testing
- ✅ pytest: **120 passing** (unit / safety / integration / gateway / web demo / eval); mock+fallback golden paths green, UAR 0
- ✅ **Live public deployment verified (2026-07-24):** gateway `meantbyme.zeabur.app` (health 200, auth-gated — no/wrong token → 401, correct token → real `step-explore` candidates with situation+memory disambiguation) and web demo `meantbyme-demo.zeabur.app` (cloud mode, access-gated — session create without `WEB_DEMO_TOKEN` → 401)
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

### 🌐 Live deployment — verified + region latency limitation (2026-07-25)
Both public services verified end-to-end: `meantbyme.zeabur.app` (gateway: auth-gated
ASR/intent/TTS) and `meantbyme-demo.zeabur.app` (web demo: session → audio → **ASR
success** → fragments → heard-content review, cloud mode, access-gated). Real
disambiguation confirmed on the Lin Yue persona (17 verified context memories;
2 `unverified`/`prompt_eligible:false` fixtures correctly excluded from the LLM):
`step-explore` recognized fragmented "mean by me" as her project **MeantByMe** and
completed the pitch, offering distinct candidates + a clarification question.

**Limitation:** the Zeabur server is in Santa Clara (US) while StepFun is in China,
so uploading the base64 PCM payload is slow and scales with audio length —
~5.5s round-trip for a 1s clip, ~37s for a 15.5s clip. Mitigations applied:
gateway `PROVIDER_TIMEOUT_SECONDS=90`/`ROUTE_TIMEOUT_SECONDS=100`,
`WEB_DEMO_MAX_AUDIO_SECONDS=8`. Demo with short fragmented utterances (2–4s, the
real product input) → ~9–11s. Root fix (post-hackathon): host the gateway in an
Asia region near StepFun. Not a logic defect — deployment/region only.

### Other
- ✅ Persistent structured Context-Memory auto-recall (D19); `--situation` remains an explicit override
- ⬜ Ed25519 receipt signing (D3 — P0 ships unsigned)
- ⬜ `audioop` deprecation (removed in Python 3.13) — revisit before any 3.13 upgrade
- ⬜ Real end-to-end demo dataset + backup demo video
