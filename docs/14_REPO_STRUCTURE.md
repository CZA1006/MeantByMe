# 14｜Repository Structure

> **注:** SQLite 建表语句与安全约束(Gold CHECK、`patient_id` 外键、幂等主键、`authorizations` 拆表)见 [DECISIONS.md](../DECISIONS.md) D4。

```text
MeantByMe/
├── README.md
├── AGENTS.md
├── pyproject.toml
├── .env.example
├── .gitignore
├── docs/
├── src/meantbyme/
│   ├── core/
│   │   ├── domain/
│   │   ├── runtime/
│   │   ├── policies/
│   │   ├── personalization/
│   │   └── ports/
│   ├── adapters/
│   │   ├── asr/
│   │   ├── intent/
│   │   ├── tts/
│   │   ├── embedding/
│   │   └── storage/
│   ├── app/
│   │   └── pyside/
│   ├── gateway_client/
│   └── config/
├── services/
│   ├── gateway/
│   └── remote_asr/
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── safety/
│   └── fixtures/
├── demo/
│   ├── profiles/
│   ├── audio/
│   ├── fixtures/
│   └── scripts/
├── scripts/
└── artifacts/
```

## Core rule

`core/` 与平台和供应商无关。

禁止：

```text
PySide6
mlx
sounddevice
FastAPI
provider SDKs
```

## Adapter rule

所有外部数据转换成共享 schema。

```text
viaim payload
→ ViaimASRAdapter
→ ASRResult
```

## UI rule

UI 发送 command、接收 view model。

UI 不：

- 直接调用个人 TTS；
-写 Verified Memory；
-决定状态转换；
-隐藏风险；
-自动选择候选。

## Demo fixtures

必须有确定性 fixture：

- golden path；
-high uncertainty；
-None of these；
-blocked TTS；
-memory reranking；
-provider timeout。

禁止提交真实患者数据。

## Suggested config

```yaml
runtime:
  mode: mock

providers:
  primary_asr: mock
  secondary_asr: mock
  intent: mock
  tts: cached

features:
  memory_trace: true
  personalized_ranking: true
  head_gesture: false
  earbud_touch: false
```

## Initial implementation order

1. domain models；
2. state machine；
3. mock providers；
4. command handler；
5. SQLite；
6. PySide6 mock flow；
7. authorization tests；
8. real ASR；
9. real LLM；
10. real TTS；
11. packaging。
