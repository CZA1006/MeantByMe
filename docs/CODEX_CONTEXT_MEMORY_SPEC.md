# Context-Memory — design + Codex spec (D19)

Give the agent a persistent, per-patient, structured **Context-Memory** so it can
accumulate knowledge about a person (routines, people, places, schedule,
preferences) and **auto-recall** it to disambiguate fragments — replacing the
manual `--situation` input. Work on `nick/runtime` (branch off `develop` @ `94bd696`).
**Do not push**; leave local commits for review.

**Read first:** `DECISIONS.md` (D1–D18, esp. D2/D4/D11/D14/D15/D17), `AGENTS.md`,
`docs/05_MEMORY_AND_PERSONALIZATION.md`, `docs/08_SECURITY_AND_CONSENT.md`.

## Current gap (verified 2026-07-24)
Writeback only ever writes `memory_type=SEMANTIC` (engine, cli seed, eval seed).
`memories.context` is a fixed stub `{"source":"confirmed_expression"}`. Retrieval
(`search_verified_memories`) does text token-overlap only and ignores `context`.
`situation` is a per-session field passed to the LLM and then discarded — never
persisted. So the agent does **not** accumulate context about a person; the
"knows he sees the doctor every Sunday" scenario only works via manual input.

## Design (freeze as D19)

### Storage — reuse the `memories` table, `memory_type='context'`
No new table. A context entry is a `memories` row with:
- `memory_type = 'context'`
- `verification_level`: **`silver` for caregiver-provided, `gold` for
  patient-confirmed** (see rules below); never `gold` from AI inference.
- `text`: human-readable rendering used by the LLM + token matching,
  e.g. `"Sees the doctor every Sunday morning."`
- `context` (JSON): structured fields
  ```json
  {"kind": "routine|person|place|activity|schedule|preference",
   "detail": "doctor visit",
   "time_pattern": "weekly:sunday",   // optional, free-form ok
   "source": "caregiver|patient|seed"}
  ```
- `patient_id`, `usage_count`, `last_used_at`, `confirmation_session_id` as usual
  (Gold still requires `confirmation_session_id` per the D4 CHECK).

### Verification / provenance rules (safety — non-negotiable)
- Caregiver-entered context → **Silver**, `source:"caregiver"`. It may inform the
  composed situation and shows in the trace as caregiver-provided, but is **never**
  patient-confirmed intent (invariant 7) and must **never** auto-upgrade to Gold.
- Patient-confirmed context → **Gold** (needs an explicit confirmation; P0 only
  gets Gold context from the seeded demo profile, labeled simulated).
- **No AI-derived Gold context.** The runtime must not write context memories from
  the LLM's own inference. (Context is evidence, not authority — same rule as
  everything else.)
- Cross-patient isolation (D4): all reads/writes scoped by `patient_id`.

### Retrieval — separate context from candidate support
- **Fix (do this even though only SEMANTIC exists today):** make
  `search_verified_memories` filter `memory_type='semantic'` so context rows can
  never leak into candidate ranking.
- Add `search_context_memories(patient_id)` → gold+silver `memory_type='context'`
  rows, Gold before Silver, then recency. (P0: return all; time-pattern boosting
  is P1.)

### Auto-composed situation
- New `core/personalization/context.py::compose_situation(context_memories, *, now, override) -> str | None`:
  - if `override` (manual `--situation`) is set → return it (manual wins);
  - else if there are context memories → render
    `"Today is {now:%A %Y-%m-%d}. Known patient context: " + "; ".join(rendered)`,
    where each item renders its `text` and Silver items are tagged
    `"(caregiver-provided)"`;
  - else → `None`.
  - `now` is passed in (do not call `datetime.now` inside the composer) for
    deterministic tests.
- **Runtime wiring:** in `MEMORY_RETRIEVING`, after semantic retrieval, call
  `search_context_memories`, `compose_situation(..., now=self._now(), override=session.situation)`,
  set `session.situation`, and emit a new event `CONTEXT_RETRIEVED`
  `{count, memory_ids, sources}`. Inject the clock: add a `clock: Callable[[], datetime]`
  to the runtime constructor (default `lambda: datetime.now(UTC)`).
- **Intent flows situation explicitly:** extend `IntentPort.propose` to
  `propose(evidence, memories, confirmed_context, situation: str | None = None)`.
  The runtime passes `session.situation`. Update every adapter
  (`gateway`, `template`, `mock`, `eval/providers`): the gateway sends it; the
  others may ignore it. This replaces the construction-time `situation` on
  `GatewayIntentAdapter` (drop that field, or keep it as a fallback default).

### What stays unchanged
`normalize()` / `tokenize()` / `expression_hash` / idempotency; the confirmation
gate and authorization; semantic writeback; D1–D18. Context memories never
become candidates and never authorize speech.

## Codex implementation

1. **`adapters/storage/sqlite.py`**: `add_context_memory(patient_id, memory)` (validates gold needs confirmation; caregiver rows are silver); `search_context_memories(patient_id)`; and add `AND memory_type='semantic'` to `search_verified_memories`.
2. **`core/ports/repository.py`**: add the two methods to `RepositoryPort`.
3. **`core/personalization/context.py`**: `compose_situation(...)` as above; export it.
4. **`core/domain`**: add `RuntimeEventType.CONTEXT_RETRIEVED`. No new schema field (structured data lives in `MemoryItem.context`).
5. **`core/runtime/engine.py`**: inject `clock`; in `MEMORY_RETRIEVING` retrieve context + compose situation + set it + emit `CONTEXT_RETRIEVED`; pass `session.situation` into `intent.propose(...)`.
6. **`core/ports/providers.py` + all intent adapters**: extend `propose` signature with `situation`.
7. **`demo/profiles/david_demo.json`**: add 2–3 seeded **Gold** context memories (e.g. routine "Sees the doctor every Sunday morning" `time_pattern:"weekly:sunday"`; person "Daughter Mia visits on weekends") and 1 **Silver** caregiver-provided example. Wire seeding in `cli._seed_demo_repository`.
8. **CLI**: keep `--situation` as the manual override.

## Add decision D19 to `DECISIONS.md`
Summarize: context stored as `memory_type='context'` with structured `context`
JSON; caregiver=Silver / patient=Gold / no AI-Gold; retrieval separated from
candidate support; auto-composed situation via `compose_situation`; situation
passed explicitly through `IntentPort.propose`. Add change-record row + summary
table row.

## Tests
- Context stored/retrieved scoped by `patient_id`; cross-patient raises (D4).
- Caregiver context is Silver and never auto-Gold; Gold context requires `confirmation_session_id`.
- `search_verified_memories` no longer returns `context` rows (no candidate pollution).
- `compose_situation`: override wins; Silver items tagged caregiver-provided; empty → None; deterministic given a fixed `now`.
- Runtime emits `CONTEXT_RETRIEVED` and sets `session.situation`; a session with seeded context and **no** manual `--situation` still produces a non-empty situation.
- Context memories never appear as candidates and never authorize; `expression_hash` for an existing English string is unchanged.
- All existing tests green (65 + new); `core/` AST isolation green; mock eval hard gates pass.

**Report back:** files changed, an example auto-composed `situation` from seeded
context (no manual input), confirmation caregiver context is Silver-only and
`expression_hash` is unchanged, and the mock eval aggregate.
