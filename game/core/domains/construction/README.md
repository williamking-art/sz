# domains/construction — 建设机制

> **2026-10-07 第三十一包（DSH）**：迁入 material_tech.py（建材科技解锁注册表）。
> 2026-10-06 · 阶段 0（架构基线）· 本包为空骨架：未移动实现、未改 import

# 已迁入实现（第三十一包，2026-10-07）

| `material_tech.py` | `core/material_tech.py`（第三十一包 2026-10-07，`git mv`）| 桩 **47** 名 | ✓ 只 import `__future__`/`content.data`/`typing` ⇒ 零 `core` 依赖；3 个生产调用方（`construction.py` / `market_price.py` / `settlement_tech.py`）已同批改指新路径 |
| | | | 📌 **本批顺手修正的文档-代码不符**：原 docstring 写「本模块**尚未接线**到 `settlement.py`」，实测**已被 3 个生产模块调用** ⇒ 已按实测改写，不再声称未接线（`AGENTS.md §6.1` 要求发现不符顺手改） |
| `building_upgrade.py` | **新建**（2026-10-19 V3 建筑升级）| `level_multiplier` `upgrade_requirement` `start_upgrade` `advance_building_construction` `construction_readout` | 建筑分级升级：等级倍率 1+(lv-1)×0.15、建材+地方府库银+工期、每路限 1 项在建；等级写点走 building_bridge（未下沉回落保形态）|

## 拥有的规则

建筑、蓝图、建设成本、**营造流程与工程**

## 现有代码候选（**候选归属，迁移前须以符号调用图核实**）

```
civil_building.py
construction*.py
construction_shadow.py（仅建设流程部分）
```

## 边界

- 向下依赖 foundation（账本/状态）与 game/content（数据）；**不得反向导入 workflows 或上层**。
- 机制间协作**经显式接口**，不得跨域读写私有内部结构。
- 读数是只读投影，**不得成为结算算法权威**。

## 迁移状态

**未开始**（阶段 0 仅建骨架与 README）。
