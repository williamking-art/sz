# `specs/` · 设计规格与实施状态

本目录按**机制域**记录需求、设计、任务拆分和验收证据。规格描述目标与实施过程，**不取代生产代码和 `docs/` 中确认的当前机制口径**。

> 目录边界以 [`代码层机制模块化架构方案_2026-10-06.md`](./cross-cutting/代码层机制模块化架构方案_2026-10-06.md) 为准。

## 状态判定

- 每个专题以自身 `tasks.md` 的任务状态和可复核证据为准；本索引**不复制**易过期的测试数、基线数和逐任务清单。
- **已实现**须有生产调用路径；仅有数据模型、契约、读数模块、测试或设计稿，均**不能单独证明功能已生效**。
- **部分完成**要指出剩余的接线、平衡门或迁移事项。长局守恒通过**不等于**人口与民生平衡通过。
- 规格与当前实现冲突时，先核实代码和存档，再修订状态表；实施完成后回写 `../docs/`。

## 机制域目录

| 目录 | 覆盖机制 |
|---|---|
| [`population/`](./population/) | POP、户籍、人口结构、州府级真账（seats 下沉） |
| [`economy/`](./economy/) | 财政、市场、需求、府库、税收 |
| [`production/`](./production/) | 农业、岗位/就业、建筑产出参数、**主线 C 生产层开工门** |
| [`construction/`](./construction/) | 建筑、营造部门、劳役、产权 |
| [`transport/`](./transport/) | 陆运/水运/海运、可航性、物流 |
| [`diplomacy/`](./diplomacy/) | 外邦、市舶、外贸、外交 |
| [`cross-cutting/`](./cross-cutting/) | 跨机制：架构方案、依赖图与循环、符号归属表、存档版本实况、州府级真账总计划、政令链路、治理语义核对 |

> 各域 `.md` 文件数不写死；需要计数时以仓库根执行 `find _dev_tools/game-docs/specs -name '*.md'` 的结果为准。

## 明细

### `population/` — POP、户籍、人口结构、州府级真账（seats 下沉）

- [`seats下沉_根因诊断.md`](./population/seats下沉_根因诊断.md)
- [`yields与POP结构不相容_决定性发现.md`](./population/yields与POP结构不相容_决定性发现.md)
- [`新局seats下沉_落地受阻记录.md`](./population/新局seats下沉_落地受阻记录.md)

### `economy/` — 财政、市场、需求、府库、税收

- [`market-civilian-economy/`](./economy/market-civilian-economy/)
- [`unified-civilian-market/`](./economy/unified-civilian-market/)
- [`地方府库下沉州府级_阻塞记录.md`](./economy/地方府库下沉州府级_阻塞记录.md)
- [`消费端实测_真在消费吗与能否复购.md`](./economy/消费端实测_真在消费吗与能否复购.md)

### `production/` — 农业、岗位/就业、建筑产出参数

- [`九维建筑基数校准与盐异常.md`](./production/九维建筑基数校准与盐异常.md)
- [`种植产出归属税收_设计稿与影子推演.md`](./production/种植产出归属税收_设计稿与影子推演.md)
- [`主线C_生产层开工门台账.md`](./production/主线C_生产层开工门台账.md) —— 🔴 现行：主线 C **C0 设计核验稿，待评审**（C1–C3 均未授权）

### `construction/` — 建筑、营造部门、劳役、产权

- [`building_jobs_符号级调用图.md`](./construction/building_jobs_符号级调用图.md)
- [`pay_construction_cost_职责比对.md`](./construction/pay_construction_cost_职责比对.md)
- [`官有营造付款渠道_未完成.md`](./construction/官有营造付款渠道_未完成.md)
- [`官有营造建筑清单与规格草案.md`](./construction/官有营造建筑清单与规格草案.md)
- [`建设主体与产权设计.md`](./construction/建设主体与产权设计.md)
- [`建造部门_民间与官有.md`](./construction/建造部门_民间与官有.md)
- [`营造部门实体的治理语义与落点.md`](./construction/营造部门实体的治理语义与落点.md)
- [`营造部门线_落地状态与验证.md`](./construction/营造部门线_落地状态与验证.md)
- [`非经济回报的落点与映射.md`](./construction/非经济回报的落点与映射.md)

### `transport/` — 陆运/水运/海运、可航性、物流

- [`ROUTE_WATERWAY逐路可航性.md`](./transport/ROUTE_WATERWAY逐路可航性.md)
- [`交通下沉州府级.md`](./transport/交通下沉州府级.md)

### `diplomacy/` — 外邦、市舶、外贸、外交

- [`外贸缺失是实现缺陷非史实认定.md`](./diplomacy/外贸缺失是实现缺陷非史实认定.md)
- [`外贸调研_开局关闭且不走货.md`](./diplomacy/外贸调研_开局关闭且不走货.md)
- [`外贸货种与货腿设计稿_2026-10-18.md`](./diplomacy/外贸货种与货腿设计稿_2026-10-18.md) —— 两条通道（海路市舶/陆路榷场）、7 个类目维、逐笔货腿与双守恒
- [`外贸货腿_落地稿_2026-10-18.md`](./diplomacy/外贸货腿_落地稿_2026-10-18.md) —— F1–F5 分步落地：数据层/计算层/读数层、每步验收与回滚、标定顺序、风险登记
- [`宋与外邦贸易设计.md`](./diplomacy/宋与外邦贸易设计.md)
- [`接入前规则收口与接入方案.md`](./diplomacy/接入前规则收口与接入方案.md)
- [`接入条件5_6事实核查.md`](./diplomacy/接入条件5_6事实核查.md)

### `cross-cutting/` — 跨机制：架构方案、州府级真账总计划、政令链路、治理语义核对

- [`README.md`](./cross-cutting/README.md)
- [`decree-action-chain/`](./cross-cutting/decree-action-chain/)
- [`tiandao-engine/`](./cross-cutting/tiandao-engine/) —— 天道裁决引擎（0 Token 本地决断）+ 三条 AI 叙事管道；`tasks.md` 逐项标「已接线 / 仅声明未接线」（**本目录计数未计入上表**，计入留给 `D1-设计文档对齐`）
- [`field-registry/`](./cross-cutting/field-registry/) —— 🔴 现行：`engine/state_applier` 写契约单点注册（B-1，B-1a/B-1b 两阶段）
- [`代码层机制模块化架构方案_2026-10-06.md`](./cross-cutting/代码层机制模块化架构方案_2026-10-06.md)

- `cross-cutting/G3_粮迁移设计稿_2026-10-18.md` — 粮从 legacy 字段迁入 goods[类目成员] 的四片设计（**未实施**）
- [`阶段1_依赖图与循环依赖.md`](./cross-cutting/阶段1_依赖图与循环依赖.md)
- [`甲批_符号归属与新旧路径表.md`](./cross-cutting/甲批_符号归属与新旧路径表.md)
- [`存档schema版本消费实况_2026-10-07.md`](./cross-cutting/存档schema版本消费实况_2026-10-07.md)
- [`中立表结构与势力配置_迁移计划.md`](./cross-cutting/中立表结构与势力配置_迁移计划.md)
- [`州府级真账总批计划.md`](./cross-cutting/州府级真账总批计划.md)
- [`州府级真账计划_深化版.md`](./cross-cutting/州府级真账计划_深化版.md)
- [`语义核对_public_support与gentry_resistance.md`](./cross-cutting/语义核对_public_support与gentry_resistance.md)
- [`B2_守卫与质量放行门_设计与取证_2026-10-12.md`](./cross-cutting/B2_守卫与质量放行门_设计与取证_2026-10-12.md) —— **B-2 只读轮**：守卫↔放行门关系与账本写链盘点（未实施）
- [`AI科技维度与蓝图演进_开工门台账_2026-10-12.md`](./cross-cutting/AI科技维度与蓝图演进_开工门台账_2026-10-12.md) —— 🔴 **T0/C0 设计核验稿，待评审**：AI 自由提案、动态科技扩展、蓝图新建/升级与审批生命周期（零代码；T1–T3 未授权）

> **计数口径（2026-10-17）**：本索引不再写死各域 `.md` 文件数；需要计数时以仓库根
> `find _dev_tools/game-docs/specs -name '*.md'` 的结果为准，目录增删时只维护链接与说明。

## 每个专题的文件

| 文件 | 内容 |
|---|---|
| `requirements.md` | 需求、边界、非目标与验收条件 |
| `design.md` | 数据结构、因果口径、失败语义与模块边界 |
| `tasks.md` | 实施拆分、任务状态、验证证据和遗留事项 |
| `diplomacy/外国州府级数据_设计稿_2026-10-19.md` | **外邦分级数据设计（未实施）**：T1 六国州府级 / T2 省级 / T3 国家级；国=Σ省=Σ州府，人口按权重分解守恒 |

若某专题暂缺其中一份，应在专题目录中说明，**不根据模板虚构状态**。

跨目录冲突和改善优先级见 [`文档整体审校与改善建议.md`](../文档整体审校与改善建议.md)。
跨专题未完成设计的最新状态导航见 [`未完成设计对齐与改良方案_2026-10-05.md`](../reviews/未完成设计对齐与改良方案_2026-10-05.md)。

归档映射与跨域归属理由见 [`specs归档清单_待确认.md`](./specs归档清单_待确认.md)。
