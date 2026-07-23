# 06｜患者交互与无障碍

## Goal

> **用最少的确认动作，排除最多的错误候选，并保留已经确认的表达进度。**

## Two-interface design

### Patient UI

- 一屏一个决定；
-大按钮和大字体；
-高对比；
-最少文字；
-耳机私密播放；
-Stop / Back / None of these 始终可见。

### Memory & Decision Trace

面向 Demo、护理者和开发者，展示：

- ASR 证据；
-Memory 检索；
-排序理由；
-状态变化；
-授权状态；
-Memory 更新。

不展示自由文本 Chain of Thought，只展示可核验事件。

## Communication calibration

患者绑定时设置：

- Yes 动作；
-No 动作；
-Stop 动作；
-呈现方式；
-每屏选项数；
-重复次数；
-扫描速度；
-替代输入。

用已知问题验证 Yes/No。无响应永远不是同意。

## Confirmation ladder

### Level 0 — Universal controls

```text
Yes / No / None / Stop / Back / Repeat
I’m not finished / Switch input / Request help
```

### Level 1 — Confirm heard content

```text
I heard:
“I don’t … tomorrow”

Is that part correct?
[Yes] [No]
```

### Level 2 — Confirm category

```text
[A plan]
[Your condition]
[Asking someone for help]
[Something else]
```

### Level 3 — Select candidate

2–3 candidates + None of these.

### Level 4 — Final review

展示患者原话、AI 补全、Memory 支持和风险，再耳机私密读回和最终授权。

## Wrong-guess recovery

### None of these

不直接再生成三句长文本，而是问一个高信息区分问题或切换输入。

### Partial correction

锁定正确片段，只修改 AI-added span。

### Two failed rounds

最多两轮候选后，切换到：

- Quick Intent；
-主题板；
-图片；
-字母扫描；
-关键词重试；
-护理者辅助扫描；
-手动输入。

### No response

继续等待、换确认方式、暂停或请求帮助；不能默认第一项。

## Input modes

P0：

- 大按钮；
-键盘方向键和空格；
-耳机私密播放；
-内置麦克风 fallback。

P1：

-听觉自动扫描；
-头部动作；
-官方 SDK 支持时的耳机触控；
-单开关。

P2：

-眼动；
-专业 AAC 硬件；
-EMG / BCI。

## Earbud role

Air 2 用于：

- wearable capture；
-private candidate playback；
-private final readback；
-低摩擦交互。

耳机连接不是身份或同意。P0 必须用标准蓝牙音频 + 屏幕确认运行。

## High-risk content

医疗、法律、支付和重大关系表达要求：

1. 候选选择；
2. 完整私密读回；
3. 显式最终确认；
4. 必要时第二确认方式；
5. 高风险标签；
6. 完整 Receipt。

MVP 不自动执行外部动作。

## Caregiver

护理者可以提供上下文，但必须显示：

```text
Caregiver-provided context
Not patient-confirmed
Cannot authorize voice
```

## Accessibility requirements

- 大交互目标；
-键盘可达；
-不只用颜色表达状态；
-清晰 focus；
-可重复播放；
-可调 timeout；
-不自动选择；
-减少动画；
-错误信息使用简单语言。
