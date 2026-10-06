# `pay_construction_cost` 职责比对核查（证据与建议）

> 2026-10-06 · 承用户裁定「暂不接线、也不删除；先比对职责与真实生产调用路径，再提交证据与建议」
> **本轮只做文档核查：未改业务行为、未改 import、未接线、未删除。**

## 一、两者职责对照

| 维度 | `building_jobs.pay_construction_cost` | `civil_building.build_civil_building` |
|---|---|---|
| 资金来源 | 士绅 POP wealth → 政权 treasury dict | **出资阶层 `spec["payers"]` 的 POP wealth** |
| 钱的去向 | **全额转给工匠 wealth** | 工钱 → `CIVIL_WAGE_RECIPIENT`（本路工匠），全或无、失败原路退回 |
| 材料 | **完全不涉及** | 取料（只从本地州府仓），取不到即缺料 |
| 造价来源 | `cfg["BUILDING_COST"] × BUILDING_COST_GROWTH**(lv-1)` | **单一真源 `core.construction_cost.base_material_cost`** |
| 账本通道 | 🔴 **直写 `gentry["wealth"]` / `artisan["wealth"]`** | ✅ **走 `_pay_wage` → `state.transfer_money`（守恒）** |
| 外部政权 | 注释称「外邦禁 burn」 | — |

## 二、🔴 关键证据：**账本通道不合规**

```python
# building_jobs.py:743-747
gentry["wealth"] = g_have - from_g          # 直写
treasury["amount"] = t_have - from_t        # 直写
artisan["wealth"] = int(artisan.get("wealth", 0) or 0) + cost   # 直写
```

该函数签名只收 `pops: dict`，**不收 `state`** ⇒ 若拿路级 `pops` 传入，
会**绕过 `pop_bridge`**，违反 `AGENTS.md §3-1` POP 挂载律（写入必须落州府）。
这与已记录的 `grain_bridge`「**给了 state 就委派、没给就沿用旧载体**」是同一类漏网形态。

⇒ **当前未违规**（因为它零调用），但**一旦按现状接线就会违规**。

## 三、真实生产调用路径（实测）

| 事实 | 证据 |
|---|---|
| **生产代码零调用** | 全仓 10 处命中全是定义、测试、文档；无任何结算/生产路径调用 |
| 唯一消费者是测试 | `tests/test_building_jobs.py:199/207` 断言「升级费转工匠、无 burn」 |
| `civil_building` 不含出资阶层出资逻辑 | 成本仅「料（州府仓实物调拨）+ 钱（工钱）」两笔，**无升级费出资** |

## 四、三选一的证据与建议

| 选项 | 支持证据 | 反对证据 |
|---|---|---|
| **A 保留未接线** | 其「升级费转工匠、禁 burn」的语义是 `civil_building` **没有**的；文档 §3.5 有登记 | 与现行口径 C-c「料款与工钱彻底分离」重叠；造价真源已移到 `construction_cost`，此处 `cfg` 另立一份 |
| **B 已被替代** | 造价真源已统一；料/钱分离后其出资逻辑不再必要 | 工钱口径与它不同（`_pay_wage` 全或无+退回 vs 本函数 funded 布尔） |
| **C 存在漏接线** | 升级/降级事件流中确无出资环节 | `evolve_building_levels` 已被 `settlement_econ` 调用并可正常演化，**并不卡在这里** |

### 建议：**B（已被替代），但先补缺口再删**

理由：
1. **C 证据不足** —— 建筑等级演化的调用链**完整**，不卡出资，故「漏接线」不成立；
2. **A 与 B 并存的真实缺口是「升级费由谁出」这一口径从未落地** —— 
   `civil_building` 只覆盖「新建/修缮」，**升级路径的造价无人承担**。
   若不补这个缺口，`BUILDING_COST` 升级费就是凭空消失的钱。
3. 因此顺序应为：**先裁定「升级费口径」（官府拨付 / 士绅出资 / 不收）→ 再决定本函数删除或改写**。

⚠️ **若将来接线，必须同时满足**：
- 签名改为接收 `state`，钱腿走 `state.transfer_money`（与 `_pay_wage` 同源）；
- 付费方改为 `local:<路>` / `treasury` / `imperial_treasury`（本会话 `cfab7fd0e1` 已开通）；
- 造价改读 `construction_cost.base_material_cost`，不再用 `cfg["BUILDING_COST"]`。

## 五、关联记录

- 符号级调用图：[`building_jobs_符号级调用图.md`](./building_jobs_符号级调用图.md)
- 官有营造付款渠道：[`官有营造付款渠道_未完成.md`](./官有营造付款渠道_未完成.md)

最后更新：2026-10-06

---

## 更正（2026-10-06 二次核查）：升级不是「钱消失」，是「产能凭空增加」

本文件上方 §四 的「`BUILDING_COST` 升级费是凭空消失的钱」**方向说反了，特此更正**。

### 实测证据：`evolve_building_levels` 零金钱操作

```python
# building_jobs.py:411-418  升级分支
if surplus and not famine and R.random() < 0.05:
    bt = R.choice(cands)
    _set(bt, _cur(bt) + 1, "结余营造", +1)   # ← 只写 entry["lv"]

# _set 实现（371-380）只有：entry["lv"] = new_lv + 记录 changes
# 全函数无任何 wealth / treasury / transfer_money 操作
```

调用侧（`settlement_econ.py:1236`）同样**不补扣款**：

```python
evolve_building_levels(_p, cfg,
    surplus=(int(st["tax"]) - _pa - _po) > 0)   # 只传布尔，无金额
```

### 真实机制：这是**结构性通胀源**，不破坏守恒

| 环节 | 是否花钱 |
|---|---|
| 等级升级 `evolve_building_levels` | 否 |
| 产出增加 `produce_job_track` | 放大分子 |
| 工钱支出 `pay_wages_from_revenue` | 是（从营收出）|
| 建造/升级**造价** | **无人承担** |

=> 升级在「营收 -> 工钱」链路上**只放大分子（产出），分母（造价）为零**
=> 长期效果是**产能无成本扩张**。
=> 这**不是**钱账本失衡（不破坏守恒），而是**经济平衡门缺一道成本**。

### 附带查出：两份 `BUILDING_COST_GROWTH` 不一致

| 位置 | 值 | 状态 |
|---|---|---|
| `content/data.py:999` | **1.8** | 权威（`construction` / `blueprint_dynamic` 走它）|
| `building_jobs.py:728` | `1.35`（缺省回落）| **不一致** |

=> 目前**未生效**（`pay_construction_cost` 零调用），属**潜伏口径分歧**；
=> 若照 §四 建议接线，**必须**显式传权威值，否则会用到 1.35。

### 修正后的建议（替代 §四 的结论）

| 选项 | 修订后判断 |
|---|---|
| ~~C 存在漏接线~~ | **排除**：升级链完整，缺的不是接线，而是**成本口径本身** |
| **B 已被替代** | 仍成立 |
| **新增 D** | **真正的缺口是「升级/建造造价无人承担」**，属经济平衡问题，不是代码缺陷 |

=> **须你裁定的是 D**：`BUILDING_COST` 升级造价是否应当承担？
  - 若**承担** -> 需要新口径，且 `pay_construction_cost` 需**重写**（不能直接接线，见 §二 账本通道不合规）；
  - 若**不承担**（升级为纯事件驱动）-> 该函数可**直接删除**，并把 `BUILDING_COST` 标注为仅蓝图用。

---

**教训**：上一轮我只读了 `pay_construction_cost` 自身，**没顺调用链查升级实际发生处**，
就断言「钱消失」—— **又一次是「读了数据没查口径就下结论」**。
本次先查 `evolve_building_levels` 与调用侧，才把方向纠正过来。
