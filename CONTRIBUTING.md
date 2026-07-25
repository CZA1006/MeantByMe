# Contributing to MeantByMe

Thank you for helping build consent-first communication technology. A change is
acceptable only when it preserves the person's control over meaning, memory,
and voice.

## Before changing code

1. Read [AGENTS.md](AGENTS.md), [DECISIONS.md](DECISIONS.md), and the
   [documentation authority rules](docs/README.md).
2. Start from the latest `main` and use a focused feature branch.
3. Check the [branch audit](docs/BRANCH_AUDIT.md) before reusing code from
   `develop`, `frontend`, or `feature/earPhones`.
4. Do not include secrets, real patient data, raw patient audio, production
   voice profiles, or vendor binaries.

## Required architecture

Keep the dependency direction:

```text
UI → Core Runtime → Provider Protocols → Adapters
Backend → Core Schemas
Tests → Core Runtime and Adapters
```

Provider SDKs and UI frameworks do not belong in `core/`. External calls need
timeouts, cancellation, bounded retry behavior, validation, and explicit
failure states. Every external integration needs a deterministic mock.

## Pull request checklist

- The state transition and failure behavior are explicit.
- Unconfirmed candidates cannot use a personal voice.
- Only explicit patient confirmation can create Gold memory.
- Caregiver and system context retain their provenance.
- Silence, timeout, confidence, and device presence are not consent.
- Rejection does not become a preference.
- High-risk content follows the strict-confirmation path.
- Cross-patient retrieval is impossible.
- Runtime events explain all meaningful steps.
- Success, rejection, retry, and provider-failure paths are tested.
- The mock flow still works.
- Relevant documentation and the decision log are updated.

Run at minimum:

```bash
./.venv/bin/python -m pytest
```

Add targeted type, format, Web, gateway, or device checks when the branch
contains those components.

## Decisions and documentation

`DECISIONS.md` is the canonical decision registry. New decisions receive a new,
unused `D<number>` on `main`. Branch-local experiments use `EXP-<AREA>-<number>`
until accepted. Never reuse a decision ID with different semantics.

Documentation must say whether a capability is implemented on `main`, available
only on another branch, experimental, or planned. Avoid unverified performance
or clinical claims.

## Commit and review scope

Prefer small commits with one purpose. A pull request should identify:

- source and target branches;
- affected safety invariants;
- migrations or API changes;
- tests executed and their environment;
- known limitations and rollback path.

Broad experimental branches should be split into focused pull requests before
integration.
