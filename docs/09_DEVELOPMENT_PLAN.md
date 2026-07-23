# 09｜三天开发计划

## Freeze before coding

冻结：

- 主 Demo 句；
-blocked-path 句；
-Demo Patient；
-state machine；
-API schemas；
-primary model choices；
-P0 confirmation；
-Mock fixtures；
-team ownership；
-repo layout。

## Day 0 — two-hour spikes

验证：

1. Air 2 在 macOS 的输入和输出；
2. 录制 PCM/WAV；
3. viaim credentials 和 latency；
4. StepFun structured output；
5. StepAudio TTS；
6. second ASR viability；
7. PySide6 microphone permission；
8. 一条 mock end-to-end fixture。

不能快速验证的组件立即降级。

## Day 1 — deterministic golden path

### Nick

- domain schemas；
-state machine；
-command handler；
-provider protocols；
-mock providers；
-authorization policy；
-candidate schema。

### Jiayi

- FastAPI gateway；
-SQLite；
-session/event persistence；
-viaim/StepFun skeleton；
-mock endpoints；
-secret config。

### An

- PySide6 shell；
-listening；
-candidate；
-final review；
-static Trace；
-large buttons。

### Exit

```text
fixture audio
→ mock ASR
→ mock memory
→ candidates
→ confirmation
→ authorization
→ cached voice
→ memory write
```

## Day 2 — real models and personalization

### Nick

- transcript alignment；
-uncertainty router；
-memory retrieval input；
-LLM prompt validation；
-ranker；
-Quick Intent / Free Expression。

### Jiayi

- real viaim；
-real StepFun LLM/TTS；
-second ASR or fallback；
-timeout/retry；
-event streaming；
-patient-scoped storage。

### An

- dynamic Trace；
-category clarification；
-None of these；
-Generic/Personalized；
-Memory update；
-profile/device screens。

### Exit

```text
real mic
→ ASR
→ memory
→ candidate
→ confirmation
→ TTS
```

## Day 3 — stability and presentation

### Nick

- freeze prompts；
-20–30 samples；
-fix unsupported completion；
-safety tests；
-freeze demo。

### Jiayi

- deploy；
-cache；
-offline mock；
-arm64 packaging support；
-second Mac deployment；
-backup DB/audio。

### An

- visual polish；
-error states；
-English demo；
-backup video；
-track-specific presentation。

## Do not do on Day 3

- 新模型；
-LangGraph；
-ASR 微调；
-临时安装 CosyVoice；
-眼动；
-电话注入；
-云向量数据库；
-更换前端框架。

## Integration

每天至少合并两次：午饭前和结束前。每次合并后运行完整 mock golden path。

## Branches

```text
main
develop
nick/runtime
jiayi/backend
an/frontend
```

## Demo-ready

- arm64 app 可打开；
-麦克风权限正常；
-Air 2 或内置麦克风正常；
-mock 一键启动；
-real mode 可配置；
-golden path 完成；
-blocked path 完成；
-Trace 更新；
-Memory 更新；
-Unauthorized Voice Rate = 0；
-second Mac 可备份；
-备用视频完成。
