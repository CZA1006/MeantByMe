# Simulated User Persona: Lin Yue

This profile is used solely for MeantByMe simulation testing and contains no real patient data.

```meantbyme-profile
{
  "schema_version": 1,
  "simulated": true,
  "profile_id": "lin_yue_demo",
  "label": "Lin Yue (Simulated Test User)",
  "patient": {
    "patient_id": "lin_yue_demo",
    "display_name": "Lin Yue",
    "languages": ["en", "zh"],
    "default_language": "en"
  },
  "consent": {
    "scope": "demo_testing",
    "cloud_processing_allowed": true
  },
  "voice_consent": {
    "authorization_id": "voice-consent-lin-yue-demo",
    "consent_session_id": "voice-enrollment-lin-yue-demo",
    "voice_profile_id": "lin-yue-demo-voice"
  },
  "memories": [
    {
      "simulated": true,
      "id": "ctx-lin-yue-identity",
      "memory_type": "context",
      "verification_level": "gold",
      "source": "patient",
      "text": "I am Lin Yue, a 50-year-old woman living in New York City. I am cheerful, independent, practical, and resilient.",
      "language": "en",
      "context": {
        "kind": "personal_background",
        "tags": ["identity", "New York City", "personality"]
      },
      "usage_count": 1,
      "confirmation_session_id": "simulated-confirmation-lin-001",
      "sensitivity": "ordinary",
      "prompt_eligible": true
    },
    {
      "simulated": true,
      "id": "ctx-lin-yue-work",
      "memory_type": "context",
      "verification_level": "gold",
      "source": "patient",
      "text": "I am a senior backend software engineer with more than 20 years of experience, focusing on platform services, APIs, databases, and internal developer tools.",
      "language": "en",
      "context": {
        "kind": "work",
        "topic": "backend software engineering",
        "tags": ["programmer", "backend engineering", "platform services", "API"]
      },
      "usage_count": 2,
      "confirmation_session_id": "simulated-confirmation-lin-002",
      "sensitivity": "ordinary",
      "prompt_eligible": true
    },
    {
      "simulated": true,
      "id": "ctx-lin-yue-return-to-work",
      "memory_type": "context",
      "verification_level": "gold",
      "source": "patient",
      "text": "I recently returned to work after a stroke and rehabilitation. I currently work about 30 hours per week in a hybrid arrangement and reserve Wednesday for therapy and recovery.",
      "language": "en",
      "context": {
        "kind": "health_and_work",
        "tags": ["stroke survivor", "return to work", "hybrid work", "reduced hours"]
      },
      "usage_count": 1,
      "confirmation_session_id": "simulated-confirmation-lin-003",
      "sensitivity": "sensitive",
      "prompt_eligible": true
    },
    {
      "simulated": true,
      "id": "ctx-lin-yue-work-duties",
      "memory_type": "context",
      "verification_level": "gold",
      "source": "patient",
      "text": "My work includes maintaining backend services, designing APIs and database schemas, investigating production issues, writing tests and documentation, reviewing code, and mentoring a junior engineer.",
      "language": "en",
      "context": {
        "kind": "work",
        "topic": "job responsibilities",
        "tags": ["backend services", "code review", "technical documentation", "mentoring"]
      },
      "usage_count": 1,
      "confirmation_session_id": "simulated-confirmation-lin-004",
      "sensitivity": "ordinary",
      "prompt_eligible": true
    },
    {
      "simulated": true,
      "id": "ctx-lin-yue-work-support",
      "memory_type": "context",
      "verification_level": "gold",
      "source": "patient",
      "text": "At work, I benefit from agendas in advance, written action items, clear priorities, meeting-free focus time, asynchronous communication, and time to write down my thoughts before speaking.",
      "language": "en",
      "context": {
        "kind": "communication_preference",
        "topic": "workplace support",
        "tags": ["meeting agenda", "written communication", "focus time", "priorities"]
      },
      "usage_count": 2,
      "confirmation_session_id": "simulated-confirmation-lin-005",
      "sensitivity": "ordinary",
      "prompt_eligible": true
    },
    {
      "simulated": true,
      "id": "ctx-lin-yue-wednesday-therapy",
      "memory_type": "context",
      "verification_level": "gold",
      "source": "patient",
      "text": "Wednesday is my regular rehabilitation day. I usually keep the morning free from work and attend one or two outpatient therapy sessions in Manhattan in the afternoon.",
      "language": "en",
      "context": {
        "kind": "routine",
        "topic": "Wednesday therapy",
        "tags": ["Wednesday", "rehabilitation", "therapy appointment", "Manhattan"]
      },
      "usage_count": 2,
      "confirmation_session_id": "simulated-confirmation-lin-006",
      "sensitivity": "sensitive",
      "prompt_eligible": true
    },
    {
      "simulated": true,
      "id": "ctx-lin-yue-therapy-types",
      "memory_type": "context",
      "verification_level": "gold",
      "source": "patient",
      "text": "My care plan may include weekly speech-language and cognitive therapy for 45 to 60 minutes, occupational therapy every other week for 45 to 60 minutes, psychotherapy every other week for about 50 minutes, and medical follow-ups every six to twelve weeks.",
      "language": "en",
      "context": {
        "kind": "healthcare",
        "topic": "rehabilitation plan",
        "tags": ["speech-language therapy", "occupational therapy", "psychotherapy", "follow-up"]
      },
      "usage_count": 1,
      "confirmation_session_id": "simulated-confirmation-lin-007",
      "sensitivity": "sensitive",
      "prompt_eligible": true
    },
    {
      "simulated": true,
      "id": "ctx-lin-yue-therapy-topics",
      "memory_type": "context",
      "verification_level": "gold",
      "source": "patient",
      "text": "In therapy, I work on organizing language in meetings, recognizing fatigue, breaking complex tasks into smaller steps, requesting workplace support, managing frustration, maintaining family boundaries, and gradually returning to outdoor and community activities.",
      "language": "en",
      "context": {
        "kind": "healthcare",
        "topic": "therapy topics",
        "tags": ["communication", "fatigue", "task planning", "family boundaries"]
      },
      "usage_count": 1,
      "confirmation_session_id": "simulated-confirmation-lin-008",
      "sensitivity": "sensitive",
      "prompt_eligible": true
    },
    {
      "simulated": true,
      "id": "ctx-lin-yue-appointment-preference",
      "memory_type": "context",
      "verification_level": "gold",
      "source": "patient",
      "text": "I prefer therapy around 2:00 p.m. on Wednesdays. I need a break between consecutive sessions, at least 24 hours of notice for waitlist openings, and about 30 minutes of quiet recovery after treatment.",
      "language": "en",
      "context": {
        "kind": "appointment_preference",
        "tags": ["Wednesday afternoon", "waitlist", "break", "recovery time"]
      },
      "usage_count": 1,
      "confirmation_session_id": "simulated-confirmation-lin-009",
      "sensitivity": "sensitive",
      "prompt_eligible": true
    },
    {
      "simulated": true,
      "id": "ctx-lin-yue-husband",
      "memory_type": "context",
      "verification_level": "gold",
      "source": "patient",
      "text": "My husband David is 53. We have been married for nearly 30 years. He helps with transportation, appointments, and household tasks, but I want him to ask what kind of help I need before taking over.",
      "language": "en",
      "context": {
        "kind": "relationship",
        "topic": "husband",
        "tags": ["David", "husband", "caregiver", "autonomy"]
      },
      "usage_count": 2,
      "confirmation_session_id": "simulated-confirmation-lin-010",
      "sensitivity": "ordinary",
      "prompt_eligible": true
    },
    {
      "simulated": true,
      "id": "ctx-lin-yue-daughter",
      "memory_type": "context",
      "verification_level": "gold",
      "source": "patient",
      "text": "My daughter Maya is 26, lives in Brooklyn, and works in digital media. We are close, speak two or three times a week, and meet for a meal or walk about every other week.",
      "language": "en",
      "context": {
        "kind": "relationship",
        "topic": "daughter",
        "tags": ["Maya", "daughter", "Brooklyn", "family"]
      },
      "usage_count": 2,
      "confirmation_session_id": "simulated-confirmation-lin-011",
      "sensitivity": "ordinary",
      "prompt_eligible": true
    },
    {
      "simulated": true,
      "id": "ctx-lin-yue-mother",
      "memory_type": "context",
      "verification_level": "gold",
      "source": "patient",
      "text": "My 78-year-old mother lives independently in Queens. I call her at least twice a week and try to visit once a month.",
      "language": "en",
      "context": {
        "kind": "relationship",
        "topic": "mother",
        "tags": ["mother", "Queens", "family contact"]
      },
      "usage_count": 1,
      "confirmation_session_id": "simulated-confirmation-lin-012",
      "sensitivity": "ordinary",
      "prompt_eligible": true
    },
    {
      "simulated": true,
      "id": "ctx-lin-yue-interests",
      "memory_type": "context",
      "verification_level": "gold",
      "source": "patient",
      "text": "Before my stroke, I enjoyed hiking. I also enjoy technology community events and occasionally participate in hackathons.",
      "language": "en",
      "context": {
        "kind": "interest",
        "tags": ["hiking", "hackathon", "technology community"]
      },
      "usage_count": 2,
      "confirmation_session_id": "simulated-confirmation-lin-013",
      "sensitivity": "ordinary",
      "prompt_eligible": true
    },
    {
      "simulated": true,
      "id": "ctx-lin-yue-meantbyme",
      "memory_type": "context",
      "verification_level": "gold",
      "source": "patient",
      "text": "I am developing MeantByMe, an open-source project that helps stroke survivors organize appointment questions, action items, energy notes, workplace communication, and selectively shared family updates.",
      "language": "en",
      "context": {
        "kind": "personal_project",
        "topic": "MeantByMe",
        "tags": ["MeantByMe", "open source", "stroke survivors", "communication support"]
      },
      "usage_count": 3,
      "confirmation_session_id": "simulated-confirmation-lin-014",
      "sensitivity": "ordinary",
      "prompt_eligible": true
    },
    {
      "simulated": true,
      "id": "ctx-lin-yue-project-boundary",
      "memory_type": "context",
      "verification_level": "gold",
      "source": "patient",
      "text": "I usually spend two to three hours per week on MeantByMe and limit each session to 90 minutes, with at least one full day each week away from the project.",
      "language": "en",
      "context": {
        "kind": "routine",
        "topic": "personal project boundaries",
        "tags": ["MeantByMe", "energy management", "time limit", "rest"]
      },
      "usage_count": 1,
      "confirmation_session_id": "simulated-confirmation-lin-015",
      "sensitivity": "ordinary",
      "prompt_eligible": true
    },
    {
      "simulated": true,
      "id": "ctx-lin-yue-privacy",
      "memory_type": "context",
      "verification_level": "gold",
      "source": "patient",
      "text": "I want to decide who can see my health information. David may see appointment times and emergency contact information, but my complete therapy notes are not shared by default.",
      "language": "en",
      "context": {
        "kind": "privacy_preference",
        "tags": ["medical privacy", "selective sharing", "consent", "autonomy"]
      },
      "usage_count": 2,
      "confirmation_session_id": "simulated-confirmation-lin-016",
      "sensitivity": "sensitive",
      "prompt_eligible": true
    },
    {
      "simulated": true,
      "id": "ctx-lin-yue-fatigue-caregiver",
      "memory_type": "context",
      "verification_level": "silver",
      "source": "caregiver",
      "text": "David has observed that Lin needs more quiet recovery time after two consecutive therapy sessions.",
      "language": "en",
      "context": {
        "kind": "caregiver_observation",
        "tags": ["fatigue", "therapy", "recovery time"]
      },
      "usage_count": 0,
      "confirmation_session_id": null,
      "sensitivity": "sensitive",
      "prompt_eligible": true
    },
    {
      "simulated": true,
      "id": "ctx-lin-yue-cognitive-assumption",
      "memory_type": "context",
      "verification_level": "unverified",
      "source": "research_fixture",
      "text": "A research assumption suggests that when Lin is tired, word retrieval may slow and interruptions may make it harder for her to resume a complex task.",
      "language": "en",
      "context": {
        "kind": "research_assumption",
        "tags": ["word retrieval", "interruptions", "fatigue", "cognitive load"]
      },
      "usage_count": 0,
      "confirmation_session_id": null,
      "sensitivity": "sensitive",
      "prompt_eligible": false
    },
    {
      "simulated": true,
      "id": "ctx-lin-yue-future-project-assumption",
      "memory_type": "context",
      "verification_level": "unverified",
      "source": "research_fixture",
      "text": "It has not yet been verified whether MeantByMe will remain a personal tool, become an open-source community project, or develop into a formal product.",
      "language": "en",
      "context": {
        "kind": "research_assumption",
        "topic": "MeantByMe future",
        "tags": ["MeantByMe", "future plan", "unverified"]
      },
      "usage_count": 0,
      "confirmation_session_id": null,
      "sensitivity": "ordinary",
      "prompt_eligible": false
    }
  ]
}
```

## Testing Note

This file contains only structured, simulated background information. It intentionally excludes any expected full answer for a specific audio or expression test.
