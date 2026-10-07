# domains/economy — 财政与市场

> 2026-10-06 · 丙批二起**已有首个实现**（`material_trade_ops.py`）。
> 2026-10-07 第十五包迁入 `dynamic_price.py`、`demand.py`；第十八包再迁入 `market.py`、
> `hoard_settle.py`、`regime_fiscal.py` ⇒ **本包现共 6 个实现文件**；
> 其余（`settlement_finance` / `settlement_granary` / `settlement_econ` / `market*` 等）
> 仍为候选归属、**未移动**——它们的被调方在 16 模块环内，属阶段 3 裁定项，不是本包能机械搬的。

## 拥有的规则

财政、税务、粮政、市场、价格、需求与商品流转

## 已迁入实现

| 模块 | 来源 | 符号 | 说明 |
|---|---|---|---|
| `material_trade_ops.py` | `core/material_holding.py` 交易侧（丙批二 2026-10-06）| `commodity_dims` `supply_merchant_materials` `trade_material` | 搬运/成交规则，非账本接口；向下依赖 `foundation/ledger/material_holding`；`trade_material` 复用 `core.market.trade_goods`（函数内延迟导入）；`supply_merchant_materials` **生产零调用但测试依赖、不得删**（甲批 §五 实测）|
| `dynamic_price.py` | `core/dynamic_price.py`（第十五包 2026-10-07，`git mv`）| `update_goods_prices` `logistics_rate` `civil_logistics` `gov_logistics` `LOGISTICS_TIERS`（+私有 `_clamp`）| **叶子**：顶层 import 只有 `__future__`/typing，连 `content` 都不引。⚠️ 代码事实：地形/战乱系数**只在显式传 `cfg` 时**生效，默认只按距离档位 ⇒ 调用方不传 cfg 就**不会**因战乱抬运费（既有口径，本批未改） |
| `demand.py` | `core/demand.py`（第十五包 2026-10-07，`git mv`）| `demand_release` `basic_need` `durable_gap` `price_sensitivity` `resolve_purchase_plan` `substitute_for`（+私有 `_num` `_cfg`）| **叶子**：顶层 typing，函数内 `from content import data`。🔴 缺失口径：人均 wealth 不可读 ⇒ `None`（**不臆造 0**）；缺基准价的商品**跳过不编造** |

| `market.py` | `core/market.py`（第十八包 2026-10-07，`git mv`）| `trade_goods` `sellable_stock` `reset_trade_ledger` `TRADE_PURPOSES` `TRADE_SCHEMA_VERSION` `TradeOutcome`（+私有 `_num`/`_int`/`_TRADE_LEDGER`/`_ledger_key`）| **唯一商品成交入口**；🔴 模块级可变台账 `_TRADE_LEDGER` 在桩后必须仍是**同一个 dict**（用例锁死：经桩 reset 要能清实现侧，且禁止在桩上重绑） |
| `hoard_settle.py` | `core/hoard_settle.py`（第十八包）| `settle_hoard` `hoard_readout`（+私有 `_drain_into_clerks` 与 6 个常量） | 叶子：stdlib `random`/typing + 函数内 `content.data` |
| `regime_fiscal.py` | `core/regime_fiscal.py`（第十八包）| `apply_fiscal_response`（+私有 `_cut` 与 7 个阈值常量） | 叶子：typing + `core.foundation.ledger.pop_structure` 公开名（人口写入走桥接，符合 POP 挂载律）|
✅ **已销账（第十包，2026-10-07）**：`material_trade_ops` 改用 ledger 显式接口
`attribute_to_seats` / `route_of`（旧私有名在 ledger 内仅作兼容别名保留，供 `core/material_holding.py`
薄桩守恒其公开面）。跨包借用私有符号已由 `test_ledger_interface_b10.py` 常驻拦截，
同包内已知欠账 `grain_bridge → pop_bridge._split_int` 单列登记、只减不增。

## 现有代码候选（**候选归属，迁移前须以符号调用图核实**）

```
market*.py
demand.py
material_market.py
settlement_finance.py
settlement_granary.py
dynamic_price.py
```

## 边界

- 向下依赖 foundation（账本/状态）与 game/content（数据）；**不得反向导入 workflows 或上层**。
- 机制间协作**经显式接口**，不得跨域读写私有内部结构。
- 读数是只读投影，**不得成为结算算法权威**。

## 迁移状态

**已开始**：丙批二（2026-10-06）迁入 `material_trade_ops.py`（交易 3 项）；
第十五包迁入 `dynamic_price.py` + `demand.py`；第十八包迁入 `market.py` + `hoard_settle.py` +
`regime_fiscal.py` ⇒ **本包现有 6 个实现文件**。
其余候选（`settlement_finance`/`settlement_granary`/`settlement_econ` 等结算域文件）**未开始**，
受阶段 3 前置（反向边**接口倒置**）约束。
