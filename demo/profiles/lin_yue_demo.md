# 林悦：中风后重返岗位的程序员

本文件由虚构用户画像整理而来，只用于 MeantByMe 模拟测试。叙事内容不会被
直接发送给模型；运行时只读取下方经过逐条来源、验证级别和用途标注的 JSON。
预期表达不会写入画像，以免把未知意图补全测试变成答案召回测试。

```meantbyme-profile
{
  "schema_version": 1,
  "simulated": true,
  "profile_id": "lin_yue_demo",
  "label": "林悦",
  "patient": {
    "patient_id": "lin_yue_demo",
    "display_name": "林悦",
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
    "voice_profile_id": "cixingnansheng"
  },
  "memories": [
    {
      "simulated": true,
      "id": "ctx-lin-yue-backend-work",
      "memory_type": "context",
      "verification_level": "gold",
      "source": "patient",
      "text": "She is a senior backend engineer returning to work after a stroke.",
      "language": "en",
      "context": {
        "kind": "work",
        "topic": "backend engineering",
        "tags": ["programmer", "backend", "work", "stroke"]
      },
      "usage_count": 1,
      "confirmation_session_id": "simulated-lin-yue-confirmation-001",
      "sensitivity": "sensitive",
      "prompt_eligible": true
    },
    {
      "simulated": true,
      "id": "ctx-lin-yue-meantbyme-project",
      "memory_type": "context",
      "verification_level": "gold",
      "source": "patient",
      "text": "She is building MeantByMe to help stroke survivors communicate.",
      "language": "en",
      "context": {
        "kind": "project",
        "project": "MeantByMe",
        "tags": ["communication", "stroke survivors", "assistive technology"]
      },
      "usage_count": 3,
      "confirmation_session_id": "simulated-lin-yue-confirmation-002",
      "sensitivity": "ordinary",
      "prompt_eligible": true
    },
    {
      "simulated": true,
      "id": "ctx-lin-yue-hackathons",
      "memory_type": "context",
      "verification_level": "gold",
      "source": "patient",
      "text": "She participates in technical communities and hackathons.",
      "language": "en",
      "context": {
        "kind": "interest",
        "tags": ["technical community", "hackathon", "project presentation"]
      },
      "usage_count": 2,
      "confirmation_session_id": "simulated-lin-yue-confirmation-003",
      "sensitivity": "ordinary",
      "prompt_eligible": true
    },
    {
      "simulated": true,
      "id": "ctx-lin-yue-communication-style",
      "memory_type": "context",
      "verification_level": "gold",
      "source": "patient",
      "text": "She prefers clear written communication and explicit confirmation.",
      "language": "en",
      "context": {
        "kind": "interaction",
        "tags": ["written communication", "confirmation", "autonomy", "privacy"]
      },
      "usage_count": 2,
      "confirmation_session_id": "simulated-lin-yue-confirmation-004",
      "sensitivity": "ordinary",
      "prompt_eligible": true
    },
    {
      "simulated": true,
      "id": "ctx-lin-yue-treatment-wednesday",
      "memory_type": "context",
      "verification_level": "gold",
      "source": "patient",
      "text": "Wednesday is normally reserved for treatment and recovery.",
      "language": "en",
      "context": {
        "kind": "routine",
        "time_pattern": "weekly:wednesday",
        "tags": ["treatment", "recovery", "schedule"]
      },
      "usage_count": 1,
      "confirmation_session_id": "simulated-lin-yue-confirmation-005",
      "sensitivity": "sensitive",
      "prompt_eligible": true
    },
    {
      "simulated": true,
      "id": "ctx-lin-yue-fatigue",
      "memory_type": "context",
      "verification_level": "gold",
      "source": "user_input",
      "text": "Speech becomes harder when she is tired.",
      "language": "en",
      "context": {
        "kind": "communication_pattern",
        "tags": ["fatigue", "speech"]
      },
      "usage_count": 0,
      "confirmation_session_id": "simulated-lin-yue-confirmation-006",
      "sensitivity": "sensitive",
      "prompt_eligible": true
    },
    {
      "simulated": true,
      "id": "research-lin-yue-disease-progression",
      "memory_type": "context",
      "verification_level": "unverified",
      "source": "research_fixture",
      "text": "Research notes speculate about future communication changes.",
      "language": "en",
      "context": {"kind": "research_assumption"},
      "usage_count": 0,
      "confirmation_session_id": null,
      "sensitivity": "sensitive",
      "prompt_eligible": false
    }
  ]
}
```

## Evaluation note

The expected sentence for the hackathon recording belongs in an evaluator-only
sidecar. It is deliberately absent from this profile.
