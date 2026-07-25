# 14｜Repository structure

The repository has a canonical baseline on `main` and additional branch-only
components. This document distinguishes actual layout from integration targets.

## Canonical `main`

```text
MeantByMe/
├── .github/
│   └── pull_request_template.md
├── AGENTS.md
├── CHANGELOG.md
├── CONTRIBUTING.md
├── DECISIONS.md
├── LICENSE
├── README.md
├── SECURITY.md
├── docs/
│   ├── README.md
│   ├── STATUS.md
│   ├── BRANCH_AUDIT.md
│   ├── 01_...14_*.md
│   ├── index.html
│   ├── demo.html
│   └── assets/
├── demo/
│   ├── audio/
│   ├── fixtures/
│   └── profiles/
├── src/meantbyme/
│   ├── core/
│   │   ├── domain/
│   │   ├── personalization/
│   │   ├── policies/
│   │   ├── ports/
│   │   └── runtime/
│   ├── adapters/
│   ├── config/
│   └── cli.py
├── tests/
├── artifacts/
└── pyproject.toml
```

`docs/index.html` is the GitHub Pages resource hub. It links the repository,
demo, business plan, release materials, and project documents; it is not the
consent runtime.

## Branch-only components

`develop` / `frontend` add:

```text
services/
├── gateway/
└── web_demo/

src/meantbyme/eval/
tests/gateway/
tests/web_demo/
```

`feature/earPhones` additionally adds:

```text
ios/MeantByMeHeadset/
├── Config/
├── Sources/
├── project.yml
└── README.md

src/meantbyme/
├── adapters/command/
├── adapters/qa/
└── core/qa/
```

It also changes profile storage and dynamic memory. These are experimental and
must not be inferred as canonical from their path.

## Dependency boundary

Allowed:

```text
UI → Core Runtime → Provider Protocols → Adapters
Backend → Core Schemas
Tests → Core Runtime and Adapters
```

Forbidden:

```text
Core Runtime → PySide6 / SwiftUI / FastAPI
Core Runtime → MLX / Viaim / StepFun SDK
Frontend → direct personal TTS
LLM Adapter → authorization or Gold-memory mutation
```

## Data and fixtures

Only simulated or appropriately licensed fixtures belong in the repository.
Do not commit real patient data, raw patient audio, production personal memory,
voice profiles, secrets, vendor SDKs, or database dumps.

Each external provider needs a deterministic mock. Required fixture paths cover
golden flow, uncertainty, rejection, `None of these`, provider failure, memory
reranking, high risk, and cross-patient isolation.

## Integration target

After staged integration, component boundaries should remain visible:

```text
clients/ or ios/    presentation and device adapters
services/           gateway and server-side BFF
src/meantbyme/core  deterministic domain/runtime/policies/ports
src/meantbyme/adapters
                    provider and storage implementations
tests/              unit, safety, integration, service and device contracts
docs/               canonical design, status and audit trail
```

Do not reorganize paths only for aesthetics; move code when the dependency
boundary and ownership become clearer and tests protect the migration.
