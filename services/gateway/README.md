# MeantByMe localhost gateway

The gateway is the only process that reads StepFun or OpenAgents API keys.
Desktop adapters receive `GATEWAY_URL` and the caller-only
`GATEWAY_TOKEN`.

```bash
cp .env.example .env
./.venv/bin/python -m pip install -e '.[test]'
./.venv/bin/python -m services.gateway
```

The development server binds to `127.0.0.1:8000`. It does not log request
bodies, headers, raw audio, candidate text, memory content, or provider
responses.

`GET /` returns a minimal public service status for deployment previews, and
`GET /v1/health` returns provider configuration booleans without secret values.

Set `GATEWAY_TOKEN` in `.env` for both the gateway and cloud-mode desktop
client. Protected provider routes fail closed with `503` when the token is
unset, while `GET /v1/health` remains public. Callers that bypass the desktop
client must send `X-Gateway-Token: <token>`.

The desktop timeout defaults to 35 seconds, slightly above the gateway's
30-second route budget. This lets the gateway return a provider result or its
own timeout response instead of the desktop prematurely entering fallback.
ASR requests are limited to 20 seconds by default
(`GATEWAY_MAX_ASR_AUDIO_SECONDS`) because longer single-request clips can
exceed the route budget. Long-form audio requires a future chunked ASR path.

The gateway applies a process-local fixed-window limit per client IP. This is
appropriate for one Uvicorn worker. Multiple workers or Zeabur replicas require
a shared rate-limit store before they can enforce a deployment-wide limit.

The defaults use Step Plan:
`STEPFUN_BASE_URL=https://api.stepfun.com/step_plan/v1`,
`INTENT_PROVIDER=stepfun`, and `INTENT_MODEL=step-explore`. OpenAgents remains
available as a fallback configuration.

In another terminal, run the manual provider smoke check with a 16 kHz mono
WAV (other PCM WAV inputs are normalized locally):

```bash
./.venv/bin/python scripts/smoke_cloud.py path/to/input.wav
```

This checks gateway health, StepFun `stepaudio-2.5-asr`, the configured intent
model with situational context, and neutral `stepaudio-2.5-tts`. It does not
enroll or invoke a personal voice. The script sends no provider key; keys
remain in the gateway process.

Voice cloning is disabled by default. With `ENABLE_VOICE_CLONING=true`, a
5-10 second WAV is uploaded to the standard StepFun file service with
`purpose=storage`, then its `file_id` is exchanged for a voice ID through the
Step Plan `/audio/voices` endpoint. A disabled flow or standard-account 402
returns no voice ID and does not fail the runtime.

To drive the full consent-first runtime through the gateway:

```bash
./.venv/bin/python -m meantbyme \
  --mode cloud \
  --audio path/to/input.wav \
  --situation "A friend asked about tomorrow's plans."
```

For microphone capture, replace `--audio` with
`--microphone-seconds 8`. The `fallback` mode remains local and deterministic.
