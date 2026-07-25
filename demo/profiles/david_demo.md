# David demo profile

This is the structured equivalent of the original Milestone 1 simulated
profile. Narrative outside the JSON block is never sent to a provider.

```meantbyme-profile
{
  "schema_version": 1,
  "simulated": true,
  "profile_id": "david_demo",
  "label": "David",
  "patient": {
    "patient_id": "david_demo",
    "display_name": "David",
    "languages": ["en", "zh"],
    "default_language": "en"
  },
  "consent": {
    "scope": "demo_testing",
    "cloud_processing_allowed": true
  },
  "voice_consent": {
    "authorization_id": "voice-consent-david-demo",
    "consent_session_id": "voice-enrollment-david-demo",
    "voice_profile_id": "voice-david-demo"
  },
  "memories": [
    {
      "simulated": true,
      "id": "mem-david-go-tomorrow",
      "memory_type": "semantic",
      "verification_level": "gold",
      "source": "patient",
      "text": "I don't want to go tomorrow.",
      "language": "en",
      "context": {"topic": "planning"},
      "usage_count": 2,
      "confirmation_session_id": "historical-david-001",
      "sensitivity": "ordinary",
      "prompt_eligible": true
    },
    {
      "simulated": true,
      "id": "mem-david-move-appointment",
      "memory_type": "semantic",
      "verification_level": "gold",
      "source": "patient",
      "text": "Move my appointment to tomorrow.",
      "language": "en",
      "context": {"topic": "schedule"},
      "usage_count": 1,
      "confirmation_session_id": "historical-david-002",
      "sensitivity": "ordinary",
      "prompt_eligible": true
    },
    {
      "simulated": true,
      "id": "ctx-david-doctor-sunday",
      "memory_type": "context",
      "verification_level": "gold",
      "source": "patient",
      "text": "Sees the doctor every Sunday morning.",
      "language": "en",
      "context": {
        "kind": "routine",
        "detail": "doctor visit",
        "time_pattern": "weekly:sunday"
      },
      "usage_count": 2,
      "confirmation_session_id": "simulated-context-confirmation-001",
      "sensitivity": "sensitive",
      "prompt_eligible": true
    },
    {
      "simulated": true,
      "id": "ctx-david-daughter-weekends",
      "memory_type": "context",
      "verification_level": "gold",
      "source": "patient",
      "text": "Daughter Mia visits on weekends.",
      "language": "en",
      "context": {
        "kind": "person",
        "detail": "daughter Mia visits",
        "time_pattern": "weekly:weekend"
      },
      "usage_count": 2,
      "confirmation_session_id": "simulated-context-confirmation-002",
      "sensitivity": "ordinary",
      "prompt_eligible": true
    },
    {
      "simulated": true,
      "id": "ctx-david-window-afternoon",
      "memory_type": "context",
      "verification_level": "gold",
      "source": "user_input",
      "text": "Prefers the living-room window open in the afternoon.",
      "language": "en",
      "context": {
        "kind": "preference",
        "detail": "living-room window open",
        "time_pattern": "daily:afternoon"
      },
      "usage_count": 0,
      "confirmation_session_id": "simulated-context-confirmation-003",
      "sensitivity": "ordinary",
      "prompt_eligible": true
    }
  ]
}
```
