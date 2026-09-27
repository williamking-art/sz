# A · 结算与经济守恒审查

- 审查对象：《宋祚 Songzuo》月度结算与经济守恒主链
- 审查范围：`core/settlement.py`（448 行）、`core/settlement_steps.py`（3164 行）、`core/game_state_econ.py`（523 行），交叉只读 `content/data.py` 常量、`core/game_state.py` 账户原语
- 解释器：`D:\codebuddy\.audit-venv\Scripts\python.exe`（Python 3.13），审查脚本置于 `D:\codebuddy\sz\_dev_tools\_scratch\audit-2026\`，**未修改 game 下任何源文件**
- 说明：工作区无 `ai_config.json`，全部实测走「无 AI 契约」分支（`_economy_ai` 等槽位缺失）；AI 档位只做调制，不改守恒结构，故主要结论不受影响。带 AI 的差异点已单列（A-10）。

## 结论速览

| 编号 | 严重度 | 一句话 | 文件:行 | 证据类型 |
| --- | --- | --- | --- | --- |
| A-1 | P0 | 士绅囤粮超硬上限「强制出清」把 100% 余量从账上抹去，只按 3% 记损耗 → 24 月凭空销毁 2.65 亿石 | `core/settlement_steps.py:2033-2042` | [确认] 实测 |
| A-2 | P0 | 国库穿底后支出仍全额发到民间 POP，新造货币额 == 新增亏空深度（1:1） | `core/settlement_steps.py:2928-2963, 3003-3015` | [确认] 实测 |
| A-3 | P1 | `_settle_economy` 流民池存在「只对流入成立」的 5% 上限，实际双向钳制 → 超额流民被静默灭失 | `core/settlement_steps.py:752-755` | [确认] 实测 138,718 人/77 月 |
| A-4 | P1 | 畜栏产肉直接 `imperial_treasury +=` 无买方 → 每月凭空造 40,000 贯 | `core/settlement_steps.py:2153-2156` | [确认] 实测 |
| A-5 | P1 | 酒坊每月把常量永久累加进「月度酒课率」，无上限线性增长（600k→3.7M 贯/月，内帑 1M→152M） | `core/settlement_steps.py:2150-2152` | [确认] 实测 |
| A-6 | P1 | `p["grain"]` 兼作「年产」与「现货」，士绅囤粮按现货扣年产 → 永久削减税基/年产 | `core/settlement_steps.py:1998-2018` vs `core/game_state_econ.py:336-338,357` | [确认] 实测 |
| A-7 | P1 | 粮市撮合农卖方权重保底 0.5 覆盖「不超盈余」约束 → 农超卖盈余（实测 24 倍），蚕食 P0-① 安全垫 | `core/settlement_steps.py:1769-1784, 1795-1802` | [确认] 实测 |
| A-8 | P1 | 工程 `defense_add` 直接造兵，次月 `_settle_finance` 重聚合兵 POP → 凭空造人（与已修 arm_strength 同类） | `core/settlement_steps.py:2085-2110` + `2922-2927` | [确认] 构造态实测 |
| A-9 | P2 | 区域粮价两套公式（月演化 vs 常平触发）口径不同，常平一动价格即跳变 | `core/settlement_steps.py:1610,1624,2769-2782` | [确认] 代码 |
| A-10 | P2 | 常平「AI 强化档」是同月对同路**再跑一整轮**平粜籴（14/20 路被调用两次） | `core/settlement_steps.py:1630-1658` | [确认] 实测 |
| A-11 | P2 | `statistics["total_income"]` 存在幻影入账：机制「市舶抽解」+3,500,008 贯/月；一条鞭按名义额记账 | `core/settlement.py:86-87`；`core/settlement_steps.py:881-885` | [确认] 实测 |
| A-12 | P2 | `land["survey"]` / `land["survey_active"]` 全库只读不写 → 清丈归籍加成、士绅抵抗分支永不生效 | `core/settlement_steps.py:937, 2222-2223` | [确认] 全库 grep |
| A-13 | P2 | `state.active_decrees` 月末被整表替换为「本月新增长期诏」→ duration=12 政令次月即消失 | `core/settlement_steps.py:63, 95-108` | [确认] 实测 |
| A-14 | P2 | Step 0 终局早退：不推进回合、不写 `settlement_log`，重复调用永久空转 | `core/settlement.py:341-345` | [确认] 实测 |
| A-15 | P2 | 赈济量纲 `relieved = relief(石) × 3000(人/石)` = 6 亿人，赈济额恒不构成约束 | `core/settlement_steps.py:3109-3111` | [确认] 实测 |
| A-16 | P2 | Step 6 裁汰在 Step 4 重聚合之后执行，`_return_men` 再加农 → ΣPOP 当月虚增（实测 +50,000） | `core/settlement_steps.py:2379-2386` + `2922-2927` | [确认] 实测 |
| A-17 | P2 | 窖银单位（贯）与 `silver_in`（万贯）差 10,000 倍量纲 | `core/settlement_steps.py:1962-1970` vs `core/game_state_econ.py:114` | [确认] 代码+常量 |
| A-18 | P2 | 田产/耕地 0.2%/月无上限复利（120 月 ×1.271），且 `land["cultivated"]` 无任何业务读取 | `core/settlement_steps.py:784, 901` | [确认] 实测 |
| A-19 | P2 | 外部/产出型入账无对方账户：商品外销变现 +42.68M 贯/77 月；工程 `wine_coin_add` 同类 | `core/settlement_steps.py:1697-1714, 2112-2113` | [确认] 行级归因 |
| A-20 | P2 | 零碎口径/边界：空 `factions` 抛 IndexError；两套人均口粮表；本色俸禄 int 截断损耗被吞、`granary_stats["military"]` 误记官吏禄 | `core/settlement_steps.py:671-673, 1739 vs 1872, 1552-1567` | [确认] 实测/代码 |

**历史修复复核结论**：2026-08-31 与 2026-09 R2 的修复项**代码确实在位**（逐条见文末「已修项复核」），其中 A-7 使「农存粮安全垫」的守卫被撮合权重旁路（部分回归），A-8 与已修的 `arm_strength` 属同类缺陷但**未同步修复**，A-3 与人口总账 Step 10.5 的闭合目标冲突。

---

## 详细条目

### A-1 [P0] 士绅囤粮超硬上限强制出清：97% 的销毁量没有任何对手方与记账

- 位置：`core/settlement_steps.py:2033-2042`
- 证据：[确认]（行级归因实测 + 24 月/77 月跑量）

```python
2033  if genty["grain"] > _hard_cap:
2034      _excess = genty["grain"] - _hard_cap
2035      sold = _sell_to_buyers(p, genty, _excess, price, _copper_share)
2036      genty["grain"] = _hard_cap          # ← 余量一次性抹去
2037      _unsold = _excess - sold
2038      if _unsold > 0:
2041          _spoil = int(_unsold * HOARD_SPOIL_RATE)      # 0.03（content/data.py:240）
2042          state.granary_stats["hoard_spoil"] = ... + _spoil
```

行级追踪（`run_line_trace.py _settle_civilian_hoard all`，77 月）：

```
行 2036   Δ粮 = -1,294,946,035   genty["grain"] = _hard_cap
```

`probes2.py`（24 月，逐次读 `_excess`/`sold`）：

```
触发强制出清余量 Σ_excess = 265,245,729 石
卖入买方池 Σ_sold        = 0 石
凭空销毁 (excess-sold)   = 265,245,729 石
按 3% 记入 hoard_spoil   = 7,957,334 石 (3.00%)
granary_stats['hoard_spoil'] 实际 = 7,957,334 石
样例 (路, excess, sold) = [('两浙路',3474543,0), ('江南东路',2616738,0), ...]
```

- 影响：粮账户每月凭空减少 1,100 万石（24 月均值），占月产（约 5,900 万石）的 ~19%。`granary_stats["hoard_spoil"]` 只记 3%，任何以该统计为准的损耗对账、AI 认知层、平衡读数都会系统性低估 32 倍。且 `sold == 0` 说明买方池早已被前一段（软上限抛售）抽干，所谓「先售买方池」实际不成立。
- 验证方式：`python run_line_trace.py _settle_civilian_hoard all`；`python probes2.py`（E2 段）
- 建议修复：`genty["grain"] = _hard_cap` 之前，把 `_unsold` 全额记入 `granary_stats["hoard_spoil"]`（或分流到「压仓/焚毁」科目并给出日志），使销毁额与统计逐月闭合；同时把买方池耗尽的原因（与 `_buyer_pool` 的 `PER_CAPITA_MONTH_GRAIN` 口径、软上限先售顺序）一并复核，避免「强制出清」成为纯销毁通道。

---

### A-2 [P0] 国库穿底时支出仍全额发放民间：新造货币额 == 新增亏空深度

- 位置：`core/settlement_steps.py:2928-2963`（POP 入账）与 `2969-2973`、`3003-3015`（国库截断 + 亏空）
- 证据：[确认]（60 月实测逐月 1:1）

```python
2969  total_out = (expenditure + effective_cash_out + int(corruption_cash_ded)
2970               + payraise_used + sui_gong)
2973  actual_net = actual_tax - total_out
3004  _avail = state.treasury + int(actual_net) - int(imp_share)
3006  if _avail < 0:
3007      state.treasury_deficit = _prior_deficit + (-_avail)
3008      _avail = 0
3015  state.treasury = max(0, int(_avail))
```

而民间入账（`2934-2939` 兵/官俸禄、`2954-2963` 常费回流 40%/60% + 贪腐入官僚）**不以国库是否付得出为条件**：

```python
2954  _civil_back = max(0, expenditure)
2959      _p["pops"]["工匠"]["wealth"] += int(_civil_back * 0.4 * ...)
2961      _p["pops"]["商人"]["wealth"] += int(_civil_back * 0.6 * ...)
```

`probes4.py`（60 次 `_settle_finance`，国库从 0 起）：

```
60 月累计：Δmoney=+39,318,557   Δ亏空=+39,321,197   差=-2,640（int/float 截断）
逐月样本：(1101,1, Δmoney=+259,292, Δ亏空=+259,336, 国库=0, 累计亏空=446,105)
          (1101,1, Δmoney=+1,236,140, Δ亏空=+1,236,184, 国库=0, 累计亏空=28,195,544)
```

整局（`run_months.py 120`，实跑 77 月后破产）：

```
_settle_finance 累计 Δ钱 = +20,114,349   期末 treasury_deficit = 20,117,795
```

- 影响：亏空深度被设计为「累计未能支付的支出」的记账科目（`game_state.py:744-750`），但它同时被用作**货币**：POPs 拿到了国库从未支付的俸禄与常费。77 个月内凭空增发 2,011 万贯（约 26.1 万贯/月），并直接推高 `calc_price_level` 的货币供给。国库长期恒为 39 贯，亏空单调攀升至破产线（`TREASURY_COLLAPSE_LINE=2,000 万`），第 78 月触发 Step 0 终局。
- 验证方式：`python probes4.py`（R 段）；`python run_months.py 120`
- 建议修复：支出侧按「国库实付额」比例发放（`ratio = min(1, treasury_available / max(total_out,1))`），或把未支付部分落成对官员/工匠的**欠支科目**而非直接入 POP wealth；`treasury_deficit` 只能作为判据读数，不得与货币总量互为镜像。

---

### A-3 [P1] 流民池 5% 上限被双向钳制 → 超额流民被静默灭失

- 位置：`core/settlement_steps.py:745-755`
- 证据：[确认]

```python
745  local = p.get("refugees", 0)
746  if local > 0 or p.get("unrest", 15) >= 20:
750      absorb = (mood - 50) * 0.001 + (40 - unrest) * 0.0008 + (govern - 50) * 0.0006
751      delta = int(local * absorb)
752      cap = int(p.get("population", 1_000_000) * 0.05)
753      new_local = max(0, min(local + delta, cap))     # ← local > cap 时直接砍到 cap
```

上方注释（739-744）自述「cap（本路人口 5%）**只对流入成立**」，但实现是 `min(local+delta, cap)`：只要存量已超 cap（灾荒路径 `settlement_steps.py:3152` 上限为人口 10%，必然超过 5%），本步即无条件削减。

`probes5.py`（77 月真实长局，行级钩住第 755 行）：

```
cap 钳制削减流民：16 次，合计 138,718 人（凭空灭失）
其中 delta>=0（流入路径却被截断）的次数=16，合计 138,718 人
样例：河东路 流民 203,028 → 195,600 (delta=+4750, cap=195,600)
     陕西路 流民 263,677 → 254,200 (delta=+6802, cap=254,200)
```

构造态（`probes.py` C 段）：`refugees=839,270 → 291,348`，**单次 `_settle_economy` 灭失 485,664 人**（`Δ(ΣPOP+流民)=-485,664`）。

- 影响：人口总账（Step 10.5 `settlement.py:434-436` 以 `ΣPOP + 流民` 覆盖 `state.population`）本应闭合，此处成为「人凭空消失」科目；且流民是起义压力（`_settle_events` 1118 后按 `local_ref/2000` 加成）的输入，静默削减会削弱史实压力链。
- 验证方式：`python probes5.py`；`python probes.py`（C 段）
- 建议修复：钳制改为单向 `new_local = min(max(0, local + delta), max(cap, local))`（只限制流入增量），或在超 cap 时把差额显式转为隐户/死亡科目并记日志。

---

### A-4 [P1] 畜栏产肉直接给内帑记钱，无买方 → 每月凭空造 40,000 贯

- 位置：`core/settlement_steps.py:2153-2156`（`_settle_workshops`）
- 证据：[确认]

```python
2153  elif out_dim == "meat":
2155      state.imperial_treasury += int(yld * MEAT_PRICE)          # MEAT_PRICE=0.5
2156      state.granary_stats["meat_revenue"] = ... + int(yld * MEAT_PRICE)
```

开局即有 80 座作坊（`probes.py` G 段：`workshops=80`，40 酒坊 + 40 畜栏），其中 40 畜栏 `yield=2000`（`content/data.py:212`）：

```
第1次 _settle_workshops: 太仓 Δ=-4,000,000 石  内帑 Δ=+40,000 贯
```

行级归因（77 月）：`行 2155  Δ钱 = +2,584,000`（其余行为 0）。

- 影响：钱账户无对手方凭空增发 40,000 贯/月（约 48 万贯/年，相当于开局月税收 217 万贯的 1.8%）；同时消耗太仓 400 万石/月，交换比 100 石 ∶ 1 贯（按米价 1.16 贯/石，400 万石价值约 464 万贯，却只换回 4 万贯），15 个月即抽干 1,500 万石初始太仓（实测期末 `granary=3,184 石`）。这与已修的「市舶关税重复入账」属同一类「政府侧账户单向入账」缺失对手方。
- 验证方式：`python probes.py`（G 段）；`python run_line_trace.py _settle_workshops all`
- 建议修复：肉/畜产品应卖给民间 POP（按买方 wealth 成对划转，与 `_changping_trade` 同构），或把产出计入 `resources` 而非直接折钱；同时复核 `grain_feed`（50,000 石/座/月）与 `yield` 的量纲与数值平衡。

---

### A-5 [P1] 酒坊把常量永久累加进「月度酒课率」：无上限线性增长

- 位置：`core/settlement_steps.py:2150-2152`；下游 `core/game_state_econ.py:520`、`core/game_state_econ.py:162-165`
- 证据：[确认]

```python
2150  if out_dim == "wine":
2152      state.wine_tax += int(yld * MATERIAL_PRICE_BASE.get("wine", 0) * 0.1)
```

`wine_tax` 是**月度酒课额**（`game_state.py:211` 初值 `WINE_COIN_BASE=600,000`），但本行在**每个结算月**把它加上 `yld×price×0.1`（40 酒坊 → +48,000/月），永不清零：

```
开局 wine_tax=600,000
第1次: +48,000 → 648,000
第2次: +48,000 → 696,000
第3次: +48,000 → 744,000
若持续 120 月：≈ 6,360,000（月度酒课，无上限）
```

实测长局采样（`run_months.py`）：1101/2 = 648,000 → 1107/6 = 3,702,000（×6.2，且仍在 +48,000/月线性攀升）。该额经 `core/settlement_steps.py:2980-2999` 每月从工匠 60%/商人 40% wealth 实扣入内帑（77 月累计约 1.488 亿贯），使内帑从 100 万贯膨胀到 1.524 亿贯（同期国库归零、亏空 2,011 万）；同时经 `calc_region_grain_price` 的 `wine_grain_monthly = wine_tax / WINE_TAX_SHARE * WINE_GRAIN_PER_GUAN`（`game_state_econ.py:163`）把酿酒耗粮需求从 1,350 万石/月推到 7,700 万石/月，超过全国月产（约 5,900 万石），长期把区域粮价顶到 `GRAIN_PRICE_MAX`（实测 1103/2 起米价多次 = 2.50）。

- 影响：货币长期从民间单向抽入内帑并推高粮耗需求，是「内帑膨胀 / 国库枯竭 / 米价顶格」三条漂移的共同驱动项；数值上 6 年后酒课为初始的 6 倍且无上限。
- 验证方式：`python probes.py`（G 段）；`python run_months.py 120`（酒课列）
- 建议修复：酒坊应只增加一次性产能或把产量记入 `resources`/`wine production`，由产量×税率计算月课；若确要累加产能，需加上限并让 `wine_tax` 每期由产能重算而非 `+=`。

---

### A-6 [P1] `p["grain"]` 口径冲突：士绅囤粮按「现货」扣减「年产」字段

- 位置：`core/settlement_steps.py:1998-2018`（囤粮买入）vs `core/game_state_econ.py:336-338`、`357`（按年产 ÷12/÷3 计税）与 `core/settlement_steps.py:901`（月增 ×1.002）
- 证据：[确认]

```python
# settlement_steps.py:2005-2018（_settle_civilian_hoard「囤」分支）
2005      src = max(0, int(p.get("grain", 0) / 12.0))    # 粮源上限 = 年产/12
2017      genty["grain"] += buy
2018      p["grain"] = max(0, int(p.get("grain", 0)) - buy)   # ← 从「年产」里扣掉现货
```

```python
# game_state_econ.py:336-338（同一字段被当成年产流量）
336  gy = float(p.get("grain", 0))                   # 年总产（石/年）
337  grain_annual = gy * LAND_TAX_RATE_BENEFIT * arrival * harvest * (1 - hidden) * ...
```

`probes4.py`（U 段，`_economy_ai={"士绅":"囤","士绅力度":"大"}`）：

```
河北路 p['grain'] 35,622,000 → 35,399,363（-222,637，-0.62%，单月）
全国月二税折色 864,322 → 858,920（税基随「囤粮」下降 → 永久性，非当月波动）
```

- 影响：士绅囤粮本应是「库存转移」，实际永久削减该路年产与田赋税基（田赋、本色征收、区域粮价供给全部同源用 `p["grain"]`）。玩家/ AI 选择「囤」档位即等于削弱国家税基，且无任何日志；与 `calc_region_grain_price` 里「田产/隐田产作为市场供给」的建模意图相互矛盾。
- 验证方式：`python probes4.py`（U 段）
- 建议修复：囤粮货源应取自独立的现货科目（如 `p["storage"]`/`p["granary_stock"]`），`p["grain"]` 保持「年产能力」语义；若确实要扣年产，需同时按 `SEED_GRAIN_PER_MU` 式口径回补或明确记为耕地退化。

---

### A-7 [P1] 农卖方权重保底使农超卖盈余，「不超盈余」不变式不成立

- 位置：`core/settlement_steps.py:1769-1784`（权重与分配）、`1795-1802`（落地）
- 证据：[确认]（构造态实测）

```python
1769  _sw = {}
1770  for sname, s in sellers:
1771      w = s / sell_total
1772      if sname == "农":
1773          w = max(w, FARMER_SELL_FLOOR)      # 0.5（content/data.py:1774）
1778  _snames = list(_sw.keys())
1780      q = int(trade * _sw[sname] / _wsum)
1782          q = _left        # 尾差归末位（trade ≤ sell_total 保证不超盈余）← 该断言不成立
```

注释的「trade ≤ sell_total 保证不超盈余」只在权重和为 1 时成立；`农` 被抬到 0.5 后 `_wsum` 可达 1.5，农分得的 `q` 与自身盈余脱钩。而安全垫（P0-①）只作用在**盈余计算**上（`1745-1747`），不作用于分配。

`probes2.py`（A2 段，构造态：京畿路农盈余 1,000 石、士绅盈余 4,000 万石）：

```
京畿路 农:  q=24,283   卖出前存粮=4,972,040   （农可卖盈余仅 1,000 石 → q 为盈余的 24.3 倍）
京畿路 士绅: q=45,707
```

- 影响：`_nong["grain"] -= q` 无下限保护（`1797`），超卖直接吃掉「保留 1 个月口粮」的守卫；极端参数下可把农存粮压到 need 以下，触发 `1804-1820` 的逃荒链（0.2%/月、单路 5 万上限）。2026-08-31 的安全垫修复因此只对「盈余判定」有效，对「撮合分配」无效。
- 验证方式：`python probes2.py`（A2 段）
- 建议修复：分配后加硬约束 `q = min(q, surplus_or_available)`，或把 `FARMER_SELL_FLOOR` 改为只在**按盈余比例分配后仍有剩余**时再补足（并保证 Σq ≤ Σsurplus）。

---

### A-8 [P1] 工程 `defense_add` 直接造兵，次月兵 POP 重聚合凭空造人

- 位置：`core/settlement_steps.py:2085-2110`（造兵）与 `2922-2927`（兵 POP 重聚合）
- 证据：[确认]（构造态实测）

```python
2096      main.branches["轻步兵"] = main.branches.get("轻步兵", 0) + add
2100      state.army_units.append(ArmyUnit(..., branches={"轻步兵": add}, ...))   # 无人口来源
```

```python
2922  # 兵 POP size 重聚合（兵额唯一真账 = army_units.troops 求和 ...）
2923  for _p in state.prefectures.values():
2924      _p["pops"]["兵"]["size"] = 0
2925  for _u in state.army_units:
2927      state.prefectures[_u.station]["pops"]["兵"]["size"] += _u.troops
```

`probes.py`（D 段，注入 `output={"defense_add":5000,"defense_routes":[road]}` 的完工工程）：

```
工程前 Σ兵额=750,000 ΣPOP=80,750,000
工程后 Σ兵额=755,000 ΣPOP=80,750,000
_settle_finance 后 ΣPOP=80,755,000（Δ全程=+5,000），农 POP 不变
```

- 影响：与 2026-08-31 已修的「诏令整军凭空造人」（改用 `_levy_men`）完全同类，但工程路径未同步修复：每月 `_settle_finance` 后 `ΣPOP`（进而 `state.population`）被凭空抬高，且人无来源。
- 可达性：[疑似] 当前仓库内**无任何代码/内容产出 `defense_add`**（`grep defense_add` 仅命中消费端 `settlement_steps.py:2085,2087`；`state.projects` 无内置数据，`game_state.py:217` 注明「玩家手动发起」），故属潜在缺陷；一旦有工程/存档/AI 工具写入该键即生效。
- 验证方式：`python probes.py`（D 段）
- 建议修复：与 `arm_strength` 一致，经 `_levy_men(state, route, add)` 征补并按其返回值落兵额。

---

### A-9 [P2] 区域粮价两套公式：月演化与常平触发口径不一致

- 位置：`core/settlement_steps.py:1610`、`1624`、`1645`、`1657`（调用 `_recalc_region_price`）vs `core/settlement_steps.py:2769-2782`（实现）vs `core/game_state_econ.py:146-175`（月度 `calc_region_grain_price`）
- 证据：[确认] 代码对比

```python
# _recalc_region_price（常平触发后重算）
2779  need = p.get("population", 0) * PER_CAPITA_MONTH_GRAIN
2780  supply = max(p.get("grain", 0) / 12.0 + extra_supply, 0.01)
```

```python
# calc_region_grain_price（Step 3 月度）
165   need = p.get("population",0) * PER_CAPITA_MONTH_GRAIN * factor + wine_share  # 含隐户系数+酒耗粮
171   _pop_release = sum(pop.get("grain",0) ...) * 0.02                            # POP 存粮 2% 入市
172   supply = max(total_grain/12.0 + _pop_release - hoard * HOARD_SUPPLY_SQUEEZE, 0.01)
```

`_recalc_region_price` 缺隐户需求系数、酒耗粮、POP 存粮释放、士绅囤粮挤压四项（`ratio` 双方都 clamp 到 [0.5,2.0]）。实测 77 月内 `_settle_granary` 每月都对多路调用（见 A-10 的 34 次/月），即 `p["grain_price"]` 每月被**两套模型轮流覆盖**。
- 影响：常平操作后本地价跳变、与月度演化价不自洽；`p["grain_price"]` 又是粮市撮合价、税负保底线、士绅囤抛判据的输入，属系统性价格口径漂移（不破坏守恒账）。
- 验证方式：`python probes2.py`（H 段观测调用频次）；代码对比
- 建议修复：统一到一个函数（`_recalc_region_price` 增补 factor/wine/pop_release/squeeze 参数，或让月度函数接受 `extra_supply`）。

---

### A-10 [P2] 常平「AI 强化档」= 同月对同路再跑一整轮平粜籴

- 位置：`core/settlement_steps.py:1591-1625`（基础轮）+ `1630-1658`（AI 强化轮）
- 证据：[确认] 实测

```python
1630  if price_stabilize_mult > 1.0:          # AI 档位 中/大/巨/极 → 1.5/2.0/2.5/3.0
1631      for name, p in state.prefectures.items():   # ← 与基础轮完全同构的第二轮
1635          if price > CHANGPING_HIGH and cp_stock > 0:
1637              ratio = min(_sell_ratio, (price - CHANGPING_HIGH) * 0.5 * price_stabilize_mult)
```

`probes2.py`（H 段，`_granary_ai={"granary":{"price_stabilize":"极"}}`）：

```
该月 _changping_trade 调用 34 次，涉及 20 路；同路被调用多次的 14 路
{'陕西路': 2, '两浙路': 2, ... '广南西路': 2}
```

- 影响：AI 档位语义是「加强」，实现却是「同月再执行一次完整操作」——`ratio` 已乘 `price_stabilize_mult`，等于双倍（甚至与基础轮叠加后 4~6 倍）操作量；且第一轮已把 `p["grain_price"]` 重算（`1610`），第二轮依据被改写后的价格决策，可能出现「先平粜压价、再平籴托价」的自反操作。非守恒破坏，但档位含义与 AI 契约不自洽。
- 验证方式：`python probes2.py`（H 段）
- 建议修复：把强化档并入单轮（`ratio` 已含 mult），删除第二轮或改成「仅对未达标路补一次」。

---

### A-11 [P2] `statistics["total_income"]` 幻影入账

- 位置：`core/settlement.py:86-87`；`core/settlement_steps.py:881-885`
- 证据：[确认] 实测

```python
# core/settlement.py:86-87（机制「市舶抽解」）
86  elif eff == "maritime_tax_up":
87      state.statistics["total_income"] += int(state.calc_commerce() * 0.01)
```

```python
# core/settlement_steps.py:881-885（一条鞭）
883      silver_total = int(land_grain * state.grain_price)
884      state.statistics["total_income"] += silver_total      # 名义额，非实征额
```

`probes3.py`：

```
K: calc_commerce()=350,000,800  1%=3,500,008
   statistics['total_income'] 0 → 3,500,008（Δ=+3,500,008）
   实际货币账户 Δ=+0
L2（收获月 3 月，single_whip=True）:
   国库 Δ=+4,641,796   一条鞭计入 total_income Δ=+5,160,449（幻影 518,653）
```

- 影响：`statistics["total_income"]` 被 `flow_summary.py:134`（治务·累计岁入表）与 `ai/client_utils.py:703`（AI 上下文）消费。机制每月虚增 350 万贯（超过实际月税入 217 万贯），一条鞭虚增约 10%，导致面板与 AI 对国力的认知系统性偏高。钱账本身不增（无造币）。
- 验证方式：`python probes3.py`（K、L2 段）
- 建议修复：机制改为真实入账（并从对应账户划转）或仅写独立统计键；一条鞭按 `got_nong + got_shen` 实收额记账。

---

### A-12 [P2] `land["survey"]` / `land["survey_active"]` 只读不写：两条分支恒不生效

- 位置：`core/settlement_steps.py:937`、`core/settlement_steps.py:2222-2223`
- 证据：[确认] 全库 grep（`core/`,`content/`,`engine/`,`ai/`,`backend/`）

```python
937   survey = 1.0 if state.land.get("survey_active") else 0.0      # 恒 0
938   gentry_drift = (gentry_power - 0.5) * 2 + survey * 2 - ...
2222  _survey = int(land.get("survey", 0) or 0)                     # 恒 0
2223  _back_rate = 0.004 + (0.010 if _survey else 0.0)              # 清丈加成永不生效
```

`grep -r "survey"` 命中全部为读取端或 AI 契约字段（`agent_router.py:117`、`ai/client.py:1967` 的 `survey_settle` 只写 `_survey_ai`/`hidden_cleared`）；`state.land` 初始化键为 `['cultivated','households','hidden_households','hidden_rate','wasteland','yield']`（实测），无 `survey`/`survey_active`。`land_survey` 诏令效果只改 `hidden_rate`（`settlement_steps.py:476`）。
- 影响：① 隐户归籍永远走 0.4%/月（日志恒为「招抚」），清丈加成 1.0%/月 不可达，隐户池长期只降不升（实测 77 月 20.0M→29.2M 口上升来自逃户，但归籍速率被锁死）；② 士绅抵抗 `gentry_resistance` 少一个「清丈施压」驱动项。
- 验证方式：全库 grep「survey」；`_settle_hidden_pop` 单元实测（日志恒「招抚」）
- 建议修复：在 `_apply_decree_effect` 的 `land_survey` 分支设置 `state.land["survey"]=1`（带衰减）或统一改用 `hidden_rate` 判据，并删除另一套键名。

---

### A-13 [P2] `active_decrees` 月末被整表替换，长期政令次月即消失

- 位置：`core/settlement_steps.py:63, 95-108`
- 证据：[确认] 实测

```python
63   active_ids = {d.get("id") for d in state.active_decrees if d.get("id")}
95       did = decree.get("id")
96       if decree.get("duration", 0) > 0:
97           if did:
98               if did not in active_ids:          # 已在 active_decrees 的 → 不再收进本轮
99                   longterm_this_turn.append(decree)
107  state.active_decrees = longterm_this_turn     # ← 整表替换
```

`probes3.py`（P 段）：

```
第 1 月后 active_decrees=['长策']  pending=0
第 2 月后 active_decrees=[]          # duration=12 未到期
```

- 影响：`duration>0` 的持续政令只存活一个月；`commands_decree.py:650`（口谕）与 `save_load.py` 依赖该字段（`agent_router.py:114` 把它列入 AI 唤醒上下文，注释 `commands_decree.py:653` 称其为落地凭据）。属数据丢失/展示与 AI 上下文缺项（当前不破坏守恒，因为效果在 `_apply_decree_effect` 是即时落地）。
- 验证方式：`python probes3.py`（P 段）
- 建议修复：`state.active_decrees = [未到期旧政令…] + longterm_this_turn`（按 id 去重 + `turn_issued + duration` 到期剔除）。

---

### A-14 [P2] Step 0 终局早退：不推进回合、不写 settlement_log

- 位置：`core/settlement.py:341-345`
- 证据：[确认] 实测

```python
341  if state.deficit_depth() > TREASURY_COLLAPSE_LINE:
342      state.game_over = True
343      state.game_result = "国用耗竭，天下鼎沸——..."
345      return log                     # ← 早于 Step 11 的 turn+=1 / settlement_log.append
```

`probes3.py`（J 段）：

```
game_over=True  turn 0→0  年月 1101/1→1101/1  settlement_log 0→0  返回日志 [...]
再次调用：turn=0 年月=1101/1 settlement_log=0 → 返回同样日志=True
```

在 `run_months.py` 长局中，第 78 月起每月都是同一份日志，持续 43 次无进展。
- 影响：调用方（`commands.settle_local` / `advance_and_settle` / 前端循环）无法从返回值区分「结算完成」与「终局空转」；终局当月的 `settlement_log` 永久缺失，回放/存档审计出现断档。
- 验证方式：`python probes3.py`（J 段）
- 建议修复：终局分支同样 `state.settlement_log.append(log)`，并在返回值/`state` 上给出显式终局标记（如 `log` 首元素带 `"GAME_OVER"` 或直接抛专用异常）。

---

### A-15 [P2] 赈济量纲 `relieved = relief(石) × 3000`：赈济额恒不构成约束

- 位置：`core/settlement_steps.py:3106-3136`（关键行 `3111`）
- 证据：[确认] 实测

```python
3106  relief = min(relief_grain, state.granary)          # DISASTER_RELIEF_GRAIN=200,000 石
3109  if relief >= relief_grain:
3111      relieved = relief * 3000                        # 石 × 3000 "人"
3115      used = min(relieved, local)                     # 恒等于 local
3120      spill = relieved - used                         # 恒为巨大余量
3131      add = min(int(spill * rv / tot), rv)            # 逐路清空流民
```

`probes3.py`（M 段）：

```
DISASTER_RELIEF_GRAIN=200,000 石 → relieved=600,000,000 人；全国流民合计=16,930
赈济后全国流民=0
```

- 影响：`3000` 使赈济能力恒大于全国流民存量，`min(relieved, local)` / `spill` 分支全部退化，「有粮则安民、无粮则民怨」的梯度被抹平——只要太仓发出一次足额赈济，全国流民清零。人口账本身守恒（流民→农 POP），但机制数值失去意义。
- 验证方式：`python probes3.py`（M 段）
- 建议修复：明确「人均赈济粮」系数（如 0.3 石/人·月）并据此反算可安置人数，或直接用 `relief / 人均月耗` 作为安置上限。

---

### A-16 [P2] Step 6 裁汰：Step 4 已重聚合，`_return_men` 再加农 → ΣPOP 当月虚增

- 位置：`core/settlement_steps.py:2379-2386`（裁汰）与 `2922-2927`（Step 4 重聚合，顺序在前）
- 证据：[确认] 实测

```python
2380  if _cut > 0 and state.army_units:
2384      u.add_troops(-_cut)
2385      _return_men(state, u.station, _cut)     # 农 POP += _cut
```

`probes4.py`（I2 段）：

```
路=陕西路 军 troops 220,000→170,000（裁 50,000）
兵 POP 260,000→260,000（未同步，Step 4 已在本月更早完成重聚合）
农 POP 4,608,455→4,658,455（+50,000）
ΣPOP 80,750,000→80,800,000  Δ=+50,000
```

- 影响：裁汰当月 `ΣPOP`（→ `state.population`，Step 10.5）虚增「裁汰人数」；下一月 Step 4 重聚合才回落，形成月度人口齿形波动，并短暂污染按人口摊分的所有逻辑。若与 `_levy_men`（Step 1）叠加月份方向相反，误差同行相消。
- 验证方式：`python probes4.py`（I2 段）
- 建议修复：把裁汰/征补统一在 Step 4 重聚合**之前**执行，或让 `_return_men`/`_levy_men` 同时维护 `兵 POP` 而非只改农/流民。

---

### A-17 [P2] 窖银（贯）与 `silver_in`（万贯）差 10,000 倍量纲

- 位置：`core/settlement_steps.py:1962-1970`；`core/game_state_econ.py:114`；`core/game_state.py:86`
- 证据：[确认] 代码 + 常量

```python
# game_state_econ.py:113-115（silver_in 按 万贯 ×10000 计入货币总量）
113  maritime = getattr(self, "maritime", {}) or {}
114  silver = maritime.get("silver_in", 0) * (1 if maritime.get("open") else 0) * 10000
```

```python
# settlement_steps.py:1964-1969（同一字段 1:1 转入以「贯」为单位的窖银）
1964      _silver = int(_mar.get("silver_in", 0)) if isinstance(_mar, dict) else 0
1966          _silver_share = int(_silver * HOARD_COPPER_RATIO_BASE / max(len(state.prefectures), 1))
1968          genty["窖银"] = genty.get("窖银", 0) + _silver_share
1969          _mar["silver_in"] = max(0, _mar["silver_in"] - _silver_share)
```

`game_state.py:86` 注释明确「窖银（贯）」，`content/data.py` 的 `silver_in` 调制区间为 [10,60] 且乘 10000 后进货币公式 → 单位应为万贯。另注：`_silver` 在循环内被重新读取（同一池被 20 路依次取用，实际总取出 ≈ `silver_in × (1-(1-r/N)^N)`），语义既非「每路一份」也未标注为比例池。
- 影响：市舶开启时，窖银账每单位只记 1 贯却让货币总量减少 10,000 贯（`calc_price_level` 口径），而动用出窖（`2046-2050`）又按 1 贯回流工匠/商人 wealth → 白银科目在「退出/回流」两端各错 10,000 倍。当前 `silver_in` 规模小（开局 30，且实测 `maritime.open=False` 全程未开），量级影响有限，但属明确量纲缺陷。
- 验证方式：代码对比 + `python probes.py`（打印 `maritime={'open': False, 'silver_in': 30}`）
- 建议修复：窖银改用万贯或统一换算系数；并明确 `silver_in` 是「月度流入量」还是「存量」，避免同一池被逐路重复取用。

---

### A-18 [P2] 田产/耕地 0.2%/月无上限复利，且 `land["cultivated"]` 无业务读取

- 位置：`core/settlement_steps.py:784`、`901`
- 证据：[确认] 实测

```python
784  state.land["cultivated"] += int(state.land["cultivated"] * 0.002)
...
901      p["grain"] = int(p["grain"] * 1.002)     # 每路年产月增 0.2%（复利）
```

`probes3.py`（O 段，120 次 `_settle_land_local`）：

```
Σp['grain']        707,301,250 → 898,939,313 (×1.271)
land['cultivated'] 460,000,000 → 587,349,265 (×1.277)
```

真实长局（77 月）`field_grain Δ = +91,289,612`（+12.9%）。全库 grep：`land["cultivated"]` 只在 `settlement_steps.py:536,541,781,784` 被**写入**，无任何计算/判据读取（仅经 `client_narrative` 作展示素材）。
- 影响：省级年产与「垦田」两条基線以 2.4%/年复利无限增长（30 年 ×2.05），且与耕地开垦、人口、隐田无联动；是粮价长期下行/税基虚增的隐性漂移源（被灾害减产部分抵消）。`cultivated` 字段成为只增不减的死科目。
- 验证方式：`python probes3.py`（O 段）；`python run_months.py 120`（field_grain 列）
- 建议修复：把月增绑定到实际开垦（`wasteland→cultivated` 流程）或加软上限；`cultivated` 若无消费者应删除以免误导。

---

### A-19 [P2] 外部/产出型入账无对方账户（商品外销 4,268 万贯/77 月等）

- 位置：`core/settlement_steps.py:1697-1714`（商品外销）；`2112-2113`（工程 `wine_coin_add`）
- 证据：[确认] 行级归因

```python
1707  _export = min(_stock - _cap, int(_month_prod * EXPORT_RATE))
1709      artisan["goods"][_gdim] = _stock - _export
1711      artisan["wealth"] += _income            # 外部买家付款（国内无对手账户）
```

行级归因（77 月，`run_line_trace.py _settle_granary all`）：

```
行 1711   Δ钱 = +42,680,417   artisan["wealth"] += _income
```

```python
2112  if "wine_coin_add" in out:
2113      state.imperial_treasury += int(out["wine_coin_add"])     # 同类：无对手方
```

- 影响：这是 `_settle_granary` 钱残差（77 月 +42,670,683）的**唯一来源**（其余行为 ±100 贯级 int 截断）。外销属设计内的外贸收入（注释「来源=外销，非凭空」），但：① 未建立外部部门账户，任何「Σ账户=0」的对账断言都必须为它开例外；② 该入账位于仓廪步（`_settle_granary`）而非外交/市舶步，语义位置错误；③ 单价 `GOODS_PRICE={"布":1,"绸":3}`（贯/单位）与 `月产=工匠size×0.2` 的组合使外销月入约 55 万贯，与市舶（未开启时 0）不联动。`wine_coin_add` 则完全无内容产出方（同 A-8 的可达性）。
- 验证方式：`python run_line_trace.py _settle_granary all`；`python run_detail.py 24`
- 建议修复：建立显式「外部部门」科目（如 `external_account`）承接外贸/岁币/市舶，使守恒断言可写成 `Σ内部账户 Δ + Σ外部部门 Δ == 0`；并把外销移入外交/市舶步。

---

### A-20 [P2] 零碎口径与边界缺陷（合并条目）

- 位置与证据：[确认]
  1. **空 `factions` → IndexError**：`core/settlement_steps.py:671-673`

     ```python
     671  infs = [(name, f["influence"]) for name, f in state.factions.items()]
     673  if infs[0][1] - infs[-1][1] > 40:
     ```
     实测（`probes5.py` 末段）：`state.factions = {}` → `IndexError: list index out of range`，整月结算中断（`settle_local` 会回滚，但 `advance_and_settle` 的调用方只看到异常）。旧档/裁撤全部派系后可达。
  2. **两套人均口粮表**：粮市撮合用 `GRAIN_CONSUME_PER_CAPITA`（`settlement_steps.py:1739`，兵=1.5、官僚=1.8），士绅抛粮的买方池 `_buyer_pool` 用 `PER_CAPITA_MONTH_GRAIN`（`:1872`，一律 0.5）→ 兵/官僚的「缺口」被低估 3~3.6 倍、保底线口径不同，抛粮卖给的买方集合与真实缺粮集合不一致。
  3. **本色俸禄分发 int 截断损耗 & 统计串科**：`settlement_steps.py:1552-1567`，`int(soldier_grain*size/total)` 逐路截断使 Σ分发 ≤ `given`（差额无科目）；`state.granary_stats["military"] += given` 把官禄/吏禄一并记入军粮科目。
  4. **尾差买卖双方可越界**：`:1782`（卖方末位取 `_left`）与 `:1791`（买方末位取 `_left`）仅在权重归一/截断无损失时才是「不超盈余/不超可购」；卖方侧已被 A-7 放大到显著量级，买方侧越界量受 `can_buy + (n-1)` 约束属可忽略。
  5. **`_sell_to_buyers` 死变量**：`:1927-1928` 计算的 `copper` / `jiaozi_part` 未使用（卖方入账只用 `paid`），窖藏拆分语义已迁到 `_settle_civilian_hoard`，属遗留死码（不破坏守恒）。
  6. **`_settle_org_economy` net 直入国库**：`core/settlement.py:134-137`，`net>0` 时国库增收无对手方（实测 77 月 +3,003 贯，注释已声明为「既有多账审计设计」）；`net<0` 时经 `change_treasury` 的 `max(0,…)` 在国库为 0 时静默不生效。
- 影响：多为边界/口径类，单独量级小，但 1 会中断整月结算，2/3 使粮钱分发与统计对不上账。
- 验证方式：`python probes5.py`（空 factions）；`python probes.py`（C/F 段）；代码位置如上
- 建议修复：`infs` 前加空判；统一人均口粮口径（用 `GRAIN_CONSUME_PER_CAPITA` 单一权威源）；分发余数归末位或记入损耗科目；`granary_stats` 拆 `military/official/clerk` 三键。

---

## 已修项复核（历史修复是否真的在位）

| 历史修复 | 复核结果 | 证据 |
| --- | --- | --- |
| 农存粮安全垫（粮市卖方保留 1 个月口粮） | **在位但可被旁路** → 见 A-7 | `settlement_steps.py:1745-1747`（盈余扣 2×need）、`:1773`（权重保底绕过） |
| 起义史实时间闸（流民/太仓/米价/民怨 4 分支包在 `year>=1118`） | **在位** | `settlement_steps.py:2407` 包裹 2408-2429；宋江 `:2439`、花石纲 `:2431`、金 `:2446` |
| 农逃荒 0.01→0.002 且单路上限 5 万/月 | **在位** | `settlement_steps.py:1818` `_flee = min(int(pop["size"]*0.002), 50_000)` |
| 兵 `_famine` 不再重复惩罚 | **在位** | `settlement_steps.py:1813` `if pn != "兵": _famine = True` |
| 俸禄指数化守恒（发放用指数化后金额） | **在位** | `settlement_steps.py:2893-2897`（`_pay_index`）→ `:2937/:2939` 用 `army_pay/official_pay` |
| 人口总账 Step 10.5 每步对齐 ΣPOP+流民 | **在位** | `settlement.py:434-436`；`refugee_count` 为派生 property（`game_state.py:1197-1200`）——但 A-3/A-16 会污染该总额 |
| R2：熔铜池溢出分支补 `COPPER_RESOURCE_DIM` 导入 | **在位** | `settlement_steps.py:1150` 顶部导入，`1181-1191` 使用 |
| R2：市舶关税删除 `_settle_extensions` 重复入账 | **在位** | `settlement_steps.py:1023-1031` 仅分商人毛利，无 `treasury +=`；关税唯一入口 `_settle_finance:2808-2810/2829` |
| R2：破产两档线改 `deficit_depth()` 判据 | **在位** | `settlement.py:341,346`；`settlement_steps.py:3055` |
| 2026-09 诏令整军改 `_levy_men`（人守恒） | **在位** | `settlement_steps.py:562-588`；但工程路径未同步 → A-8 |

## 方法与限制

- 全部结论基于真实代码执行：`GameState('史实')` 逐月跑 `run_monthly_settlement`，配合三类仪器（均在 `_scratch/audit-2026/`，**不改 game 源文件**）：
  - `run_steps.py` / `run_detail.py` / `run_months.py`：逐步/分桶/长局的账户残差归因（monkeypatch 包装 Step 函数）
  - `run_line_trace.py`：`sys.settrace` 行级事件，把每个源码行造成的钱/粮净变化归因到具体行号
  - `probes*.py`：构造态定向复现（超卖、payraise、流民钳制、囤粮销毁、亏空=造钱、作坊、空 factions 等）
- 账户口径：钱 = ΣPOP wealth + 国库 + 内帑 + Σ地方府库 + 熔铜池 + 士绅窖银 + 大臣家产；粮 = ΣPOP grain + 太仓 + 内帑粮 + Σ州仓 storage + Σ常平仓 + Σ`p["grain"]`；人 = Σ六类 POP size + 流民（+ 隐户口×4 另列）。`jiaozi`/`silver_in`/铜料存量单列，不计入「货币守恒」基线。
- 关键实测基线：开局 钱=309,344,947 / 粮=1,001,641,038 / ΣPOP=80,750,000 / 隐户 2,000 万口；实跑 77 月后第 78 月触发 Step 0 终局（亏空 2,011.8 万 > 2,000 万）。
- 限制：① 未接真实 LLM（`_economy_ai` 等契约槽位为空），AI 档位调制路径（如 A-10 的 `price_stabilize`）用构造契约复现，未在完整 AI 回合中跑过；② `defense_add`、`wine_coin_add` 当前无内容产出方，相关条目为「代码路径可达、数据不可达」；③ 未审查 `estate_mechanic`/`focus_mechanic`/`legacy_mechanic`/`free_effect` 等被 Step 6.8-6.10 调用的外部模块（超出本次范围），但它们均在 `try/except` 内且实测无异常。
