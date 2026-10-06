# foundation — 基础与账本层

> 迁移状态文档。承架构方案 §9-5：「**代码在新目录**」**不等于**「生产调用已接入」。
> 本文件记录**实测**状态，不写计划。

---

## 子包

- `state/` GameState、初始状态构建与状态字段注册 —— ⬜ **空**
- `ledger/` POP/钱粮/物料权威账户与读写 API（含迁移期桥接）—— ✅ **已迁入 5 个**
- `persistence/` 存档读写与版本迁移 —— ⬜ **空**
- `common/` numeric、errors 等无领域语义的共享工具 —— ✅ **已迁入 1 个**

## 一、已完成（实现已迁入）

| 模块 | 新位置 | 大小 | 公开符号 |
|---|---|---:|---:|
| `money` | `foundation/ledger/money.py` | 35.2 KB | 50 |
| `pop_bridge` | `foundation/ledger/pop_bridge.py` | 25.7 KB | 32 |
| `grain_bridge` | `foundation/ledger/grain_bridge.py` | 5.6 KB | 6 |
| `numeric` | `foundation/common/numeric.py` | 2.7 KB | 8 |
| `pop_structure` | `foundation/ledger/pop_structure.py` | 12.6 KB | 19 |
| `prefecture_entity` | `foundation/ledger/prefecture_entity.py` | 11.2 KB | 24（dir() 口径）|

旧路径 `core/money.py` `core/pop_bridge.py` `core/grain_bridge.py` `core/pop_structure.py`
`core/numeric.py` `core/prefecture_entity.py` 均为**薄转发桩**（11–26 行），**不复制实现**。

✅ `pop_bridge` 对 `prefecture_entity` 的跨包反向依赖已在第五包**同批闭合**
（改指新路径；阶段 1 标注的 ledger 缺口之一清零，余 `grain_ledger`）。
⚠️ `pop_bridge.seat_pop_weights` 的 lazy import 包在 `try/except` 里**静默返回 []**，
路径断链不会炸 import —— 断言**权重非空**才算接通（回归已守）。

## 二、🔴 尚未接入：生产调用点仍走旧路径

**计数口径（可复现）**：`game/` + `_dev_tools/game-dev/tests/` 中 import 该模块的
**文件数**（不含薄转发桩与实现自身）。

| 模块 | 旧路径引用文件 | 新路径引用文件 |
|---|---:|---:|
| `money` | **38** | 0 |
| `pop_bridge` | **21** | 3 |
| `grain_bridge` | **12** | 1 |
| `pop_structure` | **15** | 0 |
| `numeric` | **15** | 0 |
| `prefecture_entity` | **8** | 1 |

⇒ 新路径引用目前**全部来自 `foundation/` 包内部**（甲批规则 1「新迁入模块彼此用新
规范路径」）；外部调用方仍 100% 走旧路径。
⇒ 符合迁移期设计，但**必须显式记录**，避免后人误以为已切换。

## 三、未完成 / 受阻

| 项 | 状态 | 说明 |
|---|---|---|
| `material_holding` | ❌ **拆分失败，已回退** | 产物 `foundation/ledger/material_holding.py`（38.2 KB）与 `domains/economy/read_models/` 为**未提交残留**，**未接入** |
| 其余子包与 `domains/*` 十域 | ⬜ 空骨架 | **均无实现** |
| 依赖图（§8 阶段 1）| ❌ **未做** | 只做过粗粒度 import 扫描，**无符号级依赖图** |

## 四、🔴 与架构方案的偏离（自查）

| 条款 | 要求 | 实际 |
|---|---|---|
| §6-6 | 包 `__init__.py` 只暴露稳定服务/类型，**不通配 re-export 整个旧模块** | 转发桩 re-export **全部符号（含私有）** |
| §8 阶段 2 | **每一小批只迁一个业务包；当轮只处理一个职责域** | 第一批一次迁了 **3 个模块** |
| §8 阶段 1 | 先产出 import 图与循环依赖 | **跳过**，直接进阶段 2 |

### `material_holding` 拆分失败的直接原因

测试 `test_seat_products_tribute.py` **直接访问私有符号** `_TRIBUTE_BY_CIRCUIT`；
转发桩若只导出公开符号即 `AttributeError`。
⇒ 这是 §6-6「**公共接口小而稳**」与「测试依赖内部结构」之间的冲突点，**待裁定**。