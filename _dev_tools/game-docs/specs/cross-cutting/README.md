# `cross-cutting/` — 跨机制文档

> 收录**跨多个机制域**的方案：架构总纲、州府级真账总计划、政令链路、治理语义核对。
> **只存一份、不在业务域复制**；需要时由各域文档引用本目录。

## 文档

- [`README.md`](./README.md)
  本文件。
- [`decree-action-chain/`](./decree-action-chain/)
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
- [`语义核对_public_support与gentry_resistance.md`](./语义核对_public_support与gentry_resistance.md)
  民心与士绅抵制的真实语义核对（**含对既有错误映射的更正**）。
- [`B2_守卫与质量放行门_设计与取证_2026-10-12.md`](./B2_守卫与质量放行门_设计与取证_2026-10-12.md)
  🔴 **B-2（只读轮）**：现有 POP 守卫与质量放行门的真实关系、运行时策略 vs 门策略的分离、
  粮/商品/资源桶写入链盘点与实施范围拆分。**设计与取证完成、未实施、未提交**。

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
