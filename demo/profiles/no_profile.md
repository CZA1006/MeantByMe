# No profile

This simulated profile contains no personal memory. It is used as the control
condition when comparing the same audio with and without personalization.

```meantbyme-profile
{
  "schema_version": 1,
  "simulated": true,
  "profile_id": "no_profile",
  "label": "No profile (control)",
  "patient": {
    "patient_id": "no_profile",
    "display_name": "Anonymous simulated user",
    "languages": ["en", "zh"],
    "default_language": "en"
  },
  "consent": {
    "scope": "demo_testing",
    "cloud_processing_allowed": true
  },
  "voice_consent": {
    "authorization_id": "voice-consent-no-profile",
    "consent_session_id": "voice-enrollment-no-profile",
    "voice_profile_id": "cixingnansheng"
  },
  "memories": []
}
```
