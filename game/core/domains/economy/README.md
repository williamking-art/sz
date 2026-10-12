# domains/economy — 财政与市场

> 2026-10-07 第二十三包（DSH）新增 `read_models/` 子包并迁入 `flow_summary.py`。
> 2026-10-06 · 丙批二起**已有首个实现**（`material_trade_ops.py`）。
> 2026-10-07 第十五包迁入 `dynamic_price.py`、`demand.py`；第十八包再迁入 `market.py`、
> `hoard_settle.py`、`regime_fiscal.py`；此后又迁入 `regime_tech.py`（第二十八包）、
> `trade_shadow.py`（第三十包）、`settlement_econ_helpers.py`（阶段 3）
> ⇒ **本包现共 9 个实现文件 ＋ `read_models/flow_summary.py`（2026-10-11 实测）**；
> 其余（`settlement_finance` / `settlement_granary` / `settlement_econ` / `market*` 等）
> 仍为候选归属、**未移动**——它们的被调方在平铺大环（v3 口径 **[17]**；旧记录写 16 是 v2 漏计
> `from core import X` 形态所致，见 `阶段1_依赖图与循环依赖.md` §一之补）内，
> 属阶段 3 裁定项，不是本包能机械搬的。

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
| `regime_tech.py` | `core/regime_tech.py`（第二十八包 2026-10-07，`git mv`）| `advance_regime_tech` 等 | 主要国家/外邦政权的**科技推进**（批 B）：与宋**同一套 `TECH_NODES` 规则**；花费走**政权库银**（税收供血），**不扣宋国库、不扣任何 POP 账户**；研究**按月摊销**，库银不足 ⇒ **暂停研究**（`research_paused`），**不透支、不挂账、不回落 0 假装** |
| `trade_shadow.py` | `core/trade_shadow.py`（第三十包 2026-10-07，`git mv`）| 外贸货腿影子函数（4 键对账） | 🔴 **影子模块（只读）——不接入正式结算**：验证「出口扣货＋进口加货＋运费＋钱流」四者对账；纯函数、不写任何 state、**不被 `settlement*` 引用**；用途＝守恒自检与接入前裁定参考。含 `ROUTE_WATERWAY`（**路级史料源表**）；`waterway_tier()` 已改为**治所级派生**（见下）|
| `waterway_seats.py` | **新建**（M39a 2026-10-13）| `SEAT_WATERWAY` `capital_seat_id` `waterway_tier_seat` `waterway_tier_route` `survey_waterway` `rebuild_seat_table` | 🔴 **航道治所级真账**（用户裁定「交通是州府级」）：`SEAT_WATERWAY`＝`{治所 id: 档位}`，由路级史料表**首府承载**生成（**不编造**其余治所档位——无地理依据）；路级 `waterway_tier_route` 是**派生聚合**（该路已登记治所最高档）⇒ 与原表**逐路相等**（零行为变化，`test_waterway_seats.py` 锁定）。缺失≠0：未登记治所 ⇒ `None` |
| `canal_bridge.py` | **新建**（M39c-1 2026-10-13）| `sink_canal_to_seats` `aggregate_route_canal_block` `aggregate_national_canal_block` `canal_set` `canal_add` `canal_set_national` `survey_canal` `seat_canal_block` `is_sunk` | 🔴 **漕运淤塞（`canal_block`）治所级真账**：原为**全国单标量**（0~100）⇒ 下沉后真账在 `seats[治所]["canal_block"]`（**首府承载**，无逐治所来源**不编造**），路级/全国值 = **按水路档位加权平均**（强3/有2/弱1，未知按 1）的派生镜像。⚠️ 未登记治所**缺席**（`None`）而非 0（0＝「通畅」这一声明）。**保持入参数值类型**（int 进 int 出——曾把 `state.canal_block` 静默变成 float，被 A/B 对照抓出）。两个全国级写点（`settlement_granary` 月度演化、`settlement_decree` 疏浚诏令）已走桥；**读者一律未改**（⇒ 零行为变化，A/B 轨迹逐轮一致）。M39c-2 才改粮价/运力判据为逐路读 |
| `settlement_econ_helpers.py` | `settlement_steps.py` 拆出（阶段 3 第二包）| `_distribute_pop_wealth`／`_settle_mint`（+私有） | 结算金钱/粮**分发助手**（零行为变更）：lump 按 POP size 分摊**尾差归最大府**（守恒）；铸钱受控（铜料约束＋熔耗＋对账台账）。POP 写入走桥接（未下沉回落原写法）|
| `read_models/flow_summary.py` | `core/flow_summary.py`（第二十三包 2026-10-07，`git mv`）| `build_flow_summary` `_parse_finance_line` `_extract_one_off`（+3 私有）| 纯派生**读数**（只读 GameState、不写 state）⇒ 归 `read_models/` 子包（架构方案 §3.1）。与 `material_trade_ops.py` 的平铺形式不同，待统一；本批已用**真实通道非空**验证（调 `build_flow_summary(s)` 返回 `{treasury, imperial}`，非空壳）。|
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
