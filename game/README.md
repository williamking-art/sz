# 宋祚 (Songzuo)

北宋徽宗治国模拟器 —— **AI 驱动的历史推演策略游戏**。

> **产品定位**：模拟一个穿越者（玩家），通过跟大臣的对话、发布圣旨（政策），来改变历史进程（北宋徽宗朝）。**AI 是游戏的核心引擎**——所有机制（经济/军事/政治/事件/外部/叙事）都通过 AI（agent）推演驱动，harness 保证稳定与编排，程序负责数值/守恒/校验。让 AI 更有效地发挥，就是游戏的宗旨。
>
> **架构**（详见 `_dev_tools/game-docs/docs/游戏机制说明.md`）：AI 通过**结构化契约**返回变更——各角色 `*_decide` 契约（JSON 输出，validate 校验）为主通道，大臣办差走 **function calling**（`enable_tools` 三档：auto/on/off）；`STATE_TOOL_SCHEMAS`（update_state/query_state/trigger_event 3 工具 + tool_choice=required）为**预留契约**（尚无生产调用方，见 `ai/client_utils.py` 注释）。变更统一经应用层 `engine/state_applier.py`（验证/合并/**守恒校验**/cascade/原子写库）→ 记忆库（**SQLite 一轮一库**：主库存圣旨/口谕/决策 + 对话记忆库存召对，每 3 回合总结去重）→ 叙事组装（narrative_guard 护栏 + persona 差异）。Agent 按需唤醒（`agent_router.AGENT_DEFS`；`PENDING_CONTRACTS` 登记未接线契约），异步化（UI 不卡），回合时序 = AI 推演 → 系统结算 → 形成叙事。

---

## 2026-09-18 全量审查与设计定稿

> ⚠️ **状态说明**：下列设计与修复**已定稿但尚未实现**（实现按 [fix_plan_2026-09-18.md](../_dev_tools/game-docs/analysis/fix_plan_2026-09-18.md) 分批次推进）。**本 README 其余各节仍描述当前版本的真实行为**——请勿把本节内容当作已生效能力。

**审查产出**

| 文档 | 内容 |
|---|---|
| [review_2026-09-18.md](../_dev_tools/game-docs/analysis/review_2026-09-18.md) | 全量审查汇总：P0×9（去重）、测试基线 379/11 与三簇归因、历史修复核实、误报澄清 |
| [fix_plan_2026-09-18.md](../_dev_tools/game-docs/analysis/fix_plan_2026-09-18.md) | 修复计划：阶段 0–6、逐项改法与验收、待拍板决策 |
| `_dev_tools/_scratch/audit-2026/` | 10 份分报告（结算经济 / 状态存档 / AI 管线 / 写状态通道 / 后端安全与 Rust / 前端 / 内容与文档 / 测试质量 / 启动打包 / 端到端） |

**设计定稿（三份；货币与财力已实现，官制大部分已实现）**

| 设计 | 文档 | 一句话 | 状态 |
|---|---|---|---|
| 货币口径 | [货币口径规范_M0M1M2.md](../_dev_tools/game-docs/docs/货币口径规范_M0M1M2.md) | 引入 M0/M1/M2/M3 与月度对账恒等式，使"凭空造币/销毁"在构造上可观测；含仓鼠症与国库封桩分层 | ✅ **B-1/B-2/B-3 已生效**：60 月残差 **+43,380,547 → −7,966 贯**；取中后 240 月 **−30,907 贯** |
| 财力消耗 | [财力消耗设计.md](../_dev_tools/game-docs/docs/财力消耗设计.md) | 六层 money sink；核心为 **L1 资产维持费**（随资产存量增长）与 **L2a 军俸补足至史实** | ✅ **L1 已落地**（Step 3.9）；**L2a/L2b/L2c 已落地**（军俸 1,349 万贯/年 ＋ 冗官膨胀 ＋ 宗室俸禄） |
| 官制与三冗 | [宋代官制与三冗设计.md](../_dev_tools/game-docs/docs/宋代官制与三冗设计.md) | 官/职/差遣分离、冗官量化定义、政务量 W 界定、地方三层可见性与路级四司、科举离散科次、吏员制度、公务员化 | 🔶 **C-1～C-7 已生效**（双账消灭＋身份子池＋官制结算步＋宗室俸禄＋免役税基＋吏制＋离散科次＋编制参数）；**C-8 地方三层可见性 / C-5′ 吏制奏议外显待做** |

**落地顺序（用户定稿）**：① 先修审查问题 → ② 再做 M0/M1/M2/M3 货币口径（含军俸提至史实、money sink）→ ③ 最后做官制完善。
进度：**① ✅ 已完成**（P0×9 ＋ 测试整理）｜**② ✅ 已收口**（B-1 观测 → B-2 守恒 → B-2′ 军俸/欠饷 → B-3 L1 维持费）｜**③ 🔶 主体已完成**（C-1～C-7）｜**④ ✅ 历史↔游戏性取中已落地**（农户粜粮完税 ＋ 结余补发积欠 ＋ 四个校准旋钮；**史实锚点不动**）。余 C-8 地方三层可见性与 C-5′ 吏制奏议外显。详见 [fix_plan_2026-09-18.md](../_dev_tools/game-docs/analysis/fix_plan_2026-09-18.md) 与 [游戏机制说明.md §七](../_dev_tools/game-docs/docs/游戏机制说明.md)。

**已拍板决策**

1. **废弃** `engine/state_applier.py` 的 `factions.*.power` cascade 规则，并同步删除过期测试 `test_cascade_faction_power`。
2. `_settle_events` 的压力事件通道**并入 `core/events.py` 富事件卡**（保留压力累积语义，产出事件带 `title`/`desc`/`choices`/`effects` 并可被 `/api/resolve_event` 反查）。
3. **不为公务员制做专门的转轨系统**（不做"归一入口"、不做转轨开关）；公务员化由玩家在局内通过现有政令链路自行达成。

**实现硬约束 · POP 挂载律**（**所有改动必须遵守**，全文见 [游戏机制说明.md §五](../_dev_tools/game-docs/docs/游戏机制说明.md)）

1. 凡**"人"**（官/吏/宗室/兵/编制）→ 必须落在 **6 类 POP 的 `size`** 上，不得另立人口账本；
2. 凡**"钱/粮"** → 必须落在某 POP 的 `wealth`/`grain` 或国库/内帑；POP 之外只允许 `core/money.py` 作为**只读对账视图**；
3. 凡**"阶层变动"** → 必须走既有 POP 流动通道，且 **ΣPOP 守恒**（或显式记为人口自然增减）；
4. **禁止**任何与 POP 平行的独立存量账本（~~现行 `officials` 与官僚 POP 双账即教训~~ **已于 2026-09-18 阶段 C-1 修复**，见下）；
5. 每条改动都要配**守恒断言**并进回归测试。

> **已修的违规一 · `officials` 双账（阶段 C-1）**：`prefectures[].officials`（原 `户数 × 0.00135` 派生后**永不变化**）与 `pops["官僚"].size`（随科举/裁汰流动）曾是**两本账**——30 月实跑官僚 POP **+23.1%** 而 `officials` **+0.0%**，国库俸禄支出 30 月**零增长**（"养更多官、一分钱不多花"）。现以 `pops["官僚"]` 为**唯一人头账**（单一权威源 `core/officialdom.py`），旧字段降为**派生镜像**（唯一写入点 `sync_legacy_mirror`，供 Rust 后端与旧档读取），并加两条不变量与自愈校验。240 月实跑：官额 **27,001 → 62,934**、官俸 **81.0 → 152.1 万贯/月**。详见 [宋代官制与三冗设计.md §十三/§十八](../_dev_tools/game-docs/docs/宋代官制与三冗设计.md)。
>
> **已修的违规二 · 被裁的人凭空消失（阶段 C-1）**：诏令「裁汰冗员」原实现直接 `pops["官僚"].size -= cut`，被裁官员**凭空消失**（破 ΣPOP 守恒）。现回流 `士绅`（罢官为民/回乡），ΣPOP 严格守恒，并由 `test_officialdom.py` 断言。**凡涉及"人"的改动都必须检查对手方。**

---

## 目录分层规范

项目严格按「游戏本体 / 开发工具 / 无关归档」三层隔离，保证游戏可单独分发、不被开发脚本与临时产物污染。

```
game/  （宋祚游戏根目录，即仓库内 songzuo 游戏本体）
├── 🎮 游戏本体（参与打包 / 运行所需）
│   ├── backend_server_entry.py  # PyInstaller 后端入口（调 backend.server.main）
│   ├── fetch_basemap.py / fetch_hillshade.py / build_map_basemap.py  # 舆图底图抓取/构建
│   ├── ai/                  # AI 叙事管线（见下方模块表）
│   ├── core/                # 游戏核心（状态 / 结算 / 存档 / 事件 / 评估 / free_effect 契约 / registries 注册表（科技+兵种）/ estate_mechanic 家产投资 / agent_router 按需唤醒 / async_ai 异步化 / minister_profile 群臣档案）
│   ├── engine/              # 应用层（state_applier：AI changes 验证/合并/守恒校验/cascade/原子写库+回滚；
│   │                        #   与 core/free_effect.py 并列为两条受控写状态通道，见模块头「通道边界」）
│   ├── memory/              # agent 记忆（memory_graph 图谱 SQLite 一轮一库 + dialogue_memory 对话记忆库，每 3 回合总结去重）
│   ├── backend/             # AI 服务抽象（LocalBackend / HttpBackend / FastAPI 参考 server）
│   ├── content/             # 数据表（派系 / 军队 / 州县 / 六部 / 科技 / 财政 / 大臣 / ministers/persona.py 人格 / 建筑 / 家产基线 / codex_data.py 图鉴数据）
│   ├── audio/               # 音频骨架：manifest 槽位登记 + tts 朗读（**播放未接线**）
│   ├── telemetry/           # 玩法遥测（store.py 指标落库，可选）
│   ├── assets/              # 美术 / 舆图资源（map / 立绘 / 事件图 / 图标 / audio / models）
│   ├── frontend/            # **唯一前端**：Electron + React + TS + MapLibre（随本体入库；node_modules/out/dist/release 不入库）
│   ├── saves/               # 玩家存档（运行时生成）
│   ├── ai_config.json / ai_config.example.json  # 运行配置（api_key / base_url / model / enable_tools）
│   ├── requirements.txt / requirements-extras.txt  # Python 依赖（本体 / 可选增强）
│   ├── SongZuo.spec         # PyInstaller 打包规格（入口 backend_server_entry.py）
│   ├── pytest.ini           # pytest 配置（testpaths → ../_dev_tools/game-dev/tests）
│   └── README.md
│
├── 📦 构建 / 分发产物（不入库 / 被忽略）
│   ├── SongZuo/             # PyInstaller 构建输出（SongZuo.exe + _internal/）
│   └── build/               # PyInstaller 构建缓存
│
├── 🛠️ 开发工具（仓库根 `_dev_tools/`，不打包，仅本地测试）
│   ├── game-dev/tests/      # pytest 回归脚本（test_*.py；本机跑前先清 PYTHONPATH，见文末）
│   ├── game-docs/           # 文档：docs/游戏机制说明.md + analysis/（重构/平衡分析）
│   └── songzuo-game-studio/ # 专家团定义元文件
│
└── 🗄️ _dev_tools/_scratch/  # 无关归档（不参与版本管理 / 打包；E 修复：原文档误作仓库根 `_scratch/`）
    ├── game-audit/          # 由 game/_scratch/ 迁入的开发/审计脚本（30 个，无运行时引用）
    ├── generated-images/    # AI 生成的未落地试验稿
    ├── generated-audio/     # AI/人工生成的未落地音频试验稿
    ├── build/               # PyInstaller 构建缓存
    ├── _ref_app/            # Electron 打包参考工程（main/preload/steam 集成）
    ├── SongZuo.exe          # 已打包产物
    └── *.log                # 运行 / 诊断日志
```

> **目录分层纪律（E 修复）**：`game/` 本体目录内**不得**存放开发/审计临时脚本；
> 原先误置于 `game/_scratch/` 的 30 个 `_audit_*.py` / `_check_*.py` / `_fix_*.py`
> 已迁至 `_dev_tools/_scratch/game-audit/`（经全库检索确认无任何运行时引用）。

### 各层职责

| 层 | 是否打包 | 说明 |
|----|---------|------|
| 游戏本体 | ✅ 是 | 运行所需全部代码、资源、配置（Electron 安装包由 `frontend/` 构建，与 Python 本体分发物组合） |
| `构建/分发产物` | ❌ 否 | `SongZuo/`、`build/` 为构建输出，可随时重建 |
| `_dev_tools/`（仓库根） | ❌ 否 | 开发期测试 / 分析脚本，路径引用以仓库根为基准 |
| `_dev_tools/_scratch/` | ❌ 否 | 临时产物 / 归档 / Electron 参考工程，可随时清理（**不在 `game/` 内**） |

---

## 模块职责

| 模块 | 职责 |
|------|------|
| `ai/` | AI 叙事管线：`client.py`（LLM 调用 + 契约 validate/回喂 + `AI_ERROR_CODES` 6 码全生产者〔超时/401/403 精确映射〕+ 角色 agent 契约 + function calling 三档）、`client_narrative.py`（叙事 agent 客户端）、`contract_adapter.py`（34 契约 → {changes, narrative} 统一视图，**待接线**：有 T5 测试覆盖，尚无生产调用方）、`client_utils.py`（STATE_TOOL_SCHEMAS 3 工具 + parse_tool_calls + _tool_dispatch）、`narrative_guard.py`（叙事-数值校验〔支持中文数字〕+ 来源闭集 + 人物校验表）。契约缺字段处置策略（B6 考证）：**类型/枚举字段 → 拒绝式**（`return None`），**强度/档位字段 → 向下降级**（一律 中/小/微/不变，全库反查无一处落到 大/巨/极）；高代价协议（和亲/盟约/纳贡/战争）档位非法时直接拒绝——宁可少给，绝不因 AI 漏字段而多给、`narrative_fallback.py`（离线降级叙事模板）、`desensitize.py`（脱敏）、`schemas.py`（A1：JSON Schema 校验，可选）、`token_meter.py`（A3：token 计量 + **HTTP 计量表分组** `grouped_meter_rows`）、`semantic.py` + `vector_store.py`（B2：本地语义检索，可选）、`model_setup.py`（B2 模型下载入口）、`safety_lexicon.json`（安全词表）、`prompts/`（23 个 .md：角色 prompt + decree_style_ref 拟旨文风） |
| `core/` | 核心逻辑：`game_state.py`（状态机）、`commands.py`（回合时序：AI 推演 → 结算 → 叙事；`advance_and_settle` 事件+结算**原子封装**〔含按回合上折，AI 不可用时走模板兜底〕；`settle_local`/`advance_and_settle` 结算异常**快照回滚**，且回滚同时按水位截断记忆库〔A2〕；`envoy_diplomacy` 遣使缔约（经 `apply_treaty` 落地，D11）；`allocate_payraise` 拨帑入加俸预算〔D9〕）+ `commands_decree.py`（拟旨族 + 内帑金额解析）、`settlement.py`（结算主流程 + 机构改制 + 承接层钩子）+ `settlement_steps.py`（Step 1~11，含财政/灾荒/士绅囤粮、金融调制读 `FINANCE_DECIDE_BASE` 单一源）、`registries.py`（科技/兵种注册表 + 软约束）、`agent_router.py`（按需唤醒：economy 必调；5 契约接线 + diff 唤醒；未接线登记 `PENDING_CONTRACTS`）、`async_ai.py`（**未接线**〔审查 B7〕：契约以已移除的 Tkinter `ui.after` 轮询为前提，现 Web 架构的非阻塞由 FastAPI 线程池 + 前端 HTTP 异步承担；保留为参照实现，接线前不计已生效能力）、`free_effect.py`（契约落地，第二条受控通道）、`estate_mechanic.py`（家产/投资）、`era_mechanic.py`（时代五维：目标值重算）、`minister_profile.py`（群臣档案：年龄/性情/生平，HTTP 与测试共用） |
| `engine/` | 应用层：`state_applier.py`——**AI changes 唯一改状态通道**（验证/合并/守恒校验/cascade/原子写库/变更日志/返回叙事层）；`CASCADE_REASON_FIX` 补来源支持按 `share` **拆分归属**（酒课 工匠60%/商人40%、田赋 农60%/士绅40%，末条吃尾差保 `ΣΔ==0` 精确，D10） |
| `memory/` | 记忆库（SQLite 一轮一库）：`memory_graph.py`（图谱：实体/关系 + 去重/6回合压缩/12回合总结/精确调动）、`dialogue_memory.py`（对话记忆库：召对对话 + 每 3 回合总结去重，与主库分离）。两库均有 `rollback_after(turn)`：结算失败时按水位截断，只删 `> turn`、不误删同回合合法写入（A2 —— 记忆库含 SQLite 连接不可深拷贝，故不能随 state 快照还原） |
| `backend/` | AI 服务抽象：`client.py`（LocalBackend / HttpBackend 统一接口）、`server.py`（B3：FastAPI + Uvicorn 参考后端，薄壳复用 LocalBackend 零复制，供 HttpBackend 联调/回归/远程体验） |
| `content/` | 数据（**单一权威源**）：`data.py`（派系 / 军队 / 州县 / 六部 / 财政 / TIER_RANGE 7 档 / FREE_EFFECT_CAP / FINANCE_DECIDE_BASE / BUILDING_STD / ESTATE_INIT / AI_ERROR_CODES / `clamp` / `TECH_EFFECT_LABELS` / `DESENSITIZE_MAP`）、`ministers/data.py`（大臣数据库）、`ministers/persona.py`（0-100 六维人格 + 立场演化〔国运取 `population_satisfaction`；仅 MINISTERS 在册者演化〕+ 阳奉阴违）、`codex_data.py`（图鉴 8 类数据，自 Tk 面板迁出） |
| `audio/` | 音频**骨架（播放未接线）**：`manifest.py`（资源清单与槽位登记 + `EVENT_AUDIO_CLASS` 分类单一源；8 个槽位 `file` 均为空，其中 6 项待生成、2 项为运行时合成）、`tts.py`（B1：大臣语音朗读，edge-tts 微软在线，可选）。Tk 界面删除后播放路径随之消失，`assets/audio/` 目前仅 `.gitkeep`；前端设置面板的音量项亦只有本地 state（不写 localStorage、无播放对象）。即「清单已定、播放未接」，待接线后方可称落地 |
| `telemetry/` | 玩法遥测：`store.py`（指标落库，可选，规划性增强中） |

---

## 前端与 HTTP API 面

**唯一前端**：`frontend/`（Electron + React + TypeScript + MapLibre）——随游戏本体入库，唯构建产物不入库。
已迁移能力（2026-09）：存档·读档槽位入口 / 返回主菜单 / Token 计量表 / 外邦省份详情 /
结算演出（本月损益 ▲▼ + 逐行揭示 + 跳过）/ 开局引子仪式 / 拟诏会签链（润色·批改·弃删）/
奏报摘要（月折）/ 朝局简报（可行动项跳转）/ 群臣档案（年龄·性情·生平）/ 中枢卡片召对 /
外交名录动态派生 / 右侧栏民生·群臣 / 界面字体族 / 办差工具三档 / 即时回执（朝报「近日机务回执」）。

**后端端点**（`backend/server.py`，前端直连；完整说明见机制文档 §八）：

| 端点 | 用途 |
|------|------|
| `POST /api/new_game` · `/api/advance` | 开局 / 回合推演（返回 events/log/report/state） |
| `POST /api/action` | 统一动作分发（与前端 `ActionName` 逐一对齐） |
| `POST /api/resolve_event` | 事件抉择（前端按 `title` 传 → 服务端反查完整事件对象；取不到明确 404） |
| `POST /api/decree/polish` · `/decree/draft` · `/decree/discard` | 诏书润色·批改 / 入待签 / 弃删 |
| `POST /api/monthly_report` · `/api/council_review` | 月折 / 三省会签（带缓存复用） |
| `GET /api/readouts` | 派生读数：army / arsenal / finance / flow / granary / `briefing` / `ministers` / defense_lines |
| `GET /api/meter` · `POST /api/meter/reset` | Token 计量表（分桶 + 召对命中率 + 历史）与清零 |
| `POST /api/save` · `/api/load` · `GET /api/save_slots` | 存档 / 读档 / 槽位列表（含损坏标记） |
| `POST /api/conclude` | 结局评估（规则七维 + AI 史评） |
| `GET|POST /api/ai_config` · `POST /api/fetch_models` | AI 配置（含 `enable_tools` 三档）/ 模型探测 |
| `GET /health` | 健康检查 |

鉴权：服务端设 `SONGZUO_SERVER_TOKEN` 后除 `/health` 外均需 `Authorization: Bearer`；
状态快照下发前脱敏（`loyalty`/`corruption` 档位词、`minister_estate` 档位化、密令 `secret_loyalty` 剔除）。

---

## 近期质量修复（2026-09 全量审计）

> **第二轮复审修复要点见本节末**（崩溃/安全/守恒/AI 管线；标注 `R2-*`）。

| 类别 | 要点 |
|------|------|
| 守恒与原子性 | `state_applier` 写入**原子回滚**（失败整批不落地）；0-100 区间校验；守恒补记账只补未配对项；内帑调拨执行前复检余额；月度结算异常**快照回滚**；存档**原子写**（`.tmp` + `os.replace`）+ 损坏档备份 `.corrupt` |
| 数值修正 | 评价「武功」量纲；士绅囤粮 / 买方分摊 / 家产封顶 / 奢侈分配的守恒漏洞；时代五维棘轮 → 目标值重算；学校科技加成小数池；`EXAM_HARD_POOR_SHARE` 补 7 档；`FINANCE_DECIDE_BASE` 单一权威源；外邦 `type` 注册；图鉴死键对齐 |
| AI 管线 | 6 错误码全生产者（超时/401/403 精确映射）；网络层退避重试；dialogue 遇端点不支持工具正确降级 + 去重复计费；叙事护栏支持中文数字；缓存改 LRU |
| 记忆库 | 对话总结冲突改**合并**（不再静默丢数据）；按需建表 + WAL；压缩/总结窗口不重叠 |
| 接口一致性 | 5 个结算侧契约接入按需唤醒 + diff 唤醒接线（`_last_agent_diff`）；未接线契约登记 `PENDING_CONTRACTS`；新增 HTTP 端点（见上节） |
| 前端 | Tk 界面与 Web 舆图桥均已删除（`ui/` 包**整体移除**）；界面全在 `frontend/`（Electron+React+MapLibre），游戏内舆图自带实现；Web 迁移补齐清单见上节 |

### 第二轮复审修复（2026-09，`R2-*`）

| 编号 | 类别 | 要点 |
|------|------|------|
| R2-1 | 崩溃 | `settlement_steps._settle_coin_melt` 熔铜池溢出分支缺 `COPPER_RESOURCE_DIM` 导入 → NameError 中断整月结算（已补导入） |
| R2-2 | 安全 | `/api/fetch_models` 原在未填 key 时回落服务端已存 Key 并以**客户端指定 base_url** 外联（凭据外泄 + SSRF）；现仅在「目标与已配置端点一致」时复用，且强制校验 http(s) |
| R2-3 | 安全 | 鉴权绕过：Python 端「未配 token 即全放行」→ 改为「无 token 时仅放行回环来源」+ `hmac.compare_digest`；Rust 端原**完全无鉴权**且绑 `0.0.0.0` → 新增 `/api/*` 鉴权中间件（同构规则），CORS 可经 `SONGZUO_CORS_ORIGINS` 收紧 |
| R2-4 | 安全 | Electron：`sandbox:false` → `true`；`shell.openExternal` 任意协议 → 仅 http(s)；补 `will-navigate` 白名单 |
| R2-5 | 守恒 | 市舶关税在 `_settle_extensions` 与 `_settle_finance` 双通道入国库（重复计账、凭空增币）→ 删去前者，只保留「税从 POP 征」守恒通道 |
| R2-6 | 守恒 | Rust `settle_granary` 二次调用带副作用的 `settle_land_local` → 本色粮单月双计（已删除该调用） |
| R2-7 | 机制 | 破产两档线（原 −500万/−2000万）与国库 `max(0,…)` 纪律矛盾 → 永不可达；改为以 **累计亏空深度** `GameState.deficit_depth()` 为唯一判据（`TREASURY_CRISIS_LINE=500万` / `TREASURY_COLLAPSE_LINE=2000万`），并同步存档/评价/简报 |
| R2-8 | 守恒 | 士绅「收租」原把**金额**并入田亩 `gentry_land`（单位错 + 无对手方）→ 改为由农 POP wealth 守恒转入大臣家产（封顶限幅） |
| R2-9 | 守恒 | `registries._pay_equip_and_grain` 原把金额按「每维度各加 `eq_total*0.5`」写入**实物**军械库（单位错 + N× 超算）→ 按 per 权重登记实物数量，并以人均装备价值折算使 Σ(数量×价) ≈ eq_total |
| R2-10 | 守恒 | `free_effect` 出账只逐项校验、不校验**合计** → 契约半落地；改为按净额合计校验（含 cost），任一不足整单拒绝 |
| R2-11 | 机制 | `focus_mechanic`：欠费月仍推进国策进度（可免费完成）→ 改为停摆不推进；互斥分支「任意解锁即整支锁死」→ 改按 `power_level` 比较；「政务·财政减耗」原扣累计统计（假效果）→ 改提升真实 `waste_reform.savings` |
| R2-12 | AI 管线 | `AIClient.enable_tools` 实例属性遮蔽同名方法（调用即 TypeError、`_call_with_tools` 永远不可达）→ 属性改名 `enable_tools_mode`，方法与属性双向同步 |
| R2-13 | AI 管线 | 召对工具分支第二轮返回 str 时穿透，落到第三次不带 tools 的请求（三倍计费且回奏被丢弃）→ 统一归一为文本后无条件返回 |
| R2-14 | AI 管线 | 办差工具 `register_draft` 的 `effects` 为对象契约，下游按列表迭代 → 会签审批 AttributeError → 新增 `_coerce_effects_to_list` 双向归一 + `effects_to_dict` 形态守卫 |
| R2-15 | AI 管线 | 非幂等重试：AI 网络层对**读超时**重试、`HttpBackend`/前端对 5xx 重试非幂等端点 → 现仅对「请求未送达」重试，非幂等端点不自动重试；T1 重发补记 token 计量，计量累加加锁 |
| R2-16 | AI 管线 | 叙事人物护栏只写 `_char_violation` 无读取方（空转）→ 按文档意图回喂一次订正要求 |
| R2-17 | 并发/健壮 | `backend/server.py` 状态判空移入全局锁内；`/api/ai_config` 联网探测移出锁；Rust 存档改 `.tmp`+rename **原子写**、补 `/health` 别名、bind 失败不再 panic；记忆库 `save()` 补清 `summaries`、`query_sql` 降级记 warning |
| R2-18 | 契约/文档 | 校正 `frontend/` 路径（在 `game/frontend/`）、`backend/client.py` 前后矛盾的后端定位、Rust 端过期 tkinter 注释/存档目录口径、工具数/路数注释等 |

细节见 `_dev_tools/game-docs/docs/游戏机制说明.md` 头部「2026-09 全量审计修复要点」。

---

## 代码规范

1. **导入约定**
   - 跨模块相互引用（如 `core.commands` ↔ `core.settlement`）一律使用**函数内延迟导入**（`from core.xxx import YYY`），禁止顶层互引，避免循环依赖。
   - 全局常量 / 配置以单一权威源为准（如 `SAVE_DIR` 定义于 `content/data.py`，其他模块从此 import，不得重复定义）。

2. **文件头**
   - 所有 `.py` 文件顶部统一以 `# -*- coding: utf-8 -*-` 开头，并附模块 docstring。

3. **资源引用**
   - 地图仅引用现存的 `assets/map/empire_bg.png` 与 `desk_bg.png`；文档字符串与代码保持一致，不得引用已删除的资源。

4. **分层纪律**
   - 游戏本体代码不得 `import _dev_tools/` 或其下的 `_scratch/`。
   - `_dev_tools/`（仓库根）、`_dev_tools/_scratch/` 下的脚本仅供本地运行，不得作为游戏运行路径的一部分。
   - 专家团 / 工具产出的临时文件默认落 `_dev_tools/_scratch/`，不污染 `game/` 本体。

5. **前端（Electron / React / TS）约定**
   - **位置**：Electron 工程在 `game/frontend/`（与游戏本体同仓同库；`node_modules/`、`out/`、`dist/`、`release/` 等构建产物不入库）；经 HTTP 桥对接 Python 后端；Node 端不得直接读写游戏存档。
   - 进程边界：渲染进程（`renderer/`）只与 `main/` 主进程通过 `preload` 暴露的桥通信（contextIsolation 开启），禁止在渲染进程内 `require('node:fs')` 直连内核。
   - 舆图：前端舆图用 MapLibre 渲染，几何源由 `scripts/build-topo.ts` 生成的 topojson 提供，状态数据取快照的 `external_regimes`；**Python 侧无舆图桥**（`ui/map_web.py` 属独立预览链，已随预览一并删除）。
   - 类型契约：前后端对齐 `frontend/src/renderer/api/client.ts` 的类型定义；状态变更以结构化 changes 为准（`ai/STATE_TOOL_SCHEMAS` 为**预留契约**，见架构段说明）。

---

## 运行

### Python 后端（唯一运行形态）

```bash
cd game
pip install -r requirements.txt
python -m backend.server        # 参考后端：127.0.0.1:8080，端点 /api/*
# 或分发入口（PyInstaller 打包用，内部等价调 backend.server.main）
python backend_server_entry.py
```

> **Tk 界面已废弃删除**（原 `gui_main.py` / `宋祚.bat` / `ui/panels_*.py` 已移除）；
> 玩家界面为 `frontend/`（Electron + React + MapLibre），经 HTTP 调用本后端。
>
> 参考后端为 **FastAPI + Uvicorn 薄壳**（需 `requirements-extras.txt`），**100% 复用
> `LocalBackend`（`core.commands`）零复制**——根治"远程后端常量漂移"质量债；
> 无 AI key 时自动走本地降级叙事（绝不伪造在线结果）；单会话全局锁（单机语义）。

配置见 `ai_config.json`（需填入可用的 LLM `base_url` / `api_key` / `model`，另有 `enable_tools` 办差工具三档）。**AI 是游戏核心引擎**（全游戏级强制 AI）：未配置时，拟旨/月报/召对/推演/自由动作**不执行**并返回明确错误（`AI_NOT_CONFIGURED`，提示配置 OpenAI 兼容 API），绝不伪造效果。

### Web 前端（Electron / React）

```bash
# Electron 工程在 game/frontend（随本体入库，构建产物不入库）
cd game/frontend
npm install
npm run dev      # electron-vite 开发模式（热更新）
npm run build    # 产出 out/（main + renderer）
npm run dist     # electron-vite build + electron-builder --win nsis → Windows 安装包
npm run typecheck
```

前端经 HTTP 桥对接 Python 后端；舆图由 MapLibre 渲染，几何源经 `npm run build:topo` 生成。

### 舆图

游戏内舆图**已完整**，位于前端 `game/frontend/src/renderer/map/`
（`MapView.tsx` / `mapController.ts` / `layers.ts` / `markers.ts`，MapLibre），
数据直接取状态快照的 `external_regimes`，不依赖任何 Python 侧舆图桥。

因此独立预览链**已删除**：`preview_map.py`、`map_web_main.py`、`ui/map_web.py`
（连带 `game/ui/` 包与根目录 `preview_map.bat`）。删除依据：后端与前端对
`ui.map_web` / `WebMapController` / `external_provinces_from_state` 均**零引用**
（实证），该链仅供独立预览；连带移除依赖它的用例 `test_external_provinces_for_web_map`，
并从 `SongZuo.spec` 的 hiddenimports 摘除 `ui` / `ui.map_web`。

> **文档**：完整机制见 `_dev_tools/game-docs/docs/游戏机制说明.md`（AI 驱动架构 / 月度结算 / 诏令 / 经济 / 军政 / persona / 记忆 / HTTP API 面）；
> 另有本 README「模块职责」段 + 各模块文件头 docstring 作为速查；设计与重构分析见 `_dev_tools/game-docs/analysis/`。
>
> **测试注意**：本机 CodeBuddy 注入 sitecustomize shim（PYTHONPATH）会干扰测试（大量假失败）——跑 pytest 前先 `$env:PYTHONPATH=''` 并删 `CODEBUDDY_TOOL_CALL_ID`/`CODEBUDDY_SAFE_DELETE_BULK_STATE_DIR` 环境变量。

依赖安装：

```bash
pip install -r requirements.txt              # 游戏本体运行依赖
pip install -r requirements-extras.txt       # 可选增强：A1 JSON Schema 校验 / A3 token 计量 / B1 语音
                                             # / B2 语义检索 / B3 参考后端（FastAPI+Uvicorn）
```

### 后端连接（本地 / 云托管）

游戏逻辑默认在本进程内执行（本地单机）。如需连接云端 Rust 后端（`songzuo_server`），按以下优先级配置：

1. **环境变量**（命令行/启动脚本）：

   ```bash
   set SONGZUO_BACKEND=https://songzuo-298842-11-1440445995.sh.run.tcloudbase.com
   python -m backend.server
   ```

2. **配置文件**（分发场景，与 `ai_config.json` 惯例一致）：在 `game/`（或 exe 同级目录）放 `backend_config.json`：

   （可选字段 `"token"`：服务端设置 `SONGZUO_SERVER_TOKEN` 时，客户端需携带同名 token 才能通过鉴权。）

   ```json
   { "backend": "remote", "url": "https://songzuo-298842-11-1440445995.sh.run.tcloudbase.com" }
   ```

   置为 `{ "backend": "local" }` 或删除该文件即回到本地模式。

后端选择顺序：`SONGZUO_BACKEND` 环境变量 > `backend_config.json` > 本地。
