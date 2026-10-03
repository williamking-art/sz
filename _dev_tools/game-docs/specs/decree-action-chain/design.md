# 圣旨行动闭环：设计

## 目标

将“自然语言旨意”变成“可审计、可执行、可结算的结构化计划”。AI 负责理解语义、拆分动作、提议蓝图配置和给定性判断；程序负责验证、提交工程、计算效果、记账和记录因果。

## 设计原则

1. **意图和执行分层**：解析结果只是提案，不等于状态变化。所有状态变更必须经 core 的注册式执行器。
2. **新蓝图可生成，效果构件受控**：AI 可提出新建筑名称、类别、地点、造价、工期、材料/工时、维护和多个效果构件；程序只能接受已注册的 effect operator 与参数 schema。参数是数据，不是代码。
3. **效果可复算**：每个效果构件定义输入字段、单位、发生时点、产出公式、CAP、维护条件、守恒对手方和归属；唯一实现放在 `core/`，AI 与 UI 不复制算法。
4. **真实位置引用**：行动计划使用稳定地理 entity id；显示名只用于界面。对城市级施工，使用权威行政/城镇 registry 映射至真实路/州县节点；无可验证实体则动作待确认或拒绝。
5. **来源链不断**：`decree_id → action_id → dynamic_blueprint_id → project_id → building_instance_id → effect_instance_id → settlement_flow/change_log`。任一节点缺失时，不显示“效果已落地”。
6. **幂等且可部分落地**：action id/fingerprint 防止重试重复立项。多动作逐项校验、逐项提交；清楚显示成功、待补信息、受阻、拒绝和已完成，不让一个动作的失败伪装成整道旨意成功。

## 流程与模块边界

```mermaid
flowchart LR
  A[圣旨原文] --> B[AI 结构化计划]
  B --> C[Schema 与语义校验]
  C --> D[效果构件注册表 / 地理注册表]
  D --> E[计划预览与确认]
  E --> F[core 执行器]
  F --> G[projects 五态施工]
  G --> H[完工登记建筑与效果实例]
  H --> I[月度确定性结算]
  I --> J[资金流 / 状态差分 / 因果日志]
  J --> K[AI 定性报告与玩家界面]
```

### AI 契约

- 版本化 `decree_action_plan` 输出：`decree_id`、`actions[]`、`unresolved[]`、`narrative`。
- 每个 action 含 `id`、原文片段、动作种类、地点 entity id、执行机构、前置、资源预算、时限和明确的 `effects[]`。
- 建筑动作可附 `blueprint_proposal`：名称、类别、可建地点标签、成本/月份/材料/工时/维护、效果构件与参数。
- AI 不填最终生效数值、不写状态路径、不生成表达式。动态数值由 operator 定义的 core 函数按当前状态计算。
- 模型缺字段/地点歧义/unsupported operator → 返回待补信息/未支持项；不能降级成“叙事已施行”。

### Core 计划验证与执行

- 新增（或等价拆分）`core/decree_plan.py`：schema 升级、类型校验、地理解析、operator 参数校验、预算/科技/地利校验、稳定 id 与幂等检查、逐项执行。
- 扩展现有 `core/construction.py` 蓝图解析，使静态与动态蓝图共用 `can_build/propose_project` 校验；动态蓝图在 `GameState` 注册表中保存版本化定义。
- 建设任务写入现有 `state.projects` 并复用 `_settle_projects`；不新建平行的施工状态机。
- 完工将建筑实例及效果实例登记到实际地点。若旧结算代码只读 `prefectures[*].buildings`，适配层要保证兼容并定义唯一权威实体，不双算。
- 工程效果按 operator 的唯一结算步位执行，处理 capacity、维护、折旧、闭市/开市条件、资源上下限和钱粮对手账户；资金流继续经现有守恒函数记账。
- 普通 `fixed_*` 事务只有在绑定了真实 handler 时才可标“告成”；无 handler 的事务应标为“未执行/待支持”，不能只累进度。

### 地点与多项目

- 当前工程接口以 `route` 提交、完工写 `prefectures[route].buildings`。需先确认权威地理表实际包含哪些层级，再制定 `location_id`；不能把 UI 文案或 AI 返回字符串当落点。
- 一道旨意可生成多条工程记录，各自有地点、工期和受阻原因；要求“广州、明州各建一处”就必须生成并追踪两个 project。

### AI 回合推演

- AI 只接收脱敏后的有效行动、工程阶段、当月已计算出的定性指标和阻碍，输出有 schema 的档位/叙事。
- `settlement_*` 按项目与效果实例确定性计算费用、进度、产能、税收/贸易或其他产出；AI 不得决定项目是否凭空完工。
- AI 叙述经来源/数值护栏后作为说明。报告必须引用状态 diff/flow；叙述与程序结果不一致时，以程序结果为准并拒绝不实句。

### 存档与兼容

- `dynamic_blueprints`、行动计划、project/source ids、building/effect instances 使用显式 schema version 序列化。
- 旧存档缺失新字段时初始化空值；动态蓝图定义以快照方式留存在存档，防将来改代码导致旧工程参数漂移。
- 回滚、重试和存档迁移覆盖所有关联状态；重复 action 不可重复扣款或重复建造。

## 前端方向

- 拟旨流程采用“原文 → 逐条行动清单 → 校验/预算/目标地点 → 颁行”文书布局，清楚区分已支持、需补充、未支持；原文仍保留可编辑。
- 多地项目显示为分项工程进度，按“拟议/已拨款/营建中/运行/降效/受阻/作罢”展示，并可查看本月贡献及来源旨意。
- 在办事务只显示执行能力进度；工程/建筑/效果各显示自己的实际状态，避免把“事务推进”误作“建筑落成”。

## 测试策略

- 单元：契约 schema、operator 边界、蓝图生成/拒绝、地点映射、幂等、构件结算、降效与维护。
- 集成：两地多工程、短款/缺料/高动乱、未注册效果拒绝、完成后效果进入下一次规定结算、来源回溯。
- 守恒：每个新资金/粮食构件有对应账户和 `ΣΔ` 断言；失败/回滚零副作用。
- 存档：旧档迁移、新档 round-trip、在建动态蓝图跨版本快照。
- AI 契约：mock 合法/缺字段/越权路径/未注册 operator/幻造地点；不依赖线上模型作为确定性回归。
- 验证阶段按 `sz/AGENTS.md` 执行对应 targeted pytest、前端 tsc/vitest/build；地图不改则不重建舆图。

## 实施前的工作区保护

> **⚠️ 本节清单已过期（2026-10-01 核实）。** 原文列举的 dirty 文件里，**5 个已被全审批次 1–9 改动**
> （`game_state.py` / `save_load.py` / `backend/server.py` / `free_effect.py` / `settlement_tech.py`），
> 且清单外另有 12 个文件被改动。**开工前必须以当前代码为基线重新清点**，
> 逐项确认"需保留的现有行为"，否则极易把已修复项误当他人未提交改动而回退。
> 完整现状表见 [`tasks.md` 的「任务 0（前置）」章节](./tasks.md)。

实现开始前逐一复核 dirty files（原清单：`ai/client.py`、`ai/contracts_decree.py`、`backend/client.py`、`backend/server.py`、`core/commands_decree.py`、`core/free_effect.py`、`core/game_state.py`、`core/save_load.py`、`core/settlement_tech.py`、`frontend/.../DecreePanel.tsx`；其中 `DecreePanel.tsx` 实测 **clean**）。

**已由后续改动覆盖、必须知晓的既有结论**（勿重复劳动、勿回退）：

- `free_effect.py`：`core/free_effect.py` 的兜底已改为**零副作用**（S7）——返回 False 时不再半落地扣款。
- `settlement_tech.py`：研发月费已改**严格通道** ＋ 非有限值留痕（S8）。
- `game_state.py`：`transfer_money` 目的池缺失时不再静默销毁（M3）。
- `save_load.py`：`resources` 已落档（M6）；`faction_split` 两级清洗已修（M7）；识字率缺失存 `None`（O10）。
- `backend/server.py`：隐藏田脱敏（M9）；`_json_safe` 已去双重 `json.dumps`（S10）。
- `settlement_decree.py`（清单外）：一次性诏令已接通 `core.decree_effect` 单点 ＋ 调兵强制施行；
  效果系数 `None` 时**挂起**不执行、留原因与计数（S1）——即本规格 `design.md:47` 的原则
  已在诏令线先行落地。
- `engine/state_applier.py`（清单外）：新增资金类字段必须登记 `VALID_PATHS` / `MONEY_PATHS` /
  `NON_NEG_PREFIXES` 三处，否则受管管线会以"缺来源/负值"整批拒绝（M2 的 `payraise_budget` 即范例）。

只在新基线上继续，不 checkout、不 clean、不覆盖其他 agent 的未提交工作。
