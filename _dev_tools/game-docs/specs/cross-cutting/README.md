# `cross-cutting/` — 跨机制文档

> 收录**跨多个机制域**的方案：架构总纲、州府级真账总计划、政令链路、治理语义核对。
> **只存一份、不在业务域复制**；需要时由各域文档引用本目录。

## 文档

- [`README.md`](./README.md)
  本文件。
- [`decree-action-chain/`](./decree-action-chain/)
- [`商品物料存量州府化_前置取证_2026-10-13.md`](./商品物料存量州府化_前置取证_2026-10-13.md)
  **只读取证**：`state.resources`（全国口径）的 11 处写点台账、只读消费方、**先桥后沉**的前置顺序；
  🔴 并区分 M40b（`storage` ↔ applier）与本项（`resources.stock` **不经** applier）。
- [`作坊工资前置取证_2026-10-13.md`](./作坊工资前置取证_2026-10-13.md)
  作坊工资**口径单点**取证：**岗位数无权威来源** ⇒ 工资义务**不可定义**（不臆造、不按人口均分）；
  可给「作坊类型→建筑类型」的**推断映射**与其 `WAGE_RATE` 候选（**标注推断非史料**）；
  并记录 M66 规则表补漏（配方面 6 型全覆盖 + 覆盖断言）。
- [`产权资金到位率_多时点取证_2026-10-13.md`](./产权资金到位率_多时点取证_2026-10-13.md)
  **多时点**（0/6/12 月）到位率取证：**没有任何载体在所有时点都够**；**民营侧随时间崩掉**
  （G-4 民营满覆盖 12/20 → 1/20 → **0/20**）；**士绅是唯一长期充裕者**；并给出 D 线「钱从哪来」的四选项。
- [`代码层机制模块化架构方案_2026-10-06.md`](./代码层机制模块化架构方案_2026-10-06.md)
  架构总纲：`game/core/` 四层责任（foundation / workflows / domains / compatibility）、依赖硬规则、五阶段迁移、验收标准与明确不做。**本目录结构的唯一依据**。
- [`阶段1_依赖图与循环依赖.md`](./阶段1_依赖图与循环依赖.md)
  承架构方案 §8 阶段 1 的**实测**依赖图：SCC=2（18 模块平铺环 + faction 2 环）与 12 条反向边登记；并更正阶段 0「循环依赖 = 0」的错误结论。
  🔴 **当前口径以该文件 §一之补为准**：第十九包发现 v2 扫描器漏计 `from core import X` 形态、
  且斜杠节点名与点分边名不一致 ⇒ 平铺大环实为 **[17]**、反向边 **12 确定 + 1 待判**。
- [`甲批_符号归属与新旧路径表.md`](./甲批_符号归属与新旧路径表.md)
  迁移批次各符号的**归属**（新位置）与新旧路径对照；与 `foundation/README.md` 的引用计数表配对使用。
- [`存档schema版本消费实况_2026-10-07.md`](./存档schema版本消费实况_2026-10-07.md)
  存档版本号机制的**普查实况**（顶层版本门真实存在；13 个子系统版本戳只被消费 1 处），并据此确定第七包"只迁真叶子"的切法。
- [`中立表结构与势力配置_迁移计划.md`](./中立表结构与势力配置_迁移计划.md)
  中立势力表结构与配置的迁移计划。
- [`州府级真账总批计划.md`](./州府级真账总批计划.md)
  州府级真账总计划：同时牵动 POP、建筑、交通、钱，无单一主属。
- [`州府级真账计划_深化版.md`](./州府级真账计划_深化版.md)
  上者的深化版。
- [`建筑下沉州府级_实施设计_2026-10-13.md`](./建筑下沉州府级_实施设计_2026-10-13.md)
  🔴 **批次 2（建筑下沉）实施设计 + M38a 落地记录**：口径（路级 = **Σ 各治所等级**；下沉初始分配 =
  **首府承载**，Jev 0.429 / 0.894）、真账 `seats[治所]["buildings"]`、写点 3 处与读者约 10 处清单、
  **为何本批刻意不开闸**（Σ 会让阈值类读者放大；M37 教训：开闸须与全桥同批）、M38b/c 计划。
- [`语义核对_public_support与gentry_resistance.md`](./语义核对_public_support与gentry_resistance.md)
  民心与士绅抵制的真实语义核对（**含对既有错误映射的更正**）。
- [`B2_守卫与质量放行门_设计与取证_2026-10-12.md`](./B2_守卫与质量放行门_设计与取证_2026-10-12.md)
  🔴 **B-2（只读轮）**：现有 POP 守卫与质量放行门的真实关系、运行时策略 vs 门策略的分离、
  粮/商品/资源桶写入链盘点与实施范围拆分。**设计与取证完成、未实施、未提交**。
- [`AI科技维度与蓝图演进_开工门台账_2026-10-12.md`](./AI科技维度与蓝图演进_开工门台账_2026-10-12.md)
  🔴 **T0/C0 设计核验稿，待评审**：AI 自由提案、动态科技维度、蓝图新建/升级版本与审批生命周期；本轮纯文档，T1–T3 未授权。

## 专题目录

`decree-action-chain/` 与 `field-registry/` 采用 `requirements.md` / `design.md` / `tasks.md` 三件套：

- [`decree-action-chain/`](./decree-action-chain/) —— 圣旨行动闭环。
- [`field-registry/`](./field-registry/) —— 🔴 **B-1**：`engine/state_applier` 六套路径/规则集合的
  **单点声明与自动派生**（B-1a 影子期 / B-1b 数据源切换），含顺序不可复现的环路证据与 E1–E8 冻结清单。

| 文件 | 内容 |
|---|---|
| `requirements.md` | 需求、边界、非目标与验收条件 |
| `design.md` | 数据结构、因果口径、失败语义与模块边界 |
| `tasks.md` | 实施拆分、任务状态、验证证据和遗留事项 |

## 跨专题台账（不属本目录，链接到其机制域）

| 台账 | 所属机制域 |
|---|---|
| [`b0-inventory-ledger.md`](../economy/market-civilian-economy/b0-inventory-ledger.md) | economy |
| [`demand-layer-calibration.md`](../economy/market-civilian-economy/demand-layer-calibration.md) | economy |
| [`inventory-building.md`](../economy/unified-civilian-market/inventory-building.md) | economy |
| [`inventory-market.md`](../economy/unified-civilian-market/inventory-market.md) | economy |

另两个专题 [`market-civilian-economy/`](../economy/market-civilian-economy/) 与 [`unified-civilian-market/`](../economy/unified-civilian-market/) 在 `economy/`。

返回：[`specs/` 索引](../README.md)
