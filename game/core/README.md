# `game/core/` · 游戏规则与状态结算

本目录包含游戏状态、玩家命令、月度结算、人口与财政、政令、工程、市场、外交及状态读数。这里的 README 是导航；单个机制的当前口径以 `_dev_tools/game-docs/docs/` 为准，阶段状态以相应规格的 `tasks.md` 与生产调用路径核实。

代码层按机制域模块化的目标架构（采用三省流程、六部业务域作责任划分参照）见 [`specs/cross-cutting/代码层机制模块化架构方案_2026-10-06.md`](../../_dev_tools/game-docs/specs/cross-cutting/代码层机制模块化架构方案_2026-10-06.md)。**分阶段实施中**：阶段 1（依赖图）已完成；阶段 2 已迁 `foundation/`（ledger 7 模块 + common/numeric）与首个 `domains/economy/` 实现；平铺旧路径全部保留薄转发桩；**生产调用点已改指新路径**（2026-10-07 第九包达成阶段 2 判据④，
生产侧旧桩引用归零；**测试侧仍走旧桩**＝兼容门面生效面）。每包实测状态唯一权威 = [`foundation/README.md`](foundation/README.md)。

## 回合与状态主链

| 模块 | 职责 |
|---|---|
| `game_state.py`、`save_load.py`、`save_load_util.py` | 初始状态、状态扩展、存档序列化与兼容迁移。<br>↪️ **2026-10-07 第七包**：槽位机械与旧档迁移的真叶子部分已迁入 [`foundation/persistence/`](foundation/README.md)（`slots.py`/`migrations.py`），`save_load.py` 保留同名转发，`from core.save_load import _slot_path` 等旧路径不变；`save_game`/`load_game` 因携带反向边**仍在原处**。<br>↪️ **2026-10-07 第八包**：`save_load_util` 的 `_safe_int`/`_safe_float` 并入 [`foundation/common/numeric.py`](foundation/README.md)（该模块是"数值工具单一权威"），`save_load_util.py` 留显式转发。<br>🔴 **读档容错口径**：整数字段被写成**小数串**（如 `"2.7"`）时，`_safe_int` 判为**缺失**并回落 `default`，**不是截断**；而 `parse_number` 缺失回 `0.0`、`_safe_int` 缺省回 `None`——两套口径**刻意并存**，别当重复代码合并（详见 `foundation/README.md` §六）。<br>🔴 **POP `goods` 命名空间（2026-10-03）**：① **物料维全部中文**——`RAW_DIMS` = `盐/茶/丝/麻/蔗/果/木/石/铁/金/铜/银/牲畜/马/药材`（已无 `timber`/`stone`/`iron` 英文轨）；② **州府桶**——`goods[治所][dim]`（治所主键 `路\|治所`），扁平项＝**无州府归属**的残量，总量 = 扁平 + Σ桶。<br>⚠️ **读写一律走 `material_holding` 单点访问层**（`goods_amount`/`goods_set`/`goods_add`/`commodity_dims`），**不得**裸取 `goods[dim]` 或裸遍历 `goods` 键（桶是 dict，会被当商品维参与算术）。<br>⚠️ **货币 ≠ 物料**：`money.py` 与蓝图 `cost.silver`、科技研发费里的 `silver`/`gold`/`copper` 是**币种**，保持英文；作为物料时才是中文「银/金/铜」。 |
| `commands.py`、`commands_decree.py` | 玩家命令入口、回合推进与政令相关操作 |
| `settlement.py`、`settlement_steps.py` | 月度结算编排与步骤顺序。<br>⚠️ **Step 4.45 建材供给**（仓 → 商人货栈，搬运守恒）／**4.46 建材到货**（本月到期批次入账）／**4.47 补货下单**（商人低于阈值即向料足的路下单）。三者**依次**排在 Step 4.4 产出链**之后**、消费侧**之前**；失败只 `log.append(WARN)` 不阻断结算。 |
| `settlement_*.py` | 财政、经济、粮政、军事、官制、政令、科技等具体结算逻辑。<br>⚠️ **建材口径（C-c + E-1）**：消费侧（`settlement_tech` / `settlement_agri` / `civil_building`）**一律只从本路商人货栈取料**，且**判定与落扣共用同一读口**；直读 `state.resources[dim]["stock"]` 等于"料可凭空调用"，**物流失去意义**（§14.2 障碍 2）。<br>⚠️ **注册表的建材维度必须校验** ∈ `material_holding.MATERIAL_DIMS`——拼错会让该建筑/升级**永远走"缺料"分支而静默失效**；`civil_building.UNKNOWN_MATERIAL_DIM_ALLOWLIST` 是**故意**引入未知维度的白名单（拦"疑似拼错"、不拦"明知故犯"）。 |
| `game_state_econ.py`、`money.py`、`flow_summary.py` | 经济状态派生、账户口径与收支读数；货币汇总口径集中维护 |
| `officialdom.py`、`minister_profile.py`、`minister_agent.py`、`agent_router.py` | 官员资料、个体 Agent 状态/路由和遗留镜像同步；具体 Agent 是否唤醒须看路由配置与调用链 |

结算顺序属于游戏规则的一部分。新增步骤要放在语义正确的位置，并核对相应测试、读数与文档；不要只依据文件名或测试文件存在就认定已接入。

## 关键机制模块

| 模块 | 当前职责边界 |
|---|---|
| `decree_effect.py`、`decree_plan.py`、`plan_commit.py`、`plan_readout.py` | 政令效果口径、行动计划校验/提交和计划状态读数 |
| `blueprint_dynamic.py`、`construction.py`、`construction_cost.py`、`longterm_task.py` | 动态蓝图、工程登记、造价与长期事项执行接口 |
| `market.py`、`market_price.py`、`demand.py` | 商品交易、价格发现、需求规则的模块化实现；每段生产调用链仍须按规格状态核实 |
| `market_readout.py`、`population_readout.py`、`income_readout.py`、`region_brief.py` | 面向 UI/AI/审计的派生读数；只读读数不等于模拟行为已经采用相同算法 |
| `settlement_agri.py`、`export_policy.py` | 农业升级与外销相关规则/决策模块；是否接入月结算以调用者为证 |
| `material_market.py`、`material_tech.py` | 建材有来源的本地市场（成交复用 `market.trade_goods`）、新材三源解锁；水泥/钢筋是架空后世材料，未解锁不可定价。**`material_market` 尚未接入工程领料**（现存供需都直连 `state.resources`、无钱腿，POP 也不持建材），当前只有只读读数可用 |
| `decree_confidential.py`、`ministry_council.py` | 密令泄露按真实知情范围/传递路径推演、朝议逐人合议；知情范围取各人自己的记忆，不得另建名单或压成"朝廷综合回答" |
| `decree_confirm.py`、`civil_building.py` | 口谕结构化复述确认与同旨补录幂等（`ensure_decree_id` 是 `decree_id` 的**唯一生成点**）、民间四动因自发造房。⚠️ 两者**须先有 `decree_id`**：全仓下旨路径曾从不写它，导致 B5-5 泄露推演长期被永假条件短路 |
| `clerks.py`（吏治单点） | `decree_execution_mult` 是**诏令与口谕强度的唯一强关联**读数 | 口谕强度/走样已改由它决定，**不再用** `KOUYU_EFFECT_MULT=0.6`／`KOUYU_DRIFT_CHANCE=0.30`（那两个常量已标废弃）；读数缺失时不按固定值假装 |
| `prefecture_entity.py`（🔴 实现已迁至 `foundation/ledger/prefecture_entity.py`，本路径为**薄转发桩**，2026-10-06 阶段 2 第五包）| **州府实体层**（只读）：稳定主键 **`路\|治所`**、身份（等级/经纬）、州府级人口经济、路级聚合断言（`Σ子+residual == 路级`，不一致即 raise）、覆盖率与**精度声明**。<br>⚠️ **主键必须是限定名**：传裸显示名一律返回 `None` **不猜**（设计文档 §4.10「用稳定地域 ID，不靠显示地名」）。<br>✅ **2026-10-02 去重**：`颍昌府` 曾在京畿/京西**各登一次且坐标全等**（同一府块被两条路各算一次＝地理双计），已删京畿路那一席 ⇒ **136 席**，主键与显示名均唯一，回归加"同名/同坐标"双守卫。<br>✅ **接入史料户口**：已录《宋史·地理志》崇宁户的路按**史料比例**分配，`basis="historical"`；未录者回退 `area_only` 并**如实报覆盖率**（当前 **75/126 有块席**）。宋侧 13/21 路成路——**已达崇宁户口真实天花板**（南方广南·夔州·益州多用「元丰户」或无年号）。 |
| `material_trade.py` | **跨州府建材成交与补货决策**（P0 · 2026-10-02）。<br>· 🔴 **粒度分工（用户 2026-10-02 纠正）**：**库存按路**（建材挂路级商人 POP `goods`，POP 挂载律）／**运输按州府**（`frm_seat`/`to_seat` 限定名 `路\|治所`）。⚠️ 曾用路级签名 + 内部随便挑一对相邻治所，等于**把整路当成一个运输节点**，与 136 席州府实体层矛盾（实测 37 对相邻路中 **31 对**因"首席治所不相邻"被误判成不通）。<br>· **钱货两腿分离**：**钱成交即付**（既有守恒通道 `transfer_money`，不新开账本）；**货走 `transport.dispatch` 进在途**，到月才入账。**钱货两清或两不做**（付款失败/不足 ⇒ 批次撤回、货回卖方）。<br>· `procure_materials()`：本地低于 `STOCK_FLOOR` 即向料足的路下单。**不追货**（按**治所**抵扣在途）；🔴 **不通 ≠ 无货源**——候选卖方不可达时**继续试下一个**，不能 break。<br>· ⚠️ 价与阈值均**设定值、非史料**。<br>· 同路请用 `material_holding.trade_material`——它**拒绝**跨州府（护栏）。 |
| `transport.py` | **州府间交通边与在途批次**（P0 · 2026-10-02）：把 §14.4 排除的"在途/断路"补上——没有它，C-c「只从本地取、取不到即缺料」只是口号（发货瞬移则"运没运到"不可观测）。<br>· ✅ **能算**：经纬度 → haversine 距离 → **运输耗时（月）**；同州府 0 耗时，跨路下限 1 月（不做"同月到达"）。<br>· 🔴 **相邻可达**（`is_adjacent` / `ADJACENT_KM`=200km）：超出阈值 ⇒ `route_days` 返回 `None`＝**"不通"**，**不是"很远"**。规格 `unified-civilian-market/tasks.md:88` 明确「**不做全图任意互通**」。⚠️ 阈值是**设定值非史料**（宋代驿路里程无可靠记载；200km 处平均度 5.5 最接近"相邻"图结构）。<br>· 🚫 **不臆造路况**：`ROAD_QUALITY` **默认为空**，耗时按平地常数 `KM_PER_MONTH=1000` 计，故所有读数**自述是设定值、非史料**。<br>· 🚫 **不做**：市场圈派生、断路/改道、季节封冻（无真实地理与路况支撑，**没有就不做**）。<br>· `dispatch()` **钱货两清或两不做**：扣不到货**不建批次**；`arrive_due()` **未到不入账**（物流可观测的关键）。<br>· 🔴 **时点口径**：用 `civil_building.abs_month_index(state)`，**不用 `state.month_index`——该字段不存在**，`getattr(...,0)` 恒返回 0 会让**所有货瞬间到达**（历史坑，有用例钉住）。<br>· ⚠️ `_seat_index()` **必须缓存**——它被调上万次，不缓存会把 12 月结算拖慢一个数量级。<br>· 批次台账 `state.material_transit`（**存档须往返**）。<br>· 🔴 **粒度分工（2026-10-03 实测厘清）**：**时效按州府、记账按路**——`route_days`/`transport_links` 用治所经纬算耗时（已州府级），而 `dispatch` 发料与 `arrive_due` 到货都走 `consume_for_circuit` / `merchant_goods(…, 路)`（**路级**）。<br>· ✅ **州府级可观测**（口径方案 `docs/建材州府级下沉_口径方案_2026-10-03.md` 方案 C，2026-10-03 落地）：批次新增 `from_circuit`/`to_circuit`；到货批次带出 `arrived_seat`/`arrived_seat_id`/`arrived_circuit`；新增 `transit_by_seat()`（按**目的地治所**汇总在途量，Σ 与发货量守恒）并挂进 `transit_report["by_seat"]`。**缺失≠0**：无在途 ⇒ `{}`。<br>· ⚠️ 州府级**存量**（该州府有多少料）**尚未落地**——须先裁定「路级 POP 持有的料如何归属州府」，详见该方案 §三补二 A/B。 |
| `material_holding.py`（🔴 自丙批二起为**纯转发桩**：账本 42 名→`foundation/ledger/material_holding.py`、交易 3 名→`domains/economy/material_trade_ops.py`，实现均不在本文件，2026-10-06）| **建材商品化**（P0，用户 2026-10-02 裁定 **C / C-c / E-1**）：<br>· **C-c**：施工侧**只从本地取料，取不到即缺料** ⇒ 建材**必须先运到**才能开工，缺料**不得**由系统自动代买/凭空补（"这样物流才有意义"）。<br>· 🔴 **E-1**：「**建材也是商品啊**」⇒ 建材是**商品**，存量落在**商人 POP `goods`**（POP 挂载律），商人因此有囤货与定价动机。<br>· ⚠️ **仓明细层 `state.resources[dim]["by_pref"]` 已整体退役**——与 POP `goods` 并存即**平行账本**，直接违反挂载律。`state.resources[dim]["stock"]` 仅保留为**全国总账/来源池**。<br>· **维度命名空间已合并**：政府工程原用 `RAW_DIMS_14` 中文名（`铁`/`石`/`木`），民间营造用 `RAW_DIMS` 英文名（`iron`/`stone`/`timber`），本是两个单元格、不合并会**同一物料双记**；现经 `to_material_dim()` 在**仓边界单一翻译点**合并。<br>· 不变量：`supply_merchant_materials()` **只是搬运**（按差额补足，**幂等、不凭空增物**）；无商人/无该维度 ⇒ `None`（**缺失≠0**）；扣不足返回**实扣量**（不静默）；**不跨路借料**。<br>· `trade_material()` **复用 `market.trade_goods` 不新写撮合**，E-1 后**无需视图适配器**；`ΣPOP goods` 与 `ΣPOP wealth` **均不变**（只是转移）。 |
| `settlement_finance.py` / `settlement_econ.py`（POP 写入段） | 🔴 **方案乙桥接化**（2026-10-04）：POP **写入**一律走 `pop_bridge`（先落州府真账、再刷路级派生镜像），存量**读取**仍走路级 `pops`（它是桥接维护的镜像，无需逐处改写）。**已桥接模块（约 130 处写入点）**：`settlement_finance`(29)·`settlement_granary`(24)·`officialdom`(22)·`settlement_econ`(19)·`settlement_common`(12)·`settlement_imperial`(4)·`commands`(4)·`clerks`(4)·`settlement_decree`(4)·`game_state`(4)·`settlement_econ_helpers`(2)·`settlement_agri`(1)。
  🔴 **`game_state.py` 是最底层模块**（被几乎所有模块导入），顶层 `from core.pop_bridge import …` 有**循环依赖**风险 ⇒ 该模块用模块级辅助 `_pop_add(state, pop, field, delta)` 做**函数内延迟导入**。
  ⚠️ `income_readout` 的 `t["size"] += …` 是**本地聚合临时 dict**，非 POP 对象。
  🔴 **`MEAN_FIELDS`（均值类，如识字率）不可求和**：拆分时**原样复制**到各治所、聚合时**按 size 加权还原**，
  且比率**保留浮点**（取整会永久丢精度）。`sync_route_pops` 必须**合并**（`row.update(agg)`）而非替换，
  否则抹掉 `estate`/`officials` 等不参与拆分的字段。
  ⚠️ POP `goods` 是「**扁平标量 + 州府桶**」双形态，拆分时**已有州府桶须原样归位**（否则建材整体丢失）。
  🛡️ **路级 `pops` 只读守卫**（5b）：`_GuardedPops`/`_GuardedRow`（dict 子类）把路级 `pops` 与各 POP 行包起来，
  写入即记账；`_pops_write_exempt` 让 `sync_route_pops` 的镜像刷新豁免（否则 407 处误报）。
  `install_all_guards(state)` 装守卫，`pops_guard_violations()` 取违规，`reset_pops_guard()` 清零。
  用例 `test_route_pops_readonly_guard.py` 把守卫覆盖路径的遗留直写基线锁为空，并测试真实 15 月月结、玩家扩编命令、一条鞭田赋折银欠税、家产月循环、士绅囤粮/市舶窖银（含高档出窖）、AI 城市化/宋侧岗位流动及组合经济压力月结。POP 写点必须经 `pop_obj_add`，落州府真账再刷新路级镜像；家产循环另核对具名镜像与州府子池以及 `M_ALL` 守恒，囤粮路径校验财富守恒、商品粮入户和路级镜像一致；城市化、就业流动的 `move_pop_people` 必须传 `state`，否则 helper 会回退到路级镜像直写。`apply_employment_flow` 的 `state` 可选，外邦省域调用不变，宋侧结算必须提供。⚠️ 桥接返回 `None` 表示该路**尚未下沉**（无 `seats`），调用方回落原写法。**外邦省域 POP**（`ex["provinces"]`）**有意不桥接** —— 另一套结构，照改会错配实体。 |
| `material_holding.py`（续） | 🔴 **2026-10-04 卡1–卡1.4 已扩展为全商品州府桶**：`supply_goods_to_seats()` 全商品供给入州府桶（默认 `GOODS_DIMS`）；`seat_weights_for()` = 人口基础权重 ×《宋史》贡物证据增强（`TRIBUTE_WEIGHT_BONUS=4`）。⚠️ **差异化现阶段只到路级**（路级 12/21 精确对齐，治所级仅 7/126 且子串匹配已否决）；**缺失 ≠ 0**，无贡物记录只代表无证据、权重不归零；贡物**不含数量**，不可当产量。 |
| `pop_bridge.py` | 🔴 **州府级 POP 基座**（2026-10-04 用户裁定**方案乙**：POP 实体下沉州府级）。真账 `prefectures[路]["seats"][治所]["pops"][类]`，**路级 `pops` 降为只读派生聚合**（写入必须落州府，否则违反 `AGENTS.md` §3-1）。`split_pops_to_seats()` 按 `demog.population` 拆分且**幂等**，`aggregate_seat_pops()` 派生聚合，`survey_pops()` 逐字段对账。🔴 尾差归权重最大者保证 `Σ治所 == 路级原值`（实测 117 治所、失配 0）。⚠️ **`pops` 直访仍有 39 文件/197 处未接入**，桥接是过渡期唯一允许的写入口。 |
| `pop_bridge.py`（补） | 🔴 **字段桥接与反查入口**（2026-10-04）：`sync_route_pops()` 刷派生镜像；`pop_get/pop_set/pop_add` 按 `(pdata, cls, field)` 读写真账，分摊权重优先用该字段在治所间的**现有分布**（征税按各治所 `wealth` 占比，比按人口更贴近真实税负）；`assert_pops_consistent()` 断言镜像==真账。⚠️ **`locate_pops(state, pop_obj)` / `pop_obj_set` / `pop_obj_add` 是必需的反查入口** —— 多数写入点手上只有 pop 对象、没有 route dict 与类名，缺此入口会迫使每处手工传参，迁移成本被严重低估。 |
| `grain_ledger.py`（🔴 实现已迁至 `foundation/ledger/grain_ledger.py`，本路径为**薄转发桩**，2026-10-06 阶段 2 第六包）、`grain_bridge.py` | 🔴 **G-3 粮迁移基座**（2026-10-04，H 裁定为**甲**：粮入 `goods[治所][米/麦]`）。`grain_ledger` 提供派生读口 `grain_of`（缺失⇒`None` 非 0）+ 对账 `survey_grain`；`grain_bridge` 是**读写桥**，写只落一个载体、**绝不双写**。⚠️ `pops[].grain` 仍有写入 262 / 读取 128 处，**迁移分片推进中、尚未退役**；期间桥接层是唯一允许的写入口。目标维「米」是**口径假设**（`grain` 无米麦分项史料），非史料依据。 |
| `production_chain.py`、`building_jobs.py`、`registries.py` | 生产与岗位逻辑、建筑/构件及科技/兵种等注册数。🔴 **卡2（L1′）**：`settlement_econ._settle_workshops` 已改**两阶段配给**（收需求→按 `recipe.ration_weight` 分配→不足同比例欠产），产出按实得料占比缩放，消除「产出随 recipe 注册顺序漂移」。 |据 |
| `faction_*.py`、`situation_*.py`、`events.py` | 派系状态/变化、局势、事件及对应派生指标 |
| `diplomacy_treaty.py`、`external_view.py`、`army_models.py` | 外交协议、外部势力读数和军队实体模型 |

## 政令到地方行动

行动链相关实现包括政令契约（`game/ai/contracts_decree.py`）、计划校验与提交、动态蓝图、地点工程、月度效果结算和 AI/UI 读数。完整验收范围与剩余问题见 [`decree-action-chain/tasks.md`](../../_dev_tools/game-docs/specs/decree-action-chain/tasks.md)。代码具备蓝图或 handler，并不自动意味着所有旨意动作均有执行器；遇到缺失 handler 应保留“未支持/待承办”状态，不把叙事或进度当成实际建设。

## POP、财政和商品账本

- 人口必须归属现有 POP 类别；阶层迁移、隐户、流民与死亡使用各自明确的迁移/统计口径。不能把累计“人月”读数解释成独立人口数。
- 钱粮和商品必须能追踪持有人、地点、用途及转移对手方；汇总读数是派生值，不能另建一份平行存量。**"扣库存"不是"买卖"**——`state.resources` 的直接扣减（工程领料、产出链入仓）**不构成付款腿**；需要真实对手方时走 `core/market.py::trade_goods`。
- 缺字段、未记录和数值为零含义不同。读档迁移不得悄悄伪造人口、财富、价格或库存。
- 市场、消费、农业、建材、官民经营与官员 Agent 的实施状态见 [`market-civilian-economy/tasks.md`](../../_dev_tools/game-docs/specs/market-civilian-economy/tasks.md)。240 月人口/民生稳定性需单独验收；货币残差为零不足以证明平衡成立。
- `statistics` 里的月度流量键（`price_demand`/`goods_spend`/`goods_traded`/`goods_unmet`/`basics_unmet`）**全库无自动清零**，语义是当月流量，须在结算起点归零；否则累加值与当月存量配对会系统性放大价格压力。开局的农业资产类建筑（`game_state._init_agri_buildings`）只为让投资有可作用对象，不产生岗位、也不含科技节点绑定建筑。

## 修改本目录前

1. 对照 [`游戏机制说明.md`](../../_dev_tools/game-docs/docs/游戏机制说明.md) 和专题机制文档，确认现行口径。
2. 检查开局构建、结算步骤、API/UI 读数和存档迁移是否同时需要变更。
3. 对人口/钱粮/商品转移保留可重建的来源—去向关系；缺数据时明确标为未知或待支持。
4. 更新相应规格状态、权威机制文档、受影响目录 README 和针对性回归证据。
5. 保护已有工作区改动；不要从历史 README 拷回已经移除或未接线的模块描述。
