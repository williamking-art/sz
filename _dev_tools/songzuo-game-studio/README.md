# Songzuo Game Studio（宋祚游戏制造组）

《宋祚》是一款以北宋徽宗朝为背景的治国模拟器。本专家包是一个 **Team 型多角色协作团队**：1 名主理人 + 11 名专家，覆盖从史实叙事、策略数值、核心架构、AI 管线、界面美术、音频、数据分析到质量保障与打包发布的全链路生产。

## 类型

Team 型（多角色协作团队）

## 文件关系（本包为专家团主体权威源）

`songzuo-game-studio/` 是专家团的**主体维护源（single source of truth）**，所有定义的新增与修订都在本包内进行：

- **`TEAM.md`**（本包）—— 专家团**主体权威定义**：总提示词 + 12 张角色卡 + 来源索引 + 调用示例 + Skillhub 分配表。优先读这份。
- **`agents/`** —— 11 个可被 Team 模式逐个加载的独立专家文件（含 frontmatter 与 SendMessage 回传规范），与主理人 `songzuo-game-studio-team-lead.md`；`agents/INDEX.md` 为 Team 模式一键加载索引（成员表 + 路由映射 + 启动剧本）。
- **`scripts/load_team.py`** —— 可执行加载脚本（解析 `agents/` 并输出团队配置/任务路由卡）。
- **（历史副本已删除）** —— 工程内 `_scratch/team_orchestra.md` 曾为工作镜像，现已并入本包并删除，专家团定义唯一存于本包。

> 权威根目录：`G:/sz/game/`。若项目结构变更，以游戏 `README.md` 为准同步。

## 团队构成

**主理人（技术统筹）**

| 成员 ID | 花名 | 职责 |
|---------|------|------|
| songzuo-game-studio-team-lead | 邹运筹 | 任务路由、最少专家集合、冲突裁决、交付验收（不代写任何成员产出） |

**专家团员**

内容与叙事

| 成员 ID | 花名 | 职责 |
|---------|------|------|
| song-narrative-designer | 史翰青 | 北宋史与叙事设计：大臣/派系/事件/诏书，史实三标签（史实/推演/抽象） |
| ai-pipeline | 言枢密 | AI 叙事管线：prompt/JSON 契约/脱敏/安全过滤/统一后端（Local+Http） |
| ai-integration | 沈舶司 | AI 接口落地：连通性/能力探测、降级链、契约自检、推演不动点回归 |

系统与数值

| 成员 ID | 花名 | 职责 |
|---------|------|------|
| strategy-systems | 蔡权衡 | 策略数值：财政/派系/军队/州县/科技/结算/结局，MDA 链路、档位封顶 |
| core-engineering | 谷承构 | 核心架构与存档：GameState/命令/12 步结算/事件触发/序列化迁移 |
| data-analytics | 析微澜 | 数据与分析：遥测/平衡挖掘/策略回放/敏感度分析/可玩性诊断 |

表现与交互

| 成员 ID | 花名 | 职责 |
|---------|------|------|
| tkinter-ui | 景呈宣 | Tkinter 界面：舆图/宋式主题/信息层级/键盘/错误反馈 |
| art-assets | 惠宋韵 | 宋式美术：地图/立绘/图标/规范/资源命名与授权 |
| sound-music-designer | 吕清商 | 宋式音频：雅乐/环境音/UI 音/事件配乐/播放总线 |

质量与交付

| 成员 ID | 花名 | 职责 |
|---------|------|------|
| regression-qa | 严归正 | 质量保障：单元/数值/AI 契约/GUI/存档/打包回归，发布质量门 |
| release-engineering | 封致远 | 打包发布：依赖审计/PyInstaller/EXE/发布包边界 |

## 协作铁律（核心约束）

1. **先建团队**：主理人亲自 `TeamCreate`，禁止委派成员建团或 spawn 主理人自己。
2. **消息中转**：成员产出经 `SendMessage` 回传主理人，再由主理人中转下一阶段，成员互不直连。
3. **成员结论为准**：专业产出必须对应成员输出后才采信。
4. **优先级**：P0 可运行代码 > P1 README/用户要求 > P2 文档 > P3 史料 > P4 经验；冲突须显式指出，不得静默选边。
5. **四不**：不伪造运行结果、测试结果、历史出处、资源或 AI 文本。

## 标准工作流程（SOP）

- **Phase 0 理解**：一句话重述目标，检查文件/入口/调用链/数据源/已有测试，列出硬约束与失败模式。
- **Phase 1 路由**：指定主责 + 协作专家 + 最少专家集合，输出任务卡（目标/非目标/玩家可见结果/硬约束/风险）。
- **Phase 2 实施**：按依赖调度成员；跨模块功能先设计后复核。
- **Phase 3 验证**：调度 `regression-qa` 做单元/子系统/跨模块与发布前回归；GUI 改动必验启动/点击/缩放/中文/键盘/缺资源。
- **Phase 4 交付**：主理人汇编报告，含 ① 结果摘要 ② 变更文件及作用 ③ 验证命令与结果 ④ 尚存风险 ⑤ 史料/算法/规范来源。

**预设 Workflow**

- `W1` 跨模块新功能：主理人路由 → 主责设计 → 复核成员 → regression-qa 验证 → 主理人验收。
- `W2` 史实事件 + AI 叙事：song-narrative-designer（事件卡+三标签）→ ai-pipeline（JSON 契约与脱敏）→ 主理人汇编。
- `W3` 发布验收：release-engineering（构建+启动验证）→ regression-qa（发布前回归）→ 主理人确认边界（不含 dev/_scratch/本机密钥）。

**单 agent 路由表**

| 问法类型 | 直接调谁 |
|---------|----------|
| 跨模块需求/不明确/专家冲突/里程碑/架构取舍 | 主理人（本项目） |
| 大臣/派系/事件/诏书/史实核查 | song-narrative-designer |
| 财政/数值/平衡/结算/结局/极端场景 | strategy-systems |
| 状态机/命令/存档/迁移/循环依赖 | core-engineering |
| prompt/JSON 契约/脱敏/安全过滤/后端 | ai-pipeline |
| Tkinter/舆图/主题/交互/中文显示 | tkinter-ui |
| 立绘/地图/图标/美术规范/资源 | art-assets |
| 测试/回归/验收/坏输入/兼容 | regression-qa |
| 打包/EXE/依赖/发布边界 | release-engineering |
| 雅乐/音效/配乐/音频资源 | sound-music-designer |
| 遥测/数据挖掘/平衡分析/回放 | data-analytics |
| 综合性问题 | 走预设 Workflow（主理人编排） |

## 关键技术基准（全团共享事实）

- 状态权威 `core/game_state.py`；数值权威 `content/data.py`（禁止重复定义 SAVE_DIR/常量）。
- 档位 `TIER_RANGE = {"无":0.0,"微":0.25,"小":0.5,"中":1.0,"大":1.8}`，经 `tier_to_value()` 封顶。⚠ 当前 `TIER_RANGE` 定义于 `ai/client_utils.py:67`，`content/data.py` 仅注释引用，属常量漂移，应迁回 `content/data.py` 统一权威源。
- 12 步月度结算流水线；结局七维加权（百姓口碑 0.20 > 文治/武功/民生/声望 0.15 > 财政/艺术 0.10）。
- 分层边界：`dev/`、`_scratch/` 不得成为运行依赖；AI 调用走 urllib；地图仅 `empire_bg.png`/`desk_bg.png` 为权威资源。
- 已知质量债：远程后端常量漂移、`_tool_dispatch` 直改 GameState 应迁后端、钱荒口径多处不统一、`TIER_RANGE` 定义于 `ai/client_utils.py` 未归 `content/data.py`。

## 使用示例

- "给徽宗朝设计一个新事件并走 AI 叙事" → 走 `W2`（song-narrative-designer → ai-pipeline）。
- "调整财政平衡并验证极端场景" → strategy-systems 设计、data-analytics 回放、regression-qa 落断言。
- "打包发布 Windows 版并做发布前回归" → 走 `W3`（release-engineering → regression-qa → 主理人）。
- "跨模块新增一个国策系统" → 走 `W1`（主理人路由 → 主责设计 → 复核 → 验证 → 验收）。

## 头像

头像已自动生成在 `avatars/` 目录下。如需替换为自定义头像，要求：
- 格式：PNG（推荐）或 JPG
- 尺寸：512×512 px
- 大小：单张不超过 500KB

## 与游戏工程的关系

本专家包是《宋祚》游戏工程（`G:\sz\game`）的多智能体开发团队，12 个席位已注册为 `songzuo-game-studio` 专家团实体。专家团的全部定义（总提示词 + 12 张角色卡 + 来源索引 + Skillhub 分配表 + 注册实体信息）**统一维护在本包内**（`TEAM.md` 为权威主体），工程内不再保留 `team_orchestra.md` 副本：

- 专家文件里的「项目基准（实勘）」一律指向 `G:\sz\game` 的真实文件（`core/`、`content/`、`ai/`、`ui/`、`dev/`）。
- 本包（`TEAM.md` + `agents/`）是**唯一权威配置来源**。
- 游戏 `README.md` 规定：跨模块需求一律先经本专家团主理人路由，禁止直接改核心模块。

## 工作流对接游戏工程

| 工程动作 | 触发 Workflow | 主责专家 |
|---------|--------------|---------|
| 新增史实事件+AI 叙事 | W2 | song-narrative-designer → ai-pipeline |
| 调数值/平衡并验证极端 | 单 agent | strategy-systems → data-analytics → regression-qa |
| 跨模块新功能 | W1 | 主理人路由 → 主责 → 复核 → 验证 |
| 打包发布 | W3 | release-engineering → regression-qa → 主理人 |
| 改 Tkinter/美术/音频 | 单 agent | tkinter-ui / art-assets / sound-music-designer |

## 安装（对接本机游戏工程）

专家包已置于 `G:\sz\_dev_tools\songzuo-game-studio`。要让其驱动 `G:\sz\game` 开发，在主理人侧以 Team 模式加载本包即可（主理人会 `TeamCreate` 拉起 11 名专家成员，按上文 SOP 调度）。

如要作为独立专家包分发，保留目录结构：

```
songzuo-game-studio/
├── README.md
├── agents/            # 11 个专家 + 主理人定义
└── avatars/           # 头像
```

## 打包分享

```bash
zip -r songzuo-game-studio.zip songzuo-game-studio/
```
