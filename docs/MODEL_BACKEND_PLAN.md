# Model Backend Plan — 赞助商资源映射与申请清单

本文件记录 MeantByMe 的模型/云服务如何由 AdventureX 2026 赞助商覆盖,并给出按优先级排序的申请清单。目标:**先保证软件层核心功能真实可用**,自部署可部署的部分,分担 Jiayi 的压力。

## Scope 边界(重要)

**本阶段范围内(我们 = Nick + Codex,软件核心):**
- 识别语言:真实 ASR 转写 + 语言检测
- 识别意图:uncertainty routing + 候选生成
- 用户交互:澄清 / 选择 / 确认闭环
- 补全语言:AI completion(patient span vs AI-added span)
- 记忆自进化:确认后写回 Gold + 个性化重排

**音频输入:麦克风或 WAV 文件**(与硬件解耦)。

**后移交给 Jiayi(后续):**
- iFLYBUDS Air 2 / viaim 耳机采音与私密回放
- 流式 partial transcript、耳机生态集成
- gateway 的生产级加固、部署、secrets、可靠性

## A. 覆盖核查:每个组件 → 谁提供

| 组件 | 赞助商覆盖 | 状态 |
|---|---|---|
| 意图 LLM(候选生成) | **StepFun 文本 LLM**;备份 OpenAgents(GLM/kimi $100)、OneLinkAI $20、清程极智 ¥58 | ✅ 多重覆盖 |
| 个人声音克隆 TTS | **StepFun `POST /v1/audio/voices`**(stepaudio-2.5-tts / step-tts-mini) | ✅ 已确认能力 |
| 中性 TTS | 系统声音(本地,免费)或 StepAudio | ✅ |
| 主 ASR | StepAudio ASR;或自部署 Qwen3-ASR 到 GPU;或 whisper.cpp 本地 | ✅ 替代 viaim |
| 次 ASR(双源证据) | whisper.cpp 本地 / 自部署 | ✅ |
| 本地 fallback ASR | whisper.cpp(任意机)/ MLX(M-Mac) | ✅ 免费本地 |
| GPU 算力(自部署 ASR/LLM) | **HyperAI**(RTX 5090+PRO 6000)、**矩池云**(4090×300×80h) | ✅ |
| Gateway 托管(FastAPI) | **Zeabur**(5天无限量);备份 D1V.ai、OpenDeploy | ✅ |
| Patient Memory / SQLite | 本地,无需赞助 | ✅ N/A |
| 云存储(如需) | HyperAI 20GB、D1V.ai $50 | ✅ 可选 |
| Embedding(P1,可选) | 自部署 Qwen3-Embedding 或跳过(P0 用关键词) | ⏸️ 暂不需要 |

**唯一无直接赞助:** viaim(流式耳机 ASR)——已由 StepAudio ASR / 自部署 Qwen3-ASR 替代,且耳机后移给 Jiayi,功能无缺口。

**已确认(2026-07-24):StepFun 一家覆盖整个模型层。** 见下 §E。个人声音克隆缺口已关闭。

**唯一待验证(非申请):** 已拿到的 StepFun key 能否直达标准 `/v1/audio/*`(ASR/TTS/voices),以及计费走 StepPlan 额度还是余额。一条测试 curl 即可确认。

## E. StepFun 能力(已确认,公开 API 事实)

| 能力 | 模型 ID | 端点 / 格式 |
|---|---|---|
| ASR(中英混) | `step-asr`(实时+离线)、`stepaudio-2.5-asr`(流式)、`stepaudio-2-asr-pro`(32B) | `/v1/audio/*`(asr-sse 流式) |
| 中性 TTS | `step-tts-mini`(19 音色, 中/英/日)、`stepaudio-2.5-tts` | `POST /v1/audio/create-audio` |
| 个人声音克隆 | `stepaudio-2.5-tts` / `step-tts-mini` | `POST /v1/audio/voices`,传 5–10s WAV/MP3 → 返回 `voice id` |
| 文本 LLM | `step-explore`(审核中) / StepPlan 标准文本模型 | `/v1/messages`(x-api-key)或 `step_plan/v1` |

**两种 auth:** 标准 `/v1/audio/*` 用 `Authorization: Bearer <key>`;`step-explore` 的 `/v1/messages` 用 `x-api-key: <key>` + `anthropic-version: 2023-06-01`,**禁传 `thinking`**,429 指数退避。

**备用 LLM(已申请):** OpenAgents,`POST https://api-gateway.openagents.org/v1/chat/completions`,`Authorization: Bearer`,OpenAI 兼容,模型如 `deepseek-v4-pro`。

## F. Secrets 处理(强制)

- API key **只放 gateway 的 `.env`(已 gitignore)或 Zeabur 环境变量/密钥管理**;**永不进 git**(仓库 public)。
- `.env.example` 只放占位符。
- key 若在聊天/截图等处明文出现过,**建议赛后轮换**。
- 桌面 bundle、日志、receipt 都不得含 key。

## B. 申请清单(按优先级 + 截止排序)

> 今天 2026-07-24,比赛 7/23–7/25,多个 7/26 截止。

### 🔴 P0 — 必领(核心 + 快过期)

1. **StepFun StepPlan + API Key** — 主 LLM + 个人声音
   - 领 ¥199 Token:阶跃星辰开放平台 `platform.stepfun.com`(福利页扫码 → 立即领取)
   - 在开放平台生成 **API Key**(gateway 要配)
   - 顺便填 **Step-explore 内部模型开通申请表**(以防 StepAudio ASR/声音克隆在内部模型)
   - ⏰ 截止 **2026-07-26**
   - [x] 已领 Token  [x] 已生成 Key(step_plan/v1)  [~] step-explore 审核中  [ ] 待验证 key 直达 /v1/audio/*

2. **HyperAI 超神经 GPU** — 自部署 Qwen3-ASR / 本地 LLM 算力
   - 兑换码:`HyperAI_AdventureX202607`(RTX 5090 60h + RTX PRO 6000 12h + 20GB)
   - ⏰ 参赛窗口 7/23–7/25,兑换码 3 天有效,算力 3 个月有效
   - [ ] 已领

3. **Zeabur 云服务器** — 托管自建 gateway
   - 问卷(填 zeabur.com 注册邮箱):`https://my.feishu.cn/share/base/form/shrcnlULTFOSfiZMLakEswJn1gf`
   - ⏰ 5 天无限量,比赛期内
   - [ ] 已领

### 🟡 P1 — 建议领(备份 / 补强)

4. **OpenAgents $100 API Key** — LLM 备份(GLM/kimi)
   - `https://api-gateway.openagents.org/register_advx/`(填对姓名+email)
   - [x] 已领(OpenAI 兼容 /v1/chat/completions,deepseek-v4-pro 等)

5. **矩池云 GPU** — 备份算力(4090)
   - `https://www.matpool.com/user/welfare?type=b`(输群内兑换码)
   - [ ] 已领

6. **D1V.ai $50** — 云 DB/存储/部署备份
   - `https://www.d1v.ai/login?invite=adx0d1`,邀请码 `adx0d1`
   - ⏰ 邀请链接 **2026-07-26 20:00** 截止
   - [ ] 已领

### ⚪ P2 — 可选(更多 token / 工具)

7. **OneLinkAI $20** — `https://www.onelinkai.cloud/invitation?invitationCode=N_00BypwHn`
8. **清程极智 ¥58**(国内开源模型)— `https://aiping.cn/#?channel_partner_code=CHFMXM7R24`
9. **OpenDev/OpenDeploy $500**(需加微信 Olivia)— `https://api.openai-next.com` / `https://opendeploy.dev`
10. 开发工具(非核心):Kiro `https://kiro.dev`、ego `https://adx.ego.app`、Qoder

## C. 推荐栈(领完后)

| 环节 | 首选 | 备份 |
|---|---|---|
| 意图 LLM | StepFun 文本 LLM | OpenAgents GLM |
| 个人 TTS/声音克隆 | StepAudio create-voice | 缓存音频占位 |
| 中性 TTS | 系统声音 | StepAudio 中性音 |
| 主 ASR | StepAudio ASR 或 whisper.cpp 本地 | Qwen3-ASR @ HyperAI |
| 次 ASR | whisper.cpp 本地 | — |
| Gateway 托管 | Zeabur | 本地 localhost / HyperAI box |
| Patient Memory | 本地 SQLite | — |

## D. 红线(自建也要守)

- secrets(StepFun key 等)只在 gateway,不进桌面 bundle
- `core/` 不改,ports 契约不变
- 患者记忆本地,只传本次最小检索结果
- 个人 TTS 只吃 `AuthorizedExpression`;前端不直调
- D1–D17 冻结不动
