# 宋祚 (Songzuo)

北宋徽宗治国模拟器 —— **AI 驱动的历史推演策略游戏**。

> **产品定位**：模拟一个穿越者（玩家），通过跟大臣的对话、发布圣旨（政策），来改变历史进程（北宋徽宗朝）。**AI 是游戏的核心引擎**——所有机制（经济/军事/政治/事件/外部/叙事）都通过 AI（agent）推演驱动，harness 保证稳定与编排，程序负责数值/守恒/校验。让 AI 更有效地发挥，就是游戏的宗旨。
>
> **架构**（详见 `docs/游戏机制说明.md`）：**AI 只通过 Function Call 返回结构化 changes 改状态**（3 工具 update_state/query_state/trigger_event + tool_choice required）→ 应用层 `engine/state_applier.py`（验证/合并/**守恒校验**/cascade/写库）→ 记忆库（**SQLite 一轮一库**：主库存圣旨/口谕/决策 + 对话记忆库存召对，每 3 回合总结去重）→ 叙事组装（narrative_guard 护栏 + persona 差异）。Agent 按需唤醒（economy 必调），异步化（UI 不卡），回合时序 = AI 推演 → 系统结算 → 形成叙事。

---

## 目录分层规范

项目严格按「游戏本体 / 开发工具 / 无关归档」三层隔离，保证游戏可单独分发、不被开发脚本与临时产物污染。

```
game/  （宋祚游戏根目录，即仓库内 songzuo 游戏本体）
├── 🎮 游戏本体（参与打包 / 运行所需）
│   ├── gui_main.py              # Tkinter GUI 版入口（宋祚.bat 调用）
│   ├── backend_server_entry.py  # PyInstaller 后端入口（调 backend.server.main）
│   ├── map_web_main.py          # Web 舆图独立启动器（MapLibre，开发/验收）
│   ├── preview_map.py           # 舆图预览启动器（--demo/--serve/--browser）
│   ├── fetch_basemap.py / fetch_hillshade.py / build_map_basemap.py  # 舆图底图抓取/构建
│   ├── ai/                  # AI 叙事管线（见下方模块表）
│   ├── core/                # 游戏核心（状态 / 结算 / 存档 / 事件 / 评估 / free_effect 契约 / registries 注册表（科技+兵种）/ estate_mechanic 家产投资 / agent_router 按需唤醒 / async_ai 异步化）
│   ├── engine/              # 应用层（state_applier：AI changes 验证/合并/守恒校验/cascade/写库，唯一改状态通道）
│   ├── memory/              # agent 记忆（memory_graph 图谱 SQLite 一轮一库 + dialogue_memory 对话记忆库，每 3 回合总结去重）
│   ├── ui/                  # 界面层（Tkinter GUI / Web 舆图 MapLibre / 主题 / 资源加载 / 面板族 panels_*）
│   ├── frontend/            # Electron + React + TypeScript Web 前端（独立 npm 工程，见下方）
│   ├── backend/             # AI 服务抽象（LocalBackend / HttpBackend / FastAPI 参考 server）
│   ├── content/             # 数据表（派系 / 军队 / 州县 / 六部 / 科技 / 财政 / 大臣 / ministers/persona.py 人格 / 建筑 / 家产基线）
│   ├── audio/               # 音频（manifest 清单 + tts 语音朗读，已落地）
│   ├── telemetry/           # 玩法遥测（store.py 指标落库，可选）
│   ├── assets/              # 美术 / 舆图资源（map / 立绘 / 事件图 / 图标 / audio / models）
│   ├── saves/               # 玩家存档（运行时生成）
│   ├── ai_config.json / ai_config.example.json  # 运行配置（api_key / base_url / model）
│   ├── requirements.txt / requirements-extras.txt  # Python 依赖（本体 / 可选增强）
│   ├── SongZuo.spec         # PyInstaller 打包规格
│   ├── pytest.ini           # pytest 配置（testpaths → ../_dev_tools/game-dev/tests）
│   ├── 宋祚.bat             # Windows 一键启动（清 CodeBuddy shim 后 python gui_main.py）
│   └── README.md
│
├── 📦 构建 / 分发产物（不入库 / 被忽略）
│   ├── SongZuo/             # PyInstaller 构建输出（SongZuo.exe + _internal/）
│   └── build/               # PyInstaller 构建缓存
│
├── 🛠️ 开发工具（仓库根 `_dev_tools/`，不打包，仅本地测试）
│   ├── game-dev/tests/      # pytest 回归脚本（verify_*.py / test_*.py）
│   ├── analysis/            # 重构 / 平衡分析文档
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
| 游戏本体 | ✅ 是 | 运行所需全部代码、资源、配置（`frontend/` 一并打包进 Windows 安装包） |
| `构建/分发产物` | ❌ 否 | `SongZuo/`、`build/` 为构建输出，可随时重建 |
| `_dev_tools/`（仓库根） | ❌ 否 | 开发期测试 / 分析脚本，路径引用以仓库根为基准 |
| `_scratch/` | ❌ 否 | 临时产物 / 归档 / Electron 参考工程，可随时清理 |

---

## 模块职责

| 模块 | 职责 |
|------|------|
| `ai/` | AI 叙事管线：`client.py`（LLM 调用 + tool_choice required + AI_ERROR_CODES 6 码 + 角色 agent 契约）、`client_narrative.py`（叙事 agent 客户端）、`contract_adapter.py`（34 契约 → {changes, narrative} 统一视图）、`client_utils.py`（STATE_TOOL_SCHEMAS 3 工具 + parse_tool_calls + _tool_dispatch）、`narrative_guard.py`（叙事-数值校验 + 来源闭集 + 人物校验表）、`narrative_fallback.py`（离线降级叙事模板）、`desensitize.py`（脱敏）、`schemas.py`（A1：AI 输出 JSON Schema 结构校验，可选）、`token_meter.py`（A3：token 计量，可选）、`semantic.py` + `vector_store.py`（B2：本地语义检索，可选）、`model_setup.py`（B2 一次性模型下载入口）、`safety_lexicon.json`（安全词表）、`prompts/`（35+ 角色 prompt + decree_style_ref 拟旨文风） |
| `core/` | 核心逻辑：`game_state.py`（状态机）、`commands.py`（回合时序：AI 推演 → 结算 → 叙事）+ `commands_decree.py`（拟旨族）、`settlement.py`（结算主流程 + 机构改制 + 承接层钩子）+ `settlement_steps.py`（Step 1~11 结算函数，含财政/灾荒/士绅囤粮）、`registries.py`（科技/兵种注册表 + 软约束）、`agent_router.py`（按需唤醒：economy 必调）、`async_ai.py`（后台 AI + 主线程回调，UI 不卡）、`free_effect.py`（契约落地）、`estate_mechanic.py`（家产/投资）、`era_mechanic.py`（时代五维） |
| `engine/` | 应用层：`state_applier.py`——**AI changes 唯一改状态通道**（验证/合并/守恒校验/cascade/原子写库/变更日志/返回叙事层） |
| `memory/` | 记忆库（SQLite 一轮一库）：`memory_graph.py`（图谱：实体/关系 + 去重/6回合压缩/12回合总结/精确调动）、`dialogue_memory.py`（对话记忆库：召对对话 + 每 3 回合总结去重，与主库分离） |
| `ui/` | 界面：`gui.py`（Tkinter 主界面）、`map.py`（水墨舆图）、`map_web.py`（Web 舆图 MapLibre 控制器 + JS↔Python 双向桥）、`theme.py`（宋式配色）、`assets.py`（资源加载）、`dialog.py` / `gui_common.py`（通用组件）、`panels_*.py`（面板族：basic/core/economy/govern/menu/military/meta/codex） |
| `frontend/` | Electron + React + TypeScript 单页游戏前端（舆图 + HUD + 面板浮层一体化）：`main/`（Electron 主进程 + preload 桥）、`renderer/`（React 渲染层：map / hud / panels 26 个 / store / api / utils）、`scripts/build-topo.ts`（舆图拓扑构建）；构建 `electron-vite build` + `electron-builder --win nsis` 产出 Windows 安装包 |
| `backend/` | AI 服务抽象：`client.py`（LocalBackend / HttpBackend 统一接口）、`server.py`（B3：FastAPI + Uvicorn 参考后端，薄壳复用 LocalBackend 零复制，供 HttpBackend 联调/回归/远程体验） |
| `content/` | 数据：`data.py`（派系 / 军队 / 州县 / 六部 / 财政 / TIER_RANGE 7 档 / FREE_EFFECT_CAP / FINANCE_DECIDE_BASE / BUILDING_STD / ESTATE_INIT / AI_ERROR_CODES）、`ministers/data.py`（大臣数据库）、`ministers/persona.py`（0-100 六维人格 + 立场演化 + 阳奉阴违） |
| `audio/` | 音频（已落地）：`manifest.py`（资源清单与槽位登记）、`tts.py`（B1：大臣语音朗读，edge-tts 微软在线，可选）；音量权威源复用 `ui_config.json` 的 `volume` 键 |
| `telemetry/` | 玩法遥测：`store.py`（指标落库，可选，规划性增强中） |

---

## 代码规范

1. **导入约定**
   - 跨模块相互引用（如 `ui.gui` ↔ `ui.map`）一律使用**函数内延迟导入**（`from ui.xxx import YYY`），禁止顶层互引，避免循环依赖。
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
   - 目录隔离：`frontend/` 为独立 npm 工程，经 `renderer/api/client.ts` 的 HTTP 桥对接 Python 后端（LocalBackend / HttpBackend / 参考 server）；Node 端不得直接读写游戏存档。
   - 进程边界：渲染进程（`renderer/`）只与 `main/` 主进程通过 `preload` 暴露的桥通信（contextIsolation 开启），禁止在渲染进程内 `require('node:fs')` 直连内核。
   - 舆图：前端舆图用 MapLibre 渲染，几何源由 `scripts/build-topo.ts` 生成的 topojson 提供；Python 侧 `ui/map_web.py` 负责同源数据下发与双向事件桥。
   - 类型契约：前后端共用 `frontend/src/renderer/types/`，状态变更以结构化 changes 为准，与 `ai/STATE_TOOL_SCHEMAS` 保持一致。

---

## 运行

### GUI（Tkinter）版

```bash
# 源码
python gui_main.py
# Windows 一键启动（已清 CodeBuddy shim 环境变量，失败见 songzuo_runtime.log）
宋祚.bat
```

配置见 `ai_config.json`（需填入可用的 LLM `base_url` / `api_key` / `model`）。**AI 是游戏核心引擎**（全游戏级强制 AI）：未配置时，拟旨/月报/召对/推演/自由动作**不执行**并返回明确错误（`AI_NOT_CONFIGURED`，提示配置 OpenAI 兼容 API），绝不伪造效果。

### Web 前端（Electron / React）

```bash
cd frontend
npm install
npm run dev      # electron-vite 开发模式（热更新）
npm run build    # 产出 out/（main + renderer）
npm run dist     # electron-vite build + electron-builder --win nsis → Windows 安装包
npm run typecheck
```

前端经 `renderer/api/client.ts` 通过 HTTP 桥对接 Python 后端；舆图由 MapLibre 渲染，几何源经 `npm run build:topo` 生成。

### Python 参考后端（FastAPI，可选）

```bash
pip install -r requirements-extras.txt
python -m backend.server        # 默认 127.0.0.1:8080，端点 /api/*
```

薄壳 100% 复用 `LocalBackend`（`core.commands`，零复制——根治"远程后端常量漂移"质量债），无 AI key 时自动走本地降级叙事（绝不伪造在线结果）。前端通过 `HttpBackend` 联调。

### Web 舆图独立预览（开发 / 验收）

```bash
python preview_map.py --demo        # 演示分路易主（燕云十六州归宋）
python map_web_main.py --browser    # 系统浏览器模式（HTTP 桥 + 轮询通道）
```

> **文档**：完整机制见 `docs/游戏机制说明.md`（AI 驱动架构/记忆/persona/省 token/经济金融 AI/家产/建筑/投资）；AI 架构升级计划见 `analysis/refactor_ai_upgrade_plan.md`；harness 化重构见 `analysis/refactor_plan_ai_harness.md`。
>
> **测试注意**：本机 CodeBuddy 注入 sitecustomize shim（PYTHONPATH）会干扰测试（大量假失败）——跑 pytest 前先 `$env:PYTHONPATH=''` 并删 `CODEBUDDY_TOOL_CALL_ID`/`CODEBUDDY_SAFE_DELETE_BULK_STATE_DIR` 环境变量。

依赖安装：

```bash
pip install -r requirements.txt              # 游戏本体运行依赖
pip install -r requirements-extras.txt       # 可选增强：A1 JSON Schema 校验 / A3 token 计量 / B1 语音 / B2 语义检索 / B3 参考后端 / Web 舆图
```

### 后端连接（本地 / 云托管）

游戏逻辑默认在本进程内执行（本地单机）。如需连接云端 Rust 后端（`songzuo_server`），按以下优先级配置：

1. **环境变量**（命令行/启动脚本）：

   ```bash
   set SONGZUO_BACKEND=https://songzuo-298842-11-1440445995.sh.run.tcloudbase.com
   python gui_main.py
   ```

2. **配置文件**（exe 分发场景，与 `ai_config.json` 惯例一致）：在 `game/`（或 exe 同级目录）放 `backend_config.json`：

   ```json
   { "backend": "remote", "url": "https://songzuo-298842-11-1440445995.sh.run.tcloudbase.com" }
   ```

   置为 `{ "backend": "local" }` 或删除该文件即回到本地模式。

后端选择顺序：`SONGZUO_BACKEND` 环境变量 > `backend_config.json` > 本地。
