# 09｜集成与产品化计划

本计划取代早期“三天开发计划”。当前目标不是继续扩大分支，而是把已完成的
mock、Web/backend 与移动端实验按安全边界拆分、验证并逐步进入 `main`。

## Stage 0 — Canonical baseline

- `main` 保存项目身份、不变量、决策、文档、许可和发布入口。
- 建立 MIT、贡献、安全、PR 模板、状态和分支审计文档。
- 所有文档区分 canonical、branch-only、experimental 和 planned。
- 冻结决策编号；分支实验不得复用 D 编号。

Exit gate:

- canonical docs 互相链接且无来源冲突；
- mock runtime 和安全测试通过；
- 无 secrets、真实患者数据或个人语音材料进入提交。

## Stage 1 — Runtime and evaluation

从 `develop` 拆出可审查的 runtime/evaluation pull request：

1. CJK tokenization 与回归测试；
2. Context-Memory repository 与 patient scope；
3. Profile bundle 最小披露；
4. bounded context-grounding ranker；
5. evaluation runner 与模拟数据声明。

Exit gate:

- D1–D21 均有对应测试；
- core 不依赖 UI、FastAPI 或 provider SDK；
- mock path 不访问网络；
- 迁移与 rollback 清楚；
- 旧 24 项与新增测试全部通过。

## Stage 2 — Gateway and Web

`develop` 与 `frontend` 当前是同一 commit。保留一个 integration branch，
停止把它们视为两个独立代码源，并按组件拆分：

1. gateway contracts、认证、限流、超时和输入验证；
2. cloud adapters 与 deterministic mocks；
3. server-side Web BFF/session boundary；
4. responsive UI 与 brand assets；
5. browser safety and cache behavior。

Exit gate:

- 浏览器无法获得 gateway token 或直接调用 personal TTS；
- BFF 只能通过 runtime command 驱动状态；
- provider failure 不产生 spoken 或 Gold write；
- Web/gateway/safety tests 通过；
- deployment configuration 有 secrets 和 fallback 说明。

## Stage 3 — iOS and headset extraction

不要直接合并 `feature/earPhones`。从最新 `main` 重新建立小型分支：

1. 共享 API schema；
2. iOS shell 与 XcodeGen project；
3. audio routing 和 16 kHz PCM encoder；
4. Viaim adapter behind a protocol plus a mock；
5. explicit command confirmation；
6. private readback / public output routing。

QA runtime、MySQL profile storage、dynamic memory 分别独立评审。
`EXP-MEM-01` 不进入集成。

Exit gate:

- simulator build；
- signed arm64 physical-device test；
- vendor SDK version/license/provisioning documented；
- headset missing/disconnect/reconnect/timeout paths tested；
- neutral preview and personal-voice authorization boundaries tested；
- Stop/Back/None/Switch remain reachable。

## Stage 4 — Release hardening

- 在 CI 固定 Python 3.11 并运行 unit/integration/safety suites。
- 移除 `audioop` 与 legacy TestClient deprecation warnings。
- 运行 dependency/license/secret scanning。
- 验证 GitHub Pages、release assets、QR code 和 README links。
- 生成明确版本、changelog、known limitations 和 rollback instructions。
- 任何真实用户研究先完成伦理、隐私、同意和数据保留审核。

## Branch policy

- `main`: canonical, protected, releasable。
- `integration/<area>`: 短期集成分支。
- `feature/<area>`: 单一可审查能力。
- `experiment/<area>`: 不承诺兼容或合并。
- 已被合并或取代的重复 branch 应在确认后删除。

每个 PR 必须说明来源 branch、安全不变量、测试环境、失败路径和回滚方法。
