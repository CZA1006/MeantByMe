# Simulated Profile Test Bundles

MeantByMe can run the same simulated audio with or without a structured
patient profile. This measures personalization without allowing a narrative
document or evaluator answer to become patient intent.

## File contract

A profile is UTF-8 Markdown no larger than 64 KiB. Human-readable narrative
may appear anywhere, but the importer reads exactly one fenced block:

````markdown
```meantbyme-profile
{
  "schema_version": 1,
  "simulated": true,
  "profile_id": "example_demo",
  "label": "Example simulated patient",
  "patient": {
    "patient_id": "example_demo",
    "display_name": "Example",
    "languages": ["en"],
    "default_language": "en"
  },
  "consent": {
    "scope": "demo_testing",
    "cloud_processing_allowed": true
  },
  "voice_consent": {
    "authorization_id": "voice-consent-example",
    "consent_session_id": "voice-enrollment-example",
    "voice_profile_id": "cixingnansheng"
  },
  "memories": []
}
```
````

Each memory must also carry `simulated: true`, `source`,
`verification_level`, `sensitivity`, and `prompt_eligible`.

## Provenance rules

- Gold requires `source: "patient"` and a `confirmation_session_id`.
- Caregiver observations require `verification_level: "silver"`.
- Research assumptions use `verification_level: "unverified"` and
  `prompt_eligible: false`; the importer does not seed them.
- The expected expression belongs in an evaluator-only sidecar, not the
  profile. Including it as Gold changes the test into known-phrase recall.
- Context retrieval is patient-scoped, token-relevant, and limited to five
  rows before the situation is composed.

## Web Demo

After entering the demo access code, choose:

- **No profile (control)** for the unpersonalized run;
- an included simulated profile;
- **Upload structured Markdown** for a process-local profile.

After a completed expression, **Run same audio with another profile** repeats
the exact uploaded/recorded WAV after another profile is selected. Uploads
remain in memory for the current Web Demo process and are never written to
disk.

Evaluator-only case manifests may refer to external WAV filenames because raw
audio is gitignored. See `demo/eval/lin_yue_profile_cases.jsonl`; its
acceptable answer is never loaded by the Web Demo or profile importer.

Only simulated, de-identified bundles are accepted by this demo. Cloud mode
rejects bundles whose `cloud_processing_allowed` value is false.
