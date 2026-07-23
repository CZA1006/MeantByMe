# 01｜产品定位与设计原则

## 一句话定位

> **一个与患者绑定的可信表达 Agent：它从残缺语音和患者过往已确认 Memory 中提出可能表达，通过低负担的私密澄清，让患者本人确认后才使用其声音对外表达。**

英文：

> **A patient-bound communication agent that proposes possible expressions from fragmented speech and verified personal memory, then speaks in the patient’s voice only after explicit confirmation.**

## 目标用户

Hackathon MVP 聚焦：

> 认知和表达意图相对完整，但因运动性言语障碍、发音能力衰退或暂时失声而无法清晰、完整表达的人。

可能场景包括：

- ALS 和其他进行性运动性言语障碍；
- Parkinsonian speech；
- 神经损伤后的 dysarthria；
- 喉部手术后暂时或永久失声；
- 其他“知道想说什么，但说不清楚”的情况。

不宣称覆盖所有 aphasia。部分失语症涉及理解、词汇组织或认知，不只是发音问题。

## 核心矛盾

患者说：

```text
“I… don’t… tomorrow…”
```

可能对应：

- I don’t want to go tomorrow.
- I don’t want treatment tomorrow.
- I don’t want to meet them tomorrow.
- I don’t want to decide today.

AI 越擅长补全，越可能把合理推测伪装成患者真实意图。

因此项目不解决“如何永远猜对”，而解决：

> **当 Agent 不可避免会猜错时，如何让患者用最低负担安全地把表达带回正确方向。**

## 产品原则

### 1. Complete expression, never decide intention

Agent 可以保留片段、搜索历史、提出候选、生成澄清问题、合成确认后的声音。

Agent 不可以自动选择候选、把历史偏好视为当前决定、把护理者输入视为患者授权，或直接用患者声音输出推测内容。

### 2. Evidence, not authority

ASR、音频模型、Memory、当前场景、历史频率、LLM 建议和模型分数都只是证据。

只有患者确认才形成表达授权。

### 3. Progressive clarification

- 证据充分：确认完整句子；
- 部分充分：提供 2–3 个候选；
- 严重不足：先确认类别；
- 连续失败：切换到图片、固定短语、扫描或其他输入。

### 4. Preserve confirmed progress

猜错后不要求患者从头开始。系统锁定已经确认的词、类别、对象、否定和时间信息，只修改未确认部分。

### 5. Human-verified evolution

只允许：

```text
模型候选 → 患者确认 → Verified Memory → 后续检索和重排
```

不允许：

```text
模型猜测 → 自动写入长期 Memory → 下次强化同一错误
```

## 核心功能

1. Voice-first fragmented speech capture.
2. Multi-ASR evidence extraction.
3. Stable / uncertain fragment separation.
4. Patient-bound verified memory retrieval.
5. Progressive intent clarification.
6. Candidate expression generation.
7. Transparent candidate reranking.
8. Accessible patient confirmation.
9. Final private readback.
10. Deterministic personal-voice authorization.
11. Expression Receipt.
12. Verified memory writeback.
13. Generic vs Personalized comparison.
14. Mock, cloud, and fallback modes.

## 非目标

MVP 不提供：

- 诊断和治疗建议；
- 自动医疗决策；
- 临床准确率承诺；
- 无确认代替患者表达；
- 对“真实意图”的自动判定；
- 跨患者共享私人 Memory；
- 后台无监督自训练。

## 长期愿景

三层个性化：

### Fast personalization

个人词典、高频短语、场景 Memory、发音映射和候选重排。

### Personal acoustic memory

高频短语音频 prototype、当前病程阶段样本和个人声学 embedding。

### Verified model adaptation

累计足够 Gold 数据后训练个人 ASR Adapter / LoRA，使用影子模型评估、通过后升级并保留回滚。
