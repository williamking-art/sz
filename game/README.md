# 宋祚 (Songzuo)

北宋徽宗治国模拟器 —— **AI 驱动的历史推演策略游戏**。

> **产品定位**：模拟一个穿越者（玩家），通过跟大臣的对话、发布圣旨（政策），来改变历史进程（北宋徽宗朝）。**AI 是游戏的核心引擎**——所有机制（经济/军事/政治/事件/外部/叙事）都通过 AI（agent）推演驱动，harness 保证稳定与编排，程序负责数值/守恒/校验。让 AI 更有效地发挥，就是游戏的宗旨。
>
> **架构**：整个游戏 harness 化 + agent 化（详见 `docs/游戏机制说明.md` §〇）：Harness 层（确定性/错误分类/动态工具注册/叙事数值校验）+ Agent 层（persona + 记忆知识库 + 大臣自设工具 + 12 步推演 agent）+ 程序层（结算守恒 + free_effect 契约 + query_state 按需查询）。

---

## 目录分层规范

项目严格按「游戏本体 / 开发工具 / 无关归档」三层隔离，保证游戏可单独分发、不被开发脚本与临时产物污染。

```
songzuo/
├── 🎮 游戏本体（参与打包 / 运行所需）
│   ├── gui_main.py          # GUI 版入口
│   ├── ai/                  # AI 叙事管线（prompt 工程 / JSON 契约 / 错误标记 / narrative_guard 数值校验）
│   ├── core/                # 游戏核心（状态 / 结算 / 存档 / 事件 / 评估 / free_effect 契约 / tool_registry 自设工具 / estate_mechanic 家产投资）
│   ├── memory/              # agent 记忆知识库（memory_graph：实体/关系图谱 + 衰减 + 检索，跨回合连贯）
│   ├── ui/                  # 界面层（GUI / 舆图 / 主题 / 资源加载）
│   ├── backend/             # AI 服务抽象层（本地 / 远程后端）
│   ├── content/             # 数据表（派系 / 军队 / 州县 / 六部 / 科技 / 财政 / 大臣 / ministers/persona.py 人格 / 建筑 / 家产基线）
│   ├── audio/               # 音频（播放器封装 / 资源清单 / 配置接驳，规划性落地中）
│   ├── assets/              # 美术资源（地图 / 立绘 / 事件图 / 图标 / audio/ 资源落位）
│   ├── saves/               # 玩家存档（运行时生成）
│   ├── ai_config.json       # 运行配置（api_key / base_url / model，独立于代码）
│   ├── requirements.txt     # 依赖清单
│   └── README.md
│
├── 🛠️ dev/                  # 开发用工具（不打包，仅本地测试）
│   ├── _test_click.py       # GUI 交互测试
│   ├── _verify_exe.py       # EXE 打包验证
│   ├── _verify_ext.py       # 离线维度验证
│   ├── verify_frontend.py   # 前端收敛验证
│   └── verify_*.py          # 各子系统数值 / 逻辑回归脚本
│   ├── analytics/           # 玩法遥测 / 平衡数据挖掘（规划性落地中）
│   └── replay/              # 策略回放 / 极端场景兜底复现（规划性落地中）
│
└── 🗄️ _scratch/             # 无关归档（不参与版本管理 / 打包）
    ├── generated-images/    # AI 生成的未落地试验稿
    ├── generated-audio/     # AI/人工生成的未落地音频试验稿
    ├── build/               # PyInstaller 构建缓存
    ├── SongZuo.exe          # 已打包产物
    ├── *.log                # 运行 / 诊断日志
    └── （专家团定义已迁出至 `G:/sz/_dev_tools/songzuo-game-studio/`，本目录不再保留副本）
```

### 各层职责

| 层 | 是否打包 | 说明 |
|----|---------|------|
| 游戏本体 | ✅ 是 | 运行所需全部代码、资源、配置 |
| `dev/` | ❌ 否 | 开发期测试脚本，路径引用以项目根为基准 |
| `_scratch/` | ❌ 否 | 临时产物 / 归档 / 专家团元文件，可随时清理 |

---

## 模块职责

| 模块 | 职责 |
|------|------|
| `ai/` | AI 叙事管线：`client.py`（prompt 载入 + JSON 契约 + 拒绝式校验 + AI_ERROR_CODES 6 码 + 角色 agent 契约 economy/diplomacy/military/relief/free_effect/invest_decide）、`narrative_guard.py`（叙事-数值校验 + 来源闭集 + 人物校验表）、`decree.py`（诏书润色）、`desensitize.py`（数值脱敏）、`prompts/`（35+ 角色 prompt，含 persona 注入段） |
| `core/` | 核心逻辑：`game_state.py`（状态机）、`commands.py`（指令与月度结算）、`save_load.py`（存档序列化）、`events.py`（事件触发）、`evaluation.py`（结局评估）、`free_effect.py`（自由动作契约 once/ongoing + 白名单 + 拒绝式）、`tool_registry.py`（大臣自设工具动态注册）、`estate_mechanic.py`（大臣家产/投资记账）、`settlement_reform.py`（机构改制） |
| `memory/` | agent 记忆知识库：`memory_graph.py`（实体/关系图谱 + 衰减 λ + query/keyword_search/summarize + 槽位原子写盘 + 损坏重建）；短期行为日志（圣旨/口谕/决策 append-only 不注入）+ 长期图谱（选择性注入） |
| `ui/` | 界面：`gui.py`（Tkinter 主界面）、`map.py`（水墨舆图）、`theme.py`（宋式配色）、`assets.py`（资源加载） |
| `backend/` | AI 服务抽象：`client.py`（LocalBackend / HttpBackend 统一接口） |
| `content/` | 数据：`data.py`（派系 / 军队 / 州县 / 六部 / 财政 / TIER_RANGE 7 档 / FREE_EFFECT_CAP / FINANCE_DECIDE_BASE / BUILDING_STD / ESTATE_INIT / AI_ERROR_CODES）、`ministers/data.py`（大臣数据库）、`ministers/persona.py`（0-100 六维人格 + 立场演化 + 阳奉阴违） |
| `audio/` | 音频（规划性落地中）：`player.py`（非阻塞播放器封装，资源缺失静默降级）、`manifest.py`（资源清单与槽位登记）；音量权威源复用 `ui_config.json` 的 `volume` 键 |

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
   - 游戏本体代码不得 `import dev/` 或 `_scratch/`。
   - `dev/` 下的脚本仅供本地运行，不得作为游戏运行路径的一部分。
   - 专家团 / 工具产出的临时文件默认落 `_scratch/`，不污染游戏本体。

---

## 运行

```bash
# GUI 版
python gui_main.py
```

配置见 `ai_config.json`（需填入可用的 LLM `base_url` / `api_key` / `model`）。**AI 是游戏核心引擎**（全游戏级强制 AI）：未配置时，拟旨/月报/召对/推演/自由动作**不执行**并返回明确错误（`AI_NOT_CONFIGURED`，提示配置 OpenAI 兼容 API），绝不伪造效果。

> **文档**：完整机制见 `docs/游戏机制说明.md`（AI 驱动架构/记忆/persona/省 token/经济金融 AI/家产/建筑/投资）；架构重构计划见 `analysis/refactor_plan_ai_harness.md`。

依赖安装：

```bash
pip install -r requirements.txt
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
