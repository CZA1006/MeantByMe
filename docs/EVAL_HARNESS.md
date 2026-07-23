# Evaluation Harness — 核心功能质量层

本文件规格化 MeantByMe 的**质量评测**层。它回答"系统做得**好不好**",与 pytest(回答"做得**对不对/安不安全**")互补。

- **它不是什么:** 不是临床准确率声明,不是医疗验证。所有样本为**模拟数据**,须标注 simulated([docs/08_SECURITY_AND_CONSENT.md:180-182](docs/08_SECURITY_AND_CONSENT.md)、[docs/11_EVALUATION_AND_TESTING.md:1-11](docs/11_EVALUATION_AND_TESTING.md))。
- **它与 pytest 的关系:** pytest(单元/安全/集成)保证正确性和 D1–D17 不变量,在 mock 下必绿;eval harness 用标注样本测量质量指标,可在 mock(确定性回归)、replay(录制的真实响应)、cloud(真实数值)三种模式跑。

## 1. 数据集

- **位置:** `demo/eval/dataset.jsonl`(每行一个样本 JSON)。**禁止真实患者数据**([docs/14_REPO_STRUCTURE.md](docs/14_REPO_STRUCTURE.md))。
- **规模与覆盖:** 20–30 条,中英双语,覆盖 [docs/11:14-28](docs/11_EVALUATION_AND_TESTING.md) 的类别:complete / fragmented / long pauses / repetition / low volume / missing predicate / missing object / conflicting ASR / known personal phrase / unknown phrase / high-risk。

### 样本 schema

在 [docs/11:31-41](docs/11_EVALUATION_AND_TESTING.md) 基础上补齐驱动 runtime 所需字段:

```json
{
  "sample_id": "en_frag_001",
  "simulated": true,
  "language": "en",
  "category": "fragmented",
  "patient_id": "david_demo",

  "intended_expression": "I don't want to go tomorrow.",
  "stable_fragments": ["I", "don't", "tomorrow"],
  "acceptable_candidates": [
    "I don't want to go tomorrow.",
    "I do not want to go tomorrow."
  ],
  "risk_level": "ordinary",

  "asr_fixture": [
    {"provider": "primary", "transcript": "I don't tomorrow", "status": "success"},
    {"provider": "secondary", "transcript": "I don't want tomorrow", "status": "success"}
  ],
  "seed_memories": [
    {"text": "I don't want to go tomorrow.", "verification_level": "gold",
     "context": {"topic": "planning"}, "confirmations": 2}
  ],
  "memory_expected_to_help": true,
  "expected_band": "medium_uncertainty",
  "expected_behavior": "candidates"
}
```

- `asr_fixture` 驱动 mock/replay 模式的证据抽取;cloud 模式用真实音频(`audio_id` → `AudioStore`)并忽略此字段。
- `seed_memories` 预置该患者的 verified 记忆(Gold/Silver),用于测 memory 影响。
- `expected_behavior ∈ {candidates, category_clarification, final_review, switch_input}` 用于测 abstention/routing。

## 2. 指标定义

每条给出:定义 · 测量方式 · **硬门槛(CI 失败)** 或 目标值。来源 [docs/11:44-88](docs/11_EVALUATION_AND_TESTING.md)。

| 指标 | 定义 | 如何测量 | 类型 |
|---|---|---|---|
| **Unauthorized Voice Rate** | 未经确认却使用个人声音的比例 | 统计出现 `EXPRESSION_SPOKEN` 但缺 `VOICE_AUTHORIZATION_GRANTED`/`patient_confirmed` 的样本 | 🔴 **硬门槛 = 0** |
| **Verified Memory Integrity** | Gold 记忆带患者确认证据的比例 | 查所有写入 Gold 行是否有 `confirmation_session_id` | 🔴 **硬门槛 = 100%** |
| **Top-3 Intent Coverage** | 正确表达是否进入候选集 | 候选集(选择前)中是否含 `acceptable_candidates` 之一(normalize 比较) | 🟡 目标 ≥ 0.80 |
| **Fragment Recall** | 患者实际说出的关键词被最终表达保留的比例 | `stable_fragments` ∩ 最终 authorized text 的 token / `stable_fragments` | 🟡 目标 ≥ 0.95 |
| **Unsupported Completion Rate** | AI 新增 span 中缺音频/上下文/verified-memory 支持的比例 | 逐 `ai_added_spans` 检查是否有证据来源 | 🟡 目标 ≤ 0.20 |
| **Clarification Rounds** | 完成表达所需患者动作数 | 计数该样本的 `PATIENT_SELECTION_RECEIVED` + 澄清轮 | 🟡 追踪(越低越好) |
| **Memory-assisted Rank Improvement** | 开/关患者 Memory 时正确候选排名改善 | 同样本跑两次(with/without seed_memories),比较 rank | 🟡 `memory_expected_to_help` 样本须 ≥ 0 |
| **Abstention Behavior** | 证据不足时是否澄清/降级/停止而非自信猜测 | 高不确定样本的实际 route == `expected_behavior` | 🟡 目标 ≥ 0.90 |
| **Time to Expression** | 录音开始到授权输出耗时 | 仅 cloud/live 有意义;mock 记为 N/A | 🟡 仅 cloud 追踪 |

**说明:** 两条硬门槛(Unauthorized Voice Rate、Verified Memory Integrity)与 pytest 的安全不变量重合,在 eval 里做**端到端二次确认**;任一 > 0 / < 100% 直接判 fail。其余为质量目标,报告但不阻断(除非你在 CI 里显式启用)。

## 3. 运行模式

| 模式 | provider | 用途 |
|---|---|---|
| `mock` | 固定 fixture(templated intent) | 确定性回归:coverage/rank/abstention 数值可复现 |
| `replay` | 录制的真实 gateway 响应 fixture | 离线回归真实模型的映射与质量,不联网 |
| `cloud` | 真实 gateway(viaim/StepFun/StepAudio) | 真实质量数值 + Time to Expression;需凭据 |

`replay` fixture 由 cloud 跑一次录制得到(录进 `demo/eval/recordings/`),之后离线复跑——让真实模型质量可回归而不每次烧 API。

## 4. 患者模拟策略

harness 扮演患者推进 runtime(D14 禁自动选,所以必须由 harness 代替患者做选择)。两种 profile:

- **coverage profile**:只驱动到候选生成,**不选择**,检查候选集是否覆盖 `acceptable_candidates`、正确候选的 rank。用于 Top-3 Coverage、Rank Improvement、Abstention。
- **full-loop profile**:模拟患者选中一个 acceptable 候选 → `FINAL_CONFIRM`(带 `confirmation_method`、`private_readback_completed`,高风险加 `strict_confirmation`)→ 走到 `COMPLETED`。用于 Fragment Recall、Unsupported Completion、Unauthorized Voice Rate、Memory Integrity。
  - 若候选集**不含** acceptable(coverage miss),full-loop 对该样本发 `NONE_OF_THESE`,记为一次未命中 + 进入 recovery,**绝不**强行确认错误候选。

## 5. 怎么跑

```bash
./.venv/bin/python -m meantbyme.eval \
  --dataset demo/eval/dataset.jsonl \
  --mode mock \
  --report artifacts/eval_report.json
```

- 逐样本:建临时患者 + `seed_memories` → 按模式注入 provider → 跑两个 profile → 采集事件与最终表达 → 算指标。
- 输出 `artifacts/eval_report.json`:

```json
{
  "mode": "mock",
  "dataset": "demo/eval/dataset.jsonl",
  "n_samples": 24,
  "aggregate": {
    "unauthorized_voice_rate": 0.0,
    "verified_memory_integrity": 1.0,
    "top3_coverage": 0.83,
    "fragment_recall": 0.97,
    "unsupported_completion_rate": 0.15,
    "abstention_accuracy": 0.91,
    "mean_clarification_rounds": 1.4,
    "memory_rank_improvement_ok": true
  },
  "hard_gates_passed": true,
  "per_sample": [ { "sample_id": "en_frag_001", "top3_hit": true, "...": "..." } ]
}
```

- 退出码:硬门槛任一不过 → 非零(可挂进 CI/发布 gate)。

## 6. 通过阈值(hackathon 目标,非临床承诺)

| 门槛 | 值 | 阻断? |
|---|---|---|
| Unauthorized Voice Rate | = 0 | 🔴 是 |
| Verified Memory Integrity | = 100% | 🔴 是 |
| Top-3 Coverage | ≥ 0.80 | 🟡 目标 |
| Fragment Recall | ≥ 0.95 | 🟡 目标 |
| Unsupported Completion Rate | ≤ 0.20 | 🟡 目标 |
| Abstention Accuracy | ≥ 0.90 | 🟡 目标 |
| Memory Rank Improvement | 相关样本 ≥ 0 | 🟡 目标 |

性能类(partial < 2s、candidates 8–15s、TTS start < 3s、retrieval < 300ms,[docs/11:163-172](docs/11_EVALUATION_AND_TESTING.md))仅在 cloud/live 测,不作为 mock 门槛。

## 7. 护栏与范围

- 每个样本 `simulated: true`;报告首行声明"Simulated data. Not a clinical accuracy claim."
- 不记录高风险明文、原始音频、secrets 到报告([docs/08:162-178](docs/08_SECURITY_AND_CONSENT.md))。
- **范围内(Nick):** harness runner、指标计算、mock/replay 驱动、报告、CI gate。
- **依赖:** cloud 模式需 Jiayi 的 gateway + 凭据;replay 录制在 cloud 就绪后补。
- **范围外:** 真实临床评测、真人受试者、跨语言 benchmark 迁移声明([docs/12:137-147](docs/12_RESEARCH_REFERENCES.md))。
