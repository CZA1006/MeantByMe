# MeantByMe Evaluation Harness

This harness measures product-quality behavior over simulated samples. It is
not a clinical evaluation and must not be populated with patient data.

## Deterministic mock run

```bash
./.venv/bin/python -m meantbyme.eval \
  --dataset demo/eval/dataset.jsonl \
  --mode mock \
  --report artifacts/eval_report.json
```

`mock` is the only automated-test mode. It uses the JSONL ASR fixtures,
sample-bound deterministic intent proposals, cached WAV output, and a fresh
in-memory SQLite database for every profile.

> ⚠️ **Mock metric values are NOT evidence of model quality.** The mock intent
> adapter is a fixture bound to the sample: it seeds each sample's own
> `intended_expression` into the candidate set and ignores both the transcript
> evidence and the `situation`. Coverage, Fragment Recall and Situation
> Sensitivity are therefore ~1.0 **by construction**. Mock mode exists to
> regression-test the *harness and runtime plumbing* (state transitions, memory
> writeback, hard gates) deterministically and without spending credit.
> **Quality claims must come from `cloud` mode against real models.**
>
> Reference live result (Step Plan, `step-explore`, 2026-07-24): the two
> flagship pairs — identical fragments, differing `situation` — each selected
> their own expected expression with no cross-contamination, in both English
> and Chinese. Real **Situation Sensitivity = 1.00 (2/2)**.

## Manual Step Plan cloud run

Start the local gateway with a real, gitignored `.env`, then place one
simulated 16 kHz mono WAV per sample at
`demo/eval/audio/<sample_id>.wav`. Run:

```bash
./.venv/bin/python -m services.gateway
./.venv/bin/python -m meantbyme.eval \
  --dataset demo/eval/dataset.jsonl \
  --mode cloud \
  --gateway-url http://127.0.0.1:8000 \
  --report artifacts/eval_cloud_report.json
```

Cloud mode ignores `asr_fixture`, sends the local WAV through the gateway,
passes the sample `situation` to the intent adapter, and records aggregate
latency. It may consume Step Plan credit and is never run by pytest.

## Replay format

Replay files live at `demo/eval/recordings/<sample_id>.json` and must declare
`"simulated": true`. Each contains `asr_results` plus either
`intent_proposal` or an `intent_proposals` array. Replay mode remains offline
and uses cached TTS:

```bash
./.venv/bin/python -m meantbyme.eval \
  --dataset demo/eval/dataset.jsonl \
  --mode replay \
  --report artifacts/eval_replay_report.json
```

Reports redact all high-risk candidate and final-expression plaintext. Raw
audio, secrets, and reports are ignored by git.
