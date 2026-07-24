# DECISIONS.md — 决策冻结

本文件冻结在正式编码前必须统一的架构决策,解决 `docs/` 各文档之间的冲突与缺口。

- **权威原则:** 代码中的 `core/domain` 与 SQLite schema 为单一事实源(single source of truth);文档反向对齐代码,不再维护两份散文。
- **裁决归属:** 按 [docs/10_TEAM_OWNERSHIP.md](docs/10_TEAM_OWNERSHIP.md),domain / runtime / policy 决策由 **Nick** 拍板;本文件已由决策负责人确认冻结。
- **冻结日期:** 2026-07-23(提出并确认冻结)。后续变更需记录在下方"变更记录"。

阻塞标记:🔴 阻塞里程碑 1 · 🟡 部分阻塞 · ⚪ 不阻塞

---

## D1 — 统一 `SessionStage` 状态枚举 🔴

**冲突(事实):** [docs/04_AGENT_RUNTIME.md:36-54](docs/04_AGENT_RUNTIME.md) 含 `UNCERTAINTY_ASSESSED`、`VERIFIED_MEMORY_WRITTEN` 两状态;[docs/13_API_SCHEMAS.md:8-25](docs/13_API_SCHEMAS.md) 的枚举无 `UNCERTAINTY_ASSESSED`、写记忆状态名为 `MEMORY_UPDATED`、且多出 `STOPPED`。

**决定:** 以 doc 13 枚举为权威,补回 `UNCERTAINTY_ASSESSED`。**状态名与事件名分属两套命名空间,禁止复用。**

```python
class SessionStage(StrEnum):
    READY = "ready"
    CAPTURING = "capturing"
    AUDIO_CAPTURED = "audio_captured"
    TRANSCRIBING = "transcribing"
    EVIDENCE_EXTRACTED = "evidence_extracted"
    MEMORY_RETRIEVING = "memory_retrieving"
    HEARD_CONTENT_REVIEW = "heard_content_review"
    UNCERTAINTY_ASSESSED = "uncertainty_assessed"
    CATEGORY_CLARIFICATION = "category_clarification"
    CANDIDATE_SELECTION = "candidate_selection"
    FINAL_REVIEW = "final_review"
    PATIENT_CONFIRMED = "patient_confirmed"
    VOICE_AUTHORIZED = "voice_authorized"
    SPOKEN = "spoken"
    MEMORY_UPDATED = "memory_updated"
    COMPLETED = "completed"
    STOPPED = "stopped"
```

`VERIFIED_MEMORY_WRITTEN`、`AUDIO_CAPTURED` 等仅作为 `RuntimeEvent.event_type`([docs/04_AGENT_RUNTIME.md:203-218](docs/04_AGENT_RUNTIME.md))。

**理由:** 枚举是要落成代码的一方;状态/事件重名会导致条件判断跨模块失配。

**影响:** `core/domain`、`core/runtime` 状态机、`app/pyside` 视图渲染;doc 04 状态图需改为引用本枚举。

---

## D2 — 统一 Memory 类型,授权单独建表 🔴

**冲突(事实):** [docs/05_MEMORY_AND_PERSONALIZATION.md:12-36](docs/05_MEMORY_AND_PERSONALIZATION.md) 列 6 种记忆(含 Intent、Authorization);[docs/13_API_SCHEMAS.md:58-61](docs/13_API_SCHEMAS.md) 的 `memory_type` 枚举为 5 种,用 `semantic` 而非 `intent`,且无 `authorization`。

**决定:**

```python
class MemoryType(StrEnum):
    SEMANTIC = "semantic"     # 吸收 doc 05 的 "Intent Memory"
    ACOUSTIC = "acoustic"
    CONTEXT = "context"
    LANGUAGE = "language"
    INTERACTION = "interaction"
```

Authorization **不进 `memory_type`**,单独建 `authorizations` 表(见 D4)。doc 05 表述改为"5 种记忆 + 1 张授权表"。

**理由:** 授权是状态而非语义证据;混入 `memory_type` 会在检索时被当证据召回,污染候选排序。

**影响:** `core/domain`、`core/personalization` 检索/排序、`memories` 表结构。

---

## D3 — Expression Receipt 字段名 + 签名策略 🟡

**冲突(事实):** [docs/08_SECURITY_AND_CONSENT.md:154](docs/08_SECURITY_AND_CONSENT.md) 用 `timestamp`;[docs/13_API_SCHEMAS.md:210](docs/13_API_SCHEMAS.md) 用 `created_at`。两处均要求 `signature`,但无密钥管理方案。

**决定:**
- 时间字段统一为 **`created_at`**;doc 08 的 receipt JSON 相应修改。
- `signature: str | None`。**P0 发不签名 receipt**;Ed25519 签名与密钥管理推迟至 P1。

**理由:** 字段名统一避免序列化丢字段;签名依赖尚未设计的密钥管理,不应阻塞三天 MVP。

**影响:** `core/domain` `ExpressionReceipt`、receipt 构建器;doc 08 文本。schema 部分阻塞,签名不阻塞。

---

## D4 — SQLite Schema + 安全约束(文档缺失,新增) 🔴

**缺口(事实):** 无任何文档给出建表语句;[docs/08_SECURITY_AND_CONSENT.md:107-109](docs/08_SECURITY_AND_CONSENT.md) 仅以散文要求 `patient_id` 限定。

**决定:** 将 §5 安全不变量落为数据库层约束。所有 Repository 方法签名强制携带 `patient_id`,不提供任何无患者限定的 `list/search`。

```sql
CREATE TABLE patients (
    patient_id TEXT PRIMARY KEY,
    display_name TEXT NOT NULL
);

CREATE TABLE memories (
    id TEXT PRIMARY KEY,
    patient_id TEXT NOT NULL REFERENCES patients(patient_id),
    memory_type TEXT NOT NULL,
    verification_level TEXT NOT NULL
        CHECK (verification_level IN ('gold','silver','unverified')),
    text TEXT,
    language TEXT,
    context TEXT,                  -- JSON string
    usage_count INTEGER NOT NULL DEFAULT 0,
    last_used_at TEXT,
    confirmation_session_id TEXT,
    -- 不变量:AI 内容未经患者确认不得进入 Gold
    CHECK (verification_level != 'gold' OR confirmation_session_id IS NOT NULL)
);
CREATE INDEX idx_mem_patient ON memories(patient_id);

CREATE TABLE rejected_candidates (
    -- 不变量:拒绝候选仅作负反馈,与 memories 物理隔离
    id TEXT PRIMARY KEY,
    patient_id TEXT NOT NULL REFERENCES patients(patient_id),
    text TEXT NOT NULL,
    session_id TEXT NOT NULL
);

CREATE TABLE memory_writes (
    -- 不变量:重试不重复写(幂等)
    idempotency_key TEXT PRIMARY KEY,   -- 见 D8
    memory_id TEXT NOT NULL REFERENCES memories(id),
    created_at TEXT NOT NULL
);

CREATE TABLE authorizations (
    id TEXT PRIMARY KEY,
    patient_id TEXT NOT NULL REFERENCES patients(patient_id),
    session_id TEXT NOT NULL,
    voice_profile_id TEXT,
    scope TEXT NOT NULL CHECK (scope = 'this_expression'),
    revoked INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE sessions (
    session_id TEXT PRIMARY KEY,
    patient_id TEXT NOT NULL REFERENCES patients(patient_id),
    stage TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE events (
    event_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES sessions(session_id),
    patient_id TEXT NOT NULL REFERENCES patients(patient_id),
    event_type TEXT NOT NULL,
    payload TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE receipts (
    receipt_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES sessions(session_id),
    patient_id TEXT NOT NULL REFERENCES patients(patient_id),
    body TEXT NOT NULL,          -- 序列化的 ExpressionReceipt
    signature TEXT,              -- P0 允许 NULL,见 D3
    created_at TEXT NOT NULL
);
```

**理由:** 最强的安全保证应落在数据库约束而非代码自觉;CHECK / NOT NULL / 物理隔离使违反不变量在存储层直接失败。

**影响:** `adapters/storage/sqlite.py`、`core/ports` RepositoryPort、`tests/safety`。

---

## D5 — 风险闸门归确定性规则 🔴

**冲突(事实):** [docs/07_MODELS_AND_INTEGRATIONS.md:127](docs/07_MODELS_AND_INTEGRATIONS.md) 令 LLM 做风险分类;不变量 8 要求高风险走更严格确认。

**决定:** 高风险闸门由 `core/policies/risk.py` 的确定性词表/规则拥有;LLM 的 `risk_level` 仅作建议,**只能加严、不能放松**。英文词项按单词边界匹配;中文医疗、法律、金融、紧急与关系词项按确定性子串匹配,避免 CJK 无单词边界导致漏判。

```python
def classify_risk(text: str, llm_hint: str | None) -> RiskLevel:
    rule = "high_risk" if _matches(text, HIGH_RISK_LEXICON) else "ordinary"
    if llm_hint == "high_risk":     # LLM 只能提升
        return "high_risk"
    return rule                      # 永不因 LLM 而降级
```

**理由:** 安全边界不得由概率模型单独决定;规则词表兜底 LLM 漏判。

**影响:** `core/policies/risk.py`、高风险确认路径([docs/06_INTERACTION_AND_ACCESSIBILITY.md:141-152](docs/06_INTERACTION_AND_ACCESSIBILITY.md))。

---

## D6 — 候选朗读使用中性声音 ⚪

**决定:** 候选朗读使用本地中性/缓存声音(绝不用患者克隆声);仅最终个人表达经 `AuthorizedExpression` + gateway 走个人 TTS。

**理由:** 缩小需授权 TTS 的审计面,强化"前端不得直调个人 TTS"([docs/07_MODELS_AND_INTEGRATIONS.md:156-157](docs/07_MODELS_AND_INTEGRATIONS.md))。里程碑 1 TTS 为 mock,按此假设实现。

---

## D7 — PySide6 线程模型 ⚪

**决定:** QThread worker + signal/slot;UI 仅与单一 runtime facade 通信。mock 阶段可同步实现;接入真实 ASR 前必须落地异步 worker。

**理由:** UI 主线程不得阻塞([docs/03_TECHNICAL_ARCHITECTURE.md:87](docs/03_TECHNICAL_ARCHITECTURE.md)),否则 Stop 按钮失效违反不变量 11。

---

## D8 — 幂等键定义 ⚪

**决定:** `idempotency_key = f"{session_id}:{expression_hash}:{update_type}"`,其中 `expression_hash = sha256(normalize(final_text))`。写入 `memory_writes.idempotency_key`(见 D4)。

**理由:** 明确哈希对象,保证"重试不重复写记忆"([docs/11_EVALUATION_AND_TESTING.md:104](docs/11_EVALUATION_AND_TESTING.md))在多人实现下一致。

---

## D9 — `confirmation_method` 收敛为枚举 ⚪

**冲突(事实):** [docs/13_API_SCHEMAS.md:114](docs/13_API_SCHEMAS.md) 为自由 `str`,但 receipt 与评测按其统计。

**决定:**

```python
class ConfirmationMethod(StrEnum):
    LARGE_BUTTON = "large_button"
    KEYBOARD = "keyboard"
    SCANNING = "scanning"
    DWELL = "dwell"
    SECOND_METHOD = "second_method"
```

**理由:** 自由字符串导致统计/审计口径不一。

---

---

# Agent / Runtime 设计决策(D10–D17)

以下为 runtime 行为的确定性设计,由 **Nick**(agent/runtime owner)于 2026-07-23 确认冻结。来源为设计对齐讨论,非文档冲突。所有决策均不得违反 D1–D9 与安全不变量。

## D10 — Uncertainty band 判定规则 🔴

**决定:** band 在**候选生成之前**计算,只依据 `TranscriptEvidence` 字段(确定性规则,非概率分数):

- **HIGH** 若:两路 ASR 均 failed/timeout,**或** `len(stable_fragments) < 2`,**或**(`missing_slots` 含核心槽位 **且** `conflicts` 非空)
- **LOW** 若:`conflicts` 为空 **且** `missing_slots` 为空 **且** 核心槽位齐全
- **MEDIUM:** 其余情况

**2026-07-24 修订:** 单路 ASR 成功时 token 仍全部保持 uncertain，不伪装成
stable；但若 uncertain token 至少 6 个且其中核心槽位齐全，则确定性路由为
MEDIUM，而不是仅因 `stable_fragments` 为空强制进入类别澄清。该例外永不产生
LOW、自动选择或跳过最终确认。少于 6 个 token、缺核心槽位或全部 ASR
失败仍按原规则进入 HIGH。

**核心槽位定义:** 谓语 + (宾语 或 时间)必须出现在 `stable_fragments` 中,否则至少 MEDIUM。

**理由:** 需要可执行、可测、偏保守的路由规则;禁止伪精确概率([docs/04_AGENT_RUNTIME.md:113](docs/04_AGENT_RUNTIME.md))。

**影响:** `core/runtime` uncertainty router、`tests/unit` 路由测试。

## D11 — Memory 可下调 band 一档,永不自动选择 🔴

**决定:** 强 verified memory 命中可将 band 下调**一档**(HIGH→MEDIUM,MEDIUM→直接进 FINAL_REVIEW),**绝不下调至自动选择,始终经 FINAL_REVIEW 患者确认**。

**理由:** 体现"个性化让正确候选浮上来"([docs/02_STORYTELLING_AND_DEMO.md:183-191](docs/02_STORYTELLING_AND_DEMO.md)),同时守住确认底线([docs/05_MEMORY_AND_PERSONALIZATION.md:99-105](docs/05_MEMORY_AND_PERSONALIZATION.md))。

**影响:** uncertainty router、ranker、`tests/safety`(memory 不自动选)。

## D12 — GO_BACK 为线性单步,授权后不可逆 🔴

**决定:** `GO_BACK` 为**线性单步 undo**,每次退一个阶段;session 仅需保存上一步状态。可逆映射:

| 从 | 回到 | 清除 |
|----|------|------|
| FINAL_REVIEW | CANDIDATE_SELECTION | `selected_candidate_id`、`patient_confirmed=false` |
| CANDIDATE_SELECTION | CATEGORY_CLARIFICATION / HEARD_CONTENT_REVIEW | 候选列表 |
| CATEGORY_CLARIFICATION | HEARD_CONTENT_REVIEW | 类别选择 |
| VOICE_AUTHORIZED / SPOKEN 之后 | **不可回退** | — |

**理由:** 单步符合"一屏一决定"([docs/06_INTERACTION_AND_ACCESSIBILITY.md:10-11](docs/06_INTERACTION_AND_ACCESSIBILITY.md)),实现与可逆规则简单;已说出的话不可撤销。

**影响:** `core/runtime` 状态机、`tests/safety`(go-back 只逆可逆状态)。

## D13 — 新增 `ConfirmedContext` 累加器(domain 对象) 🔴

**决定:** session 内新增 `ConfirmedContext`,跨澄清轮锁定已确认进度,每轮候选生成作为**硬约束**传给 LLM。字段:

```python
class ConfirmedContext(BaseModel):
    locked_slots: dict[str, str]   # 已确认槽位:类别/否定/时间/对象…
    locked_tokens: list[str]       # 必须保留的词(如 "tomorrow")
    rejected_texts: list[str]      # 已拒绝候选(对应 rejected_candidates 表 D4)
```

**理由:** "猜错保留进度"([docs/01_PRODUCT_VISION.md:70-72](docs/01_PRODUCT_VISION.md))与"部分修正只改 AI-added span"([docs/06_INTERACTION_AND_ACCESSIBILITY.md:88-91](docs/06_INTERACTION_AND_ACCESSIBILITY.md))的技术载体,是产品差异化核心。

**影响:** `core/domain` 新增 schema、`ExpressionSession`、LLM prompt 约束、`tests/safety`(None-of-these 保留已确认片段)。

## D14 — Ranker 分数永不触发自动选择(硬断言) 🔴

**决定:** ranker 分数**仅用于排序**。`select_candidate` 只能来自 `PatientCommand`;runtime 内以断言保证 ranker 输出永不产生选择,即使 top1 分数遥遥领先。

**理由:** 分数是排序启发式而非概率或授权([docs/04_AGENT_RUNTIME.md:174](docs/04_AGENT_RUNTIME.md));自动选即以推测替患者决策,违反第一原则。对应必测项 "memory retrieval never auto-selects"([docs/11_EVALUATION_AND_TESTING.md:97](docs/11_EVALUATION_AND_TESTING.md))。

**影响:** `core/personalization` ranker、`core/runtime` 命令处理、`tests/safety`。

## D15 — 两层 consent 模型 🔴

**决定:** 声音授权拆为两个独立对象:

1. **声音克隆/使用同意(长期):** 患者级、建 voice profile 时给予、可撤销,存 `authorizations` 表(D4)。
2. **本次表达授权(一次性):** `AuthorizedExpression`,scope=`this_expression`,每次表达现场铸造,说完即失效。

`can_use_personal_voice` 必须**同时**满足:本次 `patient_confirmed` ∧ stage 到位 ∧ 存在有效且未撤销的第 1 层声音同意。撤销第 1 层立即使所有后续表达失去个人声音。

**理由:** "A cloned voice is not cloned consent"([docs/08_SECURITY_AND_CONSENT.md:64-76](docs/08_SECURITY_AND_CONSENT.md))唯一严谨的实现;支持细粒度撤销。

**影响:** `core/policies/authorization.py`、`authorizations` 表、`tests/safety`。

## D16 — 高风险用 FINAL_REVIEW 上的 strict 标志 🔴

**决定:** 高风险表达**不新增状态**,在 FINAL_REVIEW 上挂 `strict=true`,强制:完整私密读回 + 显式确认 +(必要时)第二确认方式。风险在**选定候选的最终文本**上用 D5 确定性词表判定,时机在铸造 `AuthorizedExpression` **之前**。

**理由:** 状态机节点更少、三天更稳;满足高风险严格确认([docs/06_INTERACTION_AND_ACCESSIBILITY.md:141-152](docs/06_INTERACTION_AND_ACCESSIBILITY.md))。若未来高风险流程需外部复核,可再抽为独立状态。

**影响:** `core/runtime` FINAL_REVIEW、`core/policies/risk.py`、`tests/safety`(高风险严格确认)。

## D17 — Gold 在候选排序中严格高于 Silver 🔴

**决定:** 所有 Memory 排序信号按 verification level 加权。Gold 使用完整权重;Silver 及其他非 Gold verified memory 使用严格更小的权重:

| 排序信号 | Gold | Silver |
|----------|-----:|-------:|
| `normalize(text)` 精确匹配 | +1000 | +250 |
| `memory_support_ids` 命中 | +100 | +40 |
| `similarity_band == "high"` | +25 | +8 |

排序理由必须标明来源级别,例如 `exact gold patient phrase` 与 `exact silver-assisted phrase`。分数仅用于排序,不得触发候选选择或跳过确认(D14)。

**理由:** Silver 是辅助或间接验证的信息,不得在相同文本关系下等于或超过患者明确确认的 Gold。

**影响:** `core/personalization/ranker.py`、Memory Trace、`tests/safety`。

---

## D18 — Language-aware tokenization (CJK) 🔴

**缺陷(实测 2026-07-24):** 原 `tokenize()` 将连续 CJK 文本视为一个
`\w` token。例如 `我不想明天出门。` 只产生 `["我不想明天出门"]`。因此
中文核心槽位无法判定完整、locked-token 子集检查误拒绝有效候选、Memory
token overlap 无法达到 `high`，D11 的降 band 与中文排序均失效。

**决定:**

- `tokenize()` 对 CJK 字符逐字分词，对 Latin/数字/下划线/撇号组成的 word
  run 保持原有整词行为；混合文本同时支持两种粒度。
- locked-token 约束的两侧都必须经过 `tokenize()`，禁止比较 normalized
  phrase 与 token set。
- CJK 核心槽位使用 normalized 文本上的中文谓语/时间短语匹配，并保持
  D10 的语义规则：谓语 +（时间或其他内容）才算完整。
- `normalize()`、`expression_hash()`、idempotency key 与 exact-match
  ranking 路径不变；现有英文 tokenization 输出必须逐项保持不变。

**理由:** 这是确定性 shell 的语言处理缺陷，不是 LLM 能力问题。中文的
band、Memory overlap 与 locked-context 语义必须和英文等价，不能因文字
系统不同而强制额外澄清或静默降级。

**影响:** `core/personalization/text.py`、
`core/policies/uncertainty.py`、Intent adapters 的 confirmed-context
校验、SQLite Memory overlap、双语评测。

---

## D19 — Persistent Context-Memory 与自动情景召回 🔴

**缺口(实测 2026-07-24):** `situation` 仅能在 session 创建时手工输入，系统
不会持久保存或自动召回患者的日程、人物、地点、活动与偏好。现有 Memory
writeback 与检索只有 semantic 表达，无法实现“知道患者每周日看医生”等
持续个性化情景。

**决定:**

- Context-Memory 复用 `memories` 表，以 `memory_type='context'` 隔离；可读
  描述放 `text`，`kind/detail/time_pattern/source` 等结构化字段放
  `context` JSON，不新增表。
- 护理者提供的 context 必须为 Silver；患者明确确认的 context 才可为
  Gold，且仍需 `confirmation_session_id`。AI/LLM inference 禁止写 Gold，
  Silver 不得自动升级。
- semantic candidate support 与 context retrieval 使用独立 repository
  方法。`search_verified_memories` 只返回 semantic；context 不得进入
  semantic support、自动选择或声音授权。D21 后续允许相关、已验证 context
  对 ordering 施加有上限的小幅影响，但不得写入 `memory_support_ids`。
- runtime 按患者召回 context，通过纯函数 `compose_situation` 自动构造
  session situation；手工 `--situation` 仅作为优先级更高的 override。
- 自动召回必须使用本轮 stable + uncertain fragments 做确定性相关性过滤，
  默认最多返回 5 条；无 token overlap 时不把无关画像拼入 situation。直接
  Repository 审计读取仍可不带 fragments。
- `IntentPort.propose` 显式接收 situation，runtime 负责传递，provider
  adapter 只能将其作为证据使用。

**理由:** Context 是消歧证据，不是当前意图或同意。复用现有分级、
patient scope 与 Gold CHECK 可保持 D2/D4/D11/D14/D15/D17 的边界，同时
让个性化跨 session 持久生效。

**影响:** RepositoryPort / SQLite adapter、runtime clock 与
`CONTEXT_RETRIEVED` trace、IntentPort 及 adapters、demo profile。

---

## D20 — Simulated Profile Test Bundle 与最小披露 🔴

**缺口(实测 2026-07-24):** Web Demo 固定加载 `david_demo`，任意音频都会
携带 David 的语义和情景记忆；长篇 Markdown 用户画像同时混合患者事实、
照护者观察、研究假设、产品需求和评测答案，无法安全地整篇作为 prompt。

**决定:**

- 测试画像使用 Markdown 容器，但只有唯一的 `meantbyme-profile` JSON
  代码块可进入运行时。必须声明 `schema_version=1`、`simulated=true`、
  patient、demo consent、voice consent，并为每条 memory 声明
  `simulated=true`、source、verification level、sensitivity 和
  `prompt_eligible`。
- patient + confirmation session 才能成为 Gold；caregiver 只能是 Silver；
  research/unverified 必须 `prompt_eligible=false`，验证后留在源包但不写入
  可检索运行时记忆。禁止从自由叙事或 LLM 推断 Gold。
- 画像全文、产品需求、研究说明和 evaluator expected expression 不进入
  prompt。预期答案单独存放；把完整答案作为 Gold phrase 的测试必须明确标为
  known-phrase recall，而不能宣称未知意图补全。
- Web Demo 提供无画像 control、内置模拟画像和进程内临时上传。上传限制为
  UTF-8 Markdown、64 KiB、模拟数据；cloud mode 还必须显式允许
  `cloud_processing_allowed`。上传不落盘、不回显正文。
- 同一音频可在不同画像下重跑用于 A/B；context 仍只是排序/消歧证据，
  不得成为候选、选择、确认或授权。

**理由:** 测试必须区分个性化带来的真实排序改善与答案泄漏；最小披露和逐条
来源让详细健康、家庭、工作资料不会因为“画像”标签而被无差别发送给 provider。

**影响:** profile adapter、Web Demo session/profile API、demo fixtures、
context relevance retrieval、测试文档。

---

## D21 — Ranker context-grounding 权重 🔴

**缺口(实测 2026-07-24，Lin Yue case):** 语义正确的候选(如把 ASR 碎片补全
为 “organize their needs”)因为 `organize` 落在 `ai_added_spans` 而吃到
补全惩罚,而画像只有 Context-Memory、没有 Gold *semantic* 记忆可加分,
导致语义最正确的候选排到 #3、被模板化的字面候选压在下面。Ranker 已按
patient/AI span 与 Gold/Silver 语义记忆打分(D14/D17),但完全没有利用已检索
到的 Context-Memory 作为排序证据。

**决定:**

- Ranker 新增 context-grounding 加分:当候选的 `ai_added_spans` 的**实义
  词**与已检索 Context-Memory 的实义词重叠时，按 overlap / AI-added
  实义词覆盖率给一个有上限的小幅加分——Gold context 上限 `+20`、
  Silver(caregiver)上限 `+5`。代词、冠词、连词及 help/need/want 等泛词
  不算 grounding；CJK 单字实义 token 必须与英文等价生效。
- 该加分低于 Gold *semantic* exact/support(`+1000/+100`)，用于相近候选
  的 ordering，不构成“任何基础分组合下绝不越序”的绝对保证；真正的硬边界
  是它永远不自动选择——`rank_candidates` 仍只排序，患者仍显式选择并确认
  (D14)。
- Context 仅作排序/消歧**证据**。D21 明确修订 D19 原先“context 不得进入
  candidate ranking”为“context 可有限影响 ordering”；它仍不得进入
  semantic support / `memory_support_ids`、选择、确认或授权，也不改变 D11
  的 band 下调(仍只看 Gold semantic memory)。
- Context-Memory 沿用相关性检索(按 evidence 片段取 top-k),避免把整份
  画像倾倒进排序;engine 将检索到的 context 存入 `ExpressionSession
  .retrieved_context` 并传入 `rank_candidates(...)`。

**理由:** 个性化应让与患者确认事实、日程和偏好一致的补全在近似候选中自然
上浮；过去确认过的具体表达仍属于 semantic memory，权重显著更高。Context
是证据不是意图，加分只能改变排序，不能替患者做决定。

**影响:** `core/personalization/ranker.py`、`core/runtime/engine.py`、
`ExpressionSession` domain 字段、ranker 测试、intent prompt 候选策略。

---

## 决策汇总

| ID | 主题 | 阻塞里程碑 1 | Owner | 状态 |
|----|------|:---:|:---:|:---:|
| D1 | SessionStage 枚举 | 🔴 | Nick | ✅ 已冻结 |
| D2 | Memory 类型 + 授权拆表 | 🔴 | Nick | ✅ 已冻结 |
| D3 | Receipt 字段 + 签名 | 🟡 | Nick | ✅ 已冻结 |
| D4 | SQLite schema + 约束 | 🔴 | Nick / Jiayi | ✅ 已冻结 |
| D5 | 风险闸门归规则 | 🔴 | Nick | ✅ 已冻结 |
| D6 | 候选中性声音 | ⚪ | Nick / An | ✅ 已冻结 |
| D7 | PySide6 线程模型 | ⚪ | An | ✅ 已冻结 |
| D8 | 幂等键定义 | ⚪ | Nick | ✅ 已冻结 |
| D9 | confirmation_method 枚举 | ⚪ | Nick | ✅ 已冻结 |
| D10 | Uncertainty band 判定规则 | 🔴 | Nick | ✅ 已冻结 |
| D11 | Memory 下调 band 一档 | 🔴 | Nick | ✅ 已冻结 |
| D12 | GO_BACK 线性单步 | 🔴 | Nick | ✅ 已冻结 |
| D13 | ConfirmedContext 累加器 | 🔴 | Nick | ✅ 已冻结 |
| D14 | Ranker 不自动选(断言) | 🔴 | Nick | ✅ 已冻结 |
| D15 | 两层 consent 模型 | 🔴 | Nick | ✅ 已冻结 |
| D16 | 高风险 strict 标志 | 🔴 | Nick | ✅ 已冻结 |
| D17 | Gold 排序严格高于 Silver | 🔴 | Nick | ✅ 已冻结 |
| D18 | CJK language-aware tokenization | 🔴 | Nick | ✅ 已冻结 |
| D19 | Persistent Context-Memory + auto recall | 🔴 | Nick | ✅ 已冻结 |
| D20 | Simulated Profile Test Bundle + minimum disclosure | 🔴 | Nick | ✅ 已冻结 |
| D21 | Ranker context-grounding 权重 | 🔴 | Nick | ✅ 已冻结 |

**开工前必须确认的阻塞项:** D1、D2、D4、D5(D3 的 schema 部分),及
agent/runtime 的 D10–D21。全部已冻结。

---

## 变更记录

| 日期 | 决策 | 变更 | 记录人 |
|------|------|------|--------|
| 2026-07-23 | D1–D9 | 初次提出 | 初始 onboarding review |
| 2026-07-23 | D1–D9 | 全部确认冻结 | 决策负责人确认 |
| 2026-07-23 | D10–D16 | 新增 agent/runtime 设计决策并冻结 | Nick 确认 |
| 2026-07-23 | D17 | Gold/Silver 排序权重与 Memory 来源追踪规则冻结 | Nick 确认 |
| 2026-07-24 | D18 | 冻结 CJK 分词、槽位、locked-context 与 Memory overlap 等价规则 | Nick 确认 |
| 2026-07-24 | D19 | 冻结 Context-Memory 分级存储、独立检索与自动 situation 召回 | Nick 确认 |
| 2026-07-24 | D5/D16 | 补齐中文高风险确定性词表与 strict 确认覆盖 | Nick |
| 2026-07-24 | D10 | 单路 ASR 内容丰富时改走 MEDIUM，tokens 仍保持 uncertain | Nick 确认 |
| 2026-07-24 | D20 | 冻结结构化模拟画像、最小披露与有/无画像 A/B 测试规则 | Nick 确认 |
| 2026-07-25 | D21 | 冻结按实义词覆盖率计算的 context-grounding 上限(Gold +20 / Silver +5)，仅排序、不自动选 | Nick 确认 |
