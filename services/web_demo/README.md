# MeantByMe Web Demo

Browser-facing interaction demo for the existing deterministic runtime.

> Simulated data. Not a clinical accuracy claim.

## Boundary

```text
Browser
  -> Web Demo BFF / Session API
  -> deterministic MeantByMe Runtime
  -> provider adapters
  -> MeantByMe Gateway
  -> StepFun
```

The browser never receives `GATEWAY_TOKEN`, cannot call personal TTS, and
cannot write verified memory. It renders the runtime view model and sends
patient commands. `patient_id` is selected by the server from the simulated
profile and is never accepted from a client request.

This is not the production cloud-memory architecture:

- every session selects a structured simulated profile or the no-profile
  control;
- each session has an isolated in-memory SQLite repository;
- uploaded profile bundles remain process-local and are not written to disk;
- audio is stored in a private temporary directory;
- sessions and memory disappear when the process restarts;
- a random session token scopes every session endpoint.

## Local mock mode

```bash
./.venv/bin/python -m services.web_demo
```

Open <http://127.0.0.1:8081>. Mock mode is deterministic and uses no network
or API credit.

## Local cloud mode

Set these in the git-ignored `.env`:

```dotenv
WEB_DEMO_MODE=cloud
WEB_DEMO_TOKEN=replace_with_a_demo_access_code
GATEWAY_URL=https://meantbyme.zeabur.app
GATEWAY_TOKEN=the_gateway_caller_token
GATEWAY_TIMEOUT_SECONDS=35
WEB_DEMO_VOICE_PROFILE_ID=cixingnansheng
WEB_DEMO_MAX_AUDIO_SECONDS=20
WEB_DEMO_MAX_PROFILE_BYTES=65536
WEB_DEMO_MAX_UPLOADED_PROFILES=20
```

Then run the same module. The user enters `WEB_DEMO_TOKEN` in the browser.
That access code is distinct from `GATEWAY_TOKEN`; the provider gateway token
stays server-side.

## Zeabur

Create a second Git service from the same repository and name the service
exactly `meantbyme-demo`. Zeabur will auto-match
`Dockerfile.meantbyme-demo` for that service. Do not change the existing
`meantbyme` gateway service.

Set:

```dotenv
WEB_DEMO_MODE=cloud
WEB_DEMO_TOKEN=<random demo access code>
GATEWAY_URL=https://meantbyme.zeabur.app
GATEWAY_TOKEN=<same caller token configured on the gateway>
GATEWAY_TIMEOUT_SECONDS=35
GATEWAY_MAX_ATTEMPTS=2
WEB_DEMO_VOICE_PROFILE_ID=cixingnansheng
WEB_DEMO_MAX_AUDIO_SECONDS=20
WEB_DEMO_MAX_PROFILE_BYTES=65536
WEB_DEMO_MAX_UPLOADED_PROFILES=20
```

Do not set `STEPFUN_API_KEY` on the Web Demo service. Only the existing
provider gateway owns that secret.

After the deployment is healthy:

1. Open the Web Demo service's **Networking** tab.
2. Generate `meantbyme-demo.zeabur.app`.
3. Route it to container port `8080`.
4. Verify `GET /api/health`.

Cloud mode fails closed when `WEB_DEMO_TOKEN` or `GATEWAY_TOKEN` is missing.
Microphone capture stops automatically at 20 seconds, and the BFF rejects
longer uploaded WAV files before they can consume gateway capacity. PCM
`WAVE_FORMAT_EXTENSIBLE` input is normalized by the local AudioStore.

Profile Markdown must follow
[`docs/PROFILE_TEST_BUNDLES.md`](../../docs/PROFILE_TEST_BUNDLES.md). Only its
validated `meantbyme-profile` JSON block is imported. Gold, Silver, and
unverified provenance remain distinct, and cloud mode requires explicit
`cloud_processing_allowed`.
