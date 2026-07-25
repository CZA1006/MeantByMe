# 07｜模型与服务集成

> **Current status:** Mock providers are canonical on `main`; gateway/cloud
> adapters are branch-only on `develop`/`frontend`; the Viaim Swift headset SDK
> integration is experimental on `feature/earPhones`.

## MVP decision

三天内不微调主模型。采用成熟 API、一个本地 fallback、Patient Memory 和确定性授权。

No provider is authoritative. An ASR, LLM, TTS, embedding model, headset SDK,
or QA model can return evidence or candidates but cannot select, confirm,
authorize, or write Gold memory.

## Final chain

```text
iFLYBUDS Air 2
→ macOS audio capture
→ primary streaming ASR
→ secondary ASR evidence
→ transcript alignment
→ verified patient memory retrieval
→ uncertainty router
→ text LLM candidate generation
→ personal reranking
→ patient confirmation
→ deterministic authorization
→ personal-voice TTS
→ verified memory update
```

## Primary ASR — viaim

用途：

- 实时 partial/final transcript；
-耳机生态；
-Voice First 赛道。

官方：

- https://pypi.org/project/viaim-ai-open/
- https://open.viaim.cn/tacit/portal/home

公开 SDK 重点：

- Python 服务端；
-WebSocket streaming；
-16 kHz mono signed int16 PCM；
-secret 放可信服务端。

风险：

- SDK 早期；
-耳机触控回调未必开放；
-必须保留标准蓝牙音频 fallback。

The iOS experiment references a local vendor Swift package that is not included
in this repository. Before release, pin its version, document its license and
privacy behavior, provide a protocol-level mock, and verify signed arm64 devices.

## Secondary ASR

初始 benchmark 后二选一。

### Option A — Qwen3-ASR remote

- 多语言第二意见；
-完整短音频转写；
-未来微调基座；
-部署在远程 GPU，Mac 通过 HTTP 调用。

官方：

- https://github.com/QwenLM/Qwen3-ASR
- https://huggingface.co/Qwen/Qwen3-ASR-1.7B

### Option B — StepAudio ASR

- 快速云端接入；
-和 StepFun 生态统一；
-必须先测试残缺和异常语音；
-不能从通用 ASR benchmark 推导医疗场景性能。

## Local fallback

Apple Silicon：

- MLX Whisper
- https://github.com/ml-explore/mlx
- https://github.com/ml-explore/mlx-examples/tree/main/whisper

Cross-platform：

- whisper.cpp
- https://github.com/ggml-org/whisper.cpp

Intel Mac 只用小模型处理短音频，不作为性能基准。

## Transcript alignment

输入：

```json
{
  "primary": "I don't tomorrow",
  "secondary": "I don't want tomorrow"
}
```

输出：

```json
{
  "stable_fragments": ["I", "don't", "tomorrow"],
  "conflicts": ["want"],
  "missing_slots": ["action_or_object"],
  "evidence_band": "high_uncertainty"
}
```

MVP 使用 token/string alignment 和规则，不做复杂声学融合。

## Intent LLM

主模型使用赛事可用的 StepFun 文本 LLM。

官方：

- https://platform.stepfun.com/docs/zh/guides/models/overview
- https://platform.stepfun.com/docs/zh/api-reference/tool-call

职责：

- 结构化候选；
-一个最小澄清问题；
-标记 AI-added span；
-风险分类（仅建议;见 [DECISIONS.md](../DECISIONS.md) D5，高风险闸门由确定性规则拥有,LLM 只能加严不能放松）。

不得：

-授权声音；
-写 Memory；
-选择候选；
-调用外部动作。

要求：

- JSON Schema；
-Pydantic validation；
-timeout/retry；
-template fallback；
-output sanitization。

## TTS

主方案 StepAudio TTS。

官方：

- https://platform.stepfun.com/docs/zh/guides/models/stepaudio-2.5-tts
- https://platform.stepfun.com/docs/zh/api-reference/audio/create-voice
- https://platform.stepfun.com/docs/zh/api-reference/audio/create-audio

规则：

- 候选使用中性私密声音；
-个人声音只用于确认后的最终表达；
-授权默认仅当前 expression；
-Receipt 记录授权；
-支持撤销。

Fallback：

-缓存的已批准音频；
-系统声音；
-失败时明确显示，不伪装成功。

## Embedding / retrieval

P0：

- keyword；
-phonetic normalization；
-string similarity；
-可用时加小型本地 embedding。

P1：

- Qwen3-Embedding: https://github.com/QwenLM/Qwen3-Embedding
- FAISS: https://github.com/facebookresearch/faiss

单患者数据量小，不需要云向量数据库。

## Research systems

### Re-Sonance

支持 ASR → LLM → TTS 级联思路，但不证明严重残缺语音可被可靠恢复。MeantByMe 增加多候选、患者确认、授权和 Memory。

### HeyJay!

适合未来英语 Quick Intent 和异常 ASR adapter。它是数据集，不是即插即用模型，也不是开放式残缺表达数据。

### Speech Accessibility Project

证明特殊数据和适配可以显著改善异常 ASR，但获奖 checkpoint 不等于可直接调用的多语言意图模型。

## Fine-tuning roadmap

比赛后：

1. 收集患者同意的 verified samples；
2. speaker-independent evaluation；
3. 对 Whisper/Qwen/SenseVoice 做 adapter；
4. 训练 Quick Intent；
5. 训练患者个人 adapter；
6. 与 production baseline 比较；
7. shadow evaluation；
8. 可回滚部署。
