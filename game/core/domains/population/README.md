# domains/population — 人口与户籍

> **2026-10-07 阶段 3 第二包（DSH）**：由 `core/settlement_imperial.py` 按域拆入 `settlement_hidden.py`（隐户归籍 + 民怨骚乱）。
> 2026-10-06 · 阶段 0（架构基线）· 本包为空骨架：未移动实现、未改 import

## 已迁入实现（阶段 3 第二包，2026-10-07）

| `settlement_hidden.py` | 由 `core/settlement_imperial.py` 按域拆出（2026-10-07 用户裁定「拆开」，阶段 3 第二包）| `_hidden_people` / `ensure_hidden_in_pops` / `_settle_hidden_pop` |
| | | 隐户口数 = **农 POP 的加法子池 `hidden`（口）**，不是第 7 类人口池（POP 挂载律条 1/4）；POP 写入仍走 `pop_bridge.pop_obj_add`。旧路径 `core/settlement_imperial.py` 仍 re-export 其中两个符号 |

## 拥有的规则

POP、户籍、人口结构与人口读数

## 现有代码候选（**候选归属，迁移前须以符号调用图核实**）

```
pop_structure.py
population_readout.py
pop_identity.py
```

## 边界

- 向下依赖 foundation（账本/状态）与 game/content（数据）；**不得反向导入 workflows 或上层**。
- 机制间协作**经显式接口**，不得跨域读写私有内部结构。
- 读数是只读投影，**不得成为结算算法权威**。

## 迁移状态

**未开始**（阶段 0 仅建骨架与 README）。
