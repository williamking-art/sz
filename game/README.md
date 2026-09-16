# 宋祚 (Songzuo)

北宋徽宗治国模拟器 —— **AI 驱动的历史推演策略游戏**。

> **产品定位**：模拟一个穿越者（玩家），通过跟大臣的对话、发布圣旨（政策），来改变历史进程（北宋徽宗朝）。**AI 是游戏的核心引擎**——所有机制（经济/军事/政治/事件/外部/叙事）都通过 AI（agent）推演驱动，harness 保证稳定与编排，程序负责数值/守恒/校验。让 AI 更有效地发挥，就是游戏的宗旨。
>
> **架构**（详见 `_dev_tools/game-docs/docs/游戏机制说明.md`）：AI 通过**结构化契约**返回变更——各角色 `*_decide` 契约（JSON 输出，validate 校验）为主通道，大臣办差走 **function calling**（`enable_tools` 三档：auto/on/off）；`STATE_TOOL_SCHEMAS`（update_state/query_state/trigger_event 3 工具 + tool_choice=required）为**预留契约**（尚无生产调用方，见 `ai/client_utils.py` 注释）。变更统一经应用层 `engine/state_applier.py`（验证/合并/**守恒校验**/cascade/原子写库）→ 记忆库（**SQLite 一轮一库**：主库存圣旨/口谕/决策 + 对话记忆库存召对，每 3 回合总结去重）→ 叙事组装（narrative_guard 护栏 + persona 差异）。Agent 按需唤醒（`agent_router.AGENT_DEFS`；`PENDING_CONTRACTS` 登记未接线契约），异步化（UI 不卡），回合时序 = AI 推演 → 系统结算 → 形成叙事。

---

## 目录分层规范

项目严格按「游戏本体 / 开发工具 / 无关归档」三层隔离，保证游戏可单独分发、不被开发脚本与临时产物污染。

```
game/  （宋祚游戏根目录，即仓库内 songzuo 游戏本体）
├── 🎮 游戏本体（参与打包 / 运行所需）
│   ├── backend_server_entry.py  # PyInstaller 后端入口（调 backend.server.main）
│   ├── map_web_main.py          # Web 舆图独立启动器（MapLibre，开发/验收）
│   ├── preview_map.py           # 舆图预览启动器（--demo/--serve/--browser）
│   ├── fetch_basemap.py / fetch_hillshade.py / build_map_basemap.py  # 舆图底图抓取/构建
│   ├── ai/                  # AI 叙事管线（见下方模块表）
│   ├── core/                # 游戏核心（状态 / 结算 / 存档 / 事件 / 评估 / free_effect 契约 / registries 注册表（科技+兵种）/ estate_mechanic 家产投资 / agent_router 按需唤醒 / async_ai 异步化 / minister_profile 群臣档案）
│   ├── engine/              # 应用层（state_applier：AI changes 验证/合并/守恒校验/cascade/原子写库+回滚；
│   │                        #   与 core/free_effect.py 并列为两条受控写状态通道，见模块头「通道边界」）
│   ├── memory/              # agent 记忆（memory_graph 图谱 SQLite 一轮一库 + dialogue_memory 对话记忆库，每 3 回合总结去重）
│   ├── ui/                  # **Web 舆图桥**（Tk 已废弃删除）：仅 map_web.py（MapLibre 控制器 + JS↔Python 双向桥 + 本地 HTTP 伺服 assets/map/web）
│   ├── backend/             # AI 服务抽象（LocalBackend / HttpBackend / FastAPI 参考 server）
│   ├── content/             # 数据表（派系 / 军队 / 州县 / 六部 / 科技 / 财政 / 大臣 / ministers/persona.py 人格 / 建筑 / 家产基线 / codex_data.py 图鉴数据）
│   ├── audio/               # 音频（manifest 清单 + tts 语音朗读，已落地）
│   ├── telemetry/           # 玩法遥测（store.py 指标落库，可选）
│   ├── assets/              # 美术 / 舆图资源（map / 立绘 / 事件图 / 图标 / audio / models）
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
│   ├── frontend/            # **唯一前端**：Electron + React + TS + MapLibre（node_modules 实体）
│   ├── game-dev/tests/      # pytest 回归脚本（test_*.py；本机跑前先清 PYTHONPATH，见文末）
│   ├── game-docs/           # 文档：docs/游戏机制说明.md + analysis/（重构/平衡分析）
│   └── songzuo-game-studio/ # 专家团定义元文件
│
└── 🗄️ _scratch/             # 无关归档（不参与版本管理 / 打包）
    ├── generated-images/    # AI 生成的未落地试验稿
    ├── generated-audio/     # AI/人工生成的未落地音频试验稿
    ├── build/               # PyInstaller 构建缓存
    ├── _ref_app/            # Electron 打包参考工程（main/preload/steam 集成）
    ├── SongZuo.exe          # 已打包产物
    └── *.log                # 运行 / 诊断日志
```

### 各层职责

| 层 | 是否打包 | 说明 |
|----|---------|------|
| 游戏本体 | ✅ 是 | 运行所需全部代码、资源、配置（Electron 安装包由 `_dev_tools/frontend` 构建，与 Python 本体分发物组合） |
| `构建/分发产物` | ❌ 否 | `SongZuo/`、`build/` 为构建输出，可随时重建 |
| `_dev_tools/`（仓库根） | ❌ 否 | 开发期测试 / 分析脚本，路径引用以仓库根为基准 |
| `_scratch/` | ❌ 否 | 临时产物 / 归档 / Electron 参考工程，可随时清理 |

---

## 模块职责

| 模块 | 职责 |
|------|------|
| `ai/` | AI 叙事管线：`client.py`（LLM 调用 + 契约 validate/回喂 + `AI_ERROR_CODES` 6 码全生产者〔超时/401/403 精确映射〕+ 角色 agent 契约 + function calling 三档）、`client_narrative.py`（叙事 agent 客户端）、`contract_adapter.py`（34 契约 → {changes, narrative} 统一视图，**待接线**：有 T5 测试覆盖，尚无生产调用方）、`client_utils.py`（STATE_TOOL_SCHEMAS 3 工具 + parse_tool_calls + _tool_dispatch）、`narrative_guard.py`（叙事-数值校验〔支持中文数字〕+ 来源闭集 + 人物校验表）、`narrative_fallback.py`（离线降级叙事模板）、`desensitize.py`（脱敏）、`schemas.py`（A1：JSON Schema 校验，可选）、`token_meter.py`（A3：token 计量 + **HTTP 计量表分组** `grouped_meter_rows`）、`semantic.py` + `vector_store.py`（B2：本地语义检索，可选）、`model_setup.py`（B2 模型下载入口）、`safety_lexicon.json`（安全词表）、`prompts/`（35+ 角色 prompt + decree_style_ref 拟旨文风） |
| `core/` | 核心逻辑：`game_state.py`（状态机）、`commands.py`（回合时序：AI 推演 → 结算 → 叙事；`settle_local` 结算异常**快照回滚**）+ `commands_decree.py`（拟旨族 + 内帑金额解析）、`settlement.py`（结算主流程 + 机构改制 + 承接层钩子）+ `settlement_steps.py`（Step 1~11，含财政/灾荒/士绅囤粮、金融调制读 `FINANCE_DECIDE_BASE` 单一源）、`registries.py`（科技/兵种注册表 + 软约束）、`agent_router.py`（按需唤醒：economy 必调；5 契约接线 + diff 唤醒；未接线登记 `PENDING_CONTRACTS`）、`async_ai.py`（后台 AI + 主线程回调；网络退避重试；失败不静默）、`free_effect.py`（契约落地，第二条受控通道）、`estate_mechanic.py`（家产/投资）、`era_mechanic.py`（时代五维：目标值重算）、`minister_profile.py`（群臣档案：年龄/性情/生平，HTTP 与测试共用） |
| `engine/` | 应用层：`state_applier.py`——**AI changes 唯一改状态通道**（验证/合并/守恒校验/cascade/原子写库/变更日志/返回叙事层） |
| `memory/` | 记忆库（SQLite 一轮一库）：`memory_graph.py`（图谱：实体/关系 + 去重/6回合压缩/12回合总结/精确调动）、`dialogue_memory.py`（对话记忆库：召对对话 + 每 3 回合总结去重，与主库分离） |
| `ui/` | **Web 舆图桥**（Tk 已废弃删除，界面为 `_dev_tools/frontend` Electron+React）：`map_web.py`（MapLibre 舆图控制器 + JS↔Python 双向桥 + 本地 HTTP 伺服 `assets/map/web`，pywebview/浏览器双模式） |
| `backend/` | AI 服务抽象：`client.py`（LocalBackend / HttpBackend 统一接口）、`server.py`（B3：FastAPI + Uvicorn 参考后端，薄壳复用 LocalBackend 零复制，供 HttpBackend 联调/回归/远程体验） |
| `content/` | 数据（**单一权威源**）：`data.py`（派系 / 军队 / 州县 / 六部 / 财政 / TIER_RANGE 7 档 / FREE_EFFECT_CAP / FINANCE_DECIDE_BASE / BUILDING_STD / ESTATE_INIT / AI_ERROR_CODES / `clamp` / `TECH_EFFECT_LABELS` / `DESENSITIZE_MAP`）、`ministers/data.py`（大臣数据库）、`ministers/persona.py`（0-100 六维人格 + 立场演化〔国运取 `population_satisfaction`；仅 MINISTERS 在册者演化〕+ 阳奉阴违）、`codex_data.py`（图鉴 8 类数据，自 Tk 面板迁出） |
| `audio/` | 音频（已落地）：`manifest.py`（资源清单与槽位登记 + `EVENT_AUDIO_CLASS` 分类单一源）、`tts.py`（B1：大臣语音朗读，edge-tts 微软在线，可选）；音量由**前端设置面板**控制（localStorage），本包不自持音量定义 |
| `telemetry/` | 玩法遥测：`store.py`（指标落库，可选，规划性增强中） |

---

## 前端与 HTTP API 面

**唯一前端**：`_dev_tools/frontend`（Electron + React + TypeScript + MapLibre）。
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

| 类别 | 要点 |
|------|------|
| 守恒与原子性 | `state_applier` 写入**原子回滚**（失败整批不落地）；0-100 区间校验；守恒补记账只补未配对项；内帑调拨执行前复检余额；月度结算异常**快照回滚**；存档**原子写**（`.tmp` + `os.replace`）+ 损坏档备份 `.corrupt` |
| 数值修正 | 评价「武功」量纲；士绅囤粮 / 买方分摊 / 家产封顶 / 奢侈分配的守恒漏洞；时代五维棘轮 → 目标值重算；学校科技加成小数池；`EXAM_HARD_POOR_SHARE` 补 7 档；`FINANCE_DECIDE_BASE` 单一权威源；外邦 `type` 注册；图鉴死键对齐 |
| AI 管线 | 6 错误码全生产者（超时/401/403 精确映射）；网络层退避重试；dialogue 遇端点不支持工具正确降级 + 去重复计费；叙事护栏支持中文数字；缓存改 LRU |
| 记忆库 | 对话总结冲突改**合并**（不再静默丢数据）；按需建表 + WAL；压缩/总结窗口不重叠 |
| 接口一致性 | 5 个结算侧契约接入按需唤醒 + diff 唤醒接线（`_last_agent_diff`）；未接线契约登记 `PENDING_CONTRACTS`；新增 HTTP 端点（见上节） |
| 前端 | Tk 界面废弃删除（`ui/` 仅留 Web 舆图桥）；Web 迁移补齐清单见上节 |

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
   - 游戏本体代码不得 `import _dev_tools/` 或 `_scratch/`。
   - `_dev_tools/`（仓库根）、`_scratch/` 下的脚本仅供本地运行，不得作为游戏运行路径的一部分。
   - 专家团 / 工具产出的临时文件默认落 `_scratch/`，不污染游戏本体。

5. **前端（Electron / React / TS）约定**
   - **位置**：Electron 工程在仓库根 `_dev_tools/frontend/`（开发包，**不进 `game/`**）；经 HTTP 桥对接 Python 后端；Node 端不得直接读写游戏存档。
   - 进程边界：渲染进程（`renderer/`）只与 `main/` 主进程通过 `preload` 暴露的桥通信（contextIsolation 开启），禁止在渲染进程内 `require('node:fs')` 直连内核。
   - 舆图：前端舆图用 MapLibre 渲染，几何源由 `scripts/build-topo.ts` 生成的 topojson 提供；Python 侧 `ui/map_web.py` 负责同源数据下发与双向事件桥。
   - 类型契约：前后端对齐 `_dev_tools/frontend/src/renderer/api/client.ts` 的类型定义；状态变更以结构化 changes 为准（`ai/STATE_TOOL_SCHEMAS` 为**预留契约**，见架构段说明）。

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
> 玩家界面为 `_dev_tools/frontend`（Electron + React + MapLibre），经 HTTP 调用本后端。
>
> 参考后端为 **FastAPI + Uvicorn 薄壳**（需 `requirements-extras.txt`），**100% 复用
> `LocalBackend`（`core.commands`）零复制**——根治"远程后端常量漂移"质量债；
> 无 AI key 时自动走本地降级叙事（绝不伪造在线结果）；单会话全局锁（单机语义）。

配置见 `ai_config.json`（需填入可用的 LLM `base_url` / `api_key` / `model`，另有 `enable_tools` 办差工具三档）。**AI 是游戏核心引擎**（全游戏级强制 AI）：未配置时，拟旨/月报/召对/推演/自由动作**不执行**并返回明确错误（`AI_NOT_CONFIGURED`，提示配置 OpenAI 兼容 API），绝不伪造效果。

### Web 前端（Electron / React）

```bash
# 源码在 _dev_tools/frontend（开发工程，不进 game/）
cd ../_dev_tools/frontend
npm install
npm run dev      # electron-vite 开发模式（热更新）
npm run build    # 产出 out/（main + renderer）
npm run dist     # electron-vite build + electron-builder --win nsis → Windows 安装包
npm run typecheck
```

前端经 HTTP 桥对接 Python 后端；舆图由 MapLibre 渲染，几何源经 `npm run build:topo` 生成。

### Web 舆图独立预览（开发 / 验收）

```bash
python preview_map.py --demo        # 演示分路易主（燕云十六州归宋）
python map_web_main.py --browser    # 系统浏览器模式（HTTP 桥 + 轮询通道）
```

> **文档**：完整机制见 `_dev_tools/game-docs/docs/游戏机制说明.md`（AI 驱动架构 / 月度结算 / 诏令 / 经济 / 军政 / persona / 记忆 / HTTP API 面）；
> 另有本 README「模块职责」段 + 各模块文件头 docstring 作为速查；设计与重构分析见 `_dev_tools/game-docs/analysis/`。
>
> **测试注意**：本机 CodeBuddy 注入 sitecustomize shim（PYTHONPATH）会干扰测试（大量假失败）——跑 pytest 前先 `$env:PYTHONPATH=''` 并删 `CODEBUDDY_TOOL_CALL_ID`/`CODEBUDDY_SAFE_DELETE_BULK_STATE_DIR` 环境变量。

依赖安装：

```bash
pip install -r requirements.txt              # 游戏本体运行依赖
pip install -r requirements-extras.txt       # 可选增强：A1 JSON Schema 校验 / A3 token 计量 / B1 语音
                                             # / B2 语义检索 / B3 参考后端（FastAPI+Uvicorn）/ Web 舆图（pywebview）
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
