# MeantByMe｜意由我

> **Completed with AI. Meant by me.**  
> AI 可以帮助补全表达，但意思必须由本人确认。

MeantByMe is a **patient-bound, consent-first communication agent** for people whose cognition and communicative intent remain relatively clear, but whose speech production is impaired, fragmented, slow, or temporarily unavailable.

## Core principle

> **The Agent may complete the sentence, but it must never decide the meaning.**

MeantByMe treats ASR, language models, patient memory, and context as **evidence rather than authority**. It captures fragmented speech, retrieves verified patient-specific memory, proposes a small number of possible expressions, and speaks in the patient’s authorized voice only after explicit confirmation.

## Hackathon MVP

A native macOS desktop application with:

- iFLYBUDS Air 2 as microphone and private audio output;
- primary and secondary ASR evidence;
- stable / uncertain fragment extraction;
- patient-bound verified memory;
- progressive clarification;
- 2–3 expression candidates plus “None of these”;
- final private readback;
- deterministic personal-voice authorization;
- StepAudio personal TTS;
- Memory & Decision Trace;
- verified memory writeback;
- mock, cloud, and fallback modes.

## Golden path

```text
Fragmented speech
→ ASR evidence
→ stable / uncertain fragments
→ verified patient memory retrieval
→ clarification or candidates
→ patient selection
→ final private readback
→ explicit authorization
→ personal-voice output
→ expression receipt
→ verified memory update
```

## Why this is different

Most voice agents optimize for autonomous completion. MeantByMe optimizes for **safe recovery when the model is wrong**.

The system separates:

- what the patient directly expressed;
- what ASR inferred;
- what AI completed;
- what memory influenced;
- what the patient confirmed;
- what the system was authorized to speak.

## Development environment

The team develops with Claude Code and Codex on:

- two Apple Silicon Macs;
- one Intel Mac.

Heavy models are cloud- or remote-GPU-first. The Mac application owns interaction, state, memory, authorization, trace, and fallback behavior.

## Documentation

- [Product vision](docs/01_PRODUCT_VISION.md)
- [Storytelling and demo](docs/02_STORYTELLING_AND_DEMO.md)
- [Technical architecture](docs/03_TECHNICAL_ARCHITECTURE.md)
- [Agent runtime](docs/04_AGENT_RUNTIME.md)
- [Memory and personalization](docs/05_MEMORY_AND_PERSONALIZATION.md)
- [Interaction and accessibility](docs/06_INTERACTION_AND_ACCESSIBILITY.md)
- [Models and integrations](docs/07_MODELS_AND_INTEGRATIONS.md)
- [Security and consent](docs/08_SECURITY_AND_CONSENT.md)
- [Development plan](docs/09_DEVELOPMENT_PLAN.md)
- [Team ownership](docs/10_TEAM_OWNERSHIP.md)
- [Evaluation and testing](docs/11_EVALUATION_AND_TESTING.md)
- [Research references](docs/12_RESEARCH_REFERENCES.md)
- [API schemas](docs/13_API_SCHEMAS.md)
- [Repository structure](docs/14_REPO_STRUCTURE.md)
