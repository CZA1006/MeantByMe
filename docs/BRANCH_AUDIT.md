# Branch and code audit

Audit date: **2026-07-26**

This audit compares every active remote branch visible at the audit date. It
records implementation facts without treating branch-local decisions as
canonical.

## Branch inventory

| Remote branch | Commit | Relative to `main` | Audit result |
|---|---|---:|---|
| `main` | `c405350` | — | Canonical mock baseline and project hub |
| `develop` | `3255d7d` | 38 branch-only / 5 main-only commits | Integrated runtime, gateway, Web and evaluation prototype |
| `frontend` | `3255d7d` | same as `develop` | Exact alias; no independent frontend history |
| `feature/earPhones` | `23644de` | 41 branch-only / 5 main-only commits | Broad experimental fork with iOS and server changes |
| `nick/runtime` | `785fa6c` | intermediate ancestor | Runtime integration history |
| `nick/web-demo` | `27287c8` | intermediate ancestor | Web demo history |
| `nick/audio-input-safety` | `fb8dc90` | intermediate ancestor | Input-safety history |
| `nick/profile-bundle-routing` | `fc8279e` | intermediate ancestor | Profile-bundle history |
| `an/frontend` | `3b495bc` | behind `main` | Initial documentation/specification only |
| `jiayi/backend` | `3b495bc` | behind `main` | Initial documentation/specification only |

## `develop` / `frontend`

These two branch names point to the same commit. The snapshot contains:

- the deterministic core runtime and provider protocols;
- mock, gateway, template, cached-TTS, audio, profile, and SQLite adapters;
- a FastAPI gateway for health, ASR, intent, TTS, and voice enrollment;
- a server-side Web BFF/demo that keeps gateway tokens and voice authority out
  of the browser;
- responsive Web assets and the shared brand system;
- evaluation tooling and 142 passing tests.

Because frontend and backend changes share one snapshot, future work should use
component-scoped pull requests rather than trying to merge both branch names.

## `feature/earPhones`

Compared with `develop`, this branch changes 121 files with approximately
11,718 insertions and 6,609 deletions. It includes:

- an iOS 15 Swift client generated with XcodeGen;
- 16 kHz PCM capture and Viaim headset integration;
- private headset readback and public iPhone-speaker routing;
- explicit command confirmation and strict high-risk confirmation paths;
- command and QA adapters/runtimes;
- MySQL-backed profile storage and dynamic expression memory;
- additional gateway and Web BFF endpoints;
- 172 passing Python tests.

This is not a narrow mobile deployment patch. It must be decomposed into at
least: iOS client, headset adapter/protocol, command interpretation, QA
experiment, profile storage, and memory behavior.

The iOS project depends on a local vendor Viaim Swift package that is not
included in the repository. Signed arm64 device validation and a documented
fallback path are still required.

## Decision conflict

`develop` uses D21 for bounded context-grounding weights while preserving
Gold-over-Silver provenance. `feature/earPhones` reuses D21 for a different
proposal that makes historic Gold and Silver equal and removes the need to
distinguish patient and caregiver roles.

The mobile proposal conflicts with:

- the invariant that caregiver context remains distinguishable from
  patient-confirmed intent;
- the rule that only explicit patient confirmation creates Gold memory;
- D17, D19, and D20 provenance rules;
- the decision-ID uniqueness requirement.

Therefore:

- the `develop` meaning of D21 remains the canonical integration candidate;
- the mobile proposal is renamed conceptually to `EXP-MEM-01`;
- `EXP-MEM-01` is rejected in its current form and must not be merged;
- useful dynamic-memory mechanics may be reconsidered only with patient scope,
  source provenance, explicit confirmation, idempotency, and authorization
  separation preserved.

## Additional merge risks

- The mobile fork deletes Web brand assets present on `develop`.
- Some evaluation and semantic implementation files differ or disappear.
- MySQL introduces operational and migration requirements beyond the canonical
  local SQLite baseline.
- QA mode must remain clearly separate from authorized patient speech.
- Branch documentation contains stale test counts and overlapping decision IDs.

## Recommended integration order

1. Keep `main` canonical and land governance/documentation first.
2. Rebase one integration branch from `main`; retire the duplicate
   `frontend` pointer.
3. Integrate the deterministic runtime, evaluation, gateway, and Web BFF in
   reviewable pull requests with safety tests.
4. Rebase the iOS work onto the accepted schemas and gateway contract.
5. Selectively port headset and device code; do not merge the full mobile fork.
6. Run Python, Web, gateway, simulator, signed-device, and failure-path gates.
7. Update status, decisions, changelog, and release artifacts at each landing.
