# MeantByMe Viaim iOS Client

This target replaces browser/file capture with the Viaim iOS hardware SDK
while reusing the existing Web Demo BFF, deterministic Runtime, Gateway and
model integrations.

## Data path

```text
Viaim microphone
  -> 16 kHz mono s16le PCM callback + Viaim primary text
  -> in-memory WAV envelope on iPhone
  -> Web Demo session audio endpoint with primary evidence header
  -> existing Runtime / Gateway / StepFun flow

Local PCM/text activity
  -> 5 seconds without detected speech ends one expression
  -> Web Demo generates candidates
  -> first candidate is privately read through the earbuds
  -> a short earbud-microphone capture interprets the patient's response
  -> “是/嗯/没错” confirms; “不是/不对/换一个” reads another candidate
  -> confirmed candidate is played by the iPhone speaker in a neutral voice
  -> a fresh capture round starts automatically

QA mode uses a separate temporary conversation:

```text
Viaim PCM + primary text
  -> dual-ASR transcript evidence
  -> conservative incomplete-question completion
  -> direct AI answer for low/medium uncertainty
  -> one natural clarification for high uncertainty
  -> neutral TTS played privately through the earbuds
  -> next question capture starts automatically
```

QA turns do not enter the patient-expression authorization state machine, use
personal voice, create an expression receipt, or write verified memory.
Conversation history exists only inside the active QA session.
```

While companion mode is active, **结束本次表达** stops and discards the
current capture/readback/playback only. The backend marks that expression
`expression_cancelled`, clears its candidates and authorization scope, creates
no receipt or verified memory, and the app immediately starts a fresh capture
round. **由陪护者结束会话** remains the separate control for ending companion
mode.

No raw PCM is written to iPhone storage. Unconfirmed candidates are not shown
on the caregiver screen. Private prompts are played only after iOS verifies an
active headphone/Bluetooth audio route. The current expression flow does not
enroll, authorize, synthesize, fetch, or play a cloned patient voice.

The app reports a unique
`playback_completed` callback only after `AVAudioPlayer` finishes on the iPhone
speaker; playback errors report `playback_failed`, which prevents Receipt and
verified-memory writes.

## Voice confirmation

After the full private candidate readback and a private instruction, the app
starts a separate command capture. Once speech is detected, about 1.2 seconds
of silence ends that response. The server interprets the Viaim primary text
and an independent PCM-derived ASR result. An affirmation is accepted only
when both interpretations agree and the server-issued interpretation record
matches the active candidate and private prompt.

`stop` is fail-safe and may stop the flow when either reliable interpretation
detects it. Reject, repeat, and unknown do not authorize playback. High-risk or
L3 candidates require two distinct private readbacks and two distinct
affirmation recordings.

## Headset gesture availability

The bundled Viaim iOS v1.0.0 public SDK exposes connection/device status,
recording, PCM, text-stream, call-state and flash-record APIs. Its public
headers do not expose an earbud touch, squeeze/pinch, tap, button, or generic
gesture callback. MeantByMe therefore uses the in-app **结束本次表达／结束本次提问**
button. The expression button sends the dedicated `cancel_expression` runtime
command, while QA cancellation removes the current temporary turn. A future
vendor-supported gesture can call the same app actions without changing
consent or memory policy. Do not bind to the SDK's private headers.

## User profiles

The gear button opens user settings. Before a companion session, the caregiver
can select the current user, inspect that user's profile, answer guided
background questions to create a user, or import a UTF-8 Markdown profile.
The selected reference and language are sent on every new session, including
stopped-session recovery, and selection is locked while a companion session is
active.

Questionnaire answers and non-simulated Markdown imports are stored as Silver
caregiver context. They may help the model interpret fragments but cannot
represent patient confirmation or bypass the private readback/voice-confirm
flow. Production storage uses an independent Zeabur MySQL service. Zeabur's
standard `MYSQL_*` variables (or optional `WEB_DEMO_MYSQL_*` overrides) are
configured on the `meantbyme-ios` BFF; the native iOS app and
`meantbyme-gateway` never connect to MySQL directly.

## Prepare the project

1. Install XcodeGen:

   ```bash
   brew install xcodegen
   ```

2. Copy the vendor package supplied with the project:

   ```bash
   mkdir -p ios/MeantByMeHeadset/Vendor
   cp -R \
     "/Users/gaojiayi/Downloads/Viaim智能耳机_iOS_v1.0.0/VisionHeadsetOpenSDK" \
     ios/MeantByMeHeadset/Vendor/
   ```

3. Create the ignored secret configuration:

   ```bash
   cp ios/MeantByMeHeadset/Config/Secrets.xcconfig.example \
      ios/MeantByMeHeadset/Config/Secrets.xcconfig
   ```

   Set the Viaim AppKey/AppSecret, deployed Web Demo HTTPS URL, demo access
   token and Apple development team. The vendor SDK currently accepts the
   mobile AppSecret; request a production-safe mobile authorization mechanism
   from Viaim before App Store release.

4. Generate and open:

   ```bash
   cd ios/MeantByMeHeadset
   xcodegen generate
   open MeantByMeHeadset.xcodeproj
   ```

## Device test

- Use an arm64 iPhone running iOS 15 or later; the supplied SDK is not a
  simulator acceptance target.
- Pair the Viaim headset in iOS Bluetooth settings before pressing Connect.
- Keep the app in the foreground for the MVP.
- Speak once, then remain silent for 5 seconds. The timer is refreshed by
  Viaim partial/final text or local PCM energy, so unclear speech can still
  delimit an expression even when no text is produced.
- The 5-second trailing silence is used only as an end-of-expression signal.
  Before upload, the app removes that trailing silence while retaining small
  pre/post-roll padding around detected speech.
- Confirm that an unconfirmed readback never falls back to the iPhone speaker.
- When the system output volume is zero, the speaker test intentionally skips
  its first utterance. Raise the volume with the on-screen system slider, then
  tap **再次播放测试语音**.
- Xcode 26 may print `unsafeForcedSync` from the platform accessibility
  subsystem while presenting system controls such as `MPVolumeView`. Treat it
  as a platform diagnostic unless there is also an app crash/backtrace. Audio
  delegate callbacks still cross to `MainActor` asynchronously.
- After the private readback, say “是”, “嗯”, or “没错” to confirm.
- Say “不是”, “不对”, or “换一个” to reject and hear another candidate.
- If the two interpretations disagree or the response is unclear, the app
  privately repeats the candidate instead of playing it publicly.
- Disconnecting the headset must stop the flow without confirming.

For QA acceptance, select **向 AI 提问**, ask an incomplete question, and wait
for the private neutral-voice answer. **结束本次提问** removes the active turn
from temporary history and immediately starts a new question capture; it does
not stop the whole companion session.
