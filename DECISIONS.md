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

**决定:** 高风险闸门由 `core/policies/risk.py` 的确定性词表/规则拥有;LLM 的 `risk_level` 仅作建议,**只能加严、不能放松**。

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

**开工前必须确认的阻塞项:** D1、D2、D4、D5(D3 的 schema 部分)。其余可在里程碑 1 期间随实现确认。

---

## 变更记录

| 日期 | 决策 | 变更 | 记录人 |
|------|------|------|--------|
| 2026-07-23 | D1–D9 | 初次提出 | 初始 onboarding review |
| 2026-07-23 | D1–D9 | 全部确认冻结 | 决策负责人确认 |
