# 物产空间价差与需求地域维度 · 任务拆分与状态（v4）

> 上游设计：[`design.md`](design.md)（v4，含 §10 修订记录 v1→v2→v3→v4）· 目录说明：[`README.md`](README.md)
> **状态：P-B0 / P-D 半落地（⚠️ 定义存在＋测试 / 只读读数，无结算链生产调用方）· P-A 待 D4 裁定（⛔）· P-B1 / P-C 未开工（⬜）**——本文件只承载「怎么做、做到哪、怎么验收」；口径冲突时以 [`design.md`](design.md) 与 `../../../docs/` 权威文档为准并回改本文件。
> 用例数与基线一律不写死，以本次实跑输出为准。
>
> 🔴 **2026-10-22 五态复核（D-4 勘误）**：原文头「全部未开工」与同文件状态表 P-B0/P-D 的「✅ 首批落地」**自相矛盾**。
> 按本仓库五态（定义存在 / 已接线 / 账本闭合 / 长局校准 / 玩家可观察）逐项复核，**P-B0、P-D 都停在
> 「定义存在＋测试」**，故统一改判 **⚠️ 半落地/待接线**（不写 ✅ 全落地）；文头、§1 状态表、文末三处口径一致。
> 证据：P-B0 = `game/content/goods_category.py`（21 品目 / 62 维，`validate()` 零问题，`_register_hook()` 在
> import 时登记，`DIM_REGISTERED_HOOKS` 由 `content/data_constants.py:723-760` 的 `register_*` 消费；
> **启动自检在 production 未调用**，唯一 import 方是 P-D 只读路径 `core/domains/economy/tax_base_readout.py:99`）；
> P-D = `core/domains/economy/tax_base_readout.py::survey_tax_base`，唯一生产消费方是只读面板
> `core/domains/economy/readout_hub.py::READOUTS` 第 28 项 `tax_base_value`（`_tax_base_value`），
> **结算链零消费**（真分征待 D8）。

---

## 1 · 状态表

| 批 | 内容 | 状态 | 依赖 | 开工门产物 | 验收门 |
|---|---|---|---|---|---|
| **P-A** | 空间价差：`PROV_GOOD_ATTR` + `price_spatial.py`（`origin_price`/`route_hops`/`spatial_target`）+ **21×21 路级跳数表（启动预计算）** + `discover_price(base_price=)` + caller 改造 + `effective_buy_price(seat=)` | ⛔ **待 D4 裁定后重定范围** | **D1/D3/D4**；✅ 跳数矩阵与成本反推已取证（`D4_稀缺曲线取证_2026-10-21.md`） | 见 D4 三选项：若选 A，本批收缩为「可达性闸门 + 货源择优（到岸成本最低者）」；若选 B，另加成本级乘子（≤1.15） | design §6 断言 1–9（随裁定简化） |
| **P-B0** | 品目层：`GOODS_CATEGORY`（62 维 100% 覆盖）+ 启动自检 + **`register_*` 钩子校验** | ⚠️ **半落地/待接线**（2026-10-21 首批；2026-10-22 五态复核：**定义＋自检函数＋钩子＋测试有，无结算链生产调用方**，启动自检未在 production 调用；钩子仅在 `goods_category` 被 import 时登记，当前唯一 import 方是 P-D 只读路径） | **D6** 裁定（品目划分仍可调） | `game/content/goods_category.py`：21 品目 / 62 维；`validate()` 零问题；`note_new_dim()` 已接两个 `register_*`（`content/data_constants.py::_notify_dim_registered`） | 用例 6 例锁定覆盖/空品目/未知维/钩子告警（`test_goods_category_p_b0.py` ✅，**仅用例、不等于接线**） |
| **P-B1** | 入市率 + 地域嗜好 + 年度流行：`MARKET_RATE_BY_CATEGORY`、`TASTE_BY_ROUTE`、`fad_mult`、`preference.effective_shares` + `settlement_granary` 接入 | ⬜ | **D5/D7** 裁定；P-B0 ⚠️（定义已存，无结算链调用） | ① 三表/函数；② 归一化单点；③ 同 seed 复现用例；④ 入市率 `None` 语义（D5 裁定结论）；⑤ 需求篮子扩容说明 | design §6 断言 11–14 |
| **P-C** | 品类物流属性：`SPOILAGE_BY_CATEGORY`、`FREIGHT_DENSITY_BY_CATEGORY` + 非粮在途复利腐坏（含 `gross_initial`）+ 载具 `load` 占用 | ⬜ | P-B0 ⚠️（定义已存）；在途批次（已具备） | ① 两表；② 批次字段 `spoilage`/`gross_initial` 与 `stock_flow` 原因码；③ 三项守恒断言 | design §6 断言 15–16 |
| **P-D** | **应税产值分解（只读）**：按品目聚合「产量 × 基准价」，不动税制 | ⚠️ **半落地/待接线**（2026-10-21 首批；2026-10-22 五态复核：只读分解已接 `readout_hub` 第 28 项 `tax_base_value`，**结算链零消费**，真分征待 D8） | P-B0 ⚠️（定义已存）；**D8 未裁前禁止真分征** | `game/core/domains/economy/tax_base_readout.py` + 读数 `tax_base_value`（第 28 项）；文→贯折算 `WEN_PER_GUAN` | 用例 17/18 ✅（只读性：`prefectures/seats`、`resources`、`treasury`、`tax_breakdown`、`statistics` 逐字不变；53 维进 `no_yield_dims`，非 0 产；**仅用例、不等于接线**） |

**建议顺序**：P-A（可独立先行，只绸/布）→ P-B0 →（P-B1、P-C、P-D 读数并行）→ 真分征（待 D8）。
**禁止**：任何一批都不得改 `trade_goods` 语义（`core/domains/economy/market.py:220`，唯一成交入口）。

---

## 2 · 触点文件清单（动手前先核，避免撞车）

| 批 | 预计新增 | 预计修改（共享文件，须先 `handover.py log` 声明） |
|---|---|---|
| P-A | `game/core/domains/economy/price_spatial.py`、`game/content/prov_good_attr.py` | `game/core/market_price.py`（`discover_price` 加可选 `base_price`、`effective_buy_price` 加 `seat`）、`game/core/settlement_granary.py:521`（caller） |
| P-B0 | `game/content/goods_category.py` | `game/content/data_constants.py`（`register_raw_material`/`register_finished_good` 加品目校验）、`game/content/README.md`（索引表） |
| P-B1 | `game/core/domains/economy/preference.py`、`game/content/{market_rate,taste,fad}*.py` | `game/core/settlement_granary.py:440-448`（份额分配） |
| P-C | `game/content/spoilage_freight.py` | `game/core/foundation/ledger/spatial_warehouse_bridge.py:322-327`（腐坏分支）、`:283-303`（dispatch 记 `gross_initial`） |
| P-D | `game/core/domains/economy/tax_base_readout.py` | **无**（只读，不碰 `settlement_finance.py`） |

> 触点以开工门复核为准：上表是**预计**，不是事实；若与既有 `claimedBy` 冲突，先 `board` 再认领。

---

## 3 · 待裁定（阻塞项，走 `_dev_tools/handover/decisions/`）

| ID | 待裁项 | 阻塞 |
|---|---|---|
| D1 | 商品/库存真账载体：`goods[治所]` 桶 vs `seats.warehouses` 四仓位 | P-A 落桶细节 |
| D2 | 粮载体甲/乙/丙（G-3） | P-A 的米/麦 |
| D3 | 品质/规模是否升级为拆维（Jev 已判不拆 0.643；用户可重议） | P-A 上限 |
| D4 | **稀缺曲线重标定 + `MAX_SPATIAL_RATIO`**（宋祚 hops 1–11、中位 4；禁止直套 1.43^n） | P-A 开工门 |
| D5 | 入市率 `None` 语义：甲（不折算+undefined）/ 乙（不可售） | P-B1 开工门 |
| D6 | 品目层划分与键空间 | P-B0/P-C/P-D |
| D7 | 需求篮子扩容（现仅绸/布） | P-B1 开工门 |
| D8 | 是否**真**按品目分征（替代 or 叠加 `commerce_tax`；税基；谁纳） | P-D 第二阶段（真分征） |

> 开工门纪律：裁定未闭环前**只允许**写只读表与纯函数，**不得**接入结算链。

---

## 4 · 非目标（明确不做）

| 不做 | 理由 |
|---|---|
| 把源模型的产地清单与年产量数据搬入宋祚 | Jev J3 = 否（0.028）；断代/地理/单位皆不同，违反「不臆造」 |
| **直套源模型的稀缺系数 `1.43^n`** | 实测宋祚 hops 1–11（中位 4），直套最远达 ≈55×；源模型表为 23 大区 0–6 跳定标（design §2.1） |
| 重写 `dynamic_price` / `discover_price` / `trade_goods` | 唯一成交入口与四态价格是既有已落地契约 |
| 新增库存/钱载体或平行账本 | `sz/AGENTS.md` §3-1；2026-10-20 曾因镜像直写造成 12 个月 +13,470,432 贯 |
| 顺手加「州府」字段假装已支持州府级 | `unified-civilian-market/tasks.md:621-623` |
| 市场圈派生 / 断路改道 / 季节封冻 / `ROAD_QUALITY` | 既有明确排除项（无史料不臆造） |
| 品质拆维（除非 D3 改为拆维） | Jev J4 = B（不拆维） |
| **在 D8 裁定前按品目真分征** | 宋祚现无按货税目；真分征＝改税基与 M0 对账（design §4.4） |
| 把 `COMMODITY_KINDS` 的 4 类当作源模型的 40 类用 | 盐与铁同为「原料」，粗粒度不足以驱动嗜好/应税分解 |

---

## 5 · 与既有主线的关系

- **并行**：P-A/P-C 可与 `unified-civilian-market` 的 M41（P1 试点＝绸：丝→绸）与 M42（逐维商品流量账）并行；**不得**改其契约。
- **不重复**：既有已设计机制（月度八步、三重上限成交、四因未满足、沈括途耗、四仓位物权）**照用不重写**；本专题只补源模型独有的三层。
- **收口条件**：每批须给「开工门产物 + 验收门证据 + 复跑命令与结果」，并按 `sz/AGENTS.md` §6.1 回写 `../../../docs/` 与 `game/core/README.md`。

---

## 6 · 证据要求（每批交付时必须附）

1. 复跑命令与真实退出码（`pytest ... >file 2>&1; echo EXIT=$?`，禁止管道吞码）。
2. 定向回归用例名 + 本次结果（不写死总数）。
3. 若触守恒：`stock_flow` 残差与 `money_audit.cum_residual` 前后对比。
4. 缺失路径的 `None` + `reason` 证据（不得回落 0/1.0）。
5. 若引入「设定值/推算」数字：在文档与代码注释中标明依据档。
6. 若新增品类/品目表：启动自检的失败样例（证明拼错会报错而不是静默）。
7. **P-A 专属**：稀缺曲线扫描的输入范围与输出（hops→倍数、最优路 ROI、`MAX_SPATIAL_RATIO` 命中率）；21×21 表的对称/对角/不可达自检输出。

---

最后更新：2026-10-22（v4；**P-B0 / P-D 半落地（定义＋测试 / 只读读数，无结算链调用方）；P-A 待 D4 裁定；P-B1 / P-C 未开工**；P-D 已降级为只读分解。本行与文头、§1 状态表同口径——D-4 勘误前原文「五批全部未开工」与表中 ✅ 矛盾，已统一）
