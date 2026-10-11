# 实施计划

> **实施状态（2026-10-01：任务 0–7 全部落地，本规格已实施完毕）**
>
> | 任务 | 状态 |
> |---|---|
> | 0 冻结基线 ＋ 状态词典 ＋ schema version | ✅ |
> | 1 清点增量（拆入任务 0） | ✅ |
> | 2 行动计划契约 ＋ core 校验器 | ✅ |
> | 3 动态蓝图注册与多地点项目 | ✅ |
> | 4 建筑/效果实例接入月度因果结算 | ✅ |
> | 5 AI 推演读取实际计划与执行状态 | ✅ |
> | 6 拟旨 UI 与因果回看 | ✅ |
> | 7 存档迁移与完整回归 | ✅ |
>
> **落地物**：`core/decree_plan.py`（校验器＋状态词典＋构件注册表）·
> `core/blueprint_dynamic.py`（动态蓝图）· `core/plan_commit.py`（提交＋跨提交幂等）·
> `core/plan_readout.py`（AI/UI 共用读数）· `core/construction.py`（动态感知＋多址立项）·
> `core/longterm_task.py`（handler 注册表）· `settlement_decree.py`／`settlement_tech.py`／
> `save_load.py`／`game_state.py` · `ai/contracts_decree.py`（2 契约）·
> `ai/narrative_guard.py`（注入＋完成宣称核对）· `ai/client.py`（护栏接线）·
> `ai/token_meter.py` · `backend/server.py`（readouts.plan）·
> `PlanReadoutPanel.tsx` ＋ `DecreePanel.tsx` ＋ `api/client.ts`。
>
> **测试**：python **+117 例** → pytest **1525 passed**（基线 1291）；
> 前端 **+6 例** → vitest **72 passed（9 文件）**。ruff 0 · tsc 双配置 0 ·
> 240 月长局残差 **0**（ΣPOP 70,360,689）。
>
> **遗留（需裁决，非缺陷）**：营造款按月重复支付（经济口径，见下）；
> 完成宣称核对仅在传入 `state` 时生效。
>
> **另：本规格的若干原则此前已在别处先行落地**（见文末「已先行落地的相关口径」）。

---

## 任务 0（前置）：重新清点并冻结工作区基线 → ✅ **已落地**

- [x] 0.1 以**当前**代码为基线重做清点（原 `design.md:81-83` 的清单已过期）
- [x] 0.2 定义行动状态词典与 decree 计划 `schema_version`
- _前置：任务 1–7 全部_

**0.2 落地物**：`game/core/decree_plan.py`
  · `DECREE_PLAN_SCHEMA_VERSION = 1`（显式版本号，供任务 7 读档迁移）
  · `ACTION_STATUS`：`拟议/已拨款/营建中/运行/降效/受阻/作罢` 七态词典。
    **刻意不含**「受理/告成/效果已生效」——那是另两个层级，混进来就违反
    `requirements.md:25`「不得混写」，并有测试反锁（`test_action_status_dictionary_is_explicit_and_complete`）。
  · `ACTION_KINDS`：`营建/军政/财政/民生/制度` 白名单（表外 → `rejected`，不静默改写）。
  · `PLAN_VERDICT`：校验阶段四态 `accepted/unresolved/unsupported/rejected` ＋ `duplicate`。

**为什么必须先做**：原清单列的 10 个 dirty 文件里，**5 个已被全审批次 1–9 改动**
（见下表），若按旧清单"只在现存增量上继续"，极易把已修复项误当他人改动回退。

| 文件 | 状态 | 归属 |
|---|---|---|
| `game/core/game_state.py` | M（10-01 12:34） | **DSH 批次 1**（M3 `transfer_money` 目的池缺失不再静默销毁） |
| `game/core/free_effect.py` | M（10-01 12:54） | **DSH 批次 2**（S7 兜底不半落地） |
| `game/core/settlement_tech.py` | M（10-01 13:02） | **DSH 批次 2**（S8 研发经费严格通道） |
| `game/backend/server.py` | M（10-01 13:11） | **DSH 批次 1/3**（M9 隐藏田脱敏 · S10 `_json_safe` 去双重序列化） |
| `game/core/save_load.py` | M（10-01 14:47） | **DSH 批次 1/6**（M6 resources 落档 · M7 faction_split 两级清洗 · O10 识字率存 None） |
| `game/ai/client.py` | M（09-29 16:01） | 他人（规格编写时既有） |
| `game/ai/contracts_decree.py` | M（09-29 15:34） | 他人 |
| `game/backend/client.py` | M（09-29 15:44） | 他人 |
| `game/core/commands_decree.py` | M（09-29 15:22） | 他人 |
| `frontend/.../DecreePanel.tsx` | **clean**（09-27） | — |

**清单外但已被改动、开工需一并纳入基线**（10-01，均为 DSH 批次 3–9）：
`core/settlement_decree.py`（S5/S1）· `core/settlement_econ.py`（S4/O3/O4/O6）·
`core/settlement_imperial.py`（S6）· `core/settlement_granary.py`（O3 + S6 逃荒腿去魔数）·
`core/settlement_common.py`（`food_insecure_headcount` 单点）· `core/decree_effect.py`（S2）·
`core/money.py`（O5 标准汇率标记）· `core/game_state_econ.py`（M2 读数侧）·
`core/settlement.py`（S3/O1/S9 接线）· `core/settlement_military.py`（M5/O2）·
`content/data.py`（S12-d 注释 · M2 `PAYRAISE_PAY_TO`）· `engine/state_applier.py`（M2 三处登记）

---

## 1. 清点并冻结现有工作区增量 → ✅ **已由任务 0 承接落地**

- [x] ~~逐文件审阅 dirty diff，记录需保留的现有行为~~ → **已由任务 0 承接**
- [x] 以本计划为基准定义行动状态词典与 schema version
- _需求：1、3、6、7、10_

**状态：已落地。** dirty 清点见上方任务 0 的现状表（含归属与日期）；
状态词典与 schema version 见 `core/decree_plan.py`。

## 2. 建立版本化行动计划契约与 core 校验器 → ✅ **已落地**

- [x] 多 action schema、来源片段、地理 entity id、unresolved/unsupported 结果
- [x] operator registry、参数范围校验、稳定 action id、重复提交防护
- _需求：1、3、6_

**落地物**：
  · `game/core/decree_plan.py`（新，校验器）：`validate_action` / `validate_plan` /
    `resolve_location` / `action_fingerprint` / `register_operator` / `_check_operator`。
  · `game/ai/contracts_decree.py::decree_action_plan`（新，契约）——沿用既有拒绝式风格
    （`validate(o)` 返回 `None` ＝ 整单失败；`self._call` ＋ `self._postprocess`）。
  · `_dev_tools/game-dev/tests/test_decree_action_chain.py`（新，**33 例全绿**）。

**已实现的验收**（对应用户故事/验收编号）：

| 验收 | 实现 | 测试 |
|---|---|---|
| #1 一旨多动作、逐项独立裁决 | `validate_plan` 逐条 `validate_action`，产出 5 类状态 | `test_multi_action_plan_validated_per_action` |
| #3 未注册构件 → **待支持/未执行** | `_check_operator` 未见注册即 `unsupported`，effects 清空并留原因 | `test_unregistered_effect_operator_is_unsupported` |
| #6 地点 → 权威 entity id | `resolve_location` 只认 `PREFECTURE_*` 注册路；广州/明州等 → `unresolved` | `test_location_resolves_only_to_registered_entity` 等 3 例 |
| #7 稳定 action id ＋ 重试幂等 | `action_fingerprint`（**不含序号**）＋ 计划内 `seen_ids` 去重 | `test_action_id_survives_action_reordering` 等 3 例 |
| #10 缺 decree_id 不得默认成功 | 缺 `decree_id` → `ok=False`；零条通过 → `ok=False` ＋ reason | `test_missing_decree_id_is_rejected_not_defaulted` 等 2 例 |
| 参数范围校验 | `register_operator(params={...min/max/required})`，bool/NaN/Inf 一律拒 | `test_operator_param_range_validation`（5 参数化） |
| 拒绝式、不静默改写 | 非法 kind → `rejected` 且 `kind=None`；坏 budget 逐键丢弃并留痕 | `test_illegal_kind_is_rejected_not_coerced` 等 |
| **不产生副作用** | 校验器不建工程、不动国库/账（反断言） | `test_validate_plan_does_not_mutate_state` |
| AI 不得填最终数值/状态路径/代码 | 提示词显式禁止 ＋ 测试锁定提示词含该要求 | `test_contract_does_not_ask_ai_for_final_values_or_code` |

**过程中发现并修掉的一个自身设计缺陷**：`action_fingerprint` 起初把**数组序号**掺进哈希，
后果有二——① 计划内两个内容相同的动作拿到不同 id，`seen_ids` 去重**永不生效**（死码）；
② AI 重试时只要重排动作顺序，同一逻辑动作就换 id，**重复立项直接漏过**。
已改为**不含序号**，并加 `test_action_id_survives_action_reordering` 锁住该性质。

**本条未覆盖（属任务 3/4，勿误判为已完成）**：
  · **跨提交幂等**——「该动作此前已立项，本次拒绝重复提交」需要 action↔project 登记表，
    依赖任务 3 的工程落点；当前只做到「id 稳定」＋「同计划内去重」。
  · **效果构件注册表当前为空**：故任何带 `effects` 的动作判 `unsupported`。这是**故意**的
    诚实行为（规格非目标第 2 条：未注册构件不得靠改名或叙述落地），待任务 3/4 注册后自动可执行。

## 3. 接通动态蓝图注册与多地点项目 → ❌ **未做**

- [ ] 安全蓝图 schema 与效果构件 DSL（只接收已注册 operator，不运行生成代码）
- [ ] 扩展 `resolve_blueprint/can_build/propose_project` 支持存档内动态蓝图与权威地点 id
- [ ] 一旨多址生成独立 project；预检资金/地利/科技/材料并返回逐项结果
- _需求：2、3、4、10_

**部分前置已就位（本次交付）**：效果构件注册表 API（`core.decree_plan.register_operator`）
与 `blueprint_proposal` 结构校验（仅「营建」类可带、构件逐个过注册表）已可用；
本任务需补的是**注册具体构件**、**动态蓝图注册表**与**多地点立项**。

**证据（改造前）**：
`resolve_blueprint(name, key)` —— 无 `state`、只查 `BUILDING_BLUEPRINTS` ＋ `BUILDING_STD`；
`can_build(state, route, name, key)`、`propose_project(state, route, name, key, levels)`
—— 只吃**名字/键**，无动态蓝图注册表、无权威 `location_id`。

## 3. 接通动态蓝图注册与多地点项目 → ✅ **已落地**

- [x] 安全蓝图 schema 与效果构件 DSL（只接收已注册 operator，不运行生成代码）
- [x] 扩展 `resolve_blueprint/can_build/propose_project` 支持存档内动态蓝图与权威地点 id
- [x] 一旨多址生成独立 project；预检资金/地利/科技/材料并返回逐项结果
- _需求：2、3、4、10_

**落地物**：
  · `game/core/blueprint_dynamic.py`（**新**）：`validate_dynamic_blueprint`（声明式 schema，
    未注册构件/越界参数/非声明式字段一律**整份拒绝**）、`register_dynamic_blueprint`、
    `resolve_dynamic_blueprint`、`dynamic_blueprint_output`（翻译成**既有** output 键）、
    `dynamic_blueprint_cost`（与静态同口径）。
  · `game/core/decree_plan.py`：新增**内建构件** `仓容/厢军/酒课`，各自绑定一个
    `_settle_projects` 完工段**已支持**的 output 键（`granary_cap_add`/`defense_add`/
    `wine_coin_add`）——**不新增结算分支**；`_ensure_builtin_operators()` 幂等自愈。
  · `game/core/construction.py`：`resolve_blueprint` 增加动态表优先查找；
    新增 `propose_projects`（一旨多址）；`propose_project` 带出动态产出与效果清单。
  · `game/core/game_state.py` ＋ `save_load.py`：`dynamic_blueprints` 字段与存档 round-trip
    （**读档逐条重过校验器**，坏项丢弃留痕，不整档失败）。
  · `game/core/settlement_tech.py`：完工落成登记识别动态蓝图键。
  · `_dev_tools/game-dev/tests/test_dynamic_blueprint.py`（**新，31 例全绿**）。

**过程中挖出的两个真坑（都有测试锁定）**：

1. **地利前置被静默绕过**：静态用的 `blueprint_region_ok(route_type, key)` 只查
   `BUILDING_BLUEPRINTS`，动态蓝图的 key 不在其中 → 它**返回 True（处处可建）**，
   动态蓝图声明的 `requires_region` 形同虚设。已改为动态蓝图按**自身声明**判定。
   （测试：`test_dynamic_region_requirement_is_not_bypassed`）
2. **完工无产出**：完工落成登记原只认静态表 `BUILDING_BLUEPRINTS`/`BUILDING_STD`，
   动态蓝图键解析不到名字 ⇒ `_bname=None` ⇒ **完工但根本不写
   `prefectures[route]["buildings"]`**，此后维持费/部署覆盖率永不生效——正是本规格要治的病。
   已补动态注册表取名。（测试：`test_dynamic_building_registers_on_completion`）

**另修**：`_clean_int` 初版对越界值**静默夹取**（−1→0、99 月→6 月），违反拒绝式与
硬约束 #3；已改为**越界即拒绝**（测试 `test_illegal_dynamic_blueprint_rejected` 锁定）。

## 4. 将建筑实例和效果实例接入月度因果结算 → ✅ **已落地**

- [x] 建筑完工按地点登记一次（**含动态建筑**，见上方任务 3 的「完工无产出」修复）
- [x] 运行时按 capacity、维护与折旧**持续**执行 operators
- [x] 货币/粮食变化经现有守恒通道，并写 flow/change provenance
- [x] **未绑定 handler 的 `fixed_*` 事务不再仅靠进度被显示为「告成」**
- _需求：4、5、8、9、11_

**落地物**：

· **handler 绑定（核心）**：`core/longterm_task.py` 新增 `TASK_HANDLERS` 注册表 ＋
  `handler_of` / `task_is_supported`。注册表只登记**能在代码里指出数值落点**的议题
  （`land_survey`／`curtail_waste`／`reduce_office`／`reform`），并标注 `applied_at`
  （`issue` = 下诏当时生效／`issue+monthly` = 建立制度后逐月生效）。
  满进度分流：
  - 有 handler → `status="done"`、`outcome="告成"`（并带出 handler 信息）；
  - **无 handler → `status="unsupported"`、`outcome="待支持"`**，写明原因，
    **不宣告成、不改任何数值**，移出在办队列但不写 memory 的 `completed` 关系；
  - 结算侧 `settlement_decree` 据此打印"待支持"而非"告成，钦此"，
    并计入 `statistics["task_unsupported"]` ＋ `task_unsupported_list`（面板可逐条展示）。

· **运行期产出**：构件新增 `timing`（`completion` / `runtime`）。
  `酒课` 标为 `runtime`；`blueprint_dynamic.dynamic_blueprint_runtime` 把它翻成
  `_runtime` 字典；`_settle_projects` 在 `operating/degraded` 分支**按月 ×capacity**
  执行，金额经**既有守恒通道** `_collect_from_pops`（实收才入账、不足少收、绝不凭空造币），
  并写 provenance：`statistics["project_runtime_yield"]` ＋ `proj["_runtime_log"]`
  （turn/op/want/got/capacity，只留最近 6 条防存档膨胀）。
  未登记落点方式的运行键**不落地但留痕**（绝不凭空发明通道）。

**关键修正**：`m1_garrison`（整军经武）**刻意不登记** —— 它只参与 `REFORM_POP_BASIS`
的立场计算，全库无数值落点（无消费方）。此前此类事务满进度一律显示"告成"，现已据实
标为**待支持**。同理，**任何 AI 自造议题**（如"兴修水利三年"）也走待支持。

**口径说明（勿误读）**：已登记议题的效果是在**下诏当时**落地的
（`_apply_decree_effect`），事务进度是**政治推进轨道**而非效果开关；
`applied_at` 字段把这层如实写出来，面板不得把政治轨道说成数值开关。

**仍未覆盖**：运行期**粮食**产出暂无守恒落点（本项目未注册粮类运行构件；
如有需要须先设计守恒的粮通道），当前任何未登记运行键都会被拒绝并留痕。

## 5. 让 AI 推演读取实际计划与执行状态 → ✅ **已落地**

- [x] 按需注入脱敏后的项目/建筑/效果摘要与阻力，固定返回允许的档位/叙事
- [x] 叙事数字/完成宣称与真实 state diff 不一致时拦截
- _需求：7、8、9_

**落地物**：
  · `core/plan_readout.py`（**新**）：`build_plan_readout` / `render_briefing_text`
    —— 一个读数**两个消费者**（AI 注入 ＋ 面板），前端与 AI 都不许各自重算（口径单点）。
  · `ai/narrative_guard._build_source_closure`：取材闭集新增**真实工程/事务状态**段，
    并加硬约束"**未告成的工程不得说成完工，无程序侧落点的事务不得说成已生效**"。
  · `ai/narrative_guard._validate_completion_claims`：**完成宣称核对** ——
    叙事说"告成/竣工/已生效"而真实工程未到 `operating` 时**改写为如实表述**
    （防 `design.md:46`「AI 叙事替程序补状态」）；否定语境（"尚未完工"）不误伤；
    点到真实已成工程名则放行；改名时避免重复工程名。
  · `ai/client._postprocess`：**接线**（`state` 为可选参数，传了才核对）——
    这是关键一步，护栏若不被调用就是死码；有测试 `test_postprocess_actually_invokes_completion_guard`
    锁定链路，另有 `..._noop_without_state` 锁定"未传 state 时跳过"的诚实边界。
  · `ai/contracts_decree.decree_narrative_decide`：叙事契约，**固定返回档位＋叙事**，
    档位非法即整单失败；提示词显式禁止给数字、禁止把未告成说成完工。
  · `ai/token_meter.TOKEN_GROUPS`：新契约登记进「推演」组（否则计量漏组）。

**注**：数字区间校验（`_validate_numeric_ranges`）与取材闭集原已存在，本次是**接入
真实工程状态**并补上"完成宣称"这条此前完全缺失的核对。

## 6. 改造拟旨 UI 与因果回看 → ✅ **已落地**

- [x] 行动拆解、待补信息/拒绝原因、逐地点工程状态、完工产出与旨意来源展示
- [x] 明确区分旨意受理 / 执行推进 / 工程告成 / 效果生效
- _需求：1、3、5、9_

**落地物**：
  · 后端 `/api/readouts` 新增 `plan` 字段（`core/plan_readout.build_plan_readout`，
    与 AI 推演**同源**；派生失败进 `readout_errors` 而不是静默空白）。
  · `frontend/src/renderer/api/client.ts`：新增 `PlanReadout` / `PlanPhaseItem` 类型镜像。
  · `frontend/src/renderer/panels/PlanReadoutPanel.tsx`（**新**）：四层级**分列**展示
    （标签由后端 `phase_labels` 单点下发，前端不得自造文案）＋ 工程台账
    （状态/进度/产能/产出/旨意来源）＋ **待支持单列**（明确"不计为告成"）。
  · `DecreePanel.tsx`：挂载"工程因果回看"区块。
  · `frontend/src/renderer/panels/__tests__/PlanReadoutPanel.test.tsx`（**新，6 例**）：
    锁显示纪律——四层分列、待支持不得出现在告成块、缺读数**不以空白冒充"无工程"**、
    进度/产能直接取后端值、按路过滤时四层与台账**一并过滤**。

**过程中修的一个真问题**：`route` 过滤起初只作用于工程台账，**四层级列表仍混着别路的条目**
（按路看时看到别人的工程）；已改为层级与台账一并过滤，并有测试锁定。

## 7. 存档迁移和完整回归 → ✅ **已落地**

- [x] schema version、旧档默认迁移、动态蓝图快照 round-trip 与回滚覆盖
- [x] 契约、幂等、多址工程、生命周期、因果、资金/粮食守恒、AI 拒绝路径测试
- [x] 执行定向 pytest / tsc / vitest / build；更新权威文档与交接状态
- _需求：6、7、10、11_

**落地物**：
  · `save_load` 落 `plan_schemas = {decree_plan, dynamic_blueprint, plan_action}` 三个**子版本**，
    读档时：旧档（无该键）按 v1 迁移（动态蓝图**逐条重过校验器**，等价迁移）；
    **子版本高于程序支持 → 拒绝该段**（不猜、不降级解释），主档继续。
  · `state.plan_actions` 落档并逐条校验（非法条目丢弃留痕——宁可失去幂等身份，不伪造历史）。
  · 测试 `test_plan_commit_grain.py`（15 例）覆盖 round-trip、旧档迁移、超版本拒绝、
    幂等身份在读档后仍有效、钱粮守恒（对照态 A/B）。

**端到端实测**（18 月真实结算，非单测）：动态蓝图注册 → 立项 → 建成 `operating`
→ `buildings[两浙路][海塘]=1` → 运行期酒课 48,000 贯 ＋ 籴买 26,000 石 →
读数四层（completed 1 / effective 1）→ 注入简报正确显示"operating（产能 100%）；产出 …"。

## 收尾补的三处缺口

| 缺口 | 落地 |
|---|---|
| **跨提交幂等**（任务 2） | 新增 `core/plan_commit.py`：`commit_plan` 校验→落地→登记 `action_id → pid`；同一 id 二次提交判 `already_submitted` 并**不重复立项**（`ok=False`，不伪装成新提交） |
| **运行期粮类落点** | 新增内建构件 `籴买`（`timing=runtime`）：经**既有守恒配对** `_state_grain_trade(..., "buy", ...)`（太仓＋粮/国库−钱/民间售粮得钱），钱粮两组 ΣΔ==0，按 capacity 缩放，provenance 记 `project_runtime_grain` |
| **蓝图坏构件被静默丢弃** | 蓝图提案含未注册构件时，原实现**丢弃该构件后照常注册**（玩家提三效果拿到两效果且不知情）→ 改为整条动作判 **`unsupported`**，不缩水通过（已有对照反回归） |

**同时修的集成 bug**：`decree_plan.validate_action` 给蓝图补了空串 `category:""`，
而 `validate_dynamic_blueprint` 把"空串"当非法分类**整份拒绝** → "AI 没给分类"的蓝图
**永远注册不了**。已修：空串/空白按"未给"处理（默认 `民生`），且上游不再补空串。

## 遗留（需用户裁决，非缺陷）

- **营造款按月重复支付**：`settlement_tech._settle_projects` 营建期每月付
  `cost_coin × 供给率` 却**不递减** `cost_coin` ⇒ 2 月工期约付 2 倍造价。
  钱是守恒转移（国库→工匠/商人，**不凭空生灭**，`money_audit` 残差 0），
  属**经济口径**问题而非守恒缺陷；改它会动平衡，故留待裁决。
- 运行期**产出/维护成本**对不同建筑的差异化（当前统一按 capacity 线性）。
- 完成宣称核对**仅在调用方传入 `state` 时生效**（未传则跳过，已由测试锁该边界）。

---

## 可复用地基（已存在，规格要求复用而非新建）

| 资产 | 位置 | 说明 |
|---|---|---|
| 蓝图解析 / 前置校验 / 立项 | `core/construction.py`：`resolve_blueprint` / `can_build` / `propose_project` | 静态版已可用，需**扩展**以支持动态蓝图 |
| 工程五态状态机 | `state.projects` ＋ `_settle_projects`（由 `propose_project` 移交） | 规格明确禁止新建平行状态机 |
| 守恒记账通道 | `transfer_public_funds_to_pops` / `transfer_public_funds_to_pops`＋`state_applier` | 资金/粮变更须继续经此，并已含钱组守恒校验 |
| 受管写路径白名单 | `engine/field_registry.py`：`RULES` 单点声明 → `derive()` 生成 `VALID_PATHS` / `MONEY_PATHS` / `GRAIN_PATHS` / `NON_NEG_PREFIXES` / `RANGE_100_FIELDS` / `CLAMP_01_FIELDS`（B-1，2026-10-12） | 新增资金类字段只改**一行** `cons=MONEY`（原「三处登记」已收口为单点声明）；契约与冻结清单见 `../field-registry/` |
| 效果构件表 | `content/data*.py`：`BUILDING_STD` / `BUILDING_BLUEPRINTS` / `IMPERIAL_*` 等 | 动态蓝图的构件来源 |

---

## 已先行落地的相关口径（**不等于本规格任务完成**）

规格的若干原则已在全审批次中以**同源口径**先行落地，但它们覆盖的是
「一次性诏令」这条线，**不是**本规格的「多动作计划 → 动态蓝图 → 效果实例」：

| 规格原则 | 已落地处 | 状态 |
|---|---|---|
| 唯一实现在 `core/`，AI/UI 不复制（`design.md:11`） | 一次性诏令改调 `core.decree_effect.decree_effect_mult`（原调用次数 0） | ✅ |
| 读数未定义**不得回落 1.0** 假装执行 | 删掉 `settlement_decree` 的 `_grip_effective = 1.0` | ✅ |
| 无 handler 不得只靠进度被显示为「告成」（`design.md:47`） | 效果系数 `None` → **挂起**：不执行不生效、退回待办、留原因与 `statistics.decree_effect_undefined` | ✅（诏令线） |
| 「计划已受理 / 施工完成 / 效果已生效」不得混写（`requirements.md:25`） | 同上（挂起态与执行态分离） | ✅（诏令线） |
| 调兵强制施行杠杆（规格全文未提，为额外口径） | `enforce_troops` 已透传至单点，受 `ARMY_ENFORCE_BONUS = 30%` 约束 | ✅（额外） |
| **长期事务 `fixed_*` 的 handler 校验** | `longterm_task.py` 注册 `TASK_HANDLERS`；月结对无 handler 项标记 unsupported，避免只凭进度告成 | ✅ **代码与定向测试已存在**（`_dev_tools/game-dev/tests/test_task4_causal_settlement.py`；本次未复跑） |

> 注：`action_id` 在 `core/commands.py`、`backend/client.py`、
> `frontend/.../PendingActionsPanel.tsx` 的大量命中，属于**既有的 AI 建议动作审批流**
> （`ai_pending` ＋ `approve_ai_action` / `reject_ai_action`，用于军事调派/财政方案），
> 与本规格的圣旨行动闭环**不是同一功能**，仅命名撞车。实现时勿误接。

---

## 核实方法（便于复核）

> **2026-10-01 更新**：任务 0/2 落地后，下列「0 命中」检索中的
> `decree_action_plan` / `core/decree_plan.py` / `operator_registry` / `blueprint_proposal`
> **已不再为 0**（由本次交付引入）。仍为 0 的是**任务 3/4/5/6** 的产物：
> `dynamic_blueprints` / `effect_instance` / `unresolved` 注入路径 / UI 行动拆解。

- 产物存在性：`grep` 全 `game/`（py/ts/tsx）搜 `decree_action_plan` / `dynamic_blueprint` /
  `blueprint_proposal` / `core/decree_plan.py` / `effect_instance` / `operator_registry`
- 变体命名宽搜：`action_plan` / `actionPlan` / `plan_actions` / `decreeActions` /
  `DECREE_ACTION` / `行动链` / `行动闭环` / `动态蓝图` / `效果构件` / `效果实例` /
  `待支持`（排除"换名已实现"）
- 本次交付物定向复核：
  `pytest _dev_tools/game-dev/tests/test_decree_action_chain.py -q` → **33 passed**
- 签名核实：`core/construction.py` 三个入口的形参（**仍不含**动态蓝图注册表）
- 缺陷 live 核实：`core/longterm_task.py:562-564`
- 副作用反断言：`test_validate_plan_does_not_mutate_state`（校验器不得建工程/动账）
- 沙箱/并发注：全量门禁见 `sz/AGENTS.md` §4；前端 vitest 在本机须用 threads 池
  （已在 `frontend/vitest.config.mts` 固定 `pool: "threads"`）
