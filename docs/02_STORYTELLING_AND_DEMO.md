# 02｜Storytelling 与 Demo

> **Demo disclosure:** All people, profiles, audio, memory, expected answers and
> receipts used in the public demo must be simulated or appropriately licensed.
> A successful demo is evidence of the designed interaction and safety contract,
> not clinical efficacy.

## Demo 要证明什么

1. Agent 能承认证据不足；
2. Agent 能使用患者已确认 Memory 缩小范围；
3. Agent 能通过低负担澄清恢复表达；
4. AI 补全部分始终可见；
5. 未确认内容不能使用本人声音；
6. 只有患者明确确认且满足写入策略的表达才会进入 Gold Memory。

## 开场

> Imagine knowing exactly what you want to say, but only being able to speak a few fragments. AI can complete the sentence—but how do we know the completed sentence is still your meaning?

中文：

> 你非常清楚自己想说什么，却只能说出几个片段。AI 可以补全一句话，但我们怎么确定，补全后的意思仍然属于你？

## Demo Profile

必须标记：

> **Simulated verified patient profile for demonstration.**

示例：

```yaml
patient:
  id: david_demo
  display_name: David
  languages: [English, Mandarin]
  confirmation_mode: large_button
  private_playback: iFLYBUDS Air 2
  verified_phrases:
    - text: I don't want to go tomorrow.
      confirmations: 2
      context: planning
    - text: Move my appointment to tomorrow.
      confirmations: 1
      context: schedule
```

## 主 Demo

目标表达：

```text
I don’t want to go tomorrow.
```

患者输入：

```text
I… don’t… tomorrow…
```

### 1. Capture

UI：

```text
Listening…
You can pause. Press “I’m done” when finished.
```

Trace：

```text
AUDIO_CAPTURED
duration: 4.8 s
long pauses: 2
manual completion: yes
```

### 2. Evidence

```text
ASR A: I don't tomorrow
ASR B: I don't want tomorrow
```

对齐：

```text
Stable:
I / don’t / tomorrow

Uncertain:
want

Missing:
action or object
```

### 3. Memory retrieval

```text
MEMORY_SEARCH_STARTED
scope: verified expressions only

3 verified memories found
0 unverified memories used
```

### 4. Category clarification

```text
Is this about:
[A plan]
[Treatment]
[Meeting someone]
[Something else]
```

患者选 A plan。

### 5. Candidates

```text
A. I don’t want to go tomorrow.
B. I want to move the plan to tomorrow.
C. I don’t want to decide today.
D. None of these.
```

Candidate A 的可验证排序理由：

```text
strong fragment support
matched verified patient phrase
same planning context
recently confirmed
```

### 6. Final review

患者选 A 后展示：

```text
Patient speech:
I / don’t / tomorrow

AI-assisted completion:
want to go

Memory support:
2 previous patient confirmations
```

耳机私密读回完整句子，再请求最终确认。

### 7. Authorization

```text
before:
L2 · awaiting confirmation
personal voice: blocked

after:
L2 · patient confirmed
personal voice: authorized for this expression only
```

### 8. Verified learning

```text
VERIFIED_MEMORY_WRITTEN
usage count: 2 → 3
new acoustic example: added
model weights: unchanged
```

## Blocked-path demo

未确认候选尝试进入个人 TTS：

```text
BLOCKED
Reason: AI-assisted content has not been confirmed by the patient.
```

## Generic vs Personalized

Generic 中正确候选排第三；开启患者 Memory 后排第一。

Trace：

```text
Candidate A moved from rank 3 to rank 1
based on 2 verified patient expressions.
```

## 结尾

> MeantByMe does not try to read the patient’s mind. It helps the patient recover control of the conversation.

> The system does not evolve from its own guesses. It evolves only from expressions verified by the patient.
