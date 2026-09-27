# `game/core/` —— 游戏内核（结算与状态）

> 上级规范：[`game/README.md`](../README.md) ｜ 测试：[`_dev_tools/game-dev/tests/`](../../_dev_tools/game-dev/tests/) ｜ 权威机制文档：[`_dev_tools/game-docs/docs/游戏机制说明.md`](../../_dev_tools/game-docs/docs/游戏机制说明.md)
>
> **本目录是整个游戏的中枢**：月度结算、状态权威源、人口/财政/派系机制都在这里。改这里＝改游戏规则，务必配守恒断言与回归测试。

## 一、状态与主流程（先看这几个）

| 文件 | 职责 |
|---|---|
| `game_state.py` | **核心游戏状态** `GameState`：开局构造、POP/州县/田亩初始化、派生读数入口 |
| `game_state_econ.py` | `GameState` 的经济计算族（mixin）：税率/俸禄/盐课/市舶/`tax_base_summary` 等 |
| `settlement.py` | **月度结算主流程** `run_monthly_settlement`：Step 1→11 的顺序与收尾（人口总账、子池兜底、货币对账） |
| `settlement_steps.py` | 各步骤实现的**唯一公共入口**（Step 1~11 的调度表 `_STEPS`） |
| `save_load.py` / `save_load_util.py` | 存档读写与**旧档迁移**（新增字段时在这里做 `setdefault`，并保证幂等） |
| `errors.py` | 核心错误类型（避免循环导入的公共依赖） |

## 二、结算分步（2026-09 从 `settlement_steps.py` 拆出，零行为变更）

`settlement_common.py`（共享守恒工具）· `settlement_econ.py`（经济基础＋外邦经济）·
`settlement_econ_helpers.py`（钱粮分发助手）· `settlement_finance.py`（财政与货币信用）·
`settlement_granary.py`（仓廪漕运与灾荒）· `settlement_imperial.py`（皇帝个人与隐藏状态：含隐户动态）·
`settlement_military.py`（军事外交/派系冲击）· `settlement_officialdom.py`（官制吏制与资产维持）·
`settlement_tech.py`（科技与工程）· `settlement_decree.py`（诏令执行与长期政务）

## 三、人口 · 阶层 · 官职（POP 体系）

| 文件 | 职责 |
|---|---|
| `pop_structure.py` | **农的职位子池**（自耕农/富农/贫农/佃农）＋**丁口维度**（`ding`/`kou`）＋跨 POP 迁移带财富 `move_pop_people`（恒等式与月度兜底见文件名 docstring） |
| `officialdom.py` | **官制 × POP 的单一权威源**：官/吏子池、待阙/祠禄、科举/恩荫/宗室入官/致仕、裁汰 |
| `clerks.py` | 吏制（§16）：吏额派生（`clerks_actual`）、吏禄、陋规、把持度 |
| `literacy.py` | 识字率（逐路派生） |
| `building_jobs.py` | **建筑-岗位-就业模型**：多职位岗位槽、`allocate_employment(_detail)`、就业驱动的阶层流动 |

## 四、财政 · 货币 · 资产

`money.py`（**M0/M1/M2/M3 口径与月度对账——只读视图**）· `hoard_settle.py`（封桩分层代价）·
`institution.py`（编制参数的单一权威源）· `dynamic_price.py`（动态价格＋物流分账）·
`production_chain.py`（宋侧产出链）· `asset_context.py`（资产上下文与科技采用）·
`estate_mechanic.py`（大臣家产/建筑/投资）

## 五、派系 · 局势 · 事件

`faction_basis.py`（集团↔POP 归属，只读）· `faction_metrics.py`（派生指标，只读纯函数）·
`faction_settle.py`（**`state.factions` 唯一写入点**）· `faction_split.py`（立场占比）·
`faction_voice.py`（声量权重，只读）· `situations.py`（局势投影，v1 纯只读）·
`situation_metrics.py`（metric 注册表）· `situation_settle.py`（局势结算步）·
`events.py`（史实事件脚本）· `legacy_mechanic.py`（帝国修正）· `era_mechanic.py`（建筑-时代交互）·
`focus_mechanic.py`（国策树）· `monthly_gazette.py`（月度奏章九章）· `briefing.py`（朝局简报可行动项）

## 六、命令 · 契约 · 注册表

`commands.py`（与 UI 无关的游戏命令）· `commands_decree.py`（诏令/密旨/拟旨/会签）·
`decree_effect.py`（**诏令效果口径唯一权威**）· `free_effect.py`（free_effect 通用契约）·
`agent_router.py`（Agent 路由层）· `tool_registry.py`（大臣自设工具）· `registries.py`（科技/兵种注册）·
`diplomacy_treaty.py`（外交协议落地）· `construction.py`（蓝图前置校验，**只读纯函数**）· `async_ai.py`（AI 异步调用）

## 七、只读派生视图（给 UI/后端读，不得写状态）

`region_brief.py`（州路简报）· `flow_summary.py`（国库/内帑收支悬浮栏）· `external_view.py`（外邦 POP 简版视图）·
`evaluation.py`（结算评价）· `minister_profile.py`（群臣档案）· `army_models.py`（军队实体层）· `numeric.py`（数值工具单一权威）

## 八、硬纪律（改本目录前必读）

1. **POP 挂载律**（见机制说明 §五）：人必须落六类 POP（`农/士绅/工匠/商人/官僚/兵`）的 `size`；钱粮落 POP 或国库/内帑；
   **不得新增与 POP 平行的存量账本**；阶层变动走既有通道且 ΣPOP 守恒；每条改动配守恒断言＋回归测试。
2. **唯一写入点**原则：`state.factions` → `faction_settle`；`money.py` 只读；官方镜像（`prefectures[].officials/clerks`）只由 `officialdom.sync_legacy_mirror` 写。
3. **结算步顺序不可随意插队**：新步骤请加在 `settlement_steps._STEPS` 的语义位置，并同步
   `test_pop_identity.py` 的 `_STEPS` 镜像（有 AST 逐位比对）。
4. 等级读口用 `building_jobs.building_level()`（**保留 0**）；判"裁撤/倒闭"**不要**用会把 0 归一为 1 的 `_lv()`。
5. 改人口口径请同时看 `game_state._build_pops`、`save_load` 迁移、以及 `settlement.py` 的 Step 10.5/10.55。
