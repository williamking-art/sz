# 物产空间价差与需求地域维度 · 融合设计（**尚未实施**，v4）

> 状态：**设计稿，零代码改动**（2026-10-21；v4＝第三轮换模型深审，修正 4 处硬错误 + 6 处设计缺口，见 §10）。
> 来源：明末 Demo MOD《物产新篇》v2.2.0 的商品模型（下称「源模型」）——实测 446 货 / 40 类 / 95 产地 / 2226 条一般物产行。
> 性质：**增补设计**，不替代、不复制既有权威文档。需求与设计仍以
> [`../../../docs/民间经济与营造市场统一设计.md`](../../../docs/民间经济与营造市场统一设计.md)、
> [`../../../docs/全商品州府级与统一市场流转_架构方案_2026-10-03.md`](../../../docs/全商品州府级与统一市场流转_架构方案_2026-10-03.md)、
> [`../../../docs/货币口径规范_M0M1M2.md`](../../../docs/货币口径规范_M0M1M2.md) 为准；
> 本专题只承载「源模型独有、宋祚尚缺」的那部分。
> 本文所有「现状」结论均带 `文件:行` 出处；所有「新机制」标 **【新增】**；所有「实测数字」为 2026-10-21 只读脚本实测。

---

## 0 · 一句话

源模型比宋祚多三层东西：**价格的产地维度**（产地价 → 销地择优）、**需求的地域维度**（入市率 / 地域嗜好 / 年度流行）、**物流的品类属性**（腐坏率 / 运重）。本设计只把这三层做成**只读乘子与纯函数**，挂到既有 `unified-civilian-market` 的下一步上，**不搬数据、不立新账本、不重写已有价格与成交框架**。

---

## 1 · Jev 裁定（2026-10-21，tokenrhythm/NeoHorse-Jev-4B）

| # | 问题 | 裁定 | 概率 |
|---|---|---|---|
| J1 | 第一批是否限定为「只增补价格空间维度与需求地域维度，不动 POP/库存/物流主链、不重写既有月涨跌框架」 | **是** | 0.968 |
| J2 | 落库位置 | **B＝新立专题 `specs/economy/produce-space-price/`** | 0.759（A 续写 unified 0.050 / C 只落 docs 0.192） |
| J3 | 是否直接把源模型的产地与年产量数据搬入宋祚 | **否** | 0.028（远低于阈值） |
| J4 | 品质/规模第一批做法 | **B＝只作产地属性乘子，不拆商品维** | 0.643（A 拆维 0.285 / C 不做 0.071） |

> 台账另存 `_dev_tools/handover/decisions/JEV-wuchan-fusion-2026-10-21.json`。
> J2 的 0.759 与 J4 的 0.643 均非压倒性，故「落库位置」与「品质是否拆维」同时列入 §7 待裁定，**不由 Jev 单独定案**。

---

## 2 · 现状对照（源模型 11 概念 × 宋祚现状）

| # | 源模型机制 | 宋祚现状（出处） | 判定 | 本文处置 |
|---|---|---|---|---|
| 1 | 产地价＝基准×规模折价×品质溢价 | 只有基准价 `MATERIAL_PRICE_BASE`（`content/data_constants.py:462-517`，60 键）+ 全国乘子 `price_level`（`core/game_state_econ.py:277`）；`_base_price(dim, state)` 对**已登记新材**另有解锁闸门（`core/market_price.py:56-78`） | 部分有 | **P-A** |
| 2 | 销地唯一市价＝全天下最贱货源到岸价 | 价按**路**唯一（`core/market_price.py:147-158`；同路多治所共用一个价，`:210-219`）；无多货源择优 | 关键缺 | **P-A** |
| 3 | 跳数稀缺系数（1.43→10.50，0–6 跳） | 距离度量**已有**：`route_path()` 多跳最短路返回 `hops`（治所图边数）与 `days`（`core/transport.py:203-269`）；但**不进价格**。⚠️ **两个度量都不能直接对应源模型**：`days` 因 `KM_PER_MONTH=2400`（`:52`，设定值）在国内恒为 1；`hops` 实测 1–11（见下） | 有料未用，且需重标定 | **P-A**（重标定，非移植） |
| 4 | 品类运值比 | 运费按**距离×方式×货值**（`core/transport.py:918-932`）；载具规格按 `load`（石）（`data_constants.py:1534-1570`）；无按品类的重量/体积/价值密度 | 没有 | **P-C** |
| 5 | 品质市场倍率 | 全库无「品质」（grep 仅文案 `codex_text.py:128`） | 没有 | **P-A**（属性乘子，不拆维） |
| 6 | 富裕系数（生活标准弹性） | `demand_release` 温饱线+尺度（`data_constants.py:925-937`；`domains/economy/demand.py:39-56`）+ 结算侧 `elastic=clamp(人均wealth/5,1,3)`（`settlement_granary.py:422`）；无按品类弹性 | 部分有 | **P-B** |
| 7 | 档位压制 0.85 / 批发地板 | 无；`TIER_RANGE` 7 档只用于 AI 效果换算（`data_constants.py:962-970`） | 没有 | **P-A**（改为跨路单调断言） |
| 8 | 按品类腐坏率 / 运重系数 | 在途**只有粮**扣口粮（`foundation/ledger/spatial_warehouse_bridge.py:322-327`），并乘度量衡折减（`:312-316`）；另有海损 0.05（`trade_shadow.py:54`）、囤粮 0.03（`data_constants.py:685`）、POP 商品月折旧 5%（`settlement_granary.py:486,495`） | 部分有 | **P-C** |
| 9 | 需求＝人口×市售率 | 实现是 `wealth × GOODS_CONSUME_RATE × elastic × 景气 × release ÷ 本路价`（`settlement_granary.py:419-474`，**财富口径**）；且**只覆盖绸/布**（`GOODS_DEMAND` 仅此两维，`data_constants.py:760-767`；价格发现循环也只遍历绸/布，`settlement_granary.py:514-515`） | 部分有 | **P-B**（入市率作**供给侧**系数） |
| 10 | 嗜好 / 流行倍率 | 只有静态阶层偏好 `GOODS_DEMAND`（仅绸/布）+ 宏观景气 `BOOM_MULT`（`content/data.py:1297`） | 部分有 | **P-B** |
| 11 | 税种按「类目」声明所征货目（`*_CATS` → 货单自动推出） | 🔴 **宋祚没有按货/按类的税目**：工商税＝`Σ(工匠.size + 商人.size) × CRAFT_OUTPUT_PER_CAPITA × 税率`（`settlement_finance.py:1397-1402`），全库 grep `TAX_BY*` **0 命中**；盐课按销量（`state.calc_salt_coin`）、二税按田亩折算（`_settle_land_tax_color`） | **前提不存在** | **P-D 降级**：首批只做「应税产值分解」读数（**不改税制**）；真分征另立 **D8** |

### 2.1 三处必须先讲清的实测口径（影响引用与可实现性）

- **商品维数 62 维**（`GOODS_DIMS = RAW_DIMS 28 + FINISHED_DIMS 37 + 米/麦 2`，去重 5；`data_constants.py:520-525,543-551,574,677`）；既有文档另有 **22 / 21 / 15** 三种写法（既有文档冲突 C-5）。**本设计以代码现值为准**。
- **「类目」层尚不存在**：`GOODS_CLASSES` 只有 **食品 / 粮** 两个词条（`data_constants.py:629-658`，约 12 维），`COMMODITY_KINDS` 只有 **4 类**（粮/原料/成品/军需，`:582-603`）；源模型是 40 类 ⇒ P-B0 品目层 + D6。
- 🔴 **跳数实测（本专题自己测的，决定稀缺曲线怎么标）**：全图 **21 路 / 136 治所 / 210 个路对**；路级跳数（min over 两路治所对的 `route_path.hops`）分布——
  **min 1 / 中位 4 / 均值 4.62 / max 11**；`hops≤1` 占 17.6%、`≤4` 占 52.9%、`≤6` 占 74.3%、`≤10` 占 99.5%。
  ⇒ 源模型的 `1.43^hops`（0–6 跳、封顶 10.5×）**是为 23 大区图定标的**；直套到宋祚：`1.43^6=10.5×`、`1.43^11≈55×`。**必须按本图重标定并做扫描**（D4）。
- **产地证据覆盖率**：`content/seat_products.py:19-49` 的贡物→维映射为 **66 条贡物名 → 22 维**；即 62 维里只有 22 维有产地证据。其余 40 维 `spatial_target` 恒 `None` → 回落基准×压力（行为不变）。
- 🔴 **年产量数据只覆盖 9 维**（2026-10-21 实测）：治所 `demog["yields"]` 只有 **茶/丝/麻/蔗/果/木/石/铁/盐** 九个原料维（136 席全扫）；其余 **53 维**（含全部成品维：绸/布/纸/糖/肉/wine/铁锭…）**没有静态年产量源**——成品由作坊按月产出，无年度锚。⇒ P-D 的"覆盖 100% 有产地产量的维"应读作"覆盖这 9 维"；成品维需另找产出锚（如流量账累计 `stock_flow` 或作坊 yield 折算），**不在首批范围**。

---

## 3 · 融合原则（四条，违反即返工）

1. **口径单点**：新算法只落 `game/core/domains/economy/`，前端不复制（`sz/AGENTS.md` §3-2）；读数只走 `readout_hub.py` 注册（`扩展点与插件清单_2026-10-20.md:61,135-142`）。
2. **缺失 ≠ 0 ≠ 1.0**：任何缺数据路径返回 `None` + `reason`（`sz/AGENTS.md` §3-3；`unified-civilian-market/inventory-market.md:76`）。「未登记偏好」与「显式 1.0 无偏好」在契约上分开。
3. **不立平行账本**：本设计**不新增任何库存/钱载体**；产地属性、嗜好、入市率一律是**只读乘子**，价格仍写既有 `state.dynamic_prices`（`inventory-market.md:40`）。
4. **开工门五态**：每批须按「定义存在 / 已接线 / 账本闭合 / 长局校准 / 玩家可观察」核实，**禁止把"有代码"当"已落地"**（`unified-civilian-market/README.md:41`）。

---

## 4 · 五个融合点

### 4.1 P-A 空间价差（产地价 → 销地择优）

**【新增】表** `PROV_GOOD_ATTR`（`game/content/`，只读）：
```
{路: {维: {"规模": "大宗"|"中量"|None, "品质": "上"|"中"|"下"|None}}}
```
- 产地**存在性**沿用 `content/seat_products.py:19-49` 的贡物→维映射（66 条 → 22 维），守「只映射有明确对应的」「无证据州不归零」两条既有纪律。
- **品质/规模无史料则留 `None`**（不臆造）；有据者逐条登记依据档（照源模型的 `数据依据` 分级）。
- ⚠️ **不设「权重」字段**：v3 曾列 `权重`，但 `origin_price` 只用规模/品质、`spatial_target` 也不消费它——**死字段一律不写**。若将来要按产量份额择优，另立字段并说明用途。

**【新增】纯函数模块** `game/core/domains/economy/price_spatial.py`：

| 函数 | 语义 | 缺失语义 |
|---|---|---|
| `origin_price(dim, 路, *, base)` | `base × 规模折价 × 品质溢价`；属性 `None` → 退化为 `base` 并标 `basis="base"` | `base is None` → `None` |
| `route_hops(路A, 路B)` | 见下「21×21 预计算表」 | 不可达 → `None` |
| `spatial_target(dim, 路, *, base)` | `min over 可达产地 { origin_price × 路程因子 }`；`路程因子 = 稀缺系数(路级跳数) × 运值比(品目) × 该维稀缺溢价`；`跳数=0`（本路自产）= 本地零售加价 | 无产地 → `None` |

**【新增】21×21 路级跳数表（预计算，不是每次 min）**：
- 数据源：`prefecture_entity.seats_of(路)` 返回 **dict 列表** `[{seat, seat_id, circuit, level, lon, lat, blocked, basis, demog}]`（`prefecture_entity.py:146-165`），必须取 **`s["seat_id"]`** 才能喂给 `route_path`（其键集＝`_seat_index()` 的 `seat_id`，`transport.py:98-115,217`）。
- 算法：对每对路 `(A,B)`，`min` over `seatA × seatB` 的 `route_path(seatA_id, seatB_id)["hops"]`。
- **规模与代价**：21 路 / 136 治所 / 210 路对；最坏单对 9×9=81 次、全表约 **8.8k 次 `route_path`**（每次 Dijkstra 136 节点）。⇒ **启动时算一次、缓存 21×21 整表**，禁止在月度价格发现里现算。
- 失效条件：`transport._graph_cache_key()` 变更（治所拓扑/坐标改动）；表自检：对称、对角 0、不可达 `None`、与 `route_path` 抽样一致。
- ⚠️ **语义限制（必须写明）**：路级跳数＝**两路治所间的边数下限**，不是"路到路"的行政距离；大路（9 治所）与小路（4 治所）会因最近一对治所相邻而系统性**低估**距离。这是路级近似的固有偏差，**不得**表述为精确距离；后续若 D1 裁定下沉州府级，应改为治所对或按人口加权的路级距离。

**【新增】稀缺系数须按宋祚图重标定**（不是移植源模型表）：
- 源模型 `1.43^n`（n=0..6，封顶 10.5×）为 23 大区图；宋祚为 **hops 1–11、中位 4** 的治所图。
- 约束（供 D4 定标）：`hops=4`（中位）应落在 **1.3–1.6×**；`hops=11`（最远）应落在 **3–4×**；曲线单调、封顶。
- 定标方式：**扫描**（源模型正是「经扫描定标」，见其注释），验收＝最优路 ROI 与既有商路收益量级相容、且 `spatial_target` 不撞「放大上限」（断言 8）。
- **不得**把源模型的 1.43^n 直接抄进来——那会给出 55× 的价差。

**接入既有价格单点（不改语义）**：
- `discover_price` 是**纯函数**、内部 `_base_price(dim)`（无 `state`）取基准（`core/market_price.py:110-144`，`:120`）。⇒ 只增可选参数 `base_price: float|None = None`（缺省逐字走原路径），**不把 `state` 塞进纯函数**。
- 调用点 `settlement_granary.py:521` 传 `spatial_target(dim, 路, base=_base_price(dim, state))`；为 `None` → 退回 `_base_price(dim, state)`，`reason="spatial_undefined"`。
- **解锁闸门位置（v3 已修正，此处重申）**：`discover_price` 内部 `_base_price(dim)` 不带 `state` ⇒ **它本身从不执行解锁检查**（`market_price.py:61-62` 明写 `state is None` 时跳过 material_tech）。闸门实际由 caller 侧 `_base_price(dim, state)` 执行。断言 5 守之。
- 🔴 **两道闸的基准变了（v4 修正）**：`discover_price` 的绝对边界是 `min/max(base × PRICE_BOUNDS[0/1])`（`:141`），即**相对传入的 base**。若传入 `spatial_target`，则 `[0.5, 2.0]` 变成「相对空间价」而非「相对全国基准价」——空间价本身可以是基准价的数倍，两道闸就拦不住总量级。⇒ 必须**另加一道以全国基准价为锚的放大上限**（断言 8：`spatial_target ≤ MAX_SPATIAL_RATIO × base`，建议 4×，由 D4 扫描定），否则长程珍品会脱离控制。
- 月涨跌封顶 `cap_monthly_price`（`DEFAULT_MONTHLY_CAP=0.15`，`:53`）与四态优先级（official > dynamic > base > none，`:306-316`）不动。
- **覆盖面（当前真实限制）**：价格发现循环只遍历 `GOODS_DEMAND["农"] | ["士绅"]` 的键（= 绸/布，`settlement_granary.py:514-515`）。⇒ 首批**明示只覆盖绸/布**；且产地证据另有上限（22/62 维）。扩面依赖 P-B0/D7，**不在 P-A 内偷偷扩**。
- 治所级读价：`effective_buy_price(*, dim, state, gov_price, pref, use_dynamic)`（`market_price.py:299-321`）**增可选 `seat`**；新增优先序必须写明：**official > 治所动态价 > 路动态价 > base > none**，缺省（不传 seat）逐字不变。底层已有 `seat_good_key` / `_lookup_seat_price` / `discover_seat_price`（`:226,238,279`）。
- 本地/跨路倒挂：源模型用 `TIER_CAP=0.85` 治档位倒挂；宋祚无品质维 ⇒ 改为 **跨路单调断言**（断言 4，`min` 结构天然保证）。

### 4.2 P-B 需求地域维度（品目层 → 入市率 / 嗜好 / 流行）

#### P-B0 · 品目层（**无品目层则 P-B1/P-C/P-D 不成立**）

**【新增】表** `GOODS_CATEGORY`（`game/content/`）：`{维: 品目名}`，62 维 100% 覆盖，品目建议 12–20 个。
- 与 `COMMODITY_KINDS`（4 类）**并存不替代**：`kind` 管「能否入粮仓/是否军需」，品目管「需求口味与应税分解」。
- 自检：① 每维恰属一品目；② 品目非空。
- 🔴 **运行时新增维必须同步校验**：`GOODS_DIMS` 可经 `register_raw_material` / `register_finished_good` 在运行时扩维（`data_constants.py:716-755`），"启动自检"管不到新维。⇒ 在这两个注册函数内校验品目登记：**缺失则拒绝注册或登记为「未分类」并 `logging.warning`**（不得静默）。
- 依据：《宋史·食货志》与既有 `docs/州府特产与产业链商品目录设计_2026-10-05.md` 的分类；**不照搬源模型 40 类**（断代不同）。

#### P-B1 · 三张只读表 + 一个份额单点

| 表/函数 | 语义 | 键空间 | 缺失语义 |
|---|---|---|---|
| `MARKET_RATE_BY_CATEGORY` | **入市率**：产量中进市场流通的比例 | 品目 | 见下「None 语义待裁（D5）」 |
| `TASTE_BY_ROUTE` | 地域嗜好，三档 ×3.0/×2.0/×1.5 | 路 × 品目 | 未登记 → `None`（读数 `undefined`）；显式 `1.0` = 无偏好 |
| `fad_mult(seed, year, 路, 维)`（纯函数，不落表） | 年度流行：每路 3–5 件 ×1.10/1.25/1.50 | — | 不流行 → 1.0 |
| `preference.effective_shares(cls, 路, year)` | `GOODS_DEMAND[cls] × 嗜好 × 流行`，**归一化到 Σ=1** | 维 | 某维任一乘子缺失 → 该维不参与分配并记 `undefined`；**全部 undefined → 返回空 dict + `reason='all_undefined'`**（避免 0/0） |

- **接入点**：**不是** `demand.py`（其 `pref` 只迭代取键、份额未用，`demand.py:139,147`）。真正按份额分配在 `settlement_granary.py:440-448`（`_want_qty = want_spend × share ÷ 价`）。`demand.py` **不动**。
- **归一化是硬约束**：乘完倍率必须归一，否则 `want_spend` 被放大/缩小 ⇒ 凭空创造或消灭购买力（违 `ΔMoney ≡ 0`）。现有 `GOODS_DEMAND` 六阶层份额各自已和为 1（`data_constants.py:760-767`），归一化对现状是恒等变换。
- 🔴 **入市率 `None` 的语义待裁（D5）**：v3 写「`None` → 该维不可售」，这会让**表未填满时整个维从市场消失**（行为剧变）。两个候选取一：
  - **甲（保守）**：`None` → 不折算（等价 1.0）但**显式标 `undefined` 且读数可见**；
  - **乙（严格）**：`None` → 该维不可售（须先保证 62 维全填，否则不可用）。
  首期建议 **甲**，并把「未登记」与「登记为 1.0」在读数上分开。
- `fad_mult` 纯函数（源模型 `wuchan_fad` 即「年份的纯函数、不落盘、幂等」），对齐宋祚「同 seed 可复盘」（`游戏机制说明.md:177-178`）与「月度撮合只读冻结意向」（`民间经济…:799`）。排除货币、盐、粮。
- **入市率落点在供给侧**：`可售 = 产量 × 入市率`；落点＝`supply_goods_to_seats`（或等价入口）产出侧。**不得**与 `GOODS_CONSUME_RATE`（财富消费率，`content/data.py:1292`）混用。
- **前置（D7）**：需求篮子只有绸/布（`data_constants.py:760-767`；`BASIC_NEED_BASKET` 布 0.20 / 绸 `None`，`:948-951`）。不扩篮子，嗜好/流行**只对绸/布生效**，无法覆盖全 62 维。
- **粒度**：地域维度一律取**路**；禁止加「州府」字段假装已支持（`unified-civilian-market/tasks.md:621-623`）。

### 4.3 P-C 品类物流属性（腐坏率 / 运重）

**【新增】两表**（按品目，逐维可覆盖）：`SPOILAGE_BY_CATEGORY`、`FREIGHT_DENSITY_BY_CATEGORY`。

- **接入 1（在途腐坏）**：`foundation/ledger/spatial_warehouse_bridge.py::advance_in_transit_batches`（`:306-349`）现**只对 `goods_dim == "grain"`** 扣民夫口粮（`:322-327`），乘 M324 折减 `_loss_mult`（`:312-316`）。
  - 粮：**保持口粮模型不变**（避免双重扣减）。
  - 非粮：`spoilage = gross_amount × (1 − (1 − r)^(elapsed/30))`，**复利**，同样乘 `_loss_mult`。
  - 🔴 三处必须写清（v4 补）：① **`b["gross_amount"]` 同步扣减**（不止写 `spoilage` 字段）；② `elapsed` 是**天**（`min(days, remaining_days)`），须 `/30` 转月；③ 断言需要**初始量**，但批次只有会被就地改写的 `gross_amount` ⇒ **在 `dispatch` 时记 `gross_initial`**（或在断言里取登记值），否则恒等式无从核对。
  - 断言：`net_delivered + rations_consumed + spoilage ≡ gross_initial`（逐批逐维；粮 `spoilage ≡ 0`）。
  - 为何复利：源模型明确「每月复利减量」；线性在 >6 月会高估损耗。粮用线性是因为口粮＝人×日耗×天数，物理即线性。
- **接入 2（运力占用）**：运重系数作用于载具规格的 `load`（石）（`TRANSPORT_CARRIERS` `data_constants.py:1534-1570`；载具数 `CARRIAGE_INITIAL` `:1594-1598`；运具↔载重 `CARRIAGE_CARRIER_MAP` `:1608-1613`），**不改费率**（运费按货值比例：陆 2%/水 0.5%/海 0.3%/驿 5%，`transport.py:918-932`）。
- 腐坏率/运重缺失 → `None`：**不扣、不改运力**，读数标 `undefined`，不得当 0 损耗静默通过。

### 4.4 P-D 应税产值分解（**v4 降级：不改税制**）

> 🔴 **v3 的前提是错的**。§2 行 11 的「税目与货绑定」描述的是**源模型**，不是宋祚：宋祚工商税是「`Σ(工匠+商人)人数 × 人均产出 × 税率`」一个总数（`settlement_finance.py:1397-1402`），全库 `TAX_BY*` 0 命中；盐课按销量、二税按田亩。**不存在"新增维漏征"这回事**，也就没有可挂的"税目表"。

- **首批（低风险）**：只做**只读的应税产值分解**——按品目聚合「产量 × 产地价」（复用 P-A `origin_price` 与 `wuchan_scale` 口径），供面板展示、为将来分征提供依据。**不写 `tax_breakdown`、不改 `monthly_tax`、不动 M0 对账**。
- **真分征（D8，另裁）**：若要按品目分征，必须先回答——新税种与现有 `commerce_tax` 是**替代**（要改 `:1402` 的聚合口径与 POP 税负分配 `:1435-1436`，涉 M0/M1 对账）还是**叠加**（凭空增加税负，需守恒说明）？税基＝产量×产地价 还是 成交额（后者与 `sellable_stock` 相关）？由谁纳？——这些都超出"补一条绑定表"，单列 **D8**。
- **加价只落卖价侧**：乘子只作用于卖价，`MATERIAL_PRICE_BASE` 保持只读（用例 `test_b2r41_material_market.py:533` 已断言成交不改基准表）。

**✅ 首批已落地（2026-10-21，甲方案）**

| 产物 | 位置 | 状态 |
|---|---|---|
| 品目表（P-B0） | `game/content/goods_category.py`（21 品目 / 62 维 100% 覆盖；`validate()`；`note_new_dim()` 钩子已接 `register_raw_material`/`register_finished_good`） | ✅ 落地并有用例 |
| 只读分解（P-D 首批） | `game/core/domains/economy/tax_base_readout.py`（`survey_tax_base` / `readout_tax_base`） | ✅ 落地并有用例 |
| 读数 | `readout_hub` 第 28 项 `tax_base_value`（`READOUTS` **27 → 28**，两处棘轮用例已同步） | ✅ 落地 |

**实测口径（开局 `commands.new_game()`）**：应税产值合计 **7,607.9 万贯/年**；按品目：盐 5,553.0 万、茶 786.0 万、丝织 516.0 万、金属 310.0 万、糖果 224.6 万、木材 106.5 万、布帛 82.0 万、石料 29.9 万；**可定价维 9 / 有产量维 9 / 无产量源 53**。

🔴 **首批踩到的两个口径坑（已修，写在这里防复发）**：
1. **`MATERIAL_PRICE_BASE` 的单位是「文」不是「贯」**（其注释自陈「钱/单位」；`data_constants.py:805` 亦自陈「0.327 贯（327 文）」）⇒ 照贯显示会**大 1000 倍**（首版实测 7.6e10 被当成贯）。现统一 `WEN_PER_GUAN=1000` 折算，并加量级护栏断言（`1e4 < total_value < 1e9`）。
2. **"无年产量源" ≠ "年产 0"**：53 维必须进 `no_yield_dims` 并在读数里可见，**不得**把缺失当 0 计入产值（否则应税产值被系统性低估，且掩盖"成品无年度锚"这个真缺口）。

---

## 5 · 与既有主线的接口与顺序

| 依赖 | 说明 | 出处 |
|---|---|---|
| **D1** 载体 | `goods[治所]` 桶 vs `seats.warehouses` 四仓位并存，运行态「州府桶 0 个」。**不阻塞价格层**，阻塞"产地决定初始落桶" | 全商品方案 `:43`；底层经济闭环 `:24`；`B2c…:37` |
| **D2** 粮载体 | 甲/乙/丙（G-3）——走甲则米/麦进空间价差，走乙/丙则粮独立口径 | 全商品方案 `:67-85` |
| **D4** 稀缺定标 | 稀缺曲线须按宋祚 21 路图**重标定+扫描**（hops 1–11、中位 4），并定 `MAX_SPATIAL_RATIO` | 本文 §2.1 实测 |
| **D5** 入市率语义 | `None` → 不折算（甲）/ 不可售（乙） | 本文 §4.2 |
| **D6** 品目层 | 划分与键空间（现有词条仅 2、kind 仅 4） | 本文 §4.2 |
| **D7** 需求篮子 | 现在只有绸/布；不扩则嗜好/流行只对绸/布生效 | `data_constants.py:760-767,948-951` |
| **D8** 税目分征 | 真按品目征税=改税基与对账，另裁 | 本文 §4.4；`settlement_finance.py:1397-1402` |
| 已具备 | `route_path` 多跳（`transport.py:203-269`）；`seats_of`（`prefecture_entity.py:163-165`）；在途批次（`spatial_warehouse_bridge.py:306-349`）；路级动态价与四态（`market_price.py:110-144,299-321`） | — |
| 可并行 | P-A 与 M41（P1 切片＝绸）、M42（逐维流量账）并行；**不得改 `trade_goods` 语义**（`market.py:220`） | `inventory-market.md:36` |
| 顺序 | **P-A（可先行，只绸/布）→ P-B0 →（P-B1、P-C、P-D 读数）**；P-D 真分征需 D8 | 本文 |
| 独立回滚 | 每批：新表 + 新纯函数 + 一处接入开关（默认**关**）；关闭后逐字回到现行为 | — |

---

## 6 · 验收断言（每批必测）

**P-A**
1. 同维同路只有一个价（`pref_good_key` 语义不变）。
2. `spatial_target` 无产地 → `None`；**最终价**回落 `base × pressure` 且 `reason="spatial_undefined"`（不是 0、不是崩溃）。
3. **三道闸**：月涨跌 ≤15%（相对上期价）、价 ∈ `[0.5, 2.0] × 所用 base`、**放大上限** `spatial_target ≤ MAX_SPATIAL_RATIO × 全国基准价`（断言 8 的锚）；四态优先级不变。
4. **跨路单调**：A、B 到**同一产地**的跳数 A ≤ B 且 `pressure`/`prev_price` 相同时，`spatial_target(A) ≤ spatial_target(B)`；允许最终成交价因供需违反此序。
5. **解锁闸门不被绕过**：已登记未解锁新材 `_base_price(dim, state) is None` → `spatial_target` 为 `None` → 不可定价。
6. 接入前后 `stock_flow` 逐维残差恒 0、`money_audit.cum_residual` 不变。
7. **覆盖面声明**：首批只覆盖绸/布（且产地证据仅 22/62 维）；未覆盖维价格路径逐字不变。
8. **放大上限**：任何 `(维, 路)` 的 `spatial_target / 全国基准价 ≤ MAX_SPATIAL_RATIO`（建议 4，D4 定标）；超限即截断并标 `capped=true`。
9. **21×21 跳数表自检**：对称、对角 0、不可达 `None`、与 `route_path` 抽样一致；表在启动时算一次（不得在月度价格发现里现算）。

**P-B0**
10. 品目覆盖 100%（每维恰属一品目）；运行时 `register_*` 新增维若未登记品目 → **告警**（不静默；不拒绝，避免打断 AI 建新货通道）。——**✅ 已过**：`test_goods_category_p_b0.py`（覆盖精确/空品目/未知维/钩子告警）

**P-B1**
11. 归一化：`Σ effective_shares == 1`（±1e-9）；份额 0 → 该维不成交；全 undefined → 空 dict 不分配。
12. 嗜好/流行只**抬**不**造**：期望需求为 0 时仍为 0。
13. 同 seed + 同年 + 同路 → `fad_mult` 逐位一致（可复盘）。
14. 入市率缺失按 D5 裁定的语义执行，且**读数标 `undefined`**（不得静默当 1.0/0）。

**P-C**
15. `net_delivered + rations_consumed + spoilage ≡ gross_initial`（逐批逐维；粮 `spoilage=0`；`gross_initial` 在 dispatch 时登记）。
16. 运重只改载具 `load` 占用，不改费率。

**P-D**
17. 应税产值分解是**只读**：跑完后 `state.tax_breakdown`、`monthly_tax`、`money_audit` 逐字不变。——**✅ 已过**（另锁 `prefectures[*].seats`/`resources`/`treasury`/`statistics`）
18. 分解覆盖「**有年产量源**」的维（实测 9 维），其余 53 维进 `no_yield_dims`（**无年度锚 ≠ 年产 0**）；有产量无价者进 `undefined_dims`，均不记 0。——**✅ 已过**；单位口径另有护栏（文→贯 ÷1000，量级断言）

---

## 7 · 待裁定（走 `_dev_tools/handover/decisions/`）

| ID | 待裁项 | 为何要裁 | 阻塞 |
|---|---|---|---|
| D1 | 商品/库存真账载体：`goods[治所]` 桶 vs `seats.warehouses` | 两份文档两个载体，运行态「州府桶 0 个」 | P-A 落桶细节 |
| D2 | 粮载体甲/乙/丙（G-3） | 条文/待裁方案/用户口径/运行态四者并存 | P-A（米/麦） |
| D3 | 品质/规模是否升级为**拆维**（Jev 已判不拆 0.643；用户可重议） | 拆维乘 62 维，波及库存/成交/守恒/品目/存档迁移 | P-A 上限（当前按不拆） |
| D4 | **稀缺曲线重标定** + `MAX_SPATIAL_RATIO`（宋祚图 hops 1–11、中位 4；不得套 1.43^n） | 直套源模型表会给出 55× 价差 | ✅ **取证已出**：[`D4_稀缺曲线取证_2026-10-21.md`](D4_稀缺曲线取证_2026-10-21.md)——成本可解释上限仅 **1.063（1 跳）→ 1.091（11 跳）**，`1.43^n` 在 4 跳超额 **+3.11**、11 跳 **+50.0**；三选项 A（去掉距离稀缺，收缩为可达性+选源）／B（成本级 ≤1.15）／C（移植+供给约束，不建议）**待裁** |
| D5 | 入市率 `None` 语义：甲（不折算+undefined）/ 乙（不可售） | 乙在表未填满时会让商品从市场消失 | P-B1 开工门 |
| D6 | 品目层划分与键空间 | 现有词条仅 2、kind 仅 4，源模型 40 | **已按 21 品目落地**（P-B0）；划分仍可调，改 `goods_category.py` 一处即可 |
| D7 | 需求篮子扩容（现仅绸/布） | 不扩则嗜好/流行只对绸/布生效 | P-B1 开工门 |
| D8 | 是否真按品目分征（替代 or 叠加现有 `commerce_tax`；税基口径；谁纳） | 现税制无按货税目，真分征＝改税基与 M0 对账 | P-D 第二阶段 |

---

## 8 · 风险与回滚

| 风险 | 事实依据 | 处置 |
|---|---|---|
| **价格三源并存** | `货币口径:166`、`inventory-market.md:38`、全商品方案 `:95` | 空间价只作 `discover_price` 的 target 来源；四态优先级与宏观指数角色不变 |
| **稀缺曲线移植即失真** | 实测 hops 1–11 / 中位 4；源模型 0–6 跳封顶 10.5× | 必须重标定+扫描（D4）；断言 8 设放大上限兜底 |
| **两道闸的锚被偷换** | `discover_price` 的 `PRICE_BOUNDS` 相对传入 base（`market_price.py:141`） | 断言 3、8：另设以全国基准价为锚的放大上限 |
| **注册表拼错=静默失效** | `扩展点与插件清单:64` E5 | 启动自检 + `register_*` 钩子校验（断言 10） |
| **史料感数字被当成史料** | 宋祚「不臆造」 | 稀缺/入市率/嗜好逐条标依据档；无据标「设定值/推算」 |
| **路级跳数是近似** | 大路小路混用会低估距离 | 文档显式声明；D1 下沉后改治所级 |
| **归一化丢失→凭空创造购买力** | 份额放大 `want_spend` | 断言 11；`effective_shares` 唯一出口 |
| **不动守恒** | 2026-10-20 镜像直写致 12 个月 +13,470,432 贯 | 零新增写点；需要写点时先过 D1 + 桥接 + 守恒断言 |
| 回滚 | — | 每批开关默认关；新表可整表删除；无存档迁移 |

---

## 9 · 落库与回写

| 动作 | 目标 |
|---|---|
| 新规格状态表 | 本目录 `tasks.md`（P-A / P-B0 / P-B1 / P-C / P-D 全 ⬜） |
| 域索引 | [`../README.md`](../README.md) 子专题表 |
| 机制口径（实施后） | 经济 → `docs/货币口径规范_M0M1M2.md`；机制 → `docs/游戏机制说明.md` |
| 模块行为（实施后） | `game/core/README.md`、`game/content/README.md` |
| 结算步（若新增） | `core/settlement_pipeline.py` 注册 + 同步三处（`test_pop_identity._STEPS` / `core/README` / 机制文档） |
| 测试规模 | `_dev_tools/game-dev/tests/README.md`（不写死用例数） |
| 交接 | `_dev_tools/handover.py`：worklog + phase + decisions（D1–D8） |

---

## 10 · 修订记录

### v1 → v2（首轮自查，8 处）

| # | 问题 | 修正 |
|---|---|---|
| 1 | 要新建 `ROUTE_HOPS` 表 | 跳数已存在（`route_path.hops`），改为复用 |
| 2 | 空间价塞进 `discover_price` 带 `state` | 只加可选 `base_price`，caller 传 `_base_price(dim, state)` |
| 3 | 以为覆盖全维 | 价格发现实际只遍历绸/布 |
| 4 | P-B 接入 `demand.py` 的 `pref` | `pref` 份额未使用；实际在 `settlement_granary:440-448` |
| 5 | 假设类目键空间存在 | 仅食品/粮两词条 + 4 kind ⇒ 新增 P-B0 |
| 6 | P-C 落点写错 | 实际在 `spatial_warehouse_bridge.advance_in_transit_batches`，粮走口粮 |
| 7 | 载具引用行号错 | 改 `TRANSPORT_CARRIERS:1534-1570` 等 |
| 8 | 断言缺绝对边界 | 补 `PRICE_BOUNDS` 与覆盖面断言 |

### v2 → v3（第二轮换模型复审，10 处）

| # | 问题 | 修正 |
|---|---|---|
| 9 | 称"解锁闸门必须保留"，实则 `discover_price` 内部从未有闸门 | 明确闸门在 caller 侧 `_base_price(dim, state)` |
| 10 | 非粮腐坏用线性，与源模型复利不一致 | 改复利 |
| 11 | `route_hops` 未说明如何拿治所 | 补 `seats_of` |
| 12 | `effective_shares` 未覆盖全 undefined | 补空 dict + reason |
| 13 | D7 表述"无处生效"过度 | 改"只对绸/布生效" |
| 14 | 断言 4 缺前提 | 补 pressure/prev_price 相同 |
| 15 | D3 状态模糊 | 标 Jev 已判不拆、可重议 |
| 16 | 性能未讨论 | 补缓存策略 |
| 17 | 入市率落点未指定 | 指 `supply_goods_to_seats` |
| 18 | 税目结构未引用 | 补"实施时核验" |

### v3 → v4（第三轮换模型深审，4 硬错误 + 6 缺口）

| # | 问题（含实测） | 修正 |
|---|---|---|
| 19 | 🔴 **P-D 前提错误**：宋祚没有按货/按类税目（工商税＝人数×人均产出×税率，`settlement_finance.py:1397-1402`；`TAX_BY*` 0 命中） | P-D 降级为**只读应税产值分解**；真分征另立 **D8** |
| 20 | 🔴 **稀缺系数不可移植**：实测 21 路/136 治所/210 路对，hops 1–11、中位 4、均值 4.62；源模型 `1.43^n` 为 23 大区 0–6 跳定标，直套得 55× | 改为**按宋祚图重标定+扫描**（D4），并新增 `MAX_SPATIAL_RATIO` 放大上限（断言 8） |
| 21 | 🔴 **`seats_of` 返回 dict 列表不是 id** | 明确取 `s["seat_id"]` 再喂 `route_path` |
| 22 | 🔴 **性能**：全表约 8.8k 次 Dijkstra，若在月度价格发现里现算会拖死 | 改为**启动时预计算 21×21 整表**并缓存（断言 9） |
| 23 | 两道闸的锚被偷换（`PRICE_BOUNDS` 相对传入 base） | 断言 3 写明、断言 8 另设全国基准价锚 |
| 24 | `effective_buy_price` 加 `seat` 后优先序未定义 | 明确 official > 治所动态 > 路动态 > base > none |
| 25 | P-C 复利缺三处（gross 未扣、天/月未转、无 `gross_initial`） | 三处补齐，断言 15 重写 |
| 26 | P-B0 覆盖自检管不到运行时注册的新维 | `register_raw_material`/`register_finished_good` 内校验（断言 10） |
| 27 | 入市率 `None`→"不可售"语义过重 | 改列 D5 甲乙两案，首期建议甲（不折算+undefined） |
| 28 | `PROV_GOOD_ATTR.权重` 是死字段（公式从不消费） | 删除，并写明"死字段一律不写" |

---

### 实施记录（2026-10-21 · P-B0 + P-D 首批）

| 项 | 结果 |
|---|---|
| 新增文件 | `game/content/goods_category.py`（21 品目 / 62 维）；`game/core/domains/economy/tax_base_readout.py` |
| 修改文件 | `game/content/data_constants.py`（`DIM_REGISTERED_HOOKS` + `_notify_dim_registered`，**反向注册避免成环**）；`game/core/domains/economy/readout_hub.py`（第 28 项）；3 处读数棘轮 27→28 |
| 用例 | `test_goods_category_p_b0.py`（6 例）、`test_tax_base_readout_p_d.py`（6 例）；定向 25 例全绿 |
| 实测 | 应税产值 7,607.9 万贯/年；9 维可定价、53 维无年产量源 |
| 踩坑（已修） | ① `data_constants ↔ goods_category` import 环（被 `test_no_new_cyclic_modules` 抓）→ 改钩子注册；② 三处读数棘轮 27→28；③ 朝代字面量棘轮（新文件须 **0** 处 `宋/路/州府/治所…`，已全部改中性措辞） |
| 非我引入的红 | `game/core/ai/tiandao_facts.py`（21:45 建）、`tiandao_decision.py`（21:50 改）由**并发会话**写入，触发朝代/库存写点两条棘轮；本批**未改**这两文件 |


---

最后更新：2026-10-21（**P-B0 + P-D 首批已落地**；P-A / P-B1 / P-C 未开工；D8 真分征未启）
