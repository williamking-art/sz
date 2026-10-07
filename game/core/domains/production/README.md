# domains/production — 生产机制

> **2026-10-07 第二十九包（DSH）**：迁入 crop_shadow.py（种植影子模块，刻意不接入结算）。
> **2026-10-07 阶段 3 第六包（DSH）**：迁入 settlement_agri.py（农业供给与收入反馈，**零随机**）。**阶段 3 零随机部分全部搬完**。
> 2026-10-06 · 阶段 0 建骨架。  
> **2026-10-07 第十六包：本包已有实现**（`production_chain.py`、`farm_procurement.py`，
> 均 `git mv` 自 `core/`）。`building_jobs.py` 与 `settlement_agri.py` **仍在 `core/`**，理由见下。

## 拥有的规则

农业、**岗位/就业/岗位池**、配方、供给链与商品产出

# 已迁入实现（第十六包，2026-10-07）

| 文件 | 来源旧路径 | 公开面（桩面实测） | 叶子资格与跨域边 |
|---|---|---|---|
| `production_chain.py` | `core/production_chain.py` | 14 名（含私有 `_building_mult`/`_pick_seat`/`_write_pending`/`_write_warehouse` 与 typing/`annotations` 绑定名） | 函数内 import 只有 `content.data` 与 `core.foundation.ledger.material_holding` 公开名；
| | | | 🔴 **既有跨域边**：`from core.domains.economy.material_trade_ops import commodity_dims` —— 走的是**公开名**，符合 §6 规则2，本批只登记不改。 |
| `farm_procurement.py` | `core/farm_procurement.py` | 15 名（含私有 `_take_goods`/`_workshop_demand`/`_seat_of`） | 函数内 import 只有 `content.data` 与 ledger 公开名。 |
| `crop_shadow.py` | `core/crop_shadow.py`（第二十九包 2026-10-07，`git mv`）| 桩 **31** 名 | ✓ 只 import `__future__`+`typing`。**影子模块**：刻意**不接入正式结算**（docstring 明载），故生产调用方为 0 属正常；等价性用 `run_checks()` 迁移前后**输出逐字节比对**证明（10 项全 true、0 false） |
| settlement_agri.py | core/settlement_agri.py（阶段 3 第六包 2026-10-07，git mv）| 桩 **36** 名 | ✅ **零随机**；农业供给与收入反馈（规格 market-civilian-economy B2-R4）；✅ docstring 已按实测改写（原称「尚未接线」，实测已被 settlement.py / settlement_granary.py 两处调用）|

## 未随批搬的候选（不是遗漏，是判责未完）

- `building_jobs.py`：引 `pop_bridge`/`grain_bridge` 且被结算多步分别调用，**要先定岗位/就业规则归生产域还是行政域**（§7 已标"仅岗位/就业部分"），拆责属口径工作，不混进结构迁移。
- `settlement_agri.py`：被调方在平铺大环（v3 口径 [17]）内，属阶段 3 裁定项。

## 边界

- 向下依赖 foundation（账本/状态）与 game/content（数据）；**不得反向导入 workflows 或上层**。
- 机制间协作**经显式接口**，不得跨域读写私有内部结构。
- 读数是只读投影，**不得成为结算算法权威**。

## 迁移状态

**已开始**（第十六包，2026-10-07）：`production_chain.py`、`farm_procurement.py` 已迁入并完成生产改道；
`building_jobs.py` / `settlement_agri.py` 见上表「未随批搬的候选」。
