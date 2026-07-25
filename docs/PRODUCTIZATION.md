# Productization — architecture, platform strategy, and dev handoff

For product, backend, and frontend developers. Describes how to take the
verified MeantByMe core (runtime + model gateway) from the hackathon MVP to a
multi-platform product (web / mobile / desktop). Branch of record: `develop`
(`c500d29`).

## 0. What is already built and stable (build ON this, don't rebuild)
- **Deterministic runtime** (`src/meantbyme/core/`): state machine, uncertainty
  routing, progressive clarification, ranker, authorization, risk gate, memory
  writeback, Expression Receipt, event trace. Provider- and platform-independent.
  Enforces D1–D19 safety invariants via types + DB constraints + tests (73 green).
- **Model gateway** (`services/gateway/`): FastAPI proxy to StepFun **Step Plan**
  (free): ASR `stepaudio-2.5-asr` (SSE), intent `step-explore`, TTS
  `stepaudio-2.5-tts`. Holds secrets. Verified live.
- **Patient store**: SQLite, patient-scoped, safety-constrained (D4). Semantic +
  structured Context-Memory (D19), self-evolving usage counts.
- **The runtime's contract IS the product API** — see §4/§5. Any client renders a
  `SessionViewModel` and sends `PatientCommand`; the core never changes per platform.

## 1. The one decision that shapes everything: where do runtime + patient memory live?
Today (MVP) the runtime and SQLite memory run **in-process with the desktop app**
(local-first — memory never leaves the device; this is the original consent
promise). To reach web + mobile + cross-device, choose:

| Option | Runtime + memory | Platforms | Consent/privacy | Effort |
|---|---|---|---|---|
| **A. Thick native clients** | on each device | desktop, native mobile (not web) | strongest (local-first) | high per-platform; hard cross-device sync |
| **B. Backend runtime service** | server-side, per-patient | web + mobile + desktop | memory leaves device → needs encryption + explicit "cloud memory" consent | medium (one service, thin clients) |
| **C. Hybrid** | on-device memory + encrypted backend sync | all | strong, complex | high |

**Recommendation: Option B**, because (a) it's the only path to a web app +
mobile + cross-device, (b) the runtime is already multi-tenant-safe (every
repository call is `patient_id`-scoped, D4), and (c) thin clients keep the
safety logic in one audited place. **This changes the "memory stays on the
device" promise into "memory stays in the patient's encrypted account"** — that
must become an explicit, revocable consent scope (see §6). If the product must
keep hard local-first, use Option A for desktop and postpone web/mobile.

## 2. Target architecture (Option B)
```
Thin clients:  Web (React)  ·  Mobile (React Native / Flutter)  ·  Desktop (Tauri)
      │  HTTPS (commands, view-model)  +  WebSocket (event/trace stream)
      ▼
┌─────────────────────────────────────────────────────────────┐
│ Session API   (NEW — thin wrapper over the existing runtime)  │
│  auth (per-patient) · session lifecycle · streams view-model  │
│  + trace events · rate-limit · audit log                      │
└───────────────┬───────────────────────────┬──────────────────┘
                ▼                            ▼
   Runtime (existing core, UNCHANGED)   Patient store (SQLite→Postgres,
   + policies + memory logic            per-patient, encrypted at rest)
                │
                ▼
   Model Gateway (existing) ──► StepFun Step Plan (ASR / intent / TTS)
```
The **only new backend component is the Session API** — it maps 1:1 onto the
runtime's existing commands / view-model / events. The runtime core is reused
as a library. The gateway and store are the existing components, hardened.

## 3. Platform strategy (recommendation)
- **Product target: Web app (React) first.** Reaches every device with no
  install, easiest to demo/distribute, and the accessibility model (large
  targets, keyboard, scanning, adjustable timeouts) is fully doable in a browser.
  Audio capture via `MediaRecorder`/WebAudio; private playback via headphones.
- **Desktop**: wrap the same web app in **Tauri** (small, native audio/keychain)
  if a native private-audio path or offline mode is needed. (The original PySide6
  plan also works for a local-first desktop-only product — Option A.)
- **Mobile**: React Native or Flutter thin client against the same Session API —
  attractive (always with the patient) but adds native audio + accessibility +
  app-store effort; do it after web.
- **Hackathon note:** if the goal is the demo, the lowest-risk path is to finish
  the already-specced **PySide6 desktop thin client** (Option A, no re-architecture).
  Web + Session API is the post-hackathon product path.

## 4. Frontend developer contract
The client is a **thin renderer**. It never contains agent logic.

**Render** the `SessionViewModel` (`core/domain`): `stage`, `headline`,
`heard_stable` / `heard_uncertain`, `clarification_question` /
`clarification_options`, `candidates` (each with `text`,
`patient_supported_spans`, `ai_added_spans`, `memory_support_ids`,
`ranking_reasons`, `risk_level`), `allowed_actions`, `trace_items`,
`personal_voice_status` (`blocked` / `awaiting_confirmation` / `authorized` / `used`).

**Send** a `PatientCommand`: `start_capture`, `stop_capture`,
`confirm_heard_content`, `reject_heard_content`, `select_category`,
`select_candidate`, `none_of_these`, `final_confirm`, `edit_completion`,
`go_back`, `cancel_expression`, `stop`, `switch_input_method`,
`request_help` — with
`confirmation_method` and payload. **Only render buttons in `allowed_actions`.**

**UI must-NOTs (enforced by architecture; do not work around):**
- Never call personal TTS or the gateway TTS route directly — audio comes from the
  server after authorization.
- Never infer the next state; the server returns the next `SessionViewModel`.
- Never auto-select a candidate or auto-confirm on timeout/silence.
- Always keep **Stop / Back / None of these / Switch input** visible and reachable.
- `final_confirm` for high-risk (`strict`) or `L3` candidates must carry the extra
  confirmation flags the server requires (surface the stricter step to the patient).
- Show provenance: user-supported spans vs AI-added spans; inferred profile
  facts remain visibly pending until saved; personal-voice status stays visible.

**Accessibility (required):** large targets, full keyboard reachability, optional
scanning, adjustable timeouts, reduced motion, repeatable playback, no
color-only status.

## 5. Backend developer contract (Session API to build)
Wrap the existing runtime; keep the safety logic server-side. Suggested endpoints
(map onto existing runtime methods):
- `POST /sessions` → create a session for the authenticated patient (server sets
  `patient_id` from auth, seeds/loads their memory, auto-composes `situation` from
  Context-Memory — D19). Returns the initial `SessionViewModel`.
- `POST /sessions/{id}/commands` → apply a `PatientCommand`; returns the new
  `SessionViewModel`. Rejects commands not in `allowed_actions`.
- `GET /sessions/{id}/events` (WebSocket/SSE) → stream `RuntimeEvent`s for the
  Memory & Decision Trace.
- `GET /sessions/{id}/audio/{kind}` → fetch neutral readback / authorized personal
  audio (server-produced; the client never synthesizes).
- Memory/consent management endpoints (list/edit/delete verified memory, manage
  consent scopes) — all `patient_id`-scoped.

**Responsibilities & invariants to preserve:**
- **Identity & isolation:** authenticate the patient; derive `patient_id`
  server-side; never trust a client-supplied `patient_id`. All store access stays
  `patient_id`-scoped (D4). Cross-patient access must be impossible.
- **Store:** migrate SQLite → Postgres (same patient scope, confirmation
  evidence, and idempotent writes). **Encrypt patient memory + audio at rest.**
- **Gateway:** deploy it (see §7) with **caller auth** and rate-limiting; secrets
  only in server env / secret manager; redacted logs (no raw audio, no secrets, no
  high-risk plaintext).
- **Audio:** accept mic capture (upload or stream) as 16 kHz mono; serve private
  playback; never log raw audio.
- Keep the runtime as the single authority for state, authorization, and memory
  writes — the Session API is transport, not logic.

## 6. Consent & privacy re-architecture (required for Option B)
Moving memory server-side changes the promise; make it explicit and revocable:
- Consent scopes (per `docs/08`): mic capture, cloud ASR, **cloud memory storage**,
  voice cloning, personal-voice output, future training, export, profile sharing.
- Explicit profile input is trusted regardless of operator role. Existing
  confirm/reject/edit actions update a confidence-gated expression mapping;
  this learned mapping is not automatically promoted to a stable profile fact
  (D21).
- Right to export and delete verified memory; revoking a consent scope takes
  effect immediately (e.g. revoking voice consent blocks personal voice — already
  enforced by D15).
- Data residency / retention policy documented; unverified/timeout data purged.

## 7. Deployment (gateway) — and the auth gap that blocks public hosting
The gateway is deploy-ready **except it has no caller authentication** — every
route is open. On `localhost` that is fine; **exposed publicly it is an open
proxy to our paid StepFun credit** and must not be deployed as-is.

**Before any public deploy, add a gateway token** (small change): require a
shared `X-Gateway-Token` header (value from env `GATEWAY_TOKEN`) on all `/v1/*`
routes except `/v1/health`; reject with 401 otherwise. Desktop/Session-API
callers send the token. Also add basic per-IP rate limiting.

**Zeabur steps (gateway as a stateless model proxy):**
1. Add a `Dockerfile` (python:3.11-slim, install the package, run
   `uvicorn services.gateway.app:app --host 0.0.0.0 --port 8080`).
2. In Zeabur: new service from the repo; set env vars **in Zeabur's secret store**
   (never in git): `STEPFUN_API_KEY`, `STEPFUN_BASE_URL=https://api.stepfun.com/step_plan/v1`,
   `INTENT_PROVIDER=stepfun`, `INTENT_MODEL=step-explore`, `GATEWAY_TOKEN=<random>`,
   `ENABLE_VOICE_CLONING=false`.
3. Expose the port; verify `GET /v1/health` returns `stepfun_configured: true`.
4. Point clients at the Zeabur URL with the `X-Gateway-Token` header.

Deploy **only the stateless gateway** now. Do **not** put patient memory on
Zeabur until §6 (encryption + cloud-memory consent) is decided and the Session
API exists.

## 8. Recommended sequencing
1. Add gateway caller token + rate-limit (unblocks any public/staging deploy). *(small)*
2. Deploy the gateway to Zeabur (§7) — shared model API off localhost.
3. Decide Option A vs B (§1) — the product-defining call.
4. If B: build the Session API (§5) + migrate store to Postgres + encryption; build the Web thin client (§4).
5. Full cloud eval baseline + demo dataset; then mobile/desktop wrappers.
