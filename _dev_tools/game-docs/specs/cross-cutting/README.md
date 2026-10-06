# `cross-cutting/` — 跨机制文档

> 收录**跨多个机制域**的方案：架构总纲、州府级真账总计划、政令链路、治理语义核对。
> **只存一份、不在业务域复制**；需要时由各域文档引用本目录。

## 文档

- [`README.md`](./README.md)
  本文件。
- [`decree-action-chain/`](./decree-action-chain/)
- [`代码层机制模块化架构方案_2026-10-06.md`](./代码层机制模块化架构方案_2026-10-06.md)
  架构总纲：`game/core/` 四层责任（foundation / workflows / domains / compatibility）、依赖硬规则、五阶段迁移、验收标准与明确不做。**本目录结构的唯一依据**。
- [`州府级真账总批计划.md`](./州府级真账总批计划.md)
  州府级真账总计划：同时牵动 POP、建筑、交通、钱，无单一主属。
- [`州府级真账计划_深化版.md`](./州府级真账计划_深化版.md)
  上者的深化版。
- [`语义核对_public_support与gentry_resistance.md`](./语义核对_public_support与gentry_resistance.md)
  民心与士绅抵制的真实语义核对（**含对既有错误映射的更正**）。

## 专题目录

`decree-action-chain/` 采用 `requirements.md` / `design.md` / `tasks.md` 三件套：

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
