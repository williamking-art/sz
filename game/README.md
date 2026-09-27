# 宋祚 (Songzuo)

北宋徽宗治国模拟器 —— **AI 驱动的历史推演策略游戏**。

> **产品定位**：模拟一个穿越者（玩家），通过跟大臣的对话、发布圣旨（政策），来改变历史进程（北宋徽宗朝）。**AI 是游戏的核心引擎**——所有机制（经济/军事/政治/事件/外部/叙事）都通过 AI（agent）推演驱动，harness 保证稳定与编排，程序负责数值/守恒/校验。让 AI 更有效地发挥，就是游戏的宗旨。
>
> **架构**（详见 `_dev_tools/game-docs/docs/游戏机制说明.md`）：AI 通过**结构化契约**返回变更——各角色 `*_decide` 契约（JSON 输出，validate **拒绝式**校验）为主通道，大臣办差走 **function calling**（`enable_tools` 四档：auto/on/off/**simple**（限 4 工具面））；`STATE_TOOL_SCHEMAS`（update_state/query_state/trigger_event 3 工具 + tool_choice=required）为**预留契约**（尚无生产调用方，见 `ai/client_utils.py` 注释）。变更统一经应用层 `engine/state_applier.py`（验证/合并/**守恒校验**/cascade/原子写库）→ 记忆库（**SQLite 一轮一库**：主库存圣旨/口谕/决策 + 对话记忆库存召对，每 3 回合总结去重）→ 叙事组装（narrative_guard 护栏 + persona 差异）。Agent 按需唤醒（`agent_router.AGENT_DEFS`；`PENDING_CONTRACTS` 登记未接线契约），异步化（UI 不卡），回合时序 = AI 推演 → 系统结算 → 形成叙事。

---

## 前端构建 / 类型检查（无系统 Node 时的办法）

本仓库**不要求系统安装 Node**：`game/frontend/node_modules/electron`（**Electron 33.0.0**）
内置 **Node v20.18.0**，`ELECTRON_RUN_AS_NODE=1 electron.exe` 即等价于 `node`。
前端工具链（typescript / vite / electron-vite / react / rollup / esbuild）已随 `node_modules` 就位。

```powershell
cd game\frontend
$env:ELECTRON_RUN_AS_NODE = '1'
$node = '.\node_modules\electron\dist\electron.exe'

# 类型检查（两份配置都要过）
& $node .\node_modules\typescript\bin\tsc --noEmit -p tsconfig.web.json
& $node .\node_modules\typescript\bin\tsc --noEmit -p tsconfig.node.json

# 构建产物 → out\main、out\preload、out\renderer（主进程 loadFile('../renderer/index.html')）
& $node .\node_modules\electron-vite\bin\electron-vite.js build
```

| 事项 | 结论 |
|---|---|
| `tsc` 类型检查 | ✅ 可用（web/node 两配置） |
| `electron-vite build`（vite/rollup/esbuild） | ✅ 可用 |
| `electron-builder` **asar 打包** | ❌ **不可用**：写 `app.asar` 报 `Invalid package`（Electron 打过补丁的 `fs` 干扰 asar 写入）。打包需真正的 Node |
| 打包前置 | 还需先产出 PyInstaller 本体（`electron-builder.yml` 的 `extraResources.from: ../dist/SongZuo`；`game/dist/` 当前不存在） |
| 生效方式 | `out/` 变了之后**重启应用**（主进程产物也变了）才会加载新包 |

> `out/`、`dist/`、`node_modules/` 均已在 `game/frontend/.gitignore` 中，构建不会污染版本库。
>
> **两条可选路径**（都不需要用户预装 Node）：
> 1. **直接用 Electron 内置 Node**（上面这套，零下载）—— 适合类型检查与构建；
> 2. **让 `start.bat` 自动下载便携 Node** —— 它已内置回退逻辑：探测 `tools\nodejs\node.exe` →
>    `where node` → 都没有则提示并可**自动下载 Node 20.19.5**（npmmirror，约 30 MB）到 `tools\nodejs`，
>    随后 `npm install` + `npm run dev` 启动 Electron（客户端自行拉起 Python 后端）。
>    `tools\` 当前不存在 = 该回退尚未触发过，不是故障。

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
| `ai/` | AI 叙事管线：`client.py`（LLM 调用 + 契约 validate/回喂 + `AI_ERROR_CODES` 6 码全生产者〔超时/401/403 精确映射〕+ 角色 agent 契约 + function calling 三档）、`client_narrative.py`（叙事 agent 客户端）、~~`contract_adapter.py`~~（**2026-09-27 已移出 `game/` → `_dev_tools/unwired/contract_adapter.py`**：34 契约 → {changes, narrative} 统一视图，**待接线**）、`client_utils.py`（STATE_TOOL_SCHEMAS 3 工具 + parse_tool_calls + _tool_dispatch）、`narrative_guard.py`（叙事-数值校验〔支持中文数字〕+ 来源闭集 + 人物校验表）。契约缺字段处置策略（B6 考证）：**类型/枚举字段 → 拒绝式**（`return None`），**强度/档位字段 → 向下降级**（一律 中/小/微/不变，全库反查无一处落到 大/巨/极）；高代价协议（和亲/盟约/纳贡/战争）档位非法时直接拒绝——宁可少给，绝不因 AI 漏字段而多给、`narrative_fallback.py`（离线降级叙事模板）、`desensitize.py`（脱敏）、`schemas.py`（A1：JSON Schema 校验，可选）、`token_meter.py`（A3：token 计量 + **HTTP 计量表分组** `grouped_meter_rows`）、`semantic.py` + `vector_store.py`（B2：本地语义检索，可选）、`model_setup.py`（B2 模型下载入口）、`safety_lexicon.json`（安全词表）、`prompts/`（23 个 .md：角色 prompt + decree_style_ref 拟旨文风）、`kb_query.py`（**典章知识库**检索，见下节） |
| `core/` | 核心逻辑：`game_state.py`（状态机）、`commands.py`（回合时序：AI 推演 → 结算 → 叙事；`advance_and_settle` 事件+结算**原子封装**〔含按回合上折，AI 不可用时走模板兜底〕；`settle_local`/`advance_and_settle` 结算异常**快照回滚**，且回滚同时按水位截断记忆库〔A2〕；`envoy_diplomacy` 遣使缔约（经 `apply_treaty` 落地，D11）；`allocate_payraise` 拨帑入加俸预算〔D9〕）+ `commands_decree.py`（拟旨族 + 内帑金额解析）、`settlement.py`（结算主流程 + 机构改制 + 承接层钩子）+ `settlement_steps.py`（Step 1~11，含财政/灾荒/士绅囤粮、金融调制读 `FINANCE_DECIDE_BASE` 单一源）、`registries.py`（科技/兵种注册表 + 软约束）、`agent_router.py`（按需唤醒：economy 必调；5 契约接线 + diff 唤醒；未接线登记 `PENDING_CONTRACTS`）、`async_ai.py`（**2026-09-27 已移出 `game/` → `_dev_tools/unwired/async_ai.py`**；**未接线**〔审查 B7〕：契约以已移除的 Tkinter `ui.after` 轮询为前提，现 Web 架构的非阻塞由 FastAPI 线程池 + 前端 HTTP 异步承担；保留为参照实现，接线前不计已生效能力）、`free_effect.py`（契约落地，第二条受控通道）、`estate_mechanic.py`（家产/投资）、`era_mechanic.py`（时代五维：目标值重算）、`minister_profile.py`（群臣档案：年龄/性情/生平，HTTP 与测试共用） |
| `engine/` | 应用层：`state_applier.py`——**AI changes 唯一改状态通道**（验证/合并/守恒校验/cascade/原子写库/变更日志/返回叙事层）；`CASCADE_REASON_FIX` 补来源支持按 `share` **拆分归属**（酒课 工匠60%/商人40%、田赋 农60%/士绅40%，末条吃尾差保 `ΣΔ==0` 精确，D10） |
| `memory/` | 记忆库（SQLite 一轮一库）：`memory_graph.py`（图谱：实体/关系 + 去重/6回合压缩/12回合总结/精确调动）、`dialogue_memory.py`（对话记忆库：召对对话 + 每 3 回合总结去重，与主库分离）。两库均有 `rollback_after(turn)`：结算失败时按水位截断，只删 `> turn`、不误删同回合合法写入（A2 —— 记忆库含 SQLite 连接不可深拷贝，故不能随 state 快照还原）。**检索与容量完善（2026-09-18）**：`keyword_search` 中文改 2-gram 切分（原「连续中文整段」取词 → 玩家自然语言查询恒 0 命中，拟旨「既往同类诏令」注入长期空转）；内存 `query`/`keyword_search` 补 `turn <= self.turn` 封顶并与 `query_sql` 同口径，`load_game` 读档后按主存档水位重新对齐 `memory.turn`（审查 B-1/J-10「读旧档记得未来」）；`archive()` 由 `finish_turn` 每 12 回合接线（容量治理：低权重旧史打 archived 标记、不物理删除）；补审计读接口 `query_change_log` 与对话库 `ref_ids` 下钻（`fetch_dialogues_by_ids`/`summary_refs`/`list_summaries`）；对话总结改为回补全部未总结窗口；槽位 db 缺失（新开局/换档）时 SQL 路径回退内存镜像 |
| `backend/` | AI 服务抽象：`client.py`（LocalBackend / HttpBackend 统一接口）、`server.py`（B3：FastAPI + Uvicorn 参考后端，薄壳复用 LocalBackend 零复制，供 HttpBackend 联调/回归/远程体验） |
| `content/` | 数据（**单一权威源**）：`data.py`（派系 / 军队 / 州县 / 六部 / 财政 / TIER_RANGE 7 档 / FREE_EFFECT_CAP / FINANCE_DECIDE_BASE / BUILDING_STD / ESTATE_INIT / AI_ERROR_CODES / `clamp` / `TECH_EFFECT_LABELS` / `DESENSITIZE_MAP`）、`ministers/data.py`（大臣数据库）、`ministers/persona.py`（0-100 六维人格 + 立场演化〔国运取 `population_satisfaction`；仅 MINISTERS 在册者演化〕+ 阳奉阴违）、`codex_data.py`（图鉴 8 类数据，自 Tk 面板迁出） |
| `audio/` | 音频**骨架（播放未接线）**：`manifest.py`（资源清单与槽位登记 + `EVENT_AUDIO_CLASS` 分类单一源；8 个槽位 `file` 均为空，其中 6 项待生成、2 项为运行时合成）、`tts.py`（B1：大臣语音朗读，edge-tts 微软在线，可选）。Tk 界面删除后播放路径随之消失，`assets/audio/` 目前仅 `.gitkeep`；前端设置面板的音量项亦只有本地 state（不写 localStorage、无播放对象）。即「清单已定、播放未接」，待接线后方可称落地 |
| `telemetry/` | 玩法遥测：`store.py`（指标落库，可选，规划性增强中） |
| `assets/kb/` | **典章知识库**（随游戏分发的只读 SQLite）：`game_kb.sqlite`（6 篇设计文档 / 226 块）。与 `memory/` 的**记忆库职责正交**：记忆库 = 本局运行态（「史」，随存档变、可写）；典章库 = 静态设计规则（「典」，随分发、只读）。详见下节 |

---

## 典章知识库（`kb_search`，2026-09-24 新增）

> **定位**：把项目设计文档（`_dev_tools/game-docs/docs/*.md`）切片入库，让 AI 大臣在
> 奏对/拟旨时能**按需查阅成文规则**（货币口径、三冗、财力消耗、外邦产业链等），
> 替代原先依赖 CloudBase PG 的云端方案 —— 云端失效或断网时游戏内检索不受影响。

| 项 | 内容 |
|---|---|
| 库文件 | `game/assets/kb/game_kb.sqlite`（随游戏分发；**只读**） |
| 检索实现 | `game/ai/kb_query.py::_search()`（**唯一权威源**） |
| 构建工具 | `_dev_tools/game-docs/kb/build_kb.py`（`build` 重建 / `query` 试查） |
| 校验工具 | `_dev_tools/game-docs/kb/kb_stats.py`（文档数/块数/字符数/哈希漂移） |
| 开发库 | `_dev_tools/game-docs/kb/dev_kb.sqlite`（工程文档，**不随游戏分发**，游戏进程读不到） |

**检索算法**：FTS5 trigram（≥3 字符可靠）→ `LIKE AND`（中文子串精确，覆盖 2 字词盲区）→ `LIKE OR`（按命中词数降序）三级兜底。
`build_kb.py` 的开发侧查询**直接转调** `ai/kb_query.py::_search()`，故不存在两份副本漂移。

**接入管线**（`ai/client_utils.py`）：第 10 个工具 `kb_search`（schema `:560` / 白名单 `:583` / 必填校验 `:930` / dispatch `:1017`），
参数 `query`（必填，截断 100 字）+ `top_k`（1~5，默认 3）。**AI 主动调用**（「问到才查」），
与 `query_state` 同一省 token 哲学；单次回传上限 `MAX_RESULT_CHARS=1500` 字符。

**降级**：库缺失 / SQLite 无 FTS5 trigram / 任何异常 → 返回空串，dispatch 侧给「典章库中未查到」话术，
**绝不抛进 AI 管线**（同 `ai/semantic.py` 的降级哲学）。无命中亦不伪造内容。

**文档变更后的维护**：改完 `_dev_tools/game-docs/docs/*.md` 后必须重跑 `python build_kb.py build`，
否则游戏内读到的仍是旧切片；`kb_stats.py` 可校验内容哈希是否漂移。

---

## 前端与 HTTP API 面

**唯一前端**：`frontend/`（Electron + React + TypeScript + MapLibre）——随游戏本体入库，唯构建产物不入库。
已迁移能力（2026-09）：存档·读档槽位入口 / 返回主菜单 / Token 计量表 / 外邦省份详情 /
结算演出（本月损益 ▲▼ + 逐行揭示 + 跳过）/ 开局引子仪式 / 拟诏会签链（润色·批改·弃删）/
奏报摘要（月折）/ 朝局简报（可行动项跳转）/ 群臣档案（年龄·性情·生平）/ 中枢卡片召对 /
外交名录动态派生 / 右侧栏民生·群臣 / 界面字体族 / 办差工具三档 / 即时回执（朝报「近日机务回执」）/
记忆库面板（「记忆」：史略·概要·近关系·召对纪要·审计留痕，数据源 `GET /api/memory`）。

**后端端点**（`backend/server.py`，前端直连；完整说明见机制文档 §八）：

| 端点 | 用途 |
|------|------|
| `POST /api/new_game` · `/api/advance` | 开局 / 回合推演（返回 events/log/report/state） |
| `POST /api/action` | 统一动作分发（与前端 `ActionName` 逐一对齐） |
| `POST /api/resolve_event` | 事件抉择（前端按 `title` 传 → 服务端反查完整事件对象；取不到明确 404） |
| `POST /api/decree/polish` · `/decree/draft` · `/decree/discard` | 诏书润色·批改 / 入待签 / 弃删 |
| `POST /api/monthly_report` · `/api/council_review` | 月折 / 三省会签（带缓存复用） |
| `GET /api/readouts` | 派生读数：army / arsenal / finance / flow / granary / `briefing` / `ministers` / defense_lines |
| `GET /api/memory` | 记忆库只读视图（玩家可见「AI 记住了什么」）：实体计数 / 概要与史略 / 近 24 回合关系 / 召对纪要 / 变更留痕 |
| `GET /api/meter` · `POST /api/meter/reset` | Token 计量表（分桶 + 召对命中率 + 历史）与清零 |
| `POST /api/save` · `/api/load` · `GET /api/save_slots` | 存档 / 读档 / 槽位列表（含损坏标记） |
| `POST /api/conclude` | 结局评估（规则七维 + AI 史评） |
| `GET|POST /api/ai_config` · `POST /api/fetch_models` | AI 配置（含 `enable_tools` 三档）/ 模型探测 |
| `GET /health` | 健康检查 |

鉴权：服务端设 `SONGZUO_SERVER_TOKEN` 后除 `/health` 外均需 `Authorization: Bearer`；
状态快照下发前脱敏（`loyalty`/`corruption` 档位词、`minister_estate` 档位化、密令 `secret_loyalty` 剔除）。

---

## 历史记录（已归档）

历轮全审修复（`R2-*`~`R5-*`）、改进方案批次 0–7，以及 2026-08 ~ 09-22 的分析/修复计划/交接文档，
均已移入 [`_dev_tools/game-docs/archive/`](../_dev_tools/game-docs/archive/)（含 `review_2026-09-18`、
`fix_plan_2026-09-18`、`改进方案_合并版_2026-09-22` 等）。

**当前基线以全量 pytest 为准**（跑法见上文「运行」节）——本文**不再维护递增的 `passed` 数字**：
历史上写过 379 / 917 / 945 / 980 / 994 / 1010 等，都会过期，看测试结果即可。

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
   - 类型契约：前后端对齐 `frontend/src/renderer/api/client.ts` 的类型定义；状态变更以结构化 changes 为准（`ai/client_utils.py::STATE_TOOL_SCHEMAS` 为**预留契约**、未接生产；注意同文件的 `_tool_dispatch`/`_TOOL_SCHEMAS` **是生产路径**（八工具），两者不可混为一谈，见架构段说明）。

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
npm run test     # vitest 前端单测（jsdom；见 vitest.config.mts）
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
   set SONGZUO_BACKEND=https://<你的后端域名>      # 例：云托管服务的默认域名
   python -m backend.server
   ```

2. **配置文件**（分发场景，与 `ai_config.json` 惯例一致）：在 `game/`（或 exe 同级目录）放 `backend_config.json`：

   （可选字段 `"token"`：服务端设置 `SONGZUO_SERVER_TOKEN` 时，客户端需携带同名 token 才能通过鉴权。）

   ```json
   { "backend": "remote", "url": "https://<你的后端域名>" }
   ```

   置为 `{ "backend": "local" }` 或删除该文件即回到本地模式。

后端选择顺序：`SONGZUO_BACKEND` 环境变量 > `backend_config.json` > 本地。

## 文档同步纪律（2026-09-27 用户明确要求）

> **每次执行（改代码 / 改数据 / 改工具 / 改文档）之后，都必须修改对应文档。**
> 文档滞后于代码属**缺陷**，不是"以后再补"——提交前按下表自检。

| 改了什么 | 必须同步到 |
|---|---|
| 机制 / 数值口径（`core/`、`content/`） | `_dev_tools/game-docs/docs/游戏机制说明.md`；财政→`财力消耗设计.md`；货币→`货币口径规范_M0M1M2.md`；官制→`宋代官制与三冗设计.md`；建筑/产业链→`外邦省域产业链设计_2026-09-22.md` |
| 结算步序 | **权威镜像＝`_dev_tools/game-dev/tests/test_pop_identity.py::_STEPS`**（`test_middle_calibration.py` 逐步同函数比对）；`core/settlement_steps.py::_STEPS` 的**本地副本已于 2026-09-27 删除**（全库零引用，且其 27 条 vs 真实管线 **34** 步＝残缺，误引比没有更危险）。新增结算步必须同步**测试侧镜像**，并同步 `游戏机制说明.md` §二 流水线 |
| 新增/重构模块、目录职责变化 | 该目录的 `README.md`（`game/*/README.md`）——**这些 README 不入库但本地必须存在** |
| 工具脚本（`_dev_tools/*.ps1`、`cloudbase-check.ps1` 增删分节） | `docs/开发服务器与回归测试说明.md` 对应小节（如 §8.11 自检表） |
| **任何 `docs/*.md` 改动** | **重建知识库**：`python _dev_tools/game-docs/kb/build_kb.py build`，否则游戏内 `kb_search` 读到的仍是旧切片 |
| 知识库口径/扩源（`build_kb.py`、`kb_stats.py`） | 本节 + `游戏机制说明.md`「典章知识库」节 + `_dev_tools/README.md` |
| 新增/删除/归档文档 | `_dev_tools/game-docs/README.md`（文档树导览：权威 vs 史料） |
| 接口/快照字段（`backend/server.py`、`_state_to_dict`） | `game/backend/README.md` + `docs/` 相应口径（脱敏规则） |
| `.gitignore` / 入库策略变化 | 文件内注释写明**理由**（历史上有"被 README 引为权威却整目录不入库"的自相矛盾） |

**自动化落点（已就绪，别绕过）**：

- `_dev_tools/cloudbase-check.ps1` **第 7 节**：知识库 `STALE` → `FAIL`（`-Fix` 自动重建）；
- `_dev_tools/game-docs/analysis/check_docs_constants.py`：文档 ↔ 代码常量漂移；
- `_dev_tools/game-dev/tests/` 全量 pytest：口径类断言（役钱等额、六类 POP 单一权威源、步序镜像等）。

## 舆图资源重建（生成物不入库，2026-09-27 起）

> ⚠️ **为什么必须看这节**：舆图的**生成物已移出版本库**（避免 2200+ 文件占仓库）。
> 新克隆 / 换机后，`assets/map/web/*.geojson` 与 `frontend/public/map/**` 都是**空的**，
> 不重建则**舆图空白或只有底色**。
> （本节写在入库的 `game/README.md` 里，正是因为 `assets/README.md`、`frontend/README.md` 等
> 本地 README **不入库**——只在本地可见的文档不能承载"克隆后怎么办"。）

| 路径 | 类型 | 入库 | 再生成 |
|---|---|---|---|
| `assets/map/raw/*.json`（DataV 省级 + Natural Earth 河流/湖泊） | **源料** | ✅ | 需联网重下 |
| `assets/map/web/*.geojson`（11 层） | 生成物 | ❌ | `build_map_basemap.py` → `build_map_geo.py` |
| `frontend/public/map/{regions.topojson,land,rivers,lakes,cities.geojson,view.json}` | 生成物 | ❌ | `npm run build:topo` |
| `frontend/public/map/tiles/hill/**` | 生成物（地形晕渲 z5–z7） | ❌ | `python fetch_hillshade.py`（**需联网**） |

**四步（缺任一步舆图都不完整）**：

```powershell
$PY = 'D:\codebuddy\.audit-venv\Scripts\python.exe'   # 本机测试解释器
cd game
& $PY content/build_map_basemap.py    # → assets/map/web/{circuits,circuit_borders,prefectures,prefecture_borders}.geojson
& $PY content/build_map_geo.py        # → assets/map/web/{regimes,regime_borders,regime_prefectures,cities,land,rivers,lakes}.geojson
cd frontend; npm run build:topo       # → public/map/regions.topojson + 平移 geojson/view.json（**已实测可跑**）
cd ..; & $PY fetch_hillshade.py       # → public/map/tiles/hill/**（ESRI World Hillshade，需联网）
```

- 只缺 `tiles/` → 舆图正常但**无地形晕渲**；缺前两步或 `build:topo` → 舆图空白/只有底色。
- 📌 2026-09-27 修复历史审计 **I-8**：`fetch_hillshade.py` 原先输出到 `assets/map/web/tiles/hill`
  （**无人读取**，且 `build-topo.ts` 明写"瓦片无需拷贝"）→ 断链；现改为前端实际读取的
  `frontend/public/map/tiles/hill`（`frontend/src/renderer/map/mapController.ts` 的 hill 栅格源）。
- 📌 `.gitignore` 的对应规则在**文件末尾**（`# --- 舆图生成物：不入库`）——git 以最后匹配为准，
  后续新增放行规则时**不要把它覆盖回入库**（本项目已有"放行目录连带纳入 `__pycache__`"的先例）。

## 跑测试：快路径与全量（2026-09-27 起分层）

```bash
cd game
python -m pytest -m "not slow"      # 快路径：约 27–33 秒（跳过 8 个长时推演用例）
python -m pytest                    # 全量：约 57–60 秒
python -m pytest -m slow            # 只跑那 8 个长时用例（约 28 秒）
python -m pytest --durations=25     # 重新量耗时分布（分层阈值应据此复核）
```

- **分层依据（实测）**：全量 56.9 s；仅收集 1.4 s（故瓶颈不是导入）；最慢 25 例合计 ≈40 s，
  断崖在 1.31 s → 1.13 s，故阈值取 **≥1.3 s 标 `slow`**。
- **刻意不标 `slow` 的**：静态守卫与哨兵（如 `test_async_ai::test_async_module_is_not_wired_yet`、
  `test_faction_flows::..._static_guard`）——**快路径必须始终跑它们**。
- 覆盖度用 `--collect-only` 复核；marker 已注册在 `game/pytest.ini`（未注册会有
  `PytestUnknownMarkWarning`）。
- ⚠️ `pytest.ini` 里 `addopts = -q` 与命令行 `-q` 叠加会变 `-qq` 并**抑制摘要行**；
  要看摘要请加 `-o addopts=` 覆盖。

## 一条命令全量验证（写代码后跑这个）

```powershell
& .\_dev_tools\verify-all.ps1            # 全量：后端 + 前端 + 类型 + 截图矩阵（约 2 分钟）
& .\_dev_tools\verify-all.ps1 -Fast      # 后端快路径（-m "not slow"，省约 30 秒）
& .\_dev_tools\verify-all.ps1 -SkipShot  # 跳过截图（省约 30 秒）
& .\_dev_tools\verify-all.ps1 -Bench     # 追加地图首帧基准（信息性）
```

- 各节输出**可直接引用的摘要**（如 `pytest 1167 passed, 8 deselected`、`vitest 57 passed`、`截图 9 张`）；
- **退出码 = 失败数**，可被 CI/门禁直接消费；
- 与 `_dev_tools/cloudbase-check.ps1` 的分工：**本脚本查代码**，那边查**环境/云端/知识库**。
- 缺 Node/Edge/Python 时相关节会 **SKIP**（不制造假失败）；截图矩阵把 **<10KB 的 PNG 视为空白页**（面板崩了或 mock 没喂上）。

## 打包成 exe（打包入口）

```powershell
# 0) 依赖：Python 侧需要 PyInstaller（前端 electron/electron-builder 已在 devDependencies）
& .\.audit-venv\Scripts\python.exe -m pip install pyinstaller        # 首次

# 1) 冻 Python 后端（onedir）→ game/dist/SongZuo/
cd game
& <venv>\python.exe -m PyInstaller SongZuo.spec --noconfirm

# 2) 构建前端 + 打包 Electron 壳 → game/win-unpacked/SongZuo.exe（成品直接在 game/ 下）
cd game\frontend
npm run build
node node_modules\electron-builder\cli.js --win --dir        # 免安装的运行目录
node node_modules\electron-builder\cli.js --win nsis         # 生成安装包（需下载 nsis）

# 3) 冒烟（重要：先剥掉 ELECTRON_RUN_AS_NODE，否则 Electron 会被当 Node 跑）
Remove-Item env:ELECTRON_RUN_AS_NODE -ErrorAction SilentlyContinue
& ..\win-unpacked\SongZuo.exe
Invoke-WebRequest http://127.0.0.1:8080/health -UseBasicParsing   # 期望 {"ok":true,...}
```

**成品直接放在 `game/` 根**（`directories.output: ".."`）：
`game/win-unpacked/SongZuo.exe`＝免安装可运行入口、`game/SongZuo Setup *.exe`＝NSIS 安装包；
`game/dist/SongZuo/`＝PyInstaller 后端 onedir（**打包输入**，由 `extraResources` 拷进 `resources/backend/`，可删可重建）。

打包配置在 `package.json` 的 `build` 段：`extraResources` 把 `game/dist/SongZuo` 放进
`resources/backend/`（主进程按 `resources/backend/SongZuo.exe` 探测）；
`win.signAndEditExecutable=false` 免管理员权限（代价：图标/版本信息未写入）。
启动分段日志：设 `ELECTRON_ENABLE_LOGGING=1` 可见 `[boot] 标签 +Nms`。

### 三种形态与实测取舍（2026-09-27）

| 形态 | 位置 | 实测到后端就绪 | 说明 |
|---|---|---|---|
| **文件夹版（推荐）** | `game/win-unpacked/SongZuo.exe` | **2.8 s** | 免安装即玩，启动最快 |
| 安装包 | `game/SongZuo Setup 0.1.0.exe` | 2.8 s | 装完有桌面／开始菜单快捷方式 |
| 便携版单文件 | `game/SongZuo.exe` | **14.3 s** | 每次启动要把 ~1 GB 自解压到 `%TEMP%`，**慢 5 倍** |

便携版适合「拷一个文件就能走」；日常玩请用**文件夹版**或**安装包**。

