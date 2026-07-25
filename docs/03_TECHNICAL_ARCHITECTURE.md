# 03｜总体技术架构

> **Implementation status (2026-07-26):** `main` contains the deterministic
> mock core. Gateway and responsive Web BFF exist on `develop`/`frontend`.
> Swift/iOS headset code exists only on experimental `feature/earPhones`.
> See [STATUS.md](STATUS.md); paths below may describe the integration target.

## 架构原则

采用：

> **Deterministic shell + probabilistic services**

概率模型负责提供证据和候选；确定性 Runtime 负责流程、确认、授权、Memory 写入和安全边界。

## System overview

```text
┌───────────────────────────────────────────────┐
│ UI clients                                     │
│ Web BFF / planned desktop / experimental iOS  │
└───────────────────┬───────────────────────────┘
                    │ commands / view models
                    ▼
┌───────────────────────────────────────────────┐
│ MeantByMe Runtime                             │
│ state machine / uncertainty router            │
│ authorization / risk / memory policy          │
│ event bus / expression receipt                │
└───────────────┬───────────────────┬───────────┘
                │                   │
                ▼                   ▼
┌───────────────────────┐   ┌────────────────────────┐
│ Model providers       │   │ Patient services       │
│ viaim / second ASR    │   │ SQLite repository      │
│ text LLM / TTS        │   │ retrieval / ranker     │
│ local fallback        │   │ phrase prototypes      │
└─────────────┬─────────┘   └────────────┬───────────┘
              └────────────┬─────────────┘
                           ▼
           SQLite + encrypted audio + cache
```

## Client and deployment surfaces

No client surface is allowed to bypass the runtime authorization policy.
Web, desktop, and mobile are adapters around the same command/view-model
boundary, not independent consent implementations.

### Apple Silicon Macs

- PySide6 app；
- Core Audio；
- Air 2 采音和播放；
-本地 Memory、状态机、授权；
-可选 MLX Whisper fallback；
-arm64 `.app` 打包。

### Intel Mac

- Agent Runtime 核心开发；
- LLM workflow；
- SQLite；
- API 联调；
-测试；
- PySide6 逻辑验证。

不承担 MLX 和大型本地模型。

### Remote/cloud

- viaim 服务端凭据；
- StepFun API；
-第二路重型 ASR；
-可选远程 GPU；
-密钥保护、限流和健康检查。

### Web prototype

The branch-only Web implementation uses a server-side BFF. The browser receives
view state and sends explicit commands; it does not receive gateway credentials
or direct personal-TTS authority.

### iOS/headset experiment

The mobile branch uses SwiftUI, XcodeGen, 16 kHz PCM capture and a Viaim adapter.
It remains experimental until signed-device, disconnect, routing, vendor-license
and fallback checks pass. Headset presence or gestures are never consent.

## Process model

```text
Main process:
PySide6 event loop

Workers:
AudioCaptureWorker
ASRCoordinator
IntentWorkflowWorker
TTSWorker
EventPersistenceWorker

Optional services:
FastAPI secure gateway
Remote ASR service
```

UI 主线程不能执行网络等待、大型音频处理、模型推理或数据库批量扫描。

## Core modules

```text
core/
├── domain/
├── runtime/
├── policies/
├── personalization/
└── ports/
```

Core 必须与 PySide6、MLX、FastAPI 和供应商 SDK 解耦。

## Provider adapters

```text
adapters/
├── asr/
│   ├── viaim.py
│   ├── remote_qwen.py
│   ├── step_asr.py
│   ├── mlx_whisper.py
│   └── mock.py
├── intent/
│   ├── stepfun.py
│   ├── local_llm.py
│   ├── template.py
│   └── mock.py
├── tts/
│   ├── stepaudio.py
│   ├── system_voice.py
│   ├── cached.py
│   └── mock.py
└── embedding/
```

## Gateway

Secrets 不进入桌面程序。

```text
Desktop App
→ HTTPS / WebSocket
→ Secure Gateway
   ├── viaim proxy
   ├── StepFun proxy
   ├── session auth
   ├── rate limiting
   └── redacted logs
```

Patient Memory 默认留在本地，只传本次请求所需的最小检索结果。

## Runtime modes

### Mock

```yaml
asr: fixture
secondary_asr: fixture
intent: deterministic_fixture
tts: cached
memory: local_sqlite
```

### Cloud

```yaml
asr: viaim
secondary_asr: remote_qwen_or_step
intent: stepfun_text_llm
tts: stepaudio
memory: local_sqlite
```

### Fallback

```yaml
asr: mlx_whisper_or_whisper_cpp
secondary_asr: disabled
intent: template_or_local_small_llm
tts: system_voice_or_cache
memory: local_sqlite
```

## Failure degradation

| Failure | Degradation |
|---|---|
| viaim unavailable | local ASR or fixture |
| second ASR unavailable | single-source mode, reduced-evidence trace |
| LLM unavailable | rule-based categories and templates |
| TTS unavailable | system voice or cached audio |
| network unavailable | local mock/fallback |
| Memory unavailable | generic candidate mode |
| Air 2 unavailable | built-in microphone |
| no response | wait/switch/stop; never confirm |

## Packaging

Separate builds:

```text
MeantByMe-arm64.app
MeantByMe-x86_64.app
```

Do not attempt a universal binary during the hackathon.
