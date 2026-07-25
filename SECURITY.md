# Security Policy

## Scope

Security reports may cover source code, the Web/gateway prototype, mobile
clients, authorization boundaries, patient isolation, memory provenance, secret
handling, or personal-voice misuse.

Do not open a public issue containing a vulnerability, secret, patient data,
voice sample, or reproducible authorization bypass. Use the repository's
[private vulnerability reporting](https://github.com/CZA1006/MeantByMe/security/advisories/new)
when available. If private reporting is unavailable, contact a repository
maintainer privately before disclosing details.

## Supported code

`main` is the canonical supported baseline. Other branches are prototypes and
receive best-effort review until their changes are integrated through focused
pull requests.

## Data handling

- Use simulated profiles and synthetic or explicitly licensed fixtures.
- Never commit `.env`, tokens, private keys, raw patient audio, personal memory,
  voice-enrollment recordings, or production database snapshots.
- Rotate any credential that reaches a commit, log, screenshot, release, or
  frontend bundle; deleting the file is not sufficient.
- Keep cloud payloads minimal and patient scoped.
- Logs should contain redacted identifiers and structured status, not full
  sensitive content.

## Safety-related reports

A consent or provenance failure is treated with the same urgency as a security
failure. Examples include personal TTS before confirmation, caregiver action
authorizing patient speech, cross-patient retrieval, AI-written Gold memory, or
retry-induced duplicate memory writes.

This project is not an emergency communication service or clinically certified
medical device.
