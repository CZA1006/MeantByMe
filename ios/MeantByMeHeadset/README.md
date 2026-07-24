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

Viaim primary command ASR + command PCM
  -> Web Demo earbud interpretation endpoint
  -> independent cloud ASR + constrained command model
  -> affirm/reject/repeat/stop/back/unknown only
  -> iOS sends an existing Runtime command
```

No raw PCM is written to iPhone storage. Unconfirmed candidates are not shown
on the caregiver screen. Private prompts are played only after iOS verifies an
active headphone/Bluetooth audio route.

Personal TTS is not treated as spoken. The app reports a unique
`playback_completed` callback only after `AVAudioPlayer` finishes on the iPhone
speaker; playback errors report `playback_failed`, which prevents Receipt and
verified-memory writes.

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
- Confirm that an unconfirmed readback never falls back to the iPhone speaker.
- Disconnecting the headset must stop the flow without confirming.

The companion app currently implements expression mode. QA remains visible but
fails closed until the teammate backend exposes a QA endpoint.
