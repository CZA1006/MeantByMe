# MeantByMe documentation

This directory is the project knowledge base. Documentation uses the following
authority order when files or branches disagree:

1. [AGENTS.md](../AGENTS.md) safety and architecture invariants;
2. [DECISIONS.md](../DECISIONS.md) accepted implementation decisions;
3. code and tests on `main`;
4. accepted documentation on `main`;
5. branch-local code and documents, which are experimental until reviewed.

A branch-local document cannot silently replace a consent invariant or an
accepted decision.

## Start here

- [Current status](STATUS.md)
- [Branch audit](BRANCH_AUDIT.md)
- [Product vision](01_PRODUCT_VISION.md)
- [Technical architecture](03_TECHNICAL_ARCHITECTURE.md)
- [Agent runtime](04_AGENT_RUNTIME.md)
- [Memory and personalization](05_MEMORY_AND_PERSONALIZATION.md)
- [Security and consent](08_SECURITY_AND_CONSENT.md)
- [Integration plan](09_DEVELOPMENT_PLAN.md)
- [Evaluation and testing](11_EVALUATION_AND_TESTING.md)
- [API and domain schemas](13_API_SCHEMAS.md)
- [Repository structure](14_REPO_STRUCTURE.md)

## Document lifecycle

Each material change should update the relevant design document, tests, and
decision record in the same pull request. Describe capabilities as one of:

- **canonical** — present and verified on `main`;
- **branch-only** — implemented on a named branch;
- **experimental** — not accepted for integration;
- **planned** — design intent without verified implementation.

Dates, commit IDs, and test counts are snapshots, not permanent claims.
