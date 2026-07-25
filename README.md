# MeantByMe｜意由我

> **Completed with AI. Meant by me.**  
> AI 可以帮助补全表达，但意思与声音授权必须由本人确认。

MeantByMe is a consent-first communication agent for people whose intent remains
clear while speech is fragmented, slow, impaired, or temporarily unavailable.
It treats ASR, language models, personal memory, and context as evidence—not
authority.

[Project hub](https://cza1006.github.io/MeantByMe/) ·
[Web demo](https://cza1006.github.io/MeantByMe/demo.html) ·
[QR hub release](https://github.com/CZA1006/MeantByMe/releases/tag/qr-hub-v1) ·
[Documentation](docs/README.md)

## Safety contract

The model may propose an expression, but it may not decide what the person meant
or authorize speech on their behalf.

- Unconfirmed candidates never use the patient's personal voice.
- Silence, timeout, caregiver action, confidence, and device presence are not
  consent.
- AI output never writes directly to Gold patient memory.
- Caregiver context remains distinguishable from patient-confirmed intent.
- Rejection never becomes a patient preference.
- High-risk expressions require stricter confirmation.
- `Stop`, `Back`, `None of these`, and `Switch input method` remain available.
- Every spoken expression is traceable to evidence, completion, confirmation,
  and authorization state.

The complete engineering invariants are in [AGENTS.md](AGENTS.md), and the
frozen product decisions are in [DECISIONS.md](DECISIONS.md).

## How it works

```text
fragmented speech
→ ASR evidence
→ stable / uncertain fragments
→ patient-scoped verified memory retrieval
→ clarification or candidate expressions
→ explicit patient selection
→ private final readback
→ explicit expression authorization
→ personal-voice output
→ expression receipt
→ verified memory update
```

The architecture uses a deterministic shell around probabilistic services:

```text
UI clients
→ MeantByMe runtime
→ state machine and consent policies
→ provider protocols
→ ASR / intent / TTS / storage adapters
```

Core runtime code stays independent from UI frameworks and provider SDKs.

## Repository status

This repository currently contains several implementation tracks. Branch names
describe history, not clean component ownership:

| Track | Branch | Current contents | Verified tests |
|---|---|---|---:|
| Canonical baseline and project hub | `main` | Deterministic mock runtime, schemas, safety policies, documentation, GitHub Pages | 24 |
| Integrated web/backend prototype | `develop` and `frontend` | Same commit: runtime, gateway, responsive Web BFF/demo, cloud adapters, evaluation | 142 |
| Headset/mobile experiment | `feature/earPhones` | iOS client, Viaim headset adapter, command/QA experiments, profile persistence | 172 |

Test counts were independently verified on 2026-07-26 with Python 3.11.8.
`develop` and `frontend` currently point to the same commit and must not be
treated as independent source branches. The mobile branch is a broad
experimental fork, not a merge-ready iOS-only patch. See the
[branch audit](docs/BRANCH_AUDIT.md) for exact commits and integration risks.

## Run the canonical mock runtime

Requirements: Python 3.11.

```bash
python3.11 -m venv .venv
./.venv/bin/python -m pip install -e '.[test]'
./.venv/bin/python -m meantbyme --mode mock
./.venv/bin/python -m pytest
```

The mock flow is deterministic and uses fixture ASR, patient-scoped SQLite
memory, deterministic candidates, cached TTS, and no network. It exits
successfully only after the session reaches `completed`.

For the Web/gateway prototype or iOS experiment, switch to the corresponding
branch and follow its component README. Never place provider secrets in source,
frontend bundles, logs, fixtures, or commits.

## Documentation

- [Documentation index and authority](docs/README.md)
- [Current status](docs/STATUS.md)
- [Branch and code audit](docs/BRANCH_AUDIT.md)
- [Technical architecture](docs/03_TECHNICAL_ARCHITECTURE.md)
- [Agent runtime](docs/04_AGENT_RUNTIME.md)
- [Memory and personalization](docs/05_MEMORY_AND_PERSONALIZATION.md)
- [Security and consent](docs/08_SECURITY_AND_CONSENT.md)
- [Integration plan](docs/09_DEVELOPMENT_PLAN.md)
- [Evaluation and testing](docs/11_EVALUATION_AND_TESTING.md)
- [API and domain schemas](docs/13_API_SCHEMAS.md)
- [Repository structure](docs/14_REPO_STRUCTURE.md)
- [Contribution guide](CONTRIBUTING.md)
- [Code of conduct](CODE_OF_CONDUCT.md)
- [Security policy](SECURITY.md)

## Project boundary

MeantByMe is a research and communication-assistance prototype. It is not a
medical diagnosis system, treatment decision system, mind-reading system, or
clinically certified medical device. Do not use it as the sole channel for
emergency communication.

## License

Copyright © 2026 MeantByMe contributors. Released under the
[MIT License](LICENSE). The license permits use of the software; it does not
grant rights to patient data, voice recordings, voice identities, third-party
models, vendor SDKs, names, or trademarks.
