# MeantByMe localhost gateway

The gateway is the only process that reads StepFun or OpenAgents API keys.
Desktop adapters receive only `GATEWAY_URL`.

```bash
cp .env.example .env
./.venv/bin/python -m pip install -e '.[test]'
./.venv/bin/python -m services.gateway
```

The development server binds to `127.0.0.1:8000`. It does not log request
bodies, headers, raw audio, candidate text, memory content, or provider
responses.

`INTENT_PROVIDER=openagents` and `INTENT_MODEL=deepseek-v4-pro` are the
defaults. Use `INTENT_MODEL=deepseek-4-flash` for the faster OpenAgents option,
or set `INTENT_PROVIDER=stepfun` and `INTENT_MODEL=step-explore`.

In another terminal, run the manual provider smoke check with a 16 kHz mono
WAV (other PCM WAV inputs are normalized locally):

```bash
./.venv/bin/python scripts/smoke_cloud.py path/to/input.wav
```

This checks gateway health, StepFun `step-asr`, the configured intent model,
and neutral `step-tts-mini`. It does not enroll or invoke a personal voice.
The script sends no provider key; keys remain in the gateway process.

Voice enrollment accepts a 5-10 second WAV at the gateway. The gateway uploads
it to StepFun file storage with `purpose=storage`, then exchanges the returned
`file_id` for a voice ID through `/v1/audio/voices`.

To drive the full consent-first runtime through the gateway:

```bash
./.venv/bin/python -m meantbyme \
  --mode cloud \
  --audio path/to/input.wav
```

For microphone capture, replace `--audio` with
`--microphone-seconds 8`. The `fallback` mode remains local and deterministic.
