# 05｜Patient Memory 与自进化

## 定义

MeantByMe 的自进化是：

> **Human-verified continual personalization**

系统不从自己的猜测中学习，只从患者本人确认过的表达中更新个人化 Memory、排序、短语原型和未来训练数据。

## Memory types

> **注(见 [DECISIONS.md](../DECISIONS.md) D2):** `memory_type` 枚举为 **5 种**:`semantic / acoustic / context / language / interaction`。下文的 **Intent Memory** 映射到 `semantic`;**Authorization** 不是一种记忆,单独存入 `authorizations` 表,不进入检索与排序。

### Acoustic Memory

原始音频、设备、语言、语音阶段、ASR 输出、确认文本、embedding 和质量信息。

### Language Memory

家人姓名、地点、常用词、语言偏好、个人措辞和发音词典。

### Intent Memory（`memory_type = semantic`）

高频需求、确认表达、上下文、频率、最近使用和拒绝历史。

### Context Memory

位置、人物、活动、日程和护理者上下文。护理者上下文不等于患者确认。

### Interaction Memory

确认方式、拒绝候选、澄清轮数、选项数量、扫描速度和无障碍设置。

### Authorization（单独 `authorizations` 表,非 `memory_type`）

voice profile、授权范围、有效期、输出渠道和撤销状态。授权是状态而非语义证据,不参与检索/排序。

## Verification levels

Verification level is safety semantics, not a display preference. It must not be
collapsed into a generic `trusted` flag:

```text
patient-confirmed Gold > caregiver-assisted Silver > Unverified
```

Equal text does not imply equal authority. Gold and Silver may both inform
ordering, but their source and weight remain distinguishable. See D17, D19,
D20 and D21 in [DECISIONS.md](../DECISIONS.md).

### Gold

患者明确确认。可用于检索、排序、prototype 和经独立审核的未来模型适配。
Profile import、最终表达确认以外的系统动作、AI 推断和护理者录入不能创建 Gold。

### Silver

护理协助或外部验证，但患者确认不完整。必须单独标记。

### Unverified

ASR、LLM 猜测、未完成会话或超时。只可在临时 session 使用。

`feature/earPhones` 中 Gold/Silver 同权的 branch-local 提案已重命名为
`EXP-MEM-01` 且未采纳。动态反馈可以继续研究，但不得抹去来源、隐式创建
Gold、跨 patient scope 或扩大个人声音授权。

## Immediate learning

```text
speech attempt
→ candidate selection
→ final confirmation
→ output
→ verified memory update
```

最终确认只允许写入本次被确认的表达映射，不自动证明新的稳定人物事实。稳定
profile/context 事实需要独立、可审计的确认来源。

立即更新：

- 使用次数；
-最近时间；
-场景关联；
-新音频样本；
-排名统计；
-发音映射证据；
-拒绝记录。

模型权重不变。

## Retrieval pipeline

```text
current fragments
+ language
+ context
+ patient_id
→ patient metadata filter
→ keyword / phonetic search
→ semantic search
→ optional acoustic match
→ verified-only reranking
→ top memory evidence
```

必须先按 `patient_id` 过滤，再做相似度检索。

## Memory may / may not

Memory 可以：

- 重排候选；
-补充姓名地点；
-减少澄清轮数；
-适配语言和选项数量。

Memory 不可以：

- 自动选择；
-跳过确认；
-授权声音；
-把过去选择变成当前同意；
-把护理者解释变成患者意图。

## Progressive disease

区分：

### Voice Identity Archive

早期清晰语音用于 TTS 身份延续。

### Current Speech Adaptation Set

近期残余语音用于理解患者现在怎么说。

近期样本声学权重更高，早期样本不应主导当前识别。

## Long-term model adaptation

触发示例：

```text
50–100 new Gold samples
or recent performance decline
or explicit review
```

流程：

```text
production model A
→ verified snapshot
→ candidate adapter B
→ held-out evaluation
→ safety regression
→ shadow mode
→ reviewed promotion
→ rollback retained
```

## Three-day scope

P0：

- Patient Profile；
-预置 verified demo memories；
-SQLite；
-关键词/简单语义检索；
-候选重排；
-确认后写回；
-Memory Trace；
-Generic / Personalized 切换。

P1：

-本地 embedding；
-acoustic prototype；
-Memory 管理；
-导出和删除；
-语音阶段权重。

不做在线 LoRA、云向量数据库、后台自训练或病程自动诊断。
