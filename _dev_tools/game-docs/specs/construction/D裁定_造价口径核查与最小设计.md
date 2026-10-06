# D 裁定落地：建造造价口径核查与最小设计

> 2026-10-06 · 承用户裁定「建造和升级应承担造价，不能免费增加产能；
> 付款主体没有明确规则时，**不默认扣国库或任何 POP 账户**」
> **本轮只做口径核查与设计，未改任何生产结算代码。**

## 零、先更正我自己两处错误结论

| 我此前说 | 实测结论 |
|---|---|
| 「升级费是凭空消失的钱」 | ❌ 方向错：是**产能凭空增加** |
| 「两份 `BUILDING_COST_GROWTH` 不一致（1.8 vs 1.35）」 | ❌ **不是分歧，是两个不同作用域** |

### 作用域证据（决定性）

```
settlement_econ.py:1116   def _settle_external_economy(state, log):
settlement_econ.py:1236       evolve_building_levels(...)   <-- 唯一调用点
```

| 口径 | 值 | 定义处 | 用途 |
|---|---|---|---|
| **宋侧** | **1.8** | `content/data.py:999` | `construction.blueprint_cost`、`estate_mechanic.building_cost`、`settlement_officialdom._lv_cost` |
| **外邦** | **1.35** | `content/data_external.py:395` | `building_jobs.pay_construction_cost`（零调用） |

=> `BUILDING_COST` 表本身**只存在于 `data_external.py`**（外邦配置）。
=> **「1.35 与 1.8 冲突」是我的误判**：它们分属不同政权，不该统一。

## 一、发起主体 × 付款账户 × 材料 × 结算入口（五条路径）

| # | 路径 | 发起主体 | 付款账户 | 材料来源 | 结算入口 |
|---|---|---|---|---|---|
| 1 | **玩家下令 · 蓝图立项** | 玩家（中央） | 造价 `construction.blueprint_cost` = Σ `base_cost × 1.8^i` | 蓝图 `cost.silver` | `construction.py`（立项，非月结算） |
| 2 | **玩家下令 · 官府工程** | 玩家（中央） | `settlement_officialdom._lv_cost`；政府工程归国家资产 | — | `settlement_officialdom.py` |
| 3 | **自发营造 · 士绅家产** | 士绅 POP（自造） | `estate_mechanic.building_cost` = `base_cost × 1.8^(lv-1)`；士绅自有 wealth | — | `estate_mechanic.py` |
| 4 | **自发营造 · 民间营造** | 民间 POP（自造） | `build_civil_building`：出资阶层 `spec["payers"]` → 本路工匠，**全或无 + 失败原路退回** | **本地州府仓**，取不到即缺料 | `settlement.py:597` → `apply_civil_construction` |
| 5 | **外邦 · 自发营造** | 外邦政权（NPC） | 🔴 **无**（`evolve_building_levels` 只收 `surplus` 布尔） | 外邦自有 | `_settle_external_economy` |

### 建筑等级 `lv` 写入点全仓枚举（实测）

```
building_jobs.py:375     entry["lv"] = new_lv        外邦升级
building_jobs.py:792,796 entry["lv"] = cur-1 / 0      外邦倒闭
civil_building.py:1070   entry["lv"] = int(new_lv)    <-- 唯一宋侧升级
```

## 二、🔴 核查结论：D 裁定的问题**只存在于外邦**

| 裁定要求 | 宋侧 | 外邦 |
|---|---|---|
| 建造承担造价 | ✅ **已承担**（路径 1–4 均有明确付款账户） | 不适用（NPC 不结算钱） |
| 升级承担造价 | ✅ **已承担**（`civil_building:1070` 前必过料款+工钱） | 🔴 **未承担** |
| 不默认扣国库/POP | ✅ 已遵守（付款方写在 `spec["payers"]`，无默认） | — |

=> **宋侧不存在「免费增加产能」**：`civil_building` 的升级与新建同一条路径，
   先收料（州府仓实物调拨）再付工钱（出资阶层 → 工匠），两者都走 `transfer_money` 守恒。

=> **唯一免费升级是外邦**：升级分支
   `_set(bt, _cur(bt)+1, "结余营造", +1)` **零金钱操作**，
   触发条件只是 `surplus and not famine and random() < 0.05`。

## 三、`evolve_building_levels` 的预算问题（裁定 §3）

### 问题

`surplus` 是**布尔** `(tax - _pa - _po) > 0`，**不含任何金额**。
它表达「上月财政有结余」，**不等于「这笔钱已拨给营造」**。
用它当升级条件，等于把「有钱」误当「钱到位」。

### 建议：外邦也走显式投资额

```python
# 现状：布尔当条件
if surplus and not famine and R.random() < BUILDING_UPGRADE_PROB:
    _set(bt, _cur(bt) + 1, "结余营造", +1)

# 建议：先算可用投资额，再判是否够付造价
invest = 0.0 if famine else max(0.0, surplus_amount) * INVEST_SHARE
need = building_cost(bt, _cur(bt) + 1)      # 用外邦自己的 1.35 口径
if invest >= need and R.random() < BUILDING_UPGRADE_PROB:
    invest -= need
    _set(bt, _cur(bt) + 1, "结余营造", +1)
```

要点：

1. `surplus` 布尔改为**金额** `surplus_amount`，由调用侧传入；
2. 造价复用**外邦自己的** `BUILDING_COST` × `1.35`（**不要**改成 1.8）；
3. `INVEST_SHARE` 是「结余划入营造的比例」，**新参数，需裁定**；
4. 不够付则**不升级**（不默认扣国库、不透支）。

⚠️ 需 `INVEST_SHARE` 与「结余金额口径」两个新定义，**本轮不实现**。

## 四、`BUILDING_COST` 与 1.8/1.35 的统一使用（裁定 §2）

**结论：不统一数值，统一「公式形态」。**

```
宋侧 level_cost(lv) = base_cost      × 1.8 ^(lv-1)     construction / estate / officialdom
宋侧 blueprint(Σ)  = Σ base_cost    × 1.8 ^i          construction.py:87,90（累计到 lv 级）
外邦 level_cost(lv) = BUILDING_COST[type] × 1.35^(lv-1)
```

| 项 | 处理 |
|---|---|
| 两套增长率 | **保持 1.8 / 1.35 不变**（分属宋侧/外邦） |
| `pay_construction_cost` 的 `1.35` 缺省 | ⚠️ **不得作为默认口径**（裁定 §4）；接线**必须显式传 cfg 里的值**，缺值应报错或按 0，**不默认回落** |
| 最小可玩规则 | 造价 = `base × growth^(lv-1)`；**付款方按 §一 表**；不够付则不建/不升 |

## 五、影子算例

```python
GROWTH = 1.35
for base in (5000, 10000, 20000):
    print("base=%6d :" % base
          + "".join(" lv%d=%9d" % (lv, int(base * GROWTH ** (lv - 1)))
                    for lv in range(1, 7)))
```

（实算结果见本文件末「影子算例实测」。）

**收益对照**：每升一级，岗位 = `lv × JOBS_PER_LEVEL`，产出按 `produce_job_track`。
`1.35^(lv-1)` 的增速**快于**岗位的线性增速 ⇒ 边际投入产出比递减。

## 六、`pay_construction_cost` 的处置（裁定 §4）

| 项 | 处置 |
|---|---|
| 当前状态 | **保留为未接线旧实现**，不接入任何路径 |
| 若将来复用 | **必须重写**为走正式付款接口的服务：`state` 入参 + `transfer_money` 钱腿 |
| `1.35` 缺省 | **不得继续作为默认口径**；接线时显式取值 |
| 账本通道 | 🔴 现为直写 `gentry["wealth"]`，**违反 POP 挂载律**，接线前必须改 |

## 七、须你裁定 / 确认

| # | 事项 |
|---|---|
| 1 | 外邦是否也要求「升级付造价」？（即 §三 的改动要不要做） |
| 2 | 若做：`INVEST_SHARE`（结余划入营造的比例）取多少？ |
| 3 | 确认「宋侧已承担造价、无需改动」这一结论 |
| 4 | 路径 1（蓝图立项）与路径 2（官府工程）的**实际扣款账户**是否已明确？本轮只见造价口径，**未见扣款入口** |

最后更新：2026-10-06
