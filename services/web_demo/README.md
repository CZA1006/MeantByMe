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

The BFF also exposes a separate `/api/qa/sessions` flow for private AI
conversation. Its reconstructed questions and answers are temporary,
low/medium uncertainty is answered directly, high uncertainty asks a natural
clarification, and audio is synthesized only with neutral TTS. Cancelling a QA
turn removes both sides of that turn from the session context.

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
WEB_DEMO_MAX_UPLOADED_PROFILES=500
WEB_DEMO_PROFILE_DB_BACKEND=sqlite
WEB_DEMO_DATABASE_PATH=/tmp/meantbyme-web-demo/profiles.sqlite3
```

Then run the same module. The user enters `WEB_DEMO_TOKEN` in the browser.
That access code is distinct from `GATEWAY_TOKEN`; the provider gateway token
stays server-side.

## Zeabur

The deployed service roles are:

```text
iOS app
  -> meantbyme-ios (public session/profile BFF)
  -> meantbyme-gateway (provider gateway)
  -> model providers

meantbyme-ios
  -> mysql (independent Zeabur database service, private network only)
```

`meantbyme-ios` is built with `Dockerfile.meantbyme-demo`. The service name is
historical: it is the server API used by the native iOS app, not an iOS binary
running in Zeabur. Keep `meantbyme-gateway`, `meantbyme-ios`, and `mysql` as
three independent services.

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
WEB_DEMO_MAX_UPLOADED_PROFILES=500
WEB_DEMO_PROFILE_DB_BACKEND=mysql
WEB_DEMO_MYSQL_DATABASE=meantbyme
WEB_DEMO_MYSQL_AUTO_CREATE_SCHEMA=false
```

Set these variables on `meantbyme-ios`, not on `meantbyme-gateway`. The Zeabur
MySQL service automatically exposes `MYSQL_HOST`, `MYSQL_PORT`,
`MYSQL_USERNAME`, `MYSQL_PASSWORD`, and `MYSQL_DATABASE` to other services in
the same project. This application accepts those names directly. If automatic
exposure is disabled, set the equivalent scoped overrides on `meantbyme-ios`:

```dotenv
WEB_DEMO_MYSQL_HOST=<MySQL private-network host>
WEB_DEMO_MYSQL_PORT=3306
WEB_DEMO_MYSQL_USER=<database user>
WEB_DEMO_MYSQL_PASSWORD=<database password>
```

Do not set MySQL credentials in the native iOS app or on
`meantbyme-gateway`. Do not set `STEPFUN_API_KEY` on `meantbyme-ios`; only the
provider gateway owns that secret.

Create the database/table with
[`deploy/mysql/init_profiles.sql`](../../deploy/mysql/init_profiles.sql).
The iOS-created and Markdown-imported user profiles are then stored in the
independent MySQL service; neither application service needs a database
persistent volume. Prefer the MySQL service's private-network hostname rather
than exposing port 3306 publicly. Store the password in Zeabur Secrets, never
in source control.

After the deployment is healthy:

1. Open the `meantbyme-ios` service's **Networking** tab.
2. Generate or retain its public HTTPS domain.
3. Route it to container port `8080`.
4. Verify `GET /api/health` returns
   `"profile_database_backend": "mysql"`.

Cloud mode fails closed when `WEB_DEMO_TOKEN` or `GATEWAY_TOKEN` is missing.
Microphone capture stops automatically at 20 seconds, and the BFF rejects
longer uploaded WAV files before they can consume gateway capacity. PCM
`WAVE_FORMAT_EXTENSIBLE` input is normalized by the local AudioStore.

Profile Markdown must follow
[`docs/PROFILE_TEST_BUNDLES.md`](../../docs/PROFILE_TEST_BUNDLES.md). Only its
validated `meantbyme-profile` JSON block is imported. Explicit questionnaire
input and explicit imports are trusted regardless of the operator's role;
the existing final-confirm/reject/edit actions automatically update a
confidence-scored expression-to-intent mapping, so there is no second
**Remember** step. Legacy Gold/Silver values are read with equal trusted
weight. Cloud mode still
requires explicit `cloud_processing_allowed`, and profile import never grants
personal-voice authority.
