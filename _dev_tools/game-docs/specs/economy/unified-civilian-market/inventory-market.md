# 开工门台账 · 市场 / 库存 / 价格 / 交易域

> 依据：设计文档 §14.1 开工门要求。**只读盘点，未改任何代码。**
> 五态：定义存在 / 已接线 / 账本闭合 / 长局校准 / 玩家可观察。
> ⚠️ **本台账为 Lead 亲自核实**（两个盘点子代理均超限失败，未产出）。
> 每条均给 `文件:行`；**未亲自复核的一律标"待核"**，不臆断。

## 一、库存载体（谁持有货物）

| 载体 | 权威数据 | 粒度 | 写入点 | 读取点 | 未闭合流向 |
|---|---|---|---|---|---|
| `state.resources[dim]` | `{stock, cap}`；单位见 `RAW_UNITS` | **全国仓**（非路级） | `production_chain.py:78`（生产链入仓）<br>`material_tech.py`（解锁补空槽 `{0,0}`）<br>`save_load.py:925-936`（读档） | **71 处、横跨 8+ 模块**：`game_state_econ:110`、`settlement_econ:(4处)`、`settlement_tech:364,413`、`building_jobs:329`、`settlement_finance:291`、`settlement_econ_helpers:52`、`civil_building`、`market_readout:83-97`、`material_market` | 🔴 **无付款腿**：入仓与扣减都不涉及钱，等于"货物从地里长出、被白用"。这是 **B4-1** 要治的病 |
| `prefectures[路].pops[阶层].goods` | `{dim: qty}` | **路级 POP** | `game_state.py:124-125` 初始化 **仅** `RESOURCE_DIMS − RAW_DIMS`（= 绸/布）<br>`settlement_econ.py:1608-1634`（成品分派）<br>`material_market`（成交时） | `market.py`、`material_market`、`market_readout` | 🔴 **不含建材**：`_build_pops` 不给原料建 `goods` 槽 ⇒ `material_market` 的 `carrier="pop"` 实测恒 `stock=0` |
| 工匠 `goods` | 同上 | 路级 | `settlement_econ.py:1608-1634` | `market.py`、`export_policy` | 🟠 **产出按人口占比分派**（见 §三 缺口 1） |
| `state.workshops` | 全局 dict，键名含路名 | **全局**（键名有地点、账务无地点） | `game_state.py:539-568`（开局酒坊/畜栏/麻坊/丝坊）<br>`save_load.py:938` | `settlement_econ.py:1535` | 🔴 见 §三 缺口 1 |
| 在途货物 | **不存在** | — | — | — | 🔴 **P0/P4 的核心新实体**：现无在途状态，无运力/时滞/运价/损耗 |
| 项目预留 | `proj["_mat_left_<dim>"]` | 项目级 | `settlement_tech.py:403-420` | 同 | 只是**数量台账**，不是实物持有者 |

## 二、价格与成交

| 机制 | 权威数据 | 五态 | 说明 |
|---|---|---|---|
| 成交唯一入口 | `market.py::trade_goods` | 已接线 · 账本闭合 · 玩家可观察 | 双向原子、三重上限 `min(想要,可售,买得起)`、`(turn,trade_id)` 幂等 |
| 可售量 | `market.py::sellable_stock` | 已接线 | 派生视图，不另持货 ✅ 符合 P0「市场库存须为派生视图」 |
| 路级价格键 | `market_price.py::pref_good_key(pref, dim)` = `"<路>|<商品>"` | 已接线 | B2-R2 已落地；参数名用 `pref`（**不用 `route`**，仓库 `route` 是外邦行军路线） |
| 价格压力 | `market_price.py::price_pressure(demand, supply)` | 已接线 | 分母是**期望需求**（曾误用月末可售量致系统性压价，已修） |
| 价格四态 | `market_price.py::effective_buy_price` | 已接线 | 官定 > 路级动态 > 基准；缺失返 `None` **不回落 0** ✅ |
| 价格发现 | `market_price.py::discover_price` | 已接线 | **纯函数、不接 state** ⇒ 无法判"未解锁新材"（B4-2 遗留，已绕开） |
| 建材市场 | `material_market.py` | **已实现 · 已接线**（2026-10-02） | 四路径；`carrier="warehouse"` 官仓 / `"pop"` 路级 POP；`self_dealing` 拒绝。<br>✅ 阻塞已解除：POP 现已持建材（商人 `goods`），落地模块另见 `material_holding.py` / `transport.py` / `material_trade.py` |
| 外销 | `export_policy.py` | 已接线 | 三态 `income`：`None`(未记录) / `0`(确无余货) / `>0`(真外销)；**钱按 `external` 体外注入** |
| 外销税基 | `calc_maritime_trade()` | 已接线 | 🔴 **以公式估贸易额计税，未与逐笔成交绑定** ⇒ 与 `export_policy` 收入、`silver_in` 存在**重复税基**风险（设计文档 §4.12 点名） |

## 三、未闭合流向（按严重度）

| # | 流向 | 证据 | 影响 |
|---|---|---|---|
| 1 | **作坊产出地点信息丢失**：产出全局记账后**按各路工匠 `size` 占比分派** | `settlement_econ.py:1608-1634`（注释自陈"作坊产出是**全局**记账（`state.workshops` 不分路），故按各路工匠 size 占比分派"） | 🔴 **直接违反设计文档 §14.1**「不允许用人口比例分派掩盖地点缺失」；P2 必须解决 |
| 2 | **建材无付款腿**：入仓/扣减都不涉钱 | `production_chain.py:78`、`settlement_tech.py:413` | 🔴 工程领料**白用**；B4-1 根因 |
| 3 | **POP 无建材 `goods` 槽** | `game_state.py:124-125`（只建 `RESOURCE_DIMS − RAW_DIMS`） | 🔴 使"建材卖给工程"这条路**物理上不存在** |
| 4 | **无在途状态** | 全库无 `in_transit` / 在途批次结构 | 🔴 P0 验收门"断路时目的地不能消费未到货库存"**无从满足** |
| 5 | **运输服务通道零调用方** | R5 子代理报告：`dynamic_price.civil_logistics` / `gov_logistics` 无调用方 | 🟠 运力/运价没有结算出口 |
| 6 | **外销税基可能重复** | `calc_maritime_trade` 公式估额 vs `export_policy` 逐笔 | 🟠 财政读数不可信 |
| 7 | **宋境无工钱通道** | R5 报告：`pay_wages_from_revenue` 唯一调用方是**外邦**路径 | 🟠 农户 `open_channels` 只有 `grain_sale` 一条 |

## 四、对 P0「市场契约」的直接建议

**可直接复用**（勿重造）：
- ✅ `trade_goods` 作为**唯一物理成交接口**——P0 的"清算一次"应建立在它之上，不要另写撮合器
- ✅ `sellable_stock` 已是**派生可售视图**语义——正是 P0 要的"视图不持货"
- ✅ `pref_good_key` 的路级键——P0 的 `location_id` 现阶段可直接取**路键**（路级兼容，§14.3 允许）
- ✅ `effective_buy_price` 的四态——P0 的"价格四态"已存在

**必须新建**：
1. **交通边**（承载力/成本/时滞/季节风险/通行条件）—— 全库无
2. **在途批次**实体（含到达月、运力占用、损耗、截断原因）—— 全库无
3. **市场圈**派生（由地域 ID + 制度 + 连通性派生，**不复制库存**）—— 全库无
4. **缺失原因/来源 ID** 的结构化承载（现在散在各返回值的 `reason` 字符串里，无统一契约）

**坑（有证据）**：
- ⚠️ `state.resources` 是**全国口径**，**不得**当"本地市场供给"（`material_market` 已如实标 `scope="national_warehouse"`）
- ⚠️ `statistics` **全库无月度清零**；当月流量键必须自己在结算起点归零（`price_demand` 曾因此被系统性放大，已修）
- ⚠️ 在途货物**既不在来源可售、也不在目的可售**——若直接写进 `state.resources` 就是全国仓，会同时被两地消费
- ⚠️ **未定义价格不可回落到 0/1**（现有 `effective_buy_price` 已守此纪律，新代码须沿用）
