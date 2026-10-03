# Songzuo Game Studio（宋祚游戏制造组）

《宋祚》是一款以北宋徽宗朝为背景的治国模拟器。本专家包是一个 **Team 型多角色协作团队**：1 名主理人 + 17 名专家（2026-09-03 负载均衡拆分），覆盖从史实叙事、策略数值、财政经济、核心架构、结算结局、AI 管线与提示词、界面框架与面板、美术音频、数据分析到质量保障与打包发布的全链路生产。

## 类型

Team 型（多角色协作团队）

## 文件关系（本包为专家团主体权威源）

`songzuo-game-studio/` 是专家团的**主体维护源（single source of truth）**，所有定义的新增与修订都在本包内进行：

- **`TEAM.md`**（本包）—— 专家团**主体权威定义**：总提示词 + 18 张角色卡 + 来源索引 + 调用示例 + Skillhub 分配表。优先读这份。
- **`agents/`** —— 17 个可被 Team 模式逐个加载的独立专家文件（含 frontmatter 与 SendMessage 回传规范），与主理人 `songzuo-game-studio-team-lead.md`；`agents/INDEX.md` 为 Team 模式一键加载索引（成员表 + 路由映射 + 启动剧本）。
- **`scripts/load_team.py`** —— 可执行加载脚本（解析 `agents/` 并输出团队配置/任务路由卡）。
- **（历史副本已删除）** —— 工程内 `_scratch/team_orchestra.md` 曾为工作镜像，现已并入本包并删除，专家团定义唯一存于本包。

> 当前仓库：`D:/codebuddy/sz/`。路径、模块与运行事实以 `sz/AGENTS.md`、`game/README.md`、现行代码与规格为准；本文件的旧 Tkinter、Mixin、工具清单和基线若冲突均作废。

## 当前游戏基线（2026-10-01）

- **前端**：Electron + React + TypeScript + MapLibre；不是 Tkinter。席位 ID `tkinter-ui` 是兼容既有注册的历史 ID，景呈宣实际负责桌面前端框架、地图、主题与共享组件；潘章序负责页面、面板与交互。
- **推演**：具名 Agent 由 `agent_router` 按需唤醒，通过角色契约参与 AI 推演；大臣办差走受限工具调用。提议经契约与业务校验、`engine/state_applier.py` 和程序结算形成状态；叙事不能冒充效果已执行。
- **官员**：每位官员有独立 Actor、权限、意图与记忆。会签/朝议逐人表达，再按制度流程汇合；一个“综合回答”不能代替多个官员 Agent。
- **旨意**：以 `game-docs/specs/decree-action-chain/` 和实际代码为准，追踪旨意、action、动态蓝图、地点工程、建筑/效果、结算流水和因果读数。未注册效果或无 handler 必须是“待支持/未执行”。
- **待补**：口谕/密令/朝议流程与财政 Agent 接线；民间市场 240 月人口稳定性、路级价格域、供给缺口及外销语义；实物建材、新材解锁和民间营造触发。详见 `game-docs/specs/market-civilian-economy/tasks.md`。
- **维护原则**：角色卡中的路径、测试数字、完成状态都是可能过期的快照；每次调度先读项目约定、游戏 README、相关代码和规格。规划席位/骨架不得写成已实现能力。

## 团队构成

**主理人（技术统筹）**

| 成员 ID | 花名 | 职责 |
|---------|------|------|
| songzuo-game-studio-team-lead | 邹运筹 | 任务路由、最少专家集合、冲突裁决、交付验收（不代写任何成员产出） |

**专家团员**

内容与叙事

| 成员 ID | 花名 | 职责 |
|---------|------|------|
| song-narrative-designer | 史翰青 | 北宋史与叙事：大臣/派系/机构/州县，史实三标签（史实/推演/抽象）、人物口吻 |
| event-narrative-designer | 闻机变 | 事件诏书叙事：事件卡/战略分支/改写叙事/timeline break 硬锚 |
| ai-prompt-designer | 祝辞修 | AI 提示词：18 模板/分幕契约/诏书文风/脱敏规则设计 |
| ai-pipeline | 言枢密 | AI 叙事管线：JSON 契约校验/脱敏实现/安全过滤/统一后端（Local+Http） |
| ai-integration | 沈舶司 | AI 接口落地：连通性/能力探测、降级链、契约自检、推演不动点回归 |

系统与数值

| 成员 ID | 花名 | 职责 |
|---------|------|------|
| strategy-systems | 蔡权衡 | 策略数值：派系/军政/科技/事件概率/结局权重，MDA 链路、平衡难度 |
| economy-systems | 钱盈仓 | 财政经济：国库/仓廪/田赋/物价/州县与民间市场、商品/货币口径 |
| core-engineering | 谷承构 | 核心架构与存档：GameState/命令/序列化迁移/循环依赖/权威常量 |
| settlement-engineering | 程月衡 | 结算与结局：现行结算/事件触发/结局评价/timeline break 改写位（改动前实查顺序） |
| data-analytics | 析微澜 | 数据与分析：遥测/平衡挖掘/策略回放/敏感度分析/可玩性诊断 |

表现与交互

| 成员 ID | 花名 | 职责 |
|---------|------|------|
| tkinter-ui（历史注册 ID） | 景呈宣 | Electron/React 框架、MapLibre 舆图、宋式主题、共享组件与前端性能 |
| ui-panels | 潘章序 | React 页面/面板、信息层级、键盘可达、空/加载/错误状态与交互反馈 |
| art-assets | 惠宋韵 | 宋式美术：地图/立绘/图标/规范/资源命名与授权 |
| sound-music-designer | 吕清商 | 宋式音频：雅乐/环境音/UI 音/事件配乐/播放总线 |

质量与交付

| 成员 ID | 花名 | 职责 |
|---------|------|------|
| regression-qa | 严归正 | 质量保障：核心/数值/AI 契约/存档回归，验收矩阵与发布质量门 |
| gui-release-qa | 顾验真 | 界面发布回归：GUI/资源/音频/打包回归、冻结 EXE 验证 |
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
- `W2` 史实事件 + AI 叙事：event-narrative-designer（事件卡+三标签）→ song-narrative-designer（人物核对）→ ai-prompt-designer（prompt 契约）→ ai-pipeline（管线落地）→ 主理人汇编。
- `W3` 发布验收：release-engineering（构建+启动验证）→ gui-release-qa（GUI/打包回归）→ regression-qa（质量门）→ 主理人确认边界（不含 dev/_scratch/本机密钥）。
- `W4` 结算/经济调参：economy-systems（变量表）→ settlement-engineering（结算落地）→ data-analytics（回放验证）→ regression-qa（落断言）。
- `W5` 旨意到因果落地：定义动作意图 → core 定义 action/蓝图/存档契约 → 对应领域 handler 与结算落地 → UI 展示分项状态与因果 → 核心及 GUI QA 验收。
- `W6` 官员 Agent 与治理流程：人物制度核查 → 逐人意图/权限/记忆契约 → 朝议/会签程序汇合 → 玩家裁决或旨意执行 → 逐人回馈与权限/失败回归。
- `W7` 民间市场与长期平衡：商品与所有权口径 → 真实生产/交易/消费 → 路×商品供需读数 → 60/240 月回放 → 人口、生计、价格与钱货因果验收。

**单 agent 路由表**

| 问法类型 | 直接调谁 |
|---------|----------|
| 跨模块需求/不明确/专家冲突/里程碑/架构取舍 | 主理人（本项目） |
| 大臣/派系/机构/史实核查/人物口吻 | song-narrative-designer |
| 事件卡/诏书叙事/战略分支/改写叙事 | event-narrative-designer |
| 派系/军政/科技/结局权重/平衡/极端场景 | strategy-systems |
| 财政/国库/仓廪/物价/州县经济/档位封顶 | economy-systems |
| 状态机/命令/存档/迁移/循环依赖 | core-engineering |
| 结算/事件触发/结局评价/改写位 | settlement-engineering（以当前实现时序为准） |
| prompt 文本/分幕契约/文风/脱敏规则 | ai-prompt-designer |
| JSON 契约校验/安全过滤/后端/错误路径 | ai-pipeline |
| 连通性/能力探测/不动点回归 | ai-integration |
| Electron/React/MapLibre 框架/舆图/主题 | tkinter-ui（历史注册 ID） |
| React 页面/面板/交互/键盘/信息层级/状态反馈 | ui-panels |
| 立绘/地图/图标/美术规范/资源 | art-assets |
| 核心/数值/AI 契约/存档回归/质量门 | regression-qa |
| GUI/资源/音频/打包回归/冻结 EXE | gui-release-qa |
| 打包/EXE/依赖/发布边界 | release-engineering |
| 雅乐/音效/配乐/音频资源 | sound-music-designer |
| 遥测/数据挖掘/平衡分析/回放 | data-analytics |
| 圣旨、口谕、密令到官员承办/蓝图/工程效果 | W5（按需组合叙事/策略/core/结算/经济/UI/QA） |
| 官员 Agent 独立意见、记忆、朝议/会签 | W6（按需组合史实/策略/core/AI/结算/QA） |
| POP 消费、官民仓、市价、营造市场、长局失衡 | W7（按需组合策略/core/经济/结算/数据/QA） |
| 综合性问题 | 走预设 Workflow（主理人编排） |

## 关键技术基准（全团共享事实）

- 当前状态、结算次序、AI 契约、价格/货币口径均不在本包复制定义；权威在 `game/` 实际代码和 `_dev_tools/game-docs/docs/`。
- 常量和 schema 以当前代码唯一来源为准；本 README 与旧角色卡里的行号、档位、测试数、结算步骤和旧质量债不可直接作为现状引用。
- 分层边界与地图资产以 `game/README.md` 和 `sz/AGENTS.md` 为准。地图改动同时考虑省级几何覆盖/边界数据和 MapLibre 渲染，不能只凭截图断言数据正确。

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

本专家包是《宋祚》游戏工程（当前工作区 `D:\codebuddy\sz\game`）的多智能体开发团队。过往软件注册记录可能已迁移或失效；本专家包的全部团队定义（总提示词 + 18 张角色卡 + 来源索引 + 调用示例）统一维护于本包（`TEAM.md` 为权威主体）：

- 专家文件中的「项目基准」必须对照当前 `D:\codebuddy\sz\game` 实查；历史 `G:\sz` 路径不再有效。
- 本包（`TEAM.md` + `agents/`）是**唯一权威配置来源**。
- 游戏 `README.md` 规定：跨模块需求一律先经本专家团主理人路由，禁止直接改核心模块。

## 工作流对接游戏工程

| 工程动作 | 触发 Workflow | 主责专家 |
|---------|--------------|---------|
| 新增史实事件+AI 叙事 | W2 | song-narrative-designer → ai-pipeline |
| 调数值/平衡并验证极端 | 单 agent | strategy-systems → data-analytics → regression-qa |
| 跨模块新功能 | W1 | 主理人路由 → 主责 → 复核 → 验证 |
| 打包发布 | W3 | release-engineering → regression-qa → 主理人 |
| 改 Electron/React 界面、美术或音频 | 按模块派单；跨资源/发布加 GUI QA | tkinter-ui（历史 ID）/ ui-panels / art-assets / sound-music-designer |

## 安装（对接本机游戏工程）

专家包位于 `D:\codebuddy\sz\_dev_tools\songzuo-game-studio`，对应本体为 `D:\codebuddy\sz\game`。Team 模式由主理人按任务路由选用必要成员，不要求每项任务启动全员。

如要作为独立专家包分发，保留目录结构：

```
songzuo-game-studio/
├── README.md
├── agents/            # 17 个专家 + 主理人定义
└── avatars/           # 头像
```

## 打包分享

```bash
zip -r songzuo-game-studio.zip songzuo-game-studio/
```

---
最后更新：2026-10-02（按现行 Agent 推演、旨意因果链、市场长局待办与 Electron/React 前端重设团队基线和路由）
