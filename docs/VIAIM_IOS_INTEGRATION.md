# Viaim headset integration

The existing browser demo remains available for development and evaluation.
The iOS client is a second front end over the same session API.

## Reused backend flow

- `POST /api/sessions`
- `POST /api/sessions/{id}/audio` with optional
  `X-Viaim-Primary-Transcript-B64`
- `POST /api/sessions/{id}/commands`
- `GET /api/sessions/{id}/audio/neutral`
- `GET /api/sessions/{id}/audio/personal`

## New earbud command endpoint

```http
POST /api/sessions/{id}/earbud/interpret
Content-Type: audio/wav
X-Demo-Token: ...
X-Demo-Session: ...
X-Viaim-Primary-Transcript-B64: <base64 UTF-8>
```

The body contains only the current short command utterance. In cloud mode the
server obtains independent ASR from that audio and interprets the Viaim and
cloud transcripts separately. The resolved output is limited to:

```text
affirm reject repeat stop back unknown
```

An affirmation is returned only when both interpretations agree. `stop` is a
safe action and can be returned when either reliable channel identifies it.
The interpretation endpoint never calls TTS, mutates authorization or writes
memory.

The primary transcript is Base64-encoded in a dedicated header so patient
speech never appears in request URLs or ordinary access logs.

Expression capture uses the same header. The server prepends that Viaim
primary result to the independent ASR result produced from PCM, so the Runtime
receives two distinguishable evidence sources rather than discarding the
headset text stream.

## Current MVP capture behavior

The SDK provides PCM continuously and primary partial/final text. A final text
event starts a short silence debounce:

- expression capture: 2.5 seconds;
- command response: 0.9 seconds.

The capture also remains subject to the existing server duration limit. PCM is
wrapped as a 16 kHz mono PCM WAV in memory because the teammate's deployed
Gateway already accepts that contract. This avoids changing the proven
StepFun/Runtime path while replacing browser file input with actual headset
input.

After final confirmation, successful TTS leaves the Runtime at
`voice_authorized`. The iOS app plays the audio through the iPhone speaker and
then sends `playback_completed` with a unique playback ID. Receipt creation,
the `SPOKEN` event and verified-memory write occur only after that callback.
`playback_failed` leaves the session without a receipt or memory write.

## Deployment

Deploy the updated Gateway and Web Demo containers as before. The Gateway now
also exposes `POST /v1/commands/interpret`; the Web Demo exposes the earbud
endpoint. The iOS app points at the Web Demo HTTPS domain, not directly at the
provider Gateway, so `GATEWAY_TOKEN` and provider secrets remain server-side.

For the current repository layout:

```bash
docker build -f Dockerfile -t meantbyme-gateway .
docker build -f Dockerfile.meantbyme-demo -t meantbyme-demo .
```

Expose the Gateway container only to the Web Demo/BFF where practical. Expose
the Web Demo over HTTPS on port 8080 and set that public URL as
`MEANTBYME_BASE_URL` in the ignored iOS `Secrets.xcconfig`.
