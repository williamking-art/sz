# `specs/` · 设计规格与实施状态

本目录按专题记录需求、设计、任务拆分和验收证据。规格描述目标与实施过程，不取代生产代码和 `docs/` 中确认的当前机制口径。

## 状态判定

- 每个专题以自身 `tasks.md` 的任务状态和可复核证据为准；本索引不复制易过期的测试数、基线数和逐任务清单。
- **已实现**须有生产调用路径；仅有数据模型、契约、读数模块、测试或设计稿，均不能单独证明功能已生效。
- **部分完成**要指出剩余的接线、平衡门或迁移事项。长局守恒通过不等于人口与民生平衡通过。
- 规格与当前实现冲突时，先核实代码和存档，再修订状态表；实施完成后回写 `../docs/`。

## 当前规格

| 规格 | 范围 | 状态入口 |
|---|---|---|
| [`decree-action-chain/`](decree-action-chain/tasks.md) | 圣旨/事务、行动拆解、蓝图、地点工程、月结算因果、AI/UI 读数与存档迁移 | `tasks.md` 的“0–7 完成”总声明与局部历史快照/遗留项需一并核对；以任务末尾状态、代码路径和对应回归共同判断，不能据总声明推断所有旨意动作都有执行器。 |
| [`market-civilian-economy/`](decree-action-chain/tasks.md) | POP 消费、商品市场、粮食、官民仓储/经营、营造材料与官员 Agent | 按任务表区分已实现、已接线、平衡放行和未关闭建模决策；其中多时间点状态须以最新收口表并结合当前代码复核。**B4-1 建材已于 2026-10-02 裁决 C/C-c/E-1 并接线**（商人 POP 持料＋只从本地取＋跨路在途＋补货下单）。 |
| [`unified-civilian-market/`](decree-action-chain/tasks.md) | 统一设计后续落地路线（P0–P6）：市场空间、州府经济、建筑经营、边境/远方市场、界面与质量门 | 州府实体/人口地基不等于州府级市场已经运行；市场、建材及 P0–P6 进度看任务表最新状态。本专题刻意不设 `requirements.md`/`design.md`，设计仍指向 `docs/`。 |

## 架构提案

| 文档 | 范围 | 状态 |
|---|---|---|
| [`代码层机制模块化架构方案_2026-10-06.md`](代码层机制模块化架构方案_2026-10-06.md) | 以三省流程、六部业务域为参照，规划 `game/core/` 的代码模块边界、基础账本、记忆回写抽离、依赖方向与渐进迁移 | 待评审；不代表已改代码 |

## 每个规格的文件

| 文件 | 内容 |
|---|---|
| `requirements.md` | 需求、边界、非目标与验收条件 |
| `design.md` | 数据结构、因果口径、失败语义与模块边界 |
| `tasks.md` | 实施拆分、任务状态、验证证据和遗留事项 |

### 规格内的附加台账（非模板三件套，2026-10-03 补录）

| 文件 | 所属 | 内容 |
|---|---|---|
| [`market-civilian-economy/b0-inventory-ledger.md`](../economy/market-civilian-economy/b0-inventory-ledger.md) | market-civilian-economy | B0 批次逐持有人/地点/用途的库存台账（开工地基） |
| [`market-civilian-economy/demand-layer-calibration.md`](../economy/market-civilian-economy/demand-layer-calibration.md) | market-civilian-economy | 需求分层与校准口径（B2 购��力/缺货可区分） |
| [`unified-civilian-market/inventory-building.md`](../economy/unified-civilian-market/inventory-building.md) | unified-civilian-market | 建筑域台账（开工门产物之二） |
| [`unified-civilian-market/inventory-market.md`](../economy/unified-civilian-market/inventory-market.md) | unified-civilian-market | 市场域台账（开工门产物之一） |

若某专题暂缺其中一份，应在专题目录中说明，不根据模板虚构状态。

跨目录冲突和改善优先级见 [`../文档整体审校与改善建议.md`](../../文档整体审校与改善建议.md)。
跨专题未完成设计的最新状态导航见 [`../reviews/未完成设计对齐与改良方案_2026-10-05.md`](../../reviews/未完成设计对齐与改良方案_2026-10-05.md)；任务表较早状态快照与当前交接不一致时，应先复核而不是照旧重复实施。
