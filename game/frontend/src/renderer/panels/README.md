# panels · 面板与覆盖层

> **层归属**：`game/frontend/src/renderer/panels/`。游戏主界面的所有面板/覆盖层。
> **硬约束**：面板**只呈现**，不重算业务逻辑——数值一律取后端 `readouts`（口径单点）。
> 装饰组件优先复用 `../components/PanelKit.tsx`。

## 挂载方式

- [`OverlayStack.tsx`](OverlayStack.tsx) —— 覆盖层栈，**import 并挂载 37 个面板**（按 `panelId` 分发）。
- [`PlanReadoutPanel.tsx`](PlanReadoutPanel.tsx) —— **不由 OverlayStack 挂载**，由 `DecreePanel` 内部渲染
  （它读同一份 `/api/readouts` 的 `plan` 字段，是拟旨因果回看的一部分）。
- [`MemoryDrawer.tsx`](MemoryDrawer.tsx) —— 记忆抽屉，独立挂载。

## 面板索引（按域）

### 核心循环
| 面板 | 作用 |
|---|---|
| `ReadoutHubPanel` | **入口（M85）**：右侧条「天下诸务」组 →「**读数索引**」（`hud/RightStrip.tsx`；`sectionFor` 亦归该组）。**统一读数索引（P5 第一片 · M84）**：直读后端 `/api/readouts::hub`（= `core/domains/economy/readout_hub.collect`，**21 项**只读读数摘要——M84 建时 12 项，经 **M148 → M152 → M227** 扩容至 21 项），列 label/display/unit/source，点行展开 `drill_down`。🔴 **只呈现不重算**；**不可读项显式显示「未定义」**（后端契约 `display==="undefined"`），**绝不回落 0**；真 0 照实显示 0 |
| `LongtermCasePanel.tsx` | 长期旨**案卷页**（2026-10-20）：承办人+六维 / 承办人授权(专款·余额·逐月自理·专断之权) / 案卷底册 / 阶段+进度 / 持续影响 / 推进日志 / 达成与失败代价；数据来自 /api/readouts → `longterm_cases`，缺失显示未定义 |
| `StartPanel` | 开局（选政权/难度） |
| `AdvancePanel` | 推进回合 |
| `SituationPanel` | 局势（situations） |
| `ConcludePanel` | 结局评估 |
| `IntroPanel` | 序章 |

### 诏令与治理
| 面板 | 作用 |
|---|---|
| `DecreePanel` | 拟旨/颁诏 ＋ **挂载 `PlanReadoutPanel`**（工程因果回看） |
| `SecretDecreePanel` | 密旨 |
| `TodoPanel` | 待办政事 |
| `PendingActionsPanel` | 待决动作 |
| `GovernanceHub` | 治理总枢纽 |
| `CentralOrgPanel` | 中枢机构 |
| `AudienceView` | 觐见 |
| `GazettePanel` | 邸报 |

### 人事与官制
`MinistersPanel`（大臣）· `CourtPanel`（朝堂）· `MemoryPanel`（记忆）· `PersonalPanel`（个人）

### 民生与经济
| 面板 | 作用 |
|---|---|
| `AccountingPanel` | 财政收支 |
| `GranaryPanel` | 仓廪 |
| `LandPanel` | 田土 |
| `PopPanel` | 人口 |
| `PrefecturePanel` | 路（州府） |
| `LocalArchivePanel` | 地方志 |
| `ProvinceMilitaryPanel` | 州郡军 |
| `ProvinceArchivePanel` | **州路档案（左侧多页面抽屉）**：选中舆图上的**路**后由 `App` 常驻挂载；页签＝概览/人口/民情/施政/军政/营建/财赋，同一选中对象下切页；州府下钻走既有 `LocalArchivePanel`（不另造府级口径） |

### 军政与外交
`MilitaryPanel`（军）· `DiplomacyPanel`（外交）

### 科技与营造
| 面板 | 作用 |
|---|---|
| `EngineeringPanel` | **科技树**（营造速度/成本等是科技效果，**不是**单工程的投入面板） |
| `TechPanel` | 科技 |

> ⚠️ **注意**：`EngineeringPanel` 是科技树面板。**单工程的投入/赶工旋钮目前不存在**
> （见 `../../../../_dev_tools/game-docs/docs/民间需求与营造材料市场设计.md`）。

### 其他
`EventPanel`（事件）· `DetailPanel`（详情）· `FocusPanel`（聚焦）· `DailyLogPanel`（日志）·
`CodexPanel`（图鉴）· `SavePanel`（存档）· `SettingsPanel`（设置）· `MeterPanel`（调用计量）·
`PlaceholderPanel`（未完成入口占位）

## 测试

[`__tests__/`](__tests__) —— vitest 组件测试：

| 文件 | 覆盖 |
|---|---|
| `PlanReadoutPanel.test.tsx` | **显示纪律**：四层分列、待支持不进告成块、缺读数不以空白冒充"无工程"、按路过滤时层级与台账一并过滤 |
| `LocalArchivePanel.test.tsx` | 地方志面板 |
| `regionLinkage.test.tsx` | 区域联动 |
| `ProvinceArchivePanel.test.tsx` | 州路档案多页面抽屉：默认概览、切页不改选中路、州府下钻走 `localarchive`、军队标签开单军档案、缺失显示「未定义」 |

## 纪律

1. **不复制算法**：任何计算（守恒、口径、状态机）都在 `core/`，面板只画；
2. **缺失 ≠ 0**：读数缺失要显示"未定义"，**不得**用空白冒充"无数据"；
3. **文案单点**：多阶段标签等由后端下发（如 `phase_labels`），前端不自造；
4. **改面板必配测试**：显示纪律类改动要补 `__tests__` 断言。
5. 本机 vitest 用 `pool: "threads"`（`vitest.config.mts` 已钉），`forks` 池会随机崩 worker。
