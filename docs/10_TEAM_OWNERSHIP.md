# 10｜团队分工与接口契约

## Team

- **Nick** — Agent Runtime、主要模型 workflow、最终技术集成。
- **Jiayi** — 软件后端、部署、存储和可靠性。
- **An** — 产品、患者交互、前端和 Demo 体验。

## Nick

负责：

- 状态机；
-ASR evidence fusion；
-uncertainty routing；
-Patient Memory retrieval logic；
-candidate generation；
-minimal clarification；
-candidate reranking；
-Quick Intent / Free Expression；
-authorization policy；
-verified learning；
-model evaluation。

交付：

- typed Core package；
-SessionViewModel；
-commands/events；
-provider interfaces；
-test fixtures；
-prompt schemas。

不负责最终视觉、云运维、数据库基础设施和 macOS 打包。

## Jiayi

负责：

- FastAPI gateway；
-model adapters；
-secrets；
-SQLite repository；
-patient isolation；
-session/event persistence；
-remote GPU；
-cloud deployment；
-retry/timeout/cache；
-mock backend；
-packaging support。

不决定候选语义、患者授权或患者交互。

## An

负责：

- PySide6 app；
-Patient Profile；
-audio interaction；
-progressive clarification；
-candidate cards；
-final review；
-Memory & Decision Trace；
-accessibility；
-Generic/Personalized；
-Receipt UI；
-Demo storytelling。

不负责 Prompt 调优、云部署、数据库事务和授权状态 mutation。

## Nick → An

```json
{
  "session_id": "session_001",
  "stage": "candidate_selection",
  "heard_content": {
    "stable": ["I", "don't", "tomorrow"],
    "uncertain": ["want"]
  },
  "memory_trace": {
    "verified_matches": 3,
    "acoustic_matches": 1,
    "unverified_used": 0
  },
  "candidates": [],
  "allowed_actions": [
    "select_candidate",
    "none_of_these",
    "go_back",
    "stop"
  ]
}
```

前端只渲染，不自行推断下一状态。

## An → Nick

```json
{
  "command": "select_candidate",
  "session_id": "session_001",
  "candidate_id": "A",
  "confirmation_method": "large_button"
}
```

前端不直接调用个人 TTS。

## Nick → Jiayi

```json
{
  "patient_id": "patient_001",
  "session_id": "session_001",
  "audio_ref": "...",
  "language_hint": "en",
  "context": {}
}
```

## Jiayi → Nick

```json
{
  "provider": "viaim",
  "status": "success",
  "transcript": "I don't tomorrow",
  "language": "en",
  "segments": [],
  "latency_ms": 740,
  "error": null
}
```

## Ownership matrix

| Feature | Owner | Reviewer |
|---|---|---|
| State machine | Nick | Jiayi |
| Model workflow | Nick | Jiayi |
| Memory retrieval | Nick | Jiayi |
| Candidate ranking | Nick | An |
| Authorization | Nick | Jiayi |
| Gateway | Jiayi | Nick |
| Database | Jiayi | Nick |
| Provider adapters | Jiayi | Nick |
| PySide6 UI | An | Nick |
| Patient flow | An | Nick |
| Trace visualization | An | Jiayi |
| Demo story | An | All |
| Final integration | Nick | All |

## Devices

Intel Mac：Nick 的 Runtime/LLM workflow 主开发机。  
M Mac 1：An 的 UI、Air 2 和主 Demo。  
M Mac 2：Jiayi 的服务、fallback、deployment 和备份 Demo。
