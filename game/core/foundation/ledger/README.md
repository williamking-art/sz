# foundation/ledger — 权威账本层

> POP / 钱粮 / 物料的**真账**与唯一读写入口。迁移状态总表见 [../README.md](../README.md) §一。
> 本文件只记**本子包内的模块职责与不可绕过的纪律**。

## 在整条依赖链的位置

```
业务域 (domains/*)  →  账本 (ledger)  →  状态结构
```

**所有 POP / 钱 / 粮的写入必须经过本层。** 绕过桥接的直写会被
`test_route_pops_readonly_guard.py` 当场炸掉（路级 `pops` 已由只读守卫强制）。

## 模块（11 个：8 个由 `git mv` 迁入 + 3 个 2026-10-13 新建：`local_treasury_bridge` / `building_bridge` / `storage_bridge`）

> 行数为 2026-10-11 实测快照（会随提交变化，仅作量级参考，不作为判据）。

| 模块 | 行 | 职责 |
|---|---:|---|
| `pop_bridge.py` | 805 | 🔴 **州府级 POP 基座 + 读写桥**（2026-10-04 用户裁定**方案乙**：POP 实体下沉州府级）。真账在 `prefectures[路]["seats"][治所]["pops"][类]`；含只读守卫 `install_all_guards`/`uninstall_all_guards`/`pops_guard_violations` |
| `material_holding.py` | 907 | **账本接口层**。物料/商品单点访问层——遍历 `goods` 键会把州府桶当商品维参与算术，**唯一安全判据是 `commodity_dims`** |
| `money.py` | 762 | 货币口径 M0/M1/M2/M3 与月度对账（**只读视图**） |
| `pop_structure.py` | 359 | POP 职位子池与丁口维度（B1a，2026-09-27 用户口径） |
| `prefecture_entity.py` | 239 | 州府实体层（P0/A2 · 2026-10-02） |
| `grain_bridge.py` | 128 | 🔴 **G-3 读写桥**：`pops[].grain` ⇄ `goods[治所][米]` 的**单点过渡层** |
| `occupation.py` | 111 | 🔴 **M35-C 职业人口单点**（2026-10-11 并入）：职业计数住**挂靠桶子池**（`HOST_POOL`，如 `官僚.runner_count`），**不新增 POP、不新增粮桶**；所有"人口粮需／饥饿判断／粮仓需求／购粮能力"一律经本模块取值 |
| `grain_ledger.py` | 99 | 🔴 **G-3 迁移基座**：把 `pops[].grain` 迁入 `goods[治所][米/麦]`（裁定 H·甲） |
| `local_treasury_bridge.py` | 307 | 🔴 **地方府库（`local_treasury`）下沉桥**（M37，2026-10-13 **新建**、非迁移）。真账在 `prefectures[路]["seats"][治所]["local_treasury"]`，路级降为 **Σ 派生镜像**；含聚合（未下沉⇒`None`）· 对账 `survey_local_treasury` · 写桥 `local_treasury_set/add`（未下沉⇒`None` 回落）· **治所级精确写** `seat_local_treasury_set` + `seat_local_treasury_writable`。⚠️ **别与中央 `state.treasury` 混淆**（两者不同账户） |
| `building_bridge.py` | ~310 | 🔴 **建筑（`buildings`）下沉桥**（M38a/M38b-1/M38b-2，2026-10-13 **新建**）。真账在 `seats[治所]["buildings"]`，路级 = **Σ 各治所等级**（**保形态**：任一条目是字典 ⇒ 镜像也写字典）；含 `aggregate_seat_buildings`（未下沉⇒`None`）· `survey_buildings` 逐建筑对账 · `capital_seat_id`（首府＝`SEAT_LEVELS` 序最优、同级取人口权重大者）· `sink_buildings_to_seats`（**首府承载 + 原始条目原样搬运** ⇒ Σ 与原值逐字相等）· 写桥 `building_add`（增量保形态）/ `building_set`（按原始条目精确写）/ **`building_remove`（删键，对齐 `era_mechanic` 原 `del`）** / `norm_level`（标量·`{"lv":n}`·`{"closed":true}`⇒0）。✅ **2026-10-13 已接 new_game/读档**（M38b-2；4 写点全桥：含 `era_mechanic.damage_buildings`），**A/B 对照证明零行为变化**（逐路 buildings 差异 0/20）。⚠️ 阈值类读者待「建筑落到多治所」时再改逐治所 |
| `storage_bridge.py` | ~300 | 🔴 **仓储（`changping_stock` 常平仓 / `storage` 州仓）下沉桥**（M40a/M40b，2026-10-13 新建，2026-10-17 M40b 收口）。真账在 `seats[治所][<键>]`（石），路级 = **Σ 各治所**；含 `route_stock_total`/`aggregate_route_changping`/`aggregate_route_storage`（未下沉⇒`None`）· `survey_storage` 对账 · `sink_storage_to_seats`/`sink_prefectural_storage_to_seats`（**首府承载**，Σ 与原值逐字相等，已接 `new_game` 与 `load_game` 读档幂等下沉）· 写桥 `changping_add`/`storage_add`（含 **0 下限钳**）/ `changping_set`/`storage_set`/`changping_get`/`storage_get`。✅ **M40a+M40b 全收口**：已桥接 `_changping_trade` 两处写点、`settlement_granary.py` 漕粮起运扣减、`settlement_econ.py` 本色田赋征收入库；单测 12 项全过，20/20 路仓储对账失配为 0。**不动中央太仓 `state.granary`** |
| `spatial_warehouse_bridge.py` | ~380 | 🔴 **空间确权底座与三维物流在途桥**（Bundle 1 & Bundle 4，2026-10-17 新建）。真账在 `seats[治所]["warehouses"]`，四大物理仓位：官粮廪 `public_granary` / 官工料场 `public_depot` / 商贾货栈塌房 `civilian_depots` / 私家地窖 `private_storage`。支持四大物权主体（`state:` / `imperial:` / `local:` / `pop:`）流转原子操作 `transfer_goods_ownership`；三维交通（水运/陆运/海运）跨治所调拨 `dispatch_spatial_transfer`；**沈括民夫口粮途耗模型**（运粮在途自然递减与严格守恒，运抵净值入库）`advance_in_transit_batches`；客运时空流动 `dispatch_passenger_trip` / `advance_passenger_trips`。已接 `new_game` 与 `load_game` 读档幂等下沉。 |

## 🔴 不可绕过的纪律

1. **POP 写入必须走 `pop_bridge`**；真账落**州府**，路级 `pops` 降为**只读派生聚合**（Σ 治所）。
   任何写路级 `pops` 的行为都构成「与 POP 平行的账本」。
2. **`grain_bridge` 的四个函数都支持可选 `state`**：给了就委派 `pop_bridge`（写入下沉州府），
   没给则沿用旧载体。🔴 **改调用点时务必传 `state`**，否则会继续写路级、造成分叉
   （§6.18 有三处漏网实例）。
3. **均值类字段**（`MEAN_FIELDS`，如识字率）是比率，拆分/聚合都**不可求和**（复制 + 按 size 加权）。
4. **`sync_route_pops` 是「合并」而非「替换」**，否则抹掉 `estate`/`officials` 等不参与拆分的字段。
5. 存量**读取**仍走路级 `pops`（约 210 处）——**这是刻意保留**：镜像是 `seats` 的纯函数，
   重写读取对正确性零收益、风险极高。
6. 🔴 **地方府库（`local_treasury`）写入必须走 `local_treasury_bridge`**；真账在**治所**、路级是 Σ 派生镜像。
   ⚠️ **"开闸"必须与"全部写点走桥"同批**——实测（2026-10-13，跑结算步骤 × 3 轮）：
   ① 只下沉不桥任何写点 ⇒ **第 1 轮起 20/20 路镜像漂移**（治所冻结在开局值）；
   ② 只桥账户层、留 5 处绕过账户层的直写 ⇒ **2× 冲账**；
   ③ 七处全桥 ⇒ **0 失配**。
   七处写点：账户层 `local:<路>` setter · `settlement_common`（平籴/粜粮）· `settlement_finance`
   （留州份额／必要支出优先层）· `commands_decree`（州郡赈济）；旧档 `setdefault` 由 `load_game` 顺序覆盖。
   账户 id 三段式 **`local:<路>:<治所>`** = 治所级**精确**写（不重分摊）；
   **未下沉路／治所不存在一律不可写**（否则划转静默无效、调用方仍记"已入库"＝销毁钱）。
7. 🔴 **POP 商品（`goods`）是聚合字段** ⇒ 路级 `pops[cls]["goods"]` 是**派生镜像**，
   直写会被 `sync_route_pops`（`row.update(aggregate_seat_pops(...))`，**含 goods**）**覆盖**。
   商品写点**必须走** `pop_bridge.pop_goods_add(pdata, cls, dim, qty[, seat_id])`（写治所真账 + 刷镜像）；
   月度折旧走 `pop_bridge.pop_goods_decay(pdata, cls, rate)`（**逐治所独立取整**，返回逐维核销表）。
   未下沉 ⇒ 分别返回 `None` / `{}` ⇒ 调用方回落原写法（行为不变）。
   **实测对照（2026-10-13，同种子 6 个月）**：修复前 `production_chain` 产出登记 **4,063 万**
   而 POP 实存 **0**、`settlement_granary` 折旧**完全不发生**；修复后 POP 实存 **3,408 万**、
   折旧核销 **655 万**（`price_level`/`grain_price` 未变——商品尚未接入市场供给，属 P2 范畴）。
   **第 6 处（M56，2026-10-13，已修）**：`farm_procurement.procure_from_farmers` **和买取货**
   用 `_take_goods` 扣**路级** `pops["农"]["goods"]` 镜像 ⇒ 随后 `sync_route_pops` 用 Σ治所
   重算并**整体替换**镜像 ⇒ **扣减被覆盖**，而 `slot["stock"] += take` 让国库**多收** ⇒
   **钱货不守恒 + POP 残留**（正是 M48 的 丝 +18,842 / 麻 +15 = 0.17%）。
   **定位链**：① 全流水 457 次留痕证明 `_take_goods` **账实一致（0 不一致）**⇒ 洞不在函数；
   ② 定点复核：`take=13,888`、被扣 dict `87500→73612`，但 `Σ逐路逐类` 与 `pop_goods_by_dim`
   **差 0**；③ 留痕加 `obj_id` 后判定被扣对象**不在真账对象图**（前后皆 `None`）。
   **修法**：取货改走**既有桥口** `pop_goods_sub`（按各治所持仓占比扣、逐个夹紧 ≥0、刷镜像），
   未下沉回落原写法；**登记同步改为记桥的返回值**（量"镜像前后差"会变漏记、残差翻号）。
   ✅ **结果**：`pop_goods` **6/6 维残差为 0、0 未闭合**，常驻断言已由「容忍 ≤0.5%」
   **收紧为逐维 == 0**（`test_pop_custody_identity_closes_exactly`）。
   ⚠️ Jev 当时的「甲/乙」两案**被实测推翻**（都假设"重解析能拿到真账对象"）——以实测为准。

   ✅ **家族收口（M57，2026-10-13）**：① **静态扫描**（goods 下标赋值 / setdefault / pops[类][字段] 赋值）
   未发现新的未桥接宋境写点——命中项均为**外邦路径**、`pop_goods_sub` 内部的**治所行**写、
   商品折旧的**未下沉回落分支**、以及 `settlement_finance` 的「桥优先+回落」写法；
   ② **动态扫描**（`install_all_guards` + `_GUARD_TRACE`）：朴素新局 **18 月** 与组合场景 **12 月**
   均 **违规 0、唯一写入者 0**。
   ⇒ 新增**常驻哨兵** `_dev_tools/game-dev/tests/test_m57_mirror_write_sweep.py`：
   长局开守卫 + trace，**断言无违规且 trace 明细为空**，失败时直接打印
   `function @ file:line` 的唯一写入者清单（把「找写入者」从手工二分变成自动）。
   ⚠️ **盲区**：哨兵只覆盖结算管线；**后端动作（`/api/action`）与前端触发的写点未覆盖**（生产未装守卫）。
   ✅ **读档往返盲区已补（M59，2026-10-13）**：新增哨兵
   `_dev_tools/game-dev/tests/test_m59_save_load_guard_sentinel.py` —— `save_game → load_game` 后
   ① 20/20 路有 `seats`；② 逐路 `assert_pops_consistent(pdata) == []`；③ 再跑 3 月短哨兵
   **0 违规、trace 明细为空**；④ `survey_pops` 的『字段失配』为空（覆盖「存档往返即下沉」陷阱）。
   同文件另一条哨兵把 **M50 影响面**量化：12 个月 `job_track_config_fallbacks() == []`
   ⇒ **长局无『缺政权专档 ⇒ 回落 default』** ⇒ M50 里那条更严的「拒绝产出」**保持不做**。
   ⚠️ **仍未覆盖**：后端动作路径（`/api/action`）——留待后续。
   ✅ **后端动作盲区已补（M61，2026-10-13）**：新增哨兵
   `_dev_tools/game-dev/tests/test_m61_backend_action_guard.py` —— 装守卫 + trace 后经
   `LocalBackend.action(state, name, {})` 逐个派发 **15 个代表动作**（诏令/加俸/个人行动/御前抉择/
   科技研究/focus 三件套/军令/准驳 AI 行动/长期事务旨意/口谕/合并稿/遣使）再跑一月结算 ⇒
   **0 违规、trace 明细为空**。
   ⚠️ **边界**：驱动的是 **LocalBackend（进程内）** 分派表；`HttpBackend` 把同名 action 转
   `/api/action` 后由服务端调用**同一套 `core.commands`** ⇒ 写点集合相同，但**未起 HTTP 服务做端到端验证**；
   空 payload 只覆盖「默认参数下会写到的写点」，**不覆盖「特定参数组合才写」的分支**。
   ⇒ 至此「直写路级镜像」家族**及其三个盲区（结算管线 / 读档往返 / 后端动作）全部被守望覆盖**。

8. 🔴 **`state.resources` 是「全国池」、**没有路维度**（M64 实测）** ⇒ 商品/物料存量州府化
   **不能**按 POP/地方府库那样机械"全桥+下沉"：
   * 11 处 `resources[dim]["stock"]` 写点里，只有一部分**天然有路**（生产链/和买/作坊投料/作坊产出）；
     另一些是**全国口径操作、根本没有路**（`material_market` 官仓售料/领料/基座写、铸钱扣铜、熔铜溢出）。
   * Jev 裁定 **甲 0.817：保持全国池不下沉**；新增单一写口
     `resource_stock_bridge`（`stock_add/set/take/get`）——**有路的写点先问桥，桥未接管（`None`）则回落原写法**
     ⇒ **今日零行为变化**（A/B 同种子 3 月 `resources` 完全一致），同时为将来改逐路池留好接口。
   * `stock_take` **从治所真账按持仓占比取**（逐个夹紧 ≥0、夹紧留痕）；`sink_route_resource_stock` /
     `sink_resource_stock_to_seats` **已实现但本批不调用**（翻开关须先为 6 处无路写点定**不造假地点**的归属规则）。
   * 覆盖率**可断言**：`resource_stock_survey.DIRECT_WRITE_SITES` 带 `bridged` 标记 +
     `bridge_coverage()`；用例会核对"标了 bridged 的文件里必须真出现桥调用"。✅ **M72 收口**：**可桥 4/4 已桥、可桥未桥 0（`closed=True`）**；不可桥 7 处逐点写明原因（6 处**全国口径无路** + 1 处**外邦政权口径无宋路**）；⚠️ Jev 该轮裁定（甲 0.732「`stock_set` 桥接」）的前提（该处有路）**被实测推翻**，故改为**以可桥性收口**（`bridge_coverage()` 增 `bridgeable/closed`）。历史进度：2/11 → 4/11 已桥（M65 增：`production_chain` 生产入仓、`settlement_econ` 作坊产出入仓；A/B 同种子 3 月四项指标全一致）。
   * ⚠️ **接管时的 cap 语义差异**：治所真账路径**没有全国 cap**（生产入仓记全额 `add`；作坊产出入仓记 `round(yld)` 并**跳过**直接写以防双计）——今日无路下沉 ⇒ 该分支从不走到。
   **第三处同族写点（✅ 后续已修）**：`settlement_econ` 的**成品池分派**（`:1805-1831`）曾同样直写镜像；
   试改时**触 POP 只读守卫**，守卫 trace 直指 **M45**——`market.py:180/:183`（`_trade_goods_core`）
   成交时直写路级 `pops[类]["wealth"]` 镜像（该路径平时空转，**商品真落 POP 后才被触发**）。
   **M45 已修**：成交的**财富与商品**四处写全走桥（`pop_obj_add` + `pop_goods_add` / 新增的 `pop_goods_sub`；
   未下沉回落原写法）⇒ 守卫 **12 passed**、trace 复现**违规 0 条**（原 38 条）；随后第三处落地。
   **POP custody 复测 + 常驻断言**：7 维有变动 / 7 维有账 / **5 维精确闭合** / **0 未闭合**；
   余 **丝 +18,841、麻 +15**（0.17% / 0.0002%）根因**尚未定位**（查过 `supply_merchant_materials`
   与 `material_trade._refund_batch` 两处候选，本场景均未触发；已给前者加 POP 入账登记备用）。
   ⇒ 已加**常驻断言** `test_pop_custody_identity_near_closed`：**未闭合维必须 0、各维残差 ≤ 0.5%**，
   任何新增未登记写点（残差跳变）或"有变动却完全无账"的维都会让它红；**缺口修好后应收紧为逐维残差 == 0**。

   **0.17% 残差的追查（2026-10-13，M42k/M48）——未决，证据互相矛盾**：
   ① 逐步自诊断（同时读 POP 与流量账）指向唯一不符的步骤 `farm_procurement.procure_from_farmers`
   （丝 ΔPOP=0 而 Δ账=−12,172）；② **隔离**调该函数却观测到「ΔPOP=0、农户 goods 真值=0、Δ账=−13,888」；
   ③ 但把登记改为**实测差额**后**全流水**里 `out:procure_sell` 与残差都**不变**（说明完整流水里货确实减了）。
   ⇒ 按 §3-7 记为**未决**（`tasks/M48-pop-residual-open.json`，含复现脚本与后续方法），
   **不为了把断言改绿而调参**。同时按纪律硬化：登记一律记**实测差额**，并在
   `granary_stats['procure_take_mismatch']` 留痕「算出取走量却观测不到减少」的情形。
   **POP custody 复测（同种子 6 个月）**：7 维有变动、7 维有账、**5 维精确闭合**、0 未闭合；
   余 **丝 +18,841／麻 +15** 的未登记入账（已登记待查，量级 0.17% / 0.0002%）。

9. 🔴 **地方仓储（`changping_stock` 常平仓 / `storage` 州仓）真账下沉治所**（M40a/M40b，2026-10-17 全收口）：
   真账落在 `seats[治所]["storage"]` 与 `seats[治所]["changping_stock"]`，路级 `storage`/`changping_stock`
   是纯 **Σ 治所派生镜像**。
   所有仓储增减必须走 `storage_bridge` 对应单点（`storage_add`/`storage_set`、`changping_add`/`changping_set`），
   未下沉路回落原写法；写操作内部带 `max(0, val)` 零下限钳位，并在更新治所真账后同步刷新路级镜像。
   中央太仓 `state.granary` 保持独立账户，不与地方仓储混淆。
