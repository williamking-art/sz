# B0-1 · 库存台账映射（现状实测，2026-10-11）

> 归属：[`tasks.md`](tasks.md) **B0-1**。本文是**现状测绘**，不改任何代码行为。
> 读法：先看 §1 载体，再看 §2 逐载体读写点，最后看 §4 结论与 §5 遗留问题。

---

## 1 · 库存载体总览

| # | 载体 | 路径 | 商品维度 | 归属 | 状态 |
|---|---|---|---|---|---|
| ① | 全国/官仓仓储 | `state.resources[dim]["stock"/"cap"]` | `RESOURCE_DIMS` 17 维 | **官仓/仓储**（含 `cap` 容量上限） | 存在；**开局全 0** |
| ② | POP 手持商品 | `pop[阶层]["goods"][dim]` | 见 §2.2 | **POP 持有**（无 cap） | 存在；布/绸有微量流转 |
| ③ | 太仓（粮食专用） | `state.granary` ＋ `granary_stats` | 粮 | **官仓储粮** | 存在，独立于 ①② |
| ④ | 在途 | — | — | 跨路运输中 | **未实现** |

> ⚠️ **不要把 ①②③ 合并成一个字典**（tasks §1.1）：`cap` 容量语义、用途与预留状态都不同。

---

## 2 · 逐载体读写点（穷举，实测行号）

### 2.1 ① `state.resources[dim]["stock"]`

| 位置 | 方向 | 用途 |
|---|---|---|
| `production_chain.py:80,83` | **＋** | 宋侧产出链增量（`stock + add`） |
| `settlement_econ.py:1541` | 读 | 作坊配方**缺料检查**（`stock < need`） |
| `settlement_econ.py:1553` | **－** | 作坊**加工耗用**原料（`stock − need`） |
| `settlement_econ.py:1583,1587` | **＋** | 作坊**成品入库**（按 `cap` 封顶） |
| `settlement_tech.py:352` | 读 | 工程**材料供给**检查（`resources.get(dim).stock`） |
| `settlement_tech.py:392` | **－** | 工程**领料消耗**（`stock − take`，`take = need×供给率`） |
| `settlement_finance.py:302,305` | **＋** | 财政**征发/收购**入库（`stock + taken`） |
| `settlement_econ_helpers.py:53,62` | 读/**－** | 金属需求扣减（池 ＋ 仓扣减，避免 KeyError） |
| `game_state_econ.py:110` | 读 | `project_supply_ratio` 供给满足率**最短板** |
| `save_load.py:870,874` | 读/建 | **存档读档**：`stock/cap` 迁移、缺维 `setdefault` |

### 2.2 ② `pop[阶层]["goods"][dim]`

| 位置 | 方向 | 用途 |
|---|---|---|
| `production_chain.py:100,104` | **＋** | 作坊成品 → **工匠** goods 池（生产库存） |
| `production_chain.py:107,111` | **＋** | 作坊成品 → **商人** goods 池 |
| `settlement_granary.py:270` | 读 | `_goods_empty` 护栏：工匠池空则走直产备份 |
| `settlement_granary.py:285` | **＋** | ⚠️ **POP 消费：扣钱后直接给货，无卖方扣减** |
| `settlement_granary.py:293,294` | **－** | 商品月折旧 5%（`×0.95`） |
| `settlement_granary.py:303,307` | 读/**－** | 存货外销（`GOODS_PRICE` 入工匠 wealth） |
| `save_load.py:760,761` | 建 | 读档：`goods` 缺字段时按 `_goods_dims` 补 0 |

### 2.3 ③ 太仓 `state.granary`

| 位置 | 用途 |
|---|---|
| `settlement_econ.py:1547,1580` | 作坊 `grain_feed` 从太仓扣（独立于 `resources`） |
| `settlement_common.py::_state_grain_trade` | 平粜/平籴/籴购（官仓 ↔ 民间，**钱粮两组守恒配对**） |
| `settlement_granary.py` Step 4.5 | 仓廪调价、赈济、灾荒 |

### 2.4 ④ 在途：**未实现**（跨路贸易尚未建模）

---

## 3 · 商品成交路径（**不止一条，语义不同**）

### 3.1 宋境 POP 购买 —— ⚠️ **无卖方，须修**

`settlement_granary.py:275-290`：
```python
spend = int(pop["wealth"] * base_rate * _elastic * _boom)
pop["wealth"] -= spend
for gdim, share in GOODS_DEMAND.get(pop_name, {"布": 1.0}).items():
    pop["goods"][gdim] = pop["goods"].get(gdim, 0) + int(spend * share)  # ← 凭空入库
# 尾差归商人（守恒修正）：artisan += spend×0.7；merchant += 余款
```
- **钱**：POP → 工匠 70% / 商人 30%（有对手方，守恒）；
- **货**：`pop.goods` **凭空增加**，无卖方扣减 ⇒ 虚拟供给。

### 3.2 宋境存货外销 —— ✅ **真扣货**

`settlement_granary.py:296-309`：
```python
_export = min(_stock - _cap, int(_month_prod * EXPORT_RATE))
artisan["goods"][_gdim] = _stock - _export        # 卖方扣货
artisan["wealth"] += int(_export * _gprice)       # 外部钱入
```
- 有卖方扣减；`statistics["export_income"]` 记流水。

### 3.3 外邦商品成交 —— ✅ **真扣货，但**不作用于宋境

`settlement_econ.py:759-836`（函数 `_ext_econ_phases`）：
- `_gpool` 取工匠库存，`_buy = min(_gpool, spend/price)`，**卖方扣货**（`_ag["布"] −= _buy`）；
- `settlement_econ.py:767` 明确 `kl == "工匠"` 被跳过（工匠不消费自己的货）；
- **归属外邦**（38 政权每月各调一次），宋境 `prefectures` 走的是 3.1。

> ⚠️ **重要**：不能因存在 3.3 就说"市场已有闭环"——**宋境消费走的是无卖方的 3.1**。

---

## 4 · 结论

1. **载体 4 个**（含未实现在途），其中 ② 的工匠条目**兼作生产池与消费池**，语义待拆（tasks §1.1）。
2. **成交路径 3 条**，宋境 2 条（1 条须修、1 条已真）、外邦 1 条（已真）。
3. **钱粮守恒**：三条路径的**钱**都有对手方（尾差归商人/营收池）；**失真只在货的凭空产生**。
4. **开局物资仓全 0** ⇒ 宋境 POP 无货可买（3.1 绕过了这层，靠凭空给货）。

---

## 5 · 遗留问题（交 B0-2 读数与 B1 台账）

| # | 问题 | 影响 |
|---|---|---|
| 1 | ② 工匠 goods 双重语义（生产池 vs 消费持有）未拆 | B1-3 迁移需先定性 |
| 2 | 3.1 与 3.2 是否重复消费（同一批货既凭空给又外销） | 需逐月对照流水 |
| 3 | `_goods_empty` 直产备份与生产链产出是否重复生产 | tasks B1 验收已列 |
| 4 | `RESOURCE_DIMS` 17 维在开局与生产的实际覆盖 | 供需读数需逐维确认 |

---
最后更新：2026-10-11（B0-1 台账测绘，实测行号）