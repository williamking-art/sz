# domains/politics — 政治与世界状态

> 2026-10-06 · 阶段 0 建骨架。  
> **2026-10-07 第十七包：本包已有实现**（`split.py`、`voice.py`，`git mv` 自 `core/`）。`faction_settle` / `faction_basis` / `faction_metrics` / `situation_*` / `events` **仍在 `core/`**，理由见下。

## 拥有的规则

派系、局势、事件及跨机制政治状态（**独立域，经接口协作**）

# 已迁入实现（第十七包，2026-10-07）

| 文件 | 来源旧路径 | 公开面（桩面实测） | 叶子资格 |
|---|---|---|---|
| `split.py` | `core/faction_split.py` | 20 名（含 `_` 私有与 typing/logging 绑定名）| 顶层 import 只有 logging/typing/content 与 `core.foundation.common.numeric` **公开名** |
| `voice.py` | `core/faction_voice.py` | 19 名 | 同上，另函数内引 `content.ministers.data` |

# 未随批搬的候选（各有明确理由，不是遗漏）

- `faction_basis.py`、`faction_metrics.py`：**二者自身构成 faction 环**（SCC 第二个环），搬它们=把环搬个位置；须先按 §5 反向边接口倒置。
- `faction_settle.py`：**不是叶子**——顶层 import `core.faction_basis` / `core.faction_metrics`（环内模块）。本批已把它的 `faction_split` 调用改指新路径，其余留待阶段 3。
- `situation_*.py`、`events.py`：未在本批判责范围内，§3.1 要求它们"提供稳定读写接口"，属接口设计工作。

## 边界

- 向下依赖 foundation（账本/状态）与 game/content（数据）；**不得反向导入 workflows 或上层**。
- 机制间协作**经显式接口**，不得跨域读写私有内部结构。
- 读数是只读投影，**不得成为结算算法权威**。

## 迁移状态

**未开始**（阶段 0 仅建骨架与 README）。
