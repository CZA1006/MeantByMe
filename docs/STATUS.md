# Current project status

Last verified: **2026-07-26**

## Canonical baseline

`main` is the source of truth for project identity, safety invariants, accepted
decisions, documentation, licensing, and releases. Its code currently provides
a deterministic Python 3.11 mock runtime with patient-scoped SQLite memory,
authorization policies, trace events, cached audio fixtures, and safety tests.

## Implementation tracks

| Branch | Commit audited | Status | Main capability |
|---|---|---|---|
| `main` | `c405350` | canonical baseline before this documentation update | Mock runtime, project hub, docs |
| `develop` | `3255d7d` | integration candidate | Gateway, cloud adapters, Web BFF/demo, evaluation |
| `frontend` | `3255d7d` | alias of `develop` | Same code; not a separate frontend source |
| `feature/earPhones` | `23644de` | experimental fork | iOS/headset, command/QA and profile experiments |
| `an/frontend` | `3b495bc` | historical | Initial specification only |
| `jiayi/backend` | `3b495bc` | historical | Initial specification only |

## Verified checks

Tests were run from isolated Git archives using Python 3.11.8 and
`PYTHONPATH=src:.`.

| Code snapshot | Result |
|---|---:|
| Current `main` baseline | 24 passed |
| `origin/develop` | 142 passed |
| `origin/feature/earPhones` | 172 passed |

The two larger suites emitted deprecation warnings for Python's `audioop` and
Starlette's legacy `httpx` TestClient integration. These do not change the pass
result but should be removed before upgrading the affected dependencies.

Passing tests verify implemented contracts; they do not establish clinical
accuracy, medical-device approval, real-patient validation, or production
security.

## Integration blockers

- `develop` and `frontend` need a single ownership model and branch retirement
  plan.
- The mobile fork mixes iOS, backend, memory, QA, database, and Web changes and
  must be split before review.
- The mobile fork reuses decision ID D21 with incompatible semantics and removes
  patient/caregiver provenance distinctions. That proposal is not accepted.
- The mobile fork removes Web brand assets that exist on `develop`.
- Physical-device, signed arm64, vendor-SDK, and end-to-end personal-voice
  validation remain pending.

See [BRANCH_AUDIT.md](BRANCH_AUDIT.md) for details and
[09_DEVELOPMENT_PLAN.md](09_DEVELOPMENT_PLAN.md) for the integration sequence.
