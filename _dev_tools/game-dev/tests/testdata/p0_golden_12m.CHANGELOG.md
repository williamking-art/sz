# golden 12 月基线变更说明

> `p0_golden_12m.json` 是 `test_p0_golden_replay.py` 的**行为快照基线**：
> 同种子 `new_game("史实")` + 12 个月结算后的关键读数。该测试的语义是
> 「**行为变化必须显式更新基线并说明原因**」——基线变动本身不是回归，但必须留痕。
> 每次重建基线，在本文件末尾追加一条。

---

## 2026-10-21 · 天道层 L0/L1/L2 加强（本批主动行为变更）

**裁定**：Jev `choose` 三选一 —— A=按新口径重建并注明原因 **0.9974** / B=只比对未受影响字段 0.0020 /
C=回滚本批 0.0006。记录见 `_dev_tools/handover/decisions/JEV-天道L1实现口径-2026-10-21.json`。

**为什么必须变**：本批有意改变天道裁决的**输入供给**与**公式口径**，其中 5 项裁决有生产消费方：

| 变更 | 旧口径（缺陷） | 新口径 |
|---|---|---|
| `disaster` 读数 | 读 `statistics["disaster_level"]`（全库无人写入）⇒ **恒 None**，6 条分支失去触发 | 读 `state.disaster_severity / 5`（0~5 灾级归一 0~1） |
| `integrity` 缺失 | 无贪腐读数时回落 **1.0（=吏治完美）**，违反「缺失≠1.0」 | `None`（fail-closed） |
| `stock`（常平闸门） | 传太仓 `granary` 15,000,000 | 常平仓合计 `changping_stock` 14,735,443 |
| `labor_policy` 阈值 | 绝对 `treasury >= 5000`，比真实路库低 2~3 个数量级 ⇒ `corvee` **死分支** | 可支撑月数 ≥3；无月支读数时退路库见底线 200,000（Jev A 0.742，理由见参数注释） |
| `reform_compliance` | `faction` 从不供给 ⇒ 党派加成恒 0；`diligence` 全库无生产者 | `faction` 取影响力最高派系（新党→`reform`），概率 0.505 → 0.805 |
| `score` 灾情分支 | 运算符优先级 bug：`disaster=None` 时 **unrest 被整个丢弃**（`score({unrest:160})`=上考 1.0） | 按可用项平均；两项皆缺 ⇒ `defined=False` |

**实测影响面（12 月，seed=20261021）**：

| 字段 | 新基线 | 旧基线 | Δ |
|---|---|---|---|
| `treasury` | 129,481 | 129,061 | **+420** |
| `imperial_treasury` | 5,481,338 | 5,497,479 | **−16,141** |
| `granary` | 4,073,668 | 4,073,668 | 0 |
| `finance.*` | — | — | 全部相同 |
| `routes[*]` | — | — | **20/20 全同** |
| 其余 8 个顶层字段 | — | — | 全同 |

即：影响集中在两处货币数字（量级 0.03% / 0.3%），人口、粮、路级账、财政四率均未变。
原因是 5 项裁决在新局下的 verdict 与旧一致（只有概率变化），故结算路径未分叉。

**顺带修复（零行为变更）**：`save_load.py:549` 与 `application/load_game.py` 各有一处
「错误分支引用未定义 logger」的潜伏 `NameError`（`_slog` / `_dlog`），正常路径不触发，
但一旦日历同步或任一下沉迁移失败就会**打断读档**（与注释承诺的"失败不拒档"相反）。

**重建命令**（本机已实测）：

```powershell
$py = "D:\codebuddy\.audit-venv\Scripts\python.exe"
cd D:\codebuddy\sz
$env:PYTHONPATH=""; $env:CODEBUDDY_SAFE_DELETE_ENABLED="0"
$env:P0_GOLDEN_WRITE="1"; & $py -m pytest _dev_tools/game-dev/tests/test_p0_golden_replay.py -q -p no:cacheprovider
Remove-Item Env:P0_GOLDEN_WRITE
```

---

## 2026-10-22 · 天道裁决接数值效果（L3：5 个门面首次影响玩法）

**裁定**：Jev `choose` —— 下一批优先 **A=接余 5 项门面的数值效果 0.7767** / B=重标 SEED_* 0.1490 /
C=标签数据源 0.0356 / D=外部 Jev 特化 0.0387。

**为什么必须变**：此前 11 个门面里只有 5 个有数值消费方；本批把余下 5 个接进结算：

| 裁决 | 接线位置 | 数值效果（上限/守恒） |
|---|---|---|
| `merchant_trade_or_hoard` | `settlement_econ._settle_civilian_hoard` | 囤抛力度 ×1.20/×0.90（钳位 0.85–1.25），成对买卖不变 |
| `gentry_charity_vs_annex` | `settlement_econ._settle_tiandao_land_relief` | 兼并 0.3%/月（自耕田→士绅田成对）或义庄赈济 2%/月（士绅囤粮→农户，成对） |
| `farmer_destitution_path` | 同上 + `settlement_granary` 饥荒段 | 典田入同一 0.3% 通道（双命中不叠加）；`flee_refugee` ⇒ 逃散 ×1.5（受 5 万人/路上限） |
| `canal_reroute_choice` | `settlement_granary` 漕运段 | 途耗 ×0.80（陆运，付 0.01 贯/石脚钱给商人）/ ×0.90（和籴 3%，地方府库出钱、民间粮食入太仓） |
| `recruit_refugees_to_soldiers_gate` | `settlement_granary._recruit_refugees_as_xiangjun` | True ⇒ 流民 2%/路/月（上限 2,000）入本路兵额；无实体军的路不扣人、不造单位 |

**实测影响面（12 月，seed=20261021）**：

| 字段 | 新基线 | 旧基线 | Δ |
|---|---|---|---|
| `army_troops` | 754,218 | 748,800 | **+5,418**（募流民入兵额） |
| `granary` | 4,070,617 | 4,073,668 | **−3,051** |
| `imperial_treasury` | 5,489,585 | 5,481,338 | **+8,247** |
| `treasury` | 129,148 | 129,481 | **−333** |
| `finance.*` / `routes[*]` | — | — | **全同**（财政四率与 20 路逐路账未变） |

**守恒核对（Lead 独立复核，6 个月）**：
- **中性档 ≡ 无记录 ≡ 改前**：`wait_dredge` + 募兵门 False 与「无 `_tiandao_observe`」逐字节相同（两侧各自实测 sha256）。
- 货币 M_ALL 残差：本批**中性** −3,006,634 vs **真实** −3,007,879 ⇒ 本批净贡献约 **−1,245**（残差主体是既有问题，非本批引入；两条跑法都存在）。
- 田产转移成对：京畿路 `self_farm −643,360` / `gentry_land +642,026`（差额 1,334 来自收获分粮与自然兼并的后续联动）。
- 兵额：6 个月后逐路 `兵.size == Σtroops`（0 违例）；人（ΣPOP + 流民）只在池间移动。

**注意：`self_farm+gentry+official+imperial == land` 不是本仓库的全局不变量**（初始 0/20 违例，
6 个月后中性档与真实档**都**是 20/20 违例，`land` 与 `hidden_land` 各自演化）——
别拿它当验收断言；正确的断言是「转移成对（Δself == −Δgentry）」。

**重建命令**：同上。

---

## 2026-10-22 · 接线改为**概率加权**（用户裁定：「这不都固定数？权重呢？」）

**背景**：上一条把 5 个门面接成数值效果时，只用了「argmax 档位 → 固定倍率表」，
引擎算出的概率与 choose 的整条分布被丢掉。用户当场指出这是"固定数"，
要求把天道裁决的**不定数（概率）**真正当权重用。
**Jev 复核**：命题「choose 类应取概率加权期望/混合，而非 argmax 后查表」**p=0.995 成立**。

**改法**：`observe_monthly` 记录 `strengths`（gate p）与 `distributions`（choose 分布）；
gate 用超阈强度 `(p−thr)/(1−thr)`；choose 用概率加权（商贾取概率差、田产取并集、
漕运取期望）；叠加确定性扰子 `jitter(回合,目标,地点)`（可复现，不是真随机）。

**实测影响面（12 月，seed=20261021）**：与固定表版相比

| 字段 | 概率加权版 | 固定表版 | Δ |
|---|---|---|---|
| `army_troops` | 751,780 | 748,800（接线前） | **+2,980**（固定表版曾 +5,418，概率版更收敛） |
| `granary` | 4,101,371 | 4,073,668（接线前） | **+27,703** |
| `imperial_treasury` | 5,534,703 | 5,481,338（接线前） | **+53,365** |
| `treasury` | 129,314 | 129,481（接线前） | **−167** |
| `finance.*` / `routes[*]` | — | — | **全同**（20 路逐路账未变） |

**踩坑留档（重要）**：观测副本里 `decisions` 按**门面方法名**存，而
`strengths`/`distributions` 按 **objective id** 存。消费方若只按一种写法 `dict.get`，
就会**静默读空、效果永不生效**——实测 `observe_strength("recruit_refugees_to_soldiers_gate")`
返回 None，导致全月零募兵、`army_troops` 恰好回到接线前的 748,800（差点被当成"概率版没生效"）。
现 `tiandao_effects._name_keys()` 双向解析；**新增消费方必须走 `tiandao_effects` 的读取函数**。

**重建命令**：同上。

---

## 2026-10-22 · 民怨动力学补齐 + 奏报阈值改相对锚（Jev B 0.757 / 财政判据 0.994）

**背景**：本要重标 `SEED_*` 四阈值，实测发现根因是**民怨不会动**——只会被治安支出
（按军费份额）单向抵减，`无实体军的 8 地永久冻结在初始值`（利州路/广南西路恒 24.0），
内容里 30/45/60/85 的档位全不可达。财政签「民怨>40 且 府库<5 万」两条件从不同时成立（死签）。

**改法**：民怨改为向**压力目标**月度缓动 10%（粮价/灾情/流民/治理合成，钳 0–100，
单月变化不跳变）；财政签改按「府库不足 0.1 月本地月税」触发、民怨只作严重度；
军事签改按「流民 > 本地人口 0.4%」。

**实测影响面（12 月，seed=20261021）**：

| 字段 | 本版 | 上版 | Δ |
|---|---|---|---|
| `army_troops` | 751,716 | 751,780 | **−64** |
| `granary` | 4,101,443 | 4,101,371 | **+72** |
| `imperial_treasury` | 5,534,711 | 5,534,703 | **+8** |
| `treasury` | 129,323 | 129,314 | **+9** |
| `finance.*` / `routes[*]` | — | — | **全同** |

🔴 **影响极小本身就是结论**：民怨此前几乎没有经济下游消费者，所以"让档位可达"不会体现在
这 4 个数字上——价值在 `situation_seeds`（>=30/85）与 `local_agent_decisions`
（>=30/45/60/85）那些**原本永远走不到的分支**。若要民怨真正影响账本，需另给它经济后果
（未做，登记在 `JEV-民怨动力学与奏报阈值-2026-10-22` 的 reopen_if）。

**重建命令**：同上。

---

## 2026-10-22 · 采购劳动政策改「优先读当月观测副本」（G1，Jev p=0.9915）

**背景**：core/domains/economy/procurement.py 原先在结算中**另行**用自建 state_ctx 调
EmbeddedDecisionFacade.labor_service_policy 重新裁决；而月结 Step 0 已把当月 labor_policy
裁决与概率写进 state._tiandao_observe 与 decision_log ⇒ 日志与结算可能不是同一个裁决
（与已修的 D-1 阈值双源同型）。

**改法**：labor_mode 改为**优先读观测副本**（	iandao_effects.observe_verdict），
无记录（首月/读旧档/未观察）才回落直调门面 —— 缺失语义与旧行为保持不变。

**实测影响面（12 月，seed=20261021）**：

| 字段 | 本版 | 上版 | Δ |
|---|---|---|---|
| imperial_treasury | 5,537,013 | 5,533,887 | **+3,126** |
| 	reasury | 129,335 | 129,380 | **−45** |
| rmy_troops | 751,728 | 751,716 | **+12** |
| granary | 4,101,439 | 4,101,443 | **−4** |
| inance.* / 
outes[*] | — | — | **全同** |

**重建命令**：同上。
