# Codex Spec — Gateway upgrade to Step Plan (free) + situational context

Update the gateway to run the full stack on StepFun **Step Plan** free credit (¥199, monthly reset) and add a situational-context channel for memory-based disambiguation. Every request/response shape below was **live-verified** against StepFun on 2026-07-24. `core/` must stay unchanged (AST isolation test green). Secrets stay in `.env` (gitignored) only.

Work on `nick/runtime`; do not push; leave local commits for review.

## Billing context (why these changes)
- The **standard** `https://api.stepfun.com/v1` account balance is exhausted (HTTP 402). The **free ¥199 credit lives on `https://api.stepfun.com/step_plan/v1`**.
- Step Plan covers: text (step-explore), ASR (stepaudio-2.5-asr), TTS (stepaudio-2.5-tts). Voice **cloning** needs a file upload that is standard-only (needs a ¥ top-up) — for the demo use an official voice; keep cloning behind a flag.
- `.env` already sets `STEPFUN_BASE_URL=https://api.stepfun.com/step_plan/v1`.

## 1. ASR — rewrite to the SSE endpoint (VERIFIED)
Current `providers.transcribe` uses OpenAI-style `/audio/transcriptions` (multipart) — that path 404s on Step Plan. Replace with the SSE endpoint.

- **URL:** `POST {STEPFUN_BASE_URL}/audio/asr/sse`
- **Headers:** `Authorization: Bearer <key>`, `Content-Type: application/json`, `Accept: text/event-stream`, plus `User-Agent`.
- **Body:** send **raw PCM** (strip the WAV container with `wave.readframes`), base64-encoded:
```json
{
  "audio": {
    "data": "<base64 of s16le PCM>",
    "input": {
      "transcription": {"model": "stepaudio-2.5-asr", "language": "en", "enable_itn": true},
      "format": {"type": "pcm", "codec": "pcm_s16le", "rate": 16000, "bits": 16, "channel": 1}
    }
  }
}
```
- **Response:** `text/event-stream`. Lines are `data: {json}`. Accumulate `delta` from `{"type":"transcript.text.delta","delta":"..."}` events; the final `{"type":"transcript.text.done","text":"..."}` carries the full transcript. Use the `.done` text (fall back to concatenated deltas).
- **Map to `ASRResult`:** `provider="stepfun_stepaudio_asr"`, `transcript=<done text>.strip()`, `language=<language_hint>` (ASR does not return language reliably), `segments=[]`, `status="success"`. On any error/empty → `status="failed"`.
- **Verified:** returns `" I don't want to go tomorrow."` for a 16 kHz mono clip. Input must be PCM/16k/mono — the `AudioStore` already normalizes to 16 kHz mono WAV, so just strip the header.

## 2. TTS — model + endpoint (VERIFIED)
- **URL:** `POST {STEPFUN_BASE_URL}/audio/speech`
- **Body:** `{"model": "stepaudio-2.5-tts", "input": <text>, "voice": <voice>, "response_format": "wav"}`
- Neutral: `voice = STEPFUN_NEUTRAL_VOICE` (default `cixingnansheng`). Personal: `voice = <voice_profile_id>` (an official voice for the demo, or a cloned voice id if present).
- Response is `audio/wav` bytes directly. Change the model from `step-tts-mini` → `stepaudio-2.5-tts` (step-tts-mini is not on Step Plan). Endpoint `/audio/speech` is already correct.

## 3. Voice cloning — flag-gated, file_id flow
- Cloning needs: upload to **standard** `https://api.stepfun.com/v1/files` (multipart, `purpose=storage`) → `file_id` → `POST {STEPFUN_BASE_URL}/audio/voices` `{"file_id": <id>, "model": "stepaudio-2.5-tts"}` → returns a voice id.
- The `/files` upload requires standard account balance (a ¥49 top-up); it is **not** on Step Plan.
- Gate cloning behind `ENABLE_VOICE_CLONING` (default false). When disabled, `enroll_voice` returns `None` and the runtime uses an official voice as `voice_profile_id`. When the file upload 402s, degrade the same way (return None, do not crash). Keep the safety invariant: personal TTS still only via `AuthorizedExpression`.

## 4. Situational context — new field (enables memory disambiguation)
Live test showed step-explore disambiguates fragments far better when given the situation (who is asking, calendar facts). Wire a `situation` channel end to end.

- **Domain:** add optional `situation: str | None` to the intent request path. Put it on `ExpressionSession` (settable at `create_session`, e.g. `situation="A friend asked if he wants to go out tomorrow. Tomorrow is Sunday."`). `core/` domain schema may gain this **optional** field — this is the only allowed core change; flag it in the report.
- **Adapter:** `GatewayIntentAdapter.propose` includes `"situation": session_situation` in the POST body.
- **Gateway:** add `situation: str | None = None` to `IntentRequest` (keep `extra="forbid"`), pass it into the LLM user content.
- **Prompt:** update `INTENT_SYSTEM_PROMPT` to instruct: "Use `situation` and `memories` to disambiguate the fragments and to rank candidates; never invent intent beyond evidence + memory + situation." Keep the strict output schema (arrays, risk/source enums) from the earlier fix.
- **Result contract unchanged:** still returns `IntentProposal` (2–3 candidates, `requires_confirmation:true`, no speak/authorize/write fields).

## 5. Config
- `STEPFUN_BASE_URL=https://api.stepfun.com/step_plan/v1` (done in `.env`; add to `.env.example` as the default).
- Intent: `INTENT_PROVIDER=stepfun`, `INTENT_MODEL=step-explore` (Anthropic `/messages`, `x-api-key` + `anthropic-version: 2023-06-01`, no `thinking`). OpenAgents remains a fallback but its demo endpoint is too slow — keep it as fallback only.
- Note StepFun returns transient `503 engine_overloaded`; the existing retry/backoff handles it — keep `PROVIDER_MAX_ATTEMPTS>=3`.

## 6. Tests & acceptance
- Update the **stub gateway** to emulate the SSE ASR response shape (`data: {transcript.text.delta}` … `data: {transcript.text.done}`) and the `situation` field; keep all failure-path tests.
- All existing tests stay green; `core/` isolation green; `core/` diff limited to the optional `situation` field (flag it).
- Provide/keep `scripts/smoke_cloud.py`: a human runs it with the real `.env` to verify ASR (real speech WAV → transcript), intent (step-explore candidates using `situation`), and TTS (official voice → WAV) — all on Step Plan free credit.
- Do not call real StepFun in automated tests (uses credit + network). Secrets never committed.

## Report back
Files changed, stub-gateway results, confirmation `core/` diff is only the optional `situation` field, and any request/response field that did not match this spec.
