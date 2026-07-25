# Viaim headset integration

The existing browser demo remains available for development and evaluation.
The iOS client is a second front end over the same session API.

## Reused backend flow

- `POST /api/sessions`
- `POST /api/sessions/{id}/audio` with optional
  `X-Viaim-Primary-Transcript-B64`
- `POST /api/sessions/{id}/commands`
- `GET /api/sessions/{id}/audio/neutral`

## Voice-command endpoint

`POST /api/sessions/{id}/earbud/interpret` receives the short response recorded
after private readback. It requires:

- `X-Viaim-Primary-Transcript-B64`;
- `X-MeantByMe-Prompt-ID`;
- WAV audio for independent secondary ASR.

It returns a constrained intent (`affirm`, `reject`, `repeat`, `stop`, `back`,
or `unknown`) plus a server-issued interpretation ID. The confirmation command
must present that ID; arbitrary client-supplied `affirm` evidence is rejected.
An affirmation requires agreement between both interpretations. The model only
classifies the response and cannot mutate Runtime authorization or memory.

The primary transcript is Base64-encoded in a dedicated header so speech never
appears in request URLs or ordinary access logs.

Expression capture uses the same header. The server prepends that Viaim
primary result to the independent ASR result produced from PCM, so the Runtime
receives two distinguishable evidence sources rather than discarding the
headset text stream.

## Current MVP capture behavior

The SDK provides PCM continuously and primary partial/final text. The first
detected speech starts an 8-second silence window; later speech refreshes it.
Detection uses both non-empty Viaim text events and a lightweight local PCM
energy check so indistinct speech is not dependent on successful ASR.
The 8-second end-of-expression silence is removed on-device before WAV
encoding; it is a boundary signal, not part of the ASR request. Internal pauses
between fragments are preserved, together with short pre/post-roll padding.

The capture also remains subject to the existing server duration limit. PCM is
wrapped as a 16 kHz mono PCM WAV in memory because the teammate's deployed
Gateway already accepts that contract. This avoids changing the proven
StepFun/Runtime path while replacing browser file input with actual headset
input.

The Runtime prepares one candidate without claiming that the patient selected
it. The candidate and instruction are privately played in the earbuds, then a
separate command capture listens for natural confirmation such as “是/嗯/没错”
or rejection such as “不是/不对/换一个”. About 1.2 seconds of silence ends
the short response. Unknown or disagreeing interpretations cause another
private readback and never public playback.

An agreed patient affirmation moves the expression to `patient_confirmed`.
High-risk or L3 candidates require a second full private readback and a second
distinct affirmation recording. The confirmed neutral audio is then played
through the iPhone speaker, after which iOS sends `playback_completed` with a
unique playback ID. Receipt creation, the `SPOKEN` event and verified-memory
write occur only after that callback. `playback_failed` leaves the session
without a receipt or memory write. No voice consent or cloned-voice TTS is used
by this flow.

## Deployment

Deploy the updated Gateway and Web Demo containers as before. The iOS app
points at the Web Demo HTTPS domain, not directly at the provider Gateway, so
`GATEWAY_TOKEN` and provider secrets remain server-side.

For the current repository layout:

```bash
docker build -f Dockerfile -t meantbyme-gateway .
docker build -f Dockerfile.meantbyme-demo -t meantbyme-demo .
```

Expose the Gateway container only to the Web Demo/BFF where practical. Expose
the Web Demo over HTTPS on port 8080 and set that public URL as
`MEANTBYME_BASE_URL` in the ignored iOS `Secrets.xcconfig`.
