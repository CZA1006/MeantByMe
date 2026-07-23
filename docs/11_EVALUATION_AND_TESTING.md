# 11｜评测、测试与验收

## Evaluation philosophy

不要从模拟数据声称临床准确率。Hackathon 评测证明的是：

- 架构可行；
-猜错后可恢复；
-个性化有效影响排序；
-授权边界可靠；
-系统可稳定演示。

## Test set

准备 20–30 条英语和中文模拟样本：

- complete speech；
-fragmented speech；
-long pauses；
-repetition；
-low volume；
-missing predicate；
-missing object；
-conflicting ASR；
-known personal phrase；
-unknown phrase；
-high-risk expression。

每条标注：

```json
{
  "audio_id": "",
  "language": "",
  "intended_expression": "",
  "stable_fragments": [],
  "acceptable_candidates": [],
  "risk_level": "ordinary",
  "memory_expected_to_help": true
}
```

## Metrics

### Fragment Recall

实际说出的关键词被保留多少。

### Top-3 Intent Coverage

正确表达是否进入候选集合。对于 consent-first 系统，比 top-1 更合适。

### Unsupported Completion Rate

AI 新增内容中缺乏音频、上下文或 Verified Memory 支持的比例。

### Clarification Rounds

完成表达所需患者动作数。

### Time to Expression

从录音开始到授权输出的时间。

### Memory-assisted Rank Improvement

开启患者 Memory 前后，正确候选排名改善。

### Abstention Behavior

证据不足时是否选择澄清、降级或停止，而不是自信猜测。

### Unauthorized Voice Rate

目标：

```text
0
```

### Verified Memory Integrity

Gold Memory 中带明确患者确认证据的比例：

```text
100%
```

## Required tests

```text
unconfirmed candidate cannot speak
silence cannot confirm
timeout cannot confirm
caregiver cannot authorize
rejected candidate cannot enter Gold memory
LLM cannot skip final confirmation
L3 cannot speak by default
high-risk statement requires strict confirmation
cross-patient retrieval is blocked
duplicate event does not duplicate memory
TTS failure does not mark spoken
Memory failure falls back to generic mode
None of these preserves confirmed fragments
Go back reverses only reversible state
```

## Integration scenarios

### Golden path

```text
audio fixture
→ two ASR results
→ memory retrieval
→ candidates
→ confirmation
→ TTS
→ memory update
```

### High uncertainty

```text
weak evidence
→ category clarification
→ candidates
```

### Rejection

```text
None of these
→ narrower clarification or fallback
```

### Provider failure

```text
cloud ASR failure
→ fallback
→ reduced-evidence trace
```

### Security

```text
raw candidate passed directly to personal TTS
→ rejected by type and policy
```

## UI acceptance

- 所有关键动作键盘可达；
-Stop 和 None 可见；
-无自动选择；
-Trace 与 Runtime events 一致；
-个人声音状态可见；
-高风险提示可见；
-错误信息可理解；
-Mock mode 清楚标记。

## Performance targets

Hackathon 目标，不是临床承诺：

- streaming partial ideally < 2 s；
-final candidates ideally within 8–15 s；
-TTS start < 3 s after authorization；
-local memory retrieval < 300 ms；
-UI 全程响应；
-timeout 后会话可恢复。

## Demo checklist

- 模拟 profile 标签明确；
-real/mock 均测试；
-Air 2 和内置 mic 测试；
-second Mac 可运行；
-cached audio 存在；
-network loss 测试；
-rate limit 测试；
-Receipt 可生成；
-blocked path 可演示；
-repo 无 secrets。
