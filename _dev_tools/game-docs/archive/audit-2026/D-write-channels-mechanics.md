# D · 写状态通道与机制模块审查

审查对象：《宋祚 Songzuo》两条受控写状态通道（`engine/state_applier.py`、`core/free_effect.py`）及各机制模块。
方法：只读代码审查 + 一次性脚本实证（脚本全部位于 `D:\codebuddy\sz\_dev_tools\_scratch\audit-2026\`，**未修改 `game/` 下任何源文件**）。
环境：`D:\codebuddy\.audit-venv\Scripts\python.exe`（3.13），`PYTHONPATH=''`，工作区无 `ai_config.json`（真实 LLM 调用返回 `AI_NOT_CONFIGURED` 属预期）。

> 说明：`engine/state_applier.py` 实际为 **884 行**（非任务书所述 802 行）；`core/free_effect.py` 372 行；`core/events.py` 768 行。行号均以实际文件为准。
> 注意：事件触发/清除的实际实现**不在** `core/events.py`，而在 `core/settlement_steps.py::_trigger_event`（:2462）与 `core/commands.py::resolve_event`（:583）；`core/events.py` 只含事件定义与效果换算。

---

## 结论速览

| 编号 | 严重度 | 一句话 | 文件:行 | 证据类型 |
|---|---|---|---|---|
| D-1 | **P0** | `_resolve_path_value` 被注释吞掉，函数已不存在；`_simulate_underflow` 调用它 → **任何钱/粮组 `add` 都抛 `NameError`**，通道①功能性死亡，4 个既有测试红 | `engine/state_applier.py:292,710` | 确认（实跑） |
| D-2 | P1 | `push` 不带 `value` 可把 `prestige`/`mood` 写成 `None`，直接击穿 `evaluate_game`/`check_game_over` | `engine/state_applier.py:94,195,688` | 确认（实跑） |
| D-3 | P1 | `resolve_event` 用 `title in e["message"]` 清除，但 message 存的是 desc → **已处理事件永不清除**；`title=="事件"` 时又误清 `[事件]…` 压力事件 | `core/commands.py:602-607` | 确认（实跑） |
| D-4 | P1 | `_pay_equip_and_grain` 粮饷分发 `per = pay_rem // len(paths)` **丢弃余数**；装备数量取整漂移 → 国库已扣、POP/武库未收，钱凭空销毁 | `core/registries.py:295-303,280-294` | 确认（实跑，LOST 2~18 贯） |
| D-5 | P1 | `era_state.` 在白名单内，但 `settle_era_links` 每月把五维**整体重算**为 `50+建筑贡献` → AI 写入与 `era_migrate` 全部当月被抹平（死写入通道） | `core/era_mechanic.py:79-81` | 确认（实跑） |
| D-6 | P1 | `focus_mechanic` 政务效果无上限、无重置地累加 `waste_reform.savings`（+5000/月/节点），而财政步每月按**全量** savings 冲减常费 → 约 59 个月后 `expenditure` 转负，国库凭空进钱（绕过守恒） | `core/focus_mechanic.py:477-479` | 确认（实跑+代码） |
| D-7 | P1 | `apply_treaty`：`岁币`/`榷场` 未回写 `terms["tier"]` → 关系变化恒 0；**`纳贡` 完全没有分支**（无记录、无效果） | `core/diplomacy_treaty.py:67-87,107` | 确认（实跑） |
| D-8 | P2 | 通配 changes 在容器为空时被**静默丢弃**（`errors=[]`、`applied=[]`），白名单路径形同无效 | `engine/state_applier.py:535-539` | 确认（实跑） |
| D-9 | P2 | 守恒容差 `abs(ΣΔ) > 1` 使单边 `treasury add +1` **无对手方通过** → 每批可铸 1 贯 | `engine/state_applier.py:429` | 确认（实跑） |
| D-10 | P2 | `_pay_cost` 先 `change_granary(-cv)` 再 `_grant_grain`，后者无粮池时直接 return → 太仓粮凭空销毁（与 `_apply_money_delta` 的先判池不对称） | `core/free_effect.py:93-101,225-230` | 确认（实跑） |
| D-11 | P2 | 家产四账**不闭合**：聚敛窖藏 `hoard` 只从家产扣、只加 `coin["shortage"]`，无对手账户 → 实测 Σ(家产+POP) = −4796 | `core/estate_mechanic.py:77-80,99-100` | 确认（实跑） |
| D-12 | P2 | `state.active_events` **仍然无任何上限**（历史未修项仍在），只增不减 | `core/commands.py:606`（唯一清除点） | 确认（grep） |
| D-13 | P2 | `focus_mechanic` 互斥"B7 修复"**未达其声明目的**：各分支入口只有 lv1 节点，同级比较后 lv1 仍锁 lv1，前置链使整支不可达 | `core/focus_mechanic.py:294-310` | 确认（实跑） |
| D-14 | P2 | `core/external_view.py` **全库零调用方**（死模块）；反例：`flow_summary`/`minister_profile` 已由 `backend/server.py` 接线，历史"死代码"怀疑不成立 | `core/external_view.py:1-62` | 确认（grep） |
| D-15 | P2 | `registries`：`TECH_EFFECT_WHITELIST`/`TECH_REGISTRY_MAX`/`BRANCH_POWER_CAP`/`BRANCH_REGISTRY_MAX`/`math` 均为**无引用配置**；`SPECIALIZATION_TIERS[*]["scale"]` 从未被读取；`build_cost` 效果全库无消费者（4 个科技节点的效果是死的） | `core/registries.py:13,16-17,75-81` | 确认（grep） |
| D-16 | P2 | `free_effect` 不校验 `duration`：`"abc"` → `ValueError` 穿透；`-5` → 入队为负 duration | `core/free_effect.py:122-149,331` | 确认（实跑） |
| D-17 | P2 | `applier_pipeline` 对"路径不可写"抛 `KeyError` 而非返回 `rejected`；且 `rejected` 同时承载"已拒绝"与"仅部分被丢弃"的语义 → 调用方无法区分 | `engine/state_applier.py:760-778,798-805,880-884` | 确认（实跑） |
| D-18 | P2 | `era_state.` 前缀匹配使 AI 可在 `era_state` 下**创建任意新键**（无白名单约束） | `engine/state_applier.py:31,109` | 确认（实跑） |
| D-19 | P2 | `apply_to_state` 对非守恒非负字段的穿底**静默截断为 0**（仅 warning 日志），无错误返回 | `engine/state_applier.py:745-749` | 确认（实跑） |
| D-20 | P2 | `NO_CONSERVATION_PATHS = None` 为无引用死常量；`_cascade_farmer_wealth` 注册了规则却恒返空，且其函数体内塞着 `_resolve_path_value` 的不可达残骸 | `engine/state_applier.py:277-283,361` | 确认（AST 分析） |

**总数：P0 × 1，P1 × 6，P2 × 13（共 20 条）**

### 历史修复核实结果（逐条）

| 历史项 | 结论 |
|---|---|
| 写入原子回滚（失败整批不落地） | ✅ **真修好**（实测：坏路径批次 prestige 未被改动） |
| 0-100 区间校验 / set 负值拒绝 | ✅ **真修好**（9999→100；−50 被拒） |
| 守恒补记账只补未配对项 + 末条吃尾差 | ✅ **真修好**（酒课 60/40 实测 ΣΔ=0，任意枚举顺序均精确闭合） |
| 守恒组路径禁 `set`/`mul`/`remove` | ✅ **真修好**（三者均被拒） |
| 通配展开必须在守恒校验之前 | ✅ **真修好**（单边通配被拒、成对通配通过） |
| 穿底预检（P0-6） | ⚠️ **逻辑正确但当前不可达**——依赖已消失的 `_resolve_path_value`（见 D-1） |
| `free_effect` 按净额合计校验成本 | ✅ **真修好**（effects 双出账 + cost 出账 超余额 → 整单拒绝） |
| `free_effect` 暂缓月不递减 duration | ✅ **真修好**（实测 4 个欠费月 duration 恒为 3） |
| `focus_mechanic` 欠费月停摆不推进 | ✅ **真修好**（实测欠费月 elapsed 保持 0） |
| `estate_mechanic` 士绅收租改农 POP 守恒转入 | ✅ 代码为守恒转移；但聚敛窖藏腿仍漏（D-11） |
| `registries` Σ(数量×价) ≈ eq_total | ✅ 金额恒等式成立（10000 人时 diff=0）；但 POP 侧余数漏账（D-4） |
| `_cascade_faction_power` 死代码 | ❌ **删除动作造成严重回归**——见 D-1：删除时把 `def _resolve_path_value` 一并注释掉，且 `tests/test_state_applier.py::test_cascade_faction_power` 仍在测试该规则（现为红） |
| `resolve_event` 的 `title` 缺失致全清 | ⚠️ **未真修好**：`if title:` 只消除了"空标题全清"，谓词仍比对 `message`（存 desc），退化为"永不清除 + 特定标题误清"（D-3） |
| `active_events` 无上限 | ❌ **仍未修**（D-12） |

---

## 详细条目

### D-1 [P0] `_resolve_path_value` 被注释吞掉导致通道①在钱/粮路径上必然 `NameError`

- 位置：`engine/state_applier.py:292`（定义处）、`:710`（致命调用点）、`:677`（潜在调用点）、`:855`（管道调用链）
- 证据：**[确认]** 原文第 292 行：

```python
292: # 已整体移除。def _resolve_path_value(state, path: str):
293:     """按 path 解析状态中的当前值（* 通配返回 None 表示多目标）。"""
294:     if "." not in path:
```

`def` 行被并入了上一行的注释，于是 293–325 行的整个函数体因缩进 4 与上文 `_cascade_farmer_wealth` 的 `return []`（:283）同处一层，被 Python 解析为**该函数体内 `return` 之后的不可达语句**。AST 实证：

```
_cascade_farmer_wealth lineno 278 end 325
   stmt Expr line 279 ; stmt Return line 283 ; stmt Expr line 293 ; stmt If line 294 ...
has _resolve_path_value: False
funcs: [... '_cascade_farmer_wealth', 'apply_cascade', ...]   # 无 _resolve_path_value
```

实测（`_t1_pipeline.py`，合法成对变更）：

```
=== T1: legal paired money change (treasury -1000 <-> 农.wealth +1000) ===
EXCEPTION: NameError name '_resolve_path_value' is not defined
  File "...\engine\state_applier.py", line 855, in applier_pipeline
    under = _simulate_underflow(state, merged)
  File "...\engine\state_applier.py", line 710, in _simulate_underflow
    base = _resolve_path_value(state, path)
NameError: name '_resolve_path_value' is not defined
```

既有测试套件的实测红：

```
$ python -m pytest .../test_state_applier.py .../test_review_p0_conservation.py -q
FAILED test_state_applier.py::test_cascade_faction_power
FAILED test_state_applier.py::test_pipeline_apply_log
FAILED test_state_applier.py::test_pipeline_rejected_collected
FAILED test_state_applier.py::test_underflow_reject_no_mint
4 failed, 27 passed
```

触发条件为 `_simulate_underflow` 第 705 行：`op == "add" and _is_non_neg(path) and _group_of(path) is not None`——即**任何钱组/粮组的 `add`**（`treasury`、`imperial_treasury`、`granary`、各路 POP wealth/grain、`prefectures.*.grain/storage`）都会命中第 710 行。`_apply_op`（:677）的 `_UNSET` 分支同样引用该名字，目前仅因 `apply_to_state` 总是传入 `cur=old` 而未爆发，属潜伏同类炸弹。

- 影响：**通道①在全部经济写路径上功能性死亡**。唯一生产调用方 `ai/client_utils.py:794`（赈济）用裸 `except Exception` 兜底（:810-812），因此表现为"赈济未能落地（状态应用层异常，已拒绝）"——静默失败，不报错。任何 AI 契约中的钱粮变更、任何成对划转、任何守恒补记账路径全部不可用。文件头自称的"铁律：唯一写状态通道"实质失效。同时 `_simulate_underflow`（P0-6 防 clamp 净造币）与 `_apply_op` 的 `mul` None/0 修正全部成为不可达代码——即**守恒体系只剩校验层，写入层与穿底层全灭**。
- 验证方式：
  ```powershell
  $env:PYTHONPATH=''; $env:PYTHONIOENCODING='utf-8'
  Set-Location 'D:\codebuddy\sz\game'
  & 'D:\codebuddy\.audit-venv\Scripts\python.exe' 'D:\codebuddy\sz\_dev_tools\_scratch\audit-2026\_t1_pipeline.py'
  & 'D:\codebuddy\.audit-venv\Scripts\python.exe' -m pytest 'D:\codebuddy\sz\_dev_tools\game-dev\tests\test_state_applier.py' -q
  ```
- 建议修复：把第 292 行的注释与 `def` 分行（`# 已整体移除。` 单独成行，`def _resolve_path_value(state, path: str):` 顶格另起），并同步删除 `_cascade_farmer_wealth` 内的不可达残骸；随后恢复 `tests/test_state_applier.py::test_cascade_faction_power`（该测试期望 `factions.*.power` 的级联规则存在——若确已决定移除，需一并删测试并白纸化决策记录，否则属静默改契约）。

---

### D-2 [P1] `push` 操作符无值写入 `None`，击穿评价与结算

- 位置：`engine/state_applier.py:94`（`OPS` 含 `push`）、`:195-197`（remove 才校验带值，push 无校验）、`:688-689`（`push` 直接返回 value）、`:723-755`（写入无类型校验）
- 证据：**[确认]** 实测（`_t7_push_none.py`）：

```
applied: [('prestige', 55, 'None'), ('prefectures.两浙路.mood', 66, 'None')]
prestige = None  mood = None
evaluate_game RAISED TypeError: unsupported operand type(s) for *: 'NoneType' and 'float'
check_game_over RAISED TypeError: '<' not supported between instances of 'NoneType' and 'int'
```

代码路径：`validate_changes` 只在 `op in ("set","add","mul")` 时要求数值（:181-184），`push` 落在 `elif op == "remove" and value is not None`（:195）之外 → 无值 `push` 合法通过；`apply_to_state` 的钳制均带 `isinstance(new, (int, float))` 守卫（:743、:745），`None` 一律绕过 → 直接落库。

- 影响：AI（或任何走契约的调用方）只需一条 `{"path":"prestige","op":"push","reason":"..."}` 就能把核心数值字段置为 `None`；此后 `evaluation.evaluate_game`、`check_game_over`、`briefing`、UI 全部 `TypeError` 崩溃。`push` 在 `apply_to_state` 中本就等同 `set`（:688-689 直接返回 value，无 append 语义），是**既无实现也未加防护的半成品操作符**。
- 验证方式：`& 'D:\codebuddy\.audit-venv\Scripts\python.exe' 'D:\codebuddy\sz\_dev_tools\_scratch\audit-2026\_t7_push_none.py'`
- 建议修复：二者择一——(a) 从 `OPS` 移除 `push`（当前无任何列表型白名单路径，`push` 无合法语义）；或 (b) 为 `push` 实现真正的追加，并在写入前统一校验 `new` 的类型（数值字段必须为 `int/float`，否则拒绝该条并计入 `errors`）。

---

### D-3 [P1] 事件清除谓词比对错字段：已处理事件永不清除，且存在误清旁路

- 位置：`core/commands.py:602-607`（清除逻辑）；生产者：`core/settlement.py:363`、`core/commands.py:238`、`core/settlement_steps.py:2639`、`core/settlement_steps.py:2466`
- 证据：**[确认]** 清除代码：

```python
602:     # 清除该事件在场标记（审查 P2：title 为空时 `"" not in msg` 恒 False 会清空全部在场事件，
603:     # 故空标题直接跳过清理）
604:     title = event.get("title", "")
605:     if title:
606:         state.active_events = [e for e in state.active_events
607:                                if title not in e.get("message", "")]
```

但所有生产者写入的 `message` 是**描述文本**，不是标题：

```python
# core/settlement.py:363
state.active_events.append({"title": crisis["title"], "message": crisis["desc"], "choices": crisis["choices"]})
# core/commands.py:238
state.active_events.append({"title": ev.get("title", "事件"), "message": ev.get("desc", "")})
# core/settlement_steps.py:2639
state.active_events.append({"title": ev.get("title","风险事件"), "message": _desc, ...})
```

实测（`_t2_events.py`）：

```
BEFORE: ['库藏空虚', '花石纲引发民怨']
AFTER resolve(A): ['库藏空虚', '花石纲引发民怨']
  -> resolved event still present? True

settlement.py:363    title='库藏空虚'      'title in message'=False  would_be_REMOVED=False
commands.py:238      title='花石纲引发民怨'  'title in message'=False  would_be_REMOVED=False
st_steps:2639        title='花石纲民怨沸腾'  'title in message'=False  would_be_REMOVED=False
st_steps:2466        title=''             'title in message'=True   would_be_REMOVED=False
```

反向旁路（`title` 恰为 `message` 子串时误清无关事件）：

```
BEFORE B: ['事件', '库藏空虚']
AFTER resolve(title='事件'): ['库藏空虚']     # [事件] xxx 爆发！被误清
```

`commands.py:238` 的默认标题正是字符串 `"事件"`，而 `_trigger_event`（`settlement_steps.py:2464`）写入的 message 形如 `"[事件] 方腊起义 爆发！"` → `"事件" in ...` 为真。

- 影响：与历史报告描述的"清空全部"**不是同一个 bug**，但同样错误：(1) 玩家处理掉的 `库藏空虚`／风险事件／史实事件**会永久留在 `active_events`**，UI 重复展示、可被反复 resolve（反复结算同一危机，如 `库藏空虚` 每次触发 −2 民心）；(2) 一旦某事件标题为 `"事件"`，同批次所有压力触发的 `[事件] …爆发！` 条目被连带清除，玩家看不到真实危机。历史"修复"（加 `if title:` 守卫）只堵住了 `title==""` 这一条路径。
- 验证方式：`& 'D:\codebuddy\.audit-venv\Scripts\python.exe' 'D:\codebuddy\sz\_dev_tools\_scratch\audit-2026\_t2_events.py'`
- 建议修复：谓词改为按 `title` 匹配且仅移除首个匹配项，例如
  `state.active_events = [e for e in state.active_events if (e.get("title") or "") != title]` 并只弹出第一条；同时在所有生产者处统一写入 `"title"` 与 `"message"`，`_trigger_event` 补 `"title": category`。

---

### D-4 [P1] `_pay_equip_and_grain` 粮饷余数被丢弃：国库已扣、POP 未收

- 位置：`core/registries.py:295-303`（粮饷分发）、`:280-294`（装备折算）、调用点 `:234-235`
- 证据：**[确认]** 分发代码：

```python
295:     # 粮饷入兵 POP（均分各路）
296:     pay_rem = pay_total
297:     paths = list(getattr(state, "prefectures", {}).keys())
298:     if paths and pay_rem > 0:
299:         per = pay_rem // len(paths)
300:         for name in paths:
301:             pops = state.prefectures[name].get("pops", {})
302:             if "兵" in pops:
303:                 pops["兵"]["wealth"] = pops["兵"].get("wealth", 0) + per
```

`per * len(paths)` 一般小于 `pay_rem`（余数被丢），且 `"兵" not in pops` 的路其 `per` 也一并消失。实测（`_t4_free_reg_diplo.py`）：

```
  troops=1:     cost=17.0     pay_total=2     papered_to_pops=0     LOST=2     (n_paths=20, pay_total%n=2)
      eq_total=15.0  Σ(qty×price)=5.0    diff=-10.0  total_out=5.0 vs cost=17.0
  troops=7:     cost=122.0    pay_total=18    papered_to_pops=0     LOST=18
      eq_total=104.0 Σ(qty×price)=106.0  diff=2.0    total_out=106.0 vs cost=122.0
  troops=10000: cost=175393.0 pay_total=26393 papered_to_pops=26380 LOST=13
      eq_total=149000.0 Σ(qty×price)=149000.0 diff=0.0 total_out=175380.0 vs cost=175393.0
  troops=12345: cost=216523.0 pay_total=32583 papered_to_pops=32580 LOST=3
      eq_total=183940.0 Σ(qty×price)=183919.0 diff=-21.0 total_out=216499.0 vs cost=216523.0
```

- 影响：`register_branch` 先 `state.change_treasury(-cost)`（:234），再 `_pay_equip_and_grain` 分配（:235）。实测 `troops=1` 时国库扣 17 贯，只有 5 贯的实物入库、0 贯到兵 POP → **12 贯凭空销毁**；`troops=10000` 时仍漏 13 贯。函数 docstring 自称"守恒：国库 -cost == 军械库装备 + 兵 POP 粮饷"，实际不成立。这正是历史 B5 修复想要达成的恒等式，但修复只覆盖了装备侧金额恒等（该侧确已成立），**POP 侧余数漏账未处理**。小规模招募（如 1~19 人）漏损率可达 100%。
- 验证方式：`& 'D:\codebuddy\.audit-venv\Scripts\python.exe' 'D:\codebuddy\sz\_dev_tools\_scratch\audit-2026\_t4_free_reg_diplo.py'`
- 建议修复：用与 `core/estate_mechanic.py:127-132` / `core/free_effect.py:87-89` 相同的余数归口写法：
  `per, rem = divmod(pay_rem, len(paths))`，前 `rem` 路各 +1；接收方缺失时把该份额退回国库（`state.change_treasury(...)`）或记入中央结算账，不静默丢弃。

---

### D-5 [P1] `era_state.*` 是白名单内的死写入通道；`ERA_TREND_SHIFT` 亦被抹平

- 位置：`engine/state_applier.py:31`（`"era_state."` 白名单前缀）、`core/era_mechanic.py:79-81`（覆盖式重算）
- 证据：**[确认]** `state_applier.VALID_PATHS` 含 `"era_state."`，且 `_path_ok` 对以 `.` 结尾的模式做前缀匹配（:109），故 AI 可写任意 `era_state.<dim>`；但 `settle_era_links` 每月执行：

```python
79:     for d in ERA_DIMENSIONS:
80:         era[d] = max(0, min(100, 50 + contrib.get(d, 0)))
```

实测（`_t5_mech_edges.py`）：

```
  applier applied: [{'path': 'era_state.economy_center', 'old': 50, 'new': 95, ...}]
  era right after applier: 95
  era after one settle_era_links: 50 <- AI write erased
  after era_migrate(+10): 60
  after settle_era_links: 50 <- migrate erased (ERA_TREND_SHIFT dead)
```

模块自身注释（`core/era_mechanic.py:71-78`）已把该冲突记为"已知设计冲突，待产品决策"，但结论是**白名单里的 `era_state.` 条目永不生效**，且 `era_migrate`（`ERA_TREND_SHIFT` ±10）整个机制是死的。
- 影响：AI 一切"时代维度"变更被静默丢弃（`applied` 里还会记一条成功，审计日志与实际实态不一致）；`era_trend`/上行调制 `build_speed_mod` 只能看到建筑贡献决定的值，`era_migrate` 调用方（若存在）全部无效。
- 验证方式：`& 'D:\codebuddy\.audit-venv\Scripts\python.exe' 'D:\codebuddy\sz\_dev_tools\_scratch\audit-2026\_t5_mech_edges.py'`（段 E1）
- 建议修复：按模块注释预留的方案分离基线与建筑贡献——新增 `state.era_base`，`settle_era_links` 计算 `era[d] = clamp(base[d] + contrib[d])`；AI 写入与 `era_migrate` 落在 `era_base`。或（成本更低）从 `VALID_PATHS` 移除 `era_state.`，明确宣告该能力不存在（与 `focus.*` 的处理一致），避免"白名单里存在但永不生效"。

---

### D-6 [P1] 政务国策无上限累加 `waste_reform.savings`，最终使常费转负 → 国库凭空进钱

- 位置：`core/focus_mechanic.py:471-479`（累加）、消费点 `core/settlement_steps.py:2875,2904/2907,2954,2969` 与 `core/game_state_econ.py:226-231`
- 证据：**[确认]** 累加侧：

```python
477:             wr = getattr(state, "waste_reform", None)
478:             if isinstance(wr, dict):
479:                 wr["savings"] = int(wr.get("savings", 0) or 0) + 5000
```

`settle_focus` 对**每个已解锁的政务节点每月调用一次**（`focus_mechanic.py:459-465`），政务分支共 3 个节点 → 最高 +15000/月，**无 `wr["target"]` 上限、无重置**。实测 12 个月：

```
  after 12 months, waste_reform.savings = 60000
```

消费侧 `_settle_finance` 每月按**全量存量**冲减：

```python
2875:     waste_savings = int(wr.get("savings", 0))
2904/2907:  expenditure = MONTHLY_EXP_CIVIL_BASE - waste_savings
2954:     _civil_back = max(0, expenditure)
2969:     total_out = (expenditure + effective_cash_out + ...)
2971:     net = monthly_tax_full - total_out          # → actual_net → 国库
```

`MONTHLY_EXP_CIVIL_BASE = 880000`（实测取得）→ 3 节点满额时约 **59 个月**后 `expenditure < 0`；此后每月的 `actual_net` 被抬高约 15000。注意 `_civil_back = max(0, expenditure)`（:2954）已把回流钳到 0，因此负 `expenditure` **没有任何 POP 对手方**，纯粹是国库凭空进钱——绕过 `state_applier` 与 `free_effect` 两条受控通道。
- 影响：`waste_reform` 的合法路径把 savings 封顶在 `wr["target"]`（`settlement_steps.py:2863`、`:2870`），国策路径无视该上限。长局（1101–1127 共约 324 月）下国库被持续注水，财政评价（`evaluation.py:56-61` 的 `treasury > 10_000_000` 档）与 `deficit_depth` 判据同时失真；`flow_summary` 的收支栏也随之虚高。
- 验证方式：`& 'D:\codebuddy\.audit-venv\Scripts\python.exe' 'D:\codebuddy\sz\_dev_tools\_scratch\audit-2026\_t5_mech_edges.py'`（段 X5）
- 建议修复：政务效果改为"仅提升 `target`"而非直接加 `savings`，例如 `wr["target"] = min(WR_SAVINGS_CAP, wr.get("target",0) + 5000)`，由既有 `_settle_finance` 分段推进到 target；并在 `focus_mechanic` 内尊重 `wr["target"]` 上限，禁止 savings 超过 target。

---

### D-7 [P1] `apply_treaty`：`岁币`/`榷场` 档位键未归一，`纳贡` 完全没有分支

- 位置：`core/diplomacy_treaty.py:66-71`（岁币）、`:73-87`（榷场）、`:88-104`（无纳贡分支）、`:107`（`_att_delta` 调用）
- 证据：**[确认]** 各分支读取的是类型专属键，但从不回写 `terms["tier"]`：

```python
67:         mult = SUI_GONG_MULT.get(str(terms.get("岁币") or terms.get("tier", "停")), 1.0)
74:         tier = str(terms.get("榷场") or terms.get("tier", "开"))
...
107:     delta = _att_delta(type_, terms)      # 内部读 terms.get("tier", "中")
```

而 `_DIPLO_ATT`（实测取得）为：
`{'和亲': {...}, '岁币': {'减':2,'增':-2,'停':-8}, '榷场': {'开':3,'扩':2,'停':-5}, '盟约': {'结':6,'断':-10}, '纳贡': {'献':4,'停':-6}, '战争': {'小':-8,'中':-12,'大':-12}}`
—— 键是 `减/增/停`、`开/扩/停`、`献/停`，**没有 `中`**，故 `table.get("中", 0)` → 0。

实测：

```
  岁币   terms={'岁币': '停'}   -> ok=True attitude_delta=   0 attitude 45->45 treaties=1 cost=0
  岁币   terms={'tier': '停'}   -> ok=True attitude_delta=  -8 attitude 45->37 treaties=1 cost=0
  榷场   terms={'榷场': '开'}   -> ok=True attitude_delta=   0 attitude 45->45 treaties=1 cost=-60000
  榷场   terms={'tier': '开'}   -> ok=True attitude_delta=   3 attitude 45->48 treaties=1 cost=-60000
  纳贡   terms={'纳贡': '献'}   -> ok=True attitude_delta=   0 attitude 45->45 treaties=0 cost=0
  纳贡   terms={'tier': '献'}   -> ok=True attitude_delta=   4 attitude 45->49 treaties=0 cost=0
```

`TREATY_TYPES`（:15）声明支持 `"纳贡"`，`_DIPLO_ATT` 也定义了它，但 `apply_treaty` 的 if/elif 链里**没有 `纳贡` 分支**（:44-104 只有 和亲/岁币/榷场/盟约/战争）→ `state.treaties` 不记录（`treaties=0`），仅由末尾 `_att_delta` 顺带加了一次态度。
- 影响：历史 P2-29 修复（降档后回写 `terms["tier"]`）**只覆盖了 `和亲`**（:56）。代码自身的取值优先级（`terms.get("岁币") or terms.get("tier")`）说明**首选入参形态就是类型专属键**——即 AI 契约的主要调用形态命中 delta=0 分支。后果：停止岁币（`停`，本应 −8 且触发战争风险）零代价；开榷场（本应 +3）零收益；纳贡完全无记录，外交面板与后续 `state.treaties` 消费者看不到该项。这是"白名单/枚举里存在但永不生效"的又一实例。
- 验证方式：`& 'D:\codebuddy\.audit-venv\Scripts\python.exe' 'D:\codebuddy\sz\_dev_tools\_scratch\audit-2026\_t4_free_reg_diplo.py'`（段 D1）
- 建议修复：在每个分支内把归一后的档位写回 `terms["tier"]`（岁币/榷场/纳贡），例如 `terms["tier"] = tier`；并补齐 `elif type_ == "纳贡":` 分支（记录 treaty 条目、按 `_DIPLO_ATT["纳贡"]` 换算）。更稳的做法是让 `_att_delta` 直接接收已归一化的档位参数，避免依赖 `terms` 的隐式约定。

---

### D-8 [P2] 通配 change 在容器为空时被静默丢弃

- 位置：`engine/state_applier.py:511-540`，关键分支 `:535-539`
- 证据：**[确认]**

```python
535:         for k in list(_box.keys()):
536:             if k == "*":
537:                 continue
538:             np = ".".join(k if p == "*" else p for p in parts)
539:             out.append(dict(ch, path=np, reason=f"{ch.get('reason','')}（{k}）"))
```

实测（`_t5_mech_edges.py` 段 E2），`state.legacies = {}`：

```
  applied: []  errors: []      # 变更消失，无任何错误
```

- 影响：容器为空（或键集为空）时该次变更被完全丢弃，`applier_pipeline` 返回 `applied=[]`、`errors=[]`，调用方无法区分"已应用但不产生记录"与"被静默忽略"。白名单路径（`legacies.*.*`、`defense_lines.*.*`、`prefectures.*.*`）在该状态下形同无效。属于"白名单里存在但永不生效"的传播路径。
- 验证方式：同上脚本，段 E2。
- 建议修复：`_box` 为空 dict 时追加一条显式错误（如 `f"通配路径 {path} 无可展开目标（容器为空）"`），而不是静默产出零条。

---

### D-9 [P2] 守恒容差 `> 1` 允许单边小额铸币

- 位置：`engine/state_applier.py:427-435`
- 证据：**[确认]**

```python
427:     for grp, chs in groups.items():
428:         total = sum(_delta_of(c) for c in chs)
429:         if abs(total) > 1:  # 容差 ±1（int 截断）
```

实测（`_t3_channels.py` 段 A）：

```
  [treasury +1 alone (no counterparty)] applied=1 cons_failed=None errs=[]
      treasury 1000000 -> 1000001  (minted 1)
```

`apply_conservation_fix` 同样以 `if abs(total) <= 1: continue`（:564）跳过补记账，故不会救回。
- 影响：每批次可无对手方铸/销 ±1 贯。单次量小，但 AI 每次结算都走通道①即可稳定复利；且容差对"金额"与"计数"混用（`_delta_of` 对 `set` 返回目标值而非增量，:390-399，仅在守恒组已禁 `set` 的前提下侥幸无害）。属守恒校验的真实缺口，而非风格问题。
- 验证方式：`& 'D:\codebuddy\.audit-venv\Scripts\python.exe' 'D:\codebuddy\sz\_dev_tools\_scratch\audit-2026\_t3_channels.py'`
- 建议修复：把容差从"绝对值 1"改为"相对于该组 |Δ| 总量的比例 + 严格取整校验"，或对整数贯/石直接要求 `round(total) == 0`；并对 `_delta_of` 显式区分"增量"与"目标值"语义。

---

### D-10 [P2] `_pay_cost` 在民间无粮池时把太仓粮凭空销毁

- 位置：`core/free_effect.py:93-101`（`_grant_grain`）、`:225-230`（`_pay_cost` 的 granary 分支）、对照 `:63-90`（`_apply_money_delta`）
- 证据：**[确认]** 不对称的两个实现：

```python
 63: def _apply_money_delta(state, d: int) -> None:
 68:     pools = _money_pools(state)
 69:     if not pools:
 70:         return                      # ← 先判池，未改国库
 ...
 83:         state.change_treasury(d)
```

```python
 93: def _grant_grain(state, amount: int) -> None:
 95:     pools = _grain_pools(state)
 96:     if not pools:
 97:         return                      # ← 无粮池直接返回
```
```python
226:             if getattr(state, "granary", 0) < cv:
227:                 continue
228:             state.change_granary(-cv)     # ← 已在 return 之前扣减
229:             _grant_grain(state, cv)
```

实测（`_t5_mech_edges.py` 段 F7），清空全部 POP 的 `grain` 键后：

```
  grain pools: 0
  granary 500000 -> 499000  log=['耗太仓1000石（粜济民间）']   (destroyed, no recipient)
```

- 影响：太仓 −1000 石而无任何接收方，粮凭空销毁，且日志仍声称"粜济民间"。真实 `GameState` 下 6 阶层均有 `grain` 键（实测 20 路 × 6 = 120 池），故当前不触发；但一旦某存档/迁移版本缺少粮键即静默漏账。同一函数的钱侧已用"先判池"规避，粮侧漏掉了这一步——属修复不对称导致的残留。
- 验证方式：`& 'D:\codebuddy\.audit-venv\Scripts\python.exe' 'D:\codebuddy\sz\_dev_tools\_scratch\audit-2026\_t5_mech_edges.py'`（段 F7）
- 建议修复：把 `_grant_grain` 的池检查前移到扣减之前（与 `_apply_money_delta` 一致）：无池则整条 cost 视为不可承受，不扣 `granary`；或让 `_grant_grain` 返回实际发放额，`_pay_cost` 只用该额扣减。

---

### D-11 [P2] 家产四账不闭合：聚敛窖藏的钱没有对手账户

- 位置：`core/estate_mechanic.py:76-80`（扣减）、`:99-100`（唯一去向）、模块自述 `:12-14`
- 证据：**[确认]**

```python
 77:         hoard = int(growth * EF["hoard_rate"]) if _hoard_leaning(state, name) else 0
 78:         if hoard > 0:
 79:             e["wealth"] = max(0, e["wealth"] - hoard)
 80:             hoard_total += hoard
 ...
 99:     if hoard_total > 0:
100:         state.coin["shortage"] = min(0.95, state.coin.get("shortage", 0.3) + hoard_total / 100_000_000.0)
```

`hoard_total` 除抬高 `coin["shortage"]` 外**没有任何账户接收**。实测（`_t5_mech_edges.py` 段 X6）：

```
  estate 1000000->1001034 (delta 1034)  pops delta=-5830  treasury delta=0
  result={'luxury': 10159, 'rent': 0, 'hoard': 4796}
  SUM(estate+pops)=-4796   <- hoard vanished
```

（`luxury` 腿是守恒的：`_distribute_luxury` 的余数归口已修，`Σ` 精确等于 `amount`。）
- 影响：模块 docstring 明确声称"**四账闭合**：国库-投入 + 内帑-投入 + 回报 + 截留与家产/产出 Σ 变化守恒"以及 `settle_minister_estate` 的"守恒：来源-去向差为 0"。实测家产 + POP 合计每轮净损 4796 贯，即"聚敛窖藏"把货币从世界抹除。可能是有意的通缩设计（制造钱荒），但与模块自述口径矛盾，且会使远期货币总量单调下滑、与 `coin["shortage"]` 的意图重复计一次。
- 验证方式：`& 'D:\codebuddy\.audit-venv\Scripts\python.exe' 'D:\codebuddy\sz\_dev_tools\_scratch\audit-2026\_t5_mech_edges.py'`（段 X6）
- 建议修复：给窖藏一个真实对手账户（如新增 `state.hoarded_wealth`，或计入该大臣家产下的 `cellar` 子账并允许抄没时一并入国库），使 Σ 归零；若确为有意的货币销毁，须在 docstring 与守恒清单中显式豁免并说明，勿与"四账闭合"并列表述。

---

### D-12 [P2] `state.active_events` 仍然无上限（历史未修项仍在）

- 位置：`core/commands.py:606`（唯一清除点）、写入点 `core/settlement_steps.py:2466`、`core/settlement.py:363`、`core/settlement_steps.py:2639`、`core/commands.py:238`；存档 `core/save_load.py:122,413`
- 证据：**[确认]** 全库 grep 结果（`Get-ChildItem -Recurse -Include *.py | Select-String 'active_events'`）显示仅 `commands.py:606` 一处做列表裁剪，且如 D-3 所述该裁剪**在正常路径上恒不清除任何条目**。没有任何 `[-N:]`、`len(...) > N` 之类的上限逻辑。

```
core/commands.py:606: state.active_events = [e for e in state.active_events
core/settlement.py:363: state.active_events.append({"title": crisis["title"], ...})
core/settlement_steps.py:2466: state.active_events.append({...})
core/settlement_steps.py:2639: state.active_events.append({"title": ev.get("title", "风险事件"), ...})
core/commands.py:238: state.active_events.append({"title": ev.get("title", "事件"), ...})
```

- 影响：与 D-3 叠加 → 事件条目单调累积；`_trigger_event` 每次 `event_pressure` 过阈值都追加一条且不回查（压力归零后同类别可反复触发），长局中该列表与存档（`save_load.py:122`）无界增长；`ai/narrative_guard.py:120` 与 `backend/server.py:253` 读取时也会随规模变慢。历史报告列为"未修项"，本次核实**仍在**。
- 验证方式：`Set-Location 'D:\codebuddy\sz\game'; Get-ChildItem -Recurse -Include *.py -File | Select-String -Pattern 'active_events'`
- 建议修复：在 `commands.resolve_event` 与 `settlement_steps._trigger_event` 落库处统一加裁剪（如保留最近 50 条并去重 `category`/`title`）；`_trigger_event` 追加前先查同 `category` 是否在场。

---

### D-13 [P2] 国策互斥"B7 修复"未达其声明目的：整支仍不可达

- 位置：`core/focus_mechanic.py:294-310`（互斥判定）、`:288-293`（前置链）、定义 `:26-104`
- 证据：**[确认]** 修复逻辑按 `power_level` 比较：

```python
297:     mutex = MUTUAL_EXCLUSIVE.get(branch)
298:     if mutex:
299:         my_lv = int(node_spec.get("power_level", 0) or 0)
...
307:             if _other_lv >= my_lv:
308:                 return False, (f"与「{mutex_spec.get('name', mutex)}」分支互斥...")
```

实测（`_t6_mutex.py`，`active_focus=None` 以排除"在办大策"分支）：

```
  can_unlock govern/g1_centralize: (False, '与「军事」分支互斥（已成就同级或更高大策）')   # m1 lv1 vs g1 lv1
  can_unlock govern/g2_reform:     (False, '需先功成「中央集权」')                      # 被前置链挡
  can_unlock military/m2_fortify:  (True, '')
  can_unlock military/m3_war_machine: (False, '需先功成「修城固垒」')
```

每个分支的**唯一入口节点都是 `prereq: None` 的 lv1 节点**（`g1_centralize`/`m1_garrison`/`s1_tech`/`i1_spy`/`t1_land_survey`，皆 `power_level: 1`）。`>=` 使 lv1 互锁 lv1，而 lv2/lv3 必须经 lv1 前置 → 一旦对侧解锁任一节点，本方**整支**（含 lv2/lv3）永久不可达。
- 影响：修复后错误文案从"任意解锁即整支锁死"变为"已成就同级或更高大策"，但**可达性结论完全等价**于修复前的行为；`power_level` 比较只在高等级节点之间存在可观测差异（本分支 lv2 可解锁，但因不同分支 lv1 互斥而实际到不了）。声称已修的问题在行为层未修。
- 验证方式：`& 'D:\codebuddy\.audit-venv\Scripts\python.exe' 'D:\codebuddy\sz\_dev_tools\_scratch\audit-2026\_t6_mutex.py'`
- 建议修复：明确互斥语义：若意图是"两分支只能择一深耕"，应改为 `if _other_lv > my_lv or (branch_has_any_unlocked(mutex) and my_lv == 1)` 并把规则写进 UI 文案；若意图是"仅高等级节点互斥"，则应改 `>` 并给 lv1 节点加豁免（`my_lv <= 1` 时跳过互斥），使两侧低阶节点都能开。

---

### D-14 [P2] `core/external_view.py` 全库零调用方（死模块）；附带澄清两个历史怀疑为误报

- 位置：`core/external_view.py:1-62`（整模块）
- 证据：**[确认]** 全库（含 `*.ts/*.tsx/*.json`）grep：

```powershell
Get-ChildItem -Recurse -Include *.py,*.ts,*.tsx,*.json -File |
  Select-String -Pattern 'external_view|external_pop_view|external_provinces|flow_summary|minister_profile'
```

命中中与本模块相关的**只有它自身的定义与 docstring**（`external_view.py:4,6,8,11,36,44`）；`external_pop_view` / `external_provinces` 无任何外部引用（grep 里的 `external_provinces` 命中实为 `content/data.py:1158 external_provinces_of` 与 `game_state.py:577` 的调用，属**另一个**函数）。反例（历史怀疑不成立）：

```
backend\server.py:459: from core.flow_summary import build_flow_summary
backend\server.py:483: from core.minister_profile import build_minister_profiles
```

`flow_summary`（HTTP `/api/readouts` 财务栏，前端 `AccountingPanel.tsx:219` 消费）与 `minister_profile` 均已接线——**不应再报为死代码**。`core/errors.py::AIRuntimeError` 亦被广泛使用（`ai/client.py`、`core/commands.py`、`core/commands_decree.py`、`core/async_ai.py`），非死代码。
- 影响：`external_view` 为纯展示层死模块；其 `external_provinces` 的尾差归口逻辑（:50-59）目前正确（实测 `EXTERNAL_PROVINCES` 三势力权重和均为 1.0，`_EXTERNAL_PROVINCES_DEFAULT = [("本部", 1.0)]`），但无消费者 → 外交面板实际用的是 `game_state.external_provinces_of` 一套，存在**两套平行派生实现**的漂移风险（与模块头部"平行白名单长期必然漂移"的教训同类）。
- 验证方式：上述 grep 命令。
- 建议修复：删除 `core/external_view.py`，或把它接到 `backend/server.py` 的外交面板出口并删掉 `game_state` 内的重复实现；同时更新历史分析文档中关于 `flow_summary`/`minister_profile` 为死代码的结论。

---

### D-15 [P2] `registries` 中多个配置/常量无任何引用；`build_cost` 效果全库无消费者

- 位置：`core/registries.py:13`（`import math`）、`:16-17`（`BRANCH_POWER_CAP`,`BRANCH_REGISTRY_MAX`）、`:75-81`（`TECH_REGISTRY_MAX`,`TECH_EFFECT_WHITELIST`）、`:154-162`（`SPECIALIZATION_TIERS[*]["scale"]`）、`:285-286`（`build_cost` 空分支）
- 证据：**[确认]** grep：

```
content\data.py:1673: BRANCH_POWER_CAP = 1.8
content\data.py:1675: BRANCH_REGISTRY_MAX = 3
core\registries.py:16:  BRANCH_POWER_CAP,          # 仅 import，函数体内无引用
core\registries.py:17:  BRANCH_REGISTRY_MAX,       # 仅 import
core\registries.py:75: TECH_REGISTRY_MAX = 12      # 定义后无引用
core\registries.py:77: TECH_EFFECT_WHITELIST = (...)  # 定义后无引用
```

`register_node` 调用的是 `sanity_effect(effect)`（:108），**完全没有传入/校验 `TECH_EFFECT_WHITELIST`**，故 docstring 宣称的"效果字段白名单（玩家注册节点可声明：既有效果键）"是失效配置——玩家注册节点可声明任意效果键。`SPECIALIZATION_TIERS` 的 `"scale"` 字段：全库搜索显示只有 `registries.py:155-161` 的定义，`_pay_of`（:171-185）只读 `dims`；`BRANCH_POWER_CAP`（"战力 ≤1.8×"）无实现。`build_cost` 的消费者：

```python
core\asset_context.py:285:         if effect.get("build_cost"):
core\asset_context.py:286:             pass  # build_cost 由工程结算统一读取资产汇总
```

其余命中均为 data 定义、前端标签与 `registries` 白名单字符串。`content\data.py:1950,1951,1960,1994` 有 4 个科技节点声明 `build_cost` 效果（实测 `TECH_NODES with build_cost effect: 4`），`resolve_asset_effect`/`CAPABILITY_EFFECTS` 也定义了 `build_cost`（`:1914,1919,1920`），但**没有任何代码读它来降低营造费**。
- 影响：三类"白名单/上限/乘数配置存在但永不生效"：科技注册节点效果字段无约束（AI 可声明任意键，`sanity_effect` 只做量级软降档）、新兵种战力上限 `BRANCH_POWER_CAP=1.8` 与注册上限 `BRANCH_REGISTRY_MAX=3` 未落实、`build_cost` 是 4 个科技节点的死效果。与任务关注的"白名单里存在但永不生效"同类，且属可验证的配置漂移。
- 验证方式：上述 grep 命令 + `& 'D:\codebuddy\.audit-venv\Scripts\python.exe' 'D:\codebuddy\sz\_dev_tools\_scratch\audit-2026\_t5_mech_edges.py'`（段 X2）
- 建议修复：给 `register_node` 的白名单校验接上 `TECH_EFFECT_WHITELIST`（拒绝或降档非白名单键），或在代码中删除该常量并修正 docstring；实现或删除 `BRANCH_POWER_CAP`/`BRANCH_REGISTRY_MAX`/`SPECIALIZATION_TIERS["scale"]`；为 `build_cost` 补上营造费消费者，或从 4 个节点与 `CAPABILITY_EFFECTS` 中移除。

---

### D-16 [P2] `free_effect` 未校验 `duration`：字符串抛异常、负值入队

- 位置：`core/free_effect.py:122-149`（`validate_free_effect` 无 duration 校验）、`:331`（无保护 `int()`）
- 证据：**[确认]** 实测（`_t4_free_reg_diplo.py` 段 F5）：

```
  RAISED ValueError: invalid literal for int() with base 10: 'abc'
  duration=-5 queued as: [('自由制度', -5)]
```

```python
331:             "duration": int(contract.get("duration", 12)),
```

`validate_free_effect` 只校验 `mode`/`effects`/`cost`（:126-148），`name` 与 `duration` 完全未验。`duration=-5` 入队后：`_settle_free_effects`（:358-371）中 `dur == 0` 为假、`applied` 为真时 `dur -= 1 → -6`，`elif dur > 0` 为假 → 直接"到期核销"（实际是入队当月即被丢弃，只是没报错）；若 `applied` 恒为假则该项**永久滞留**。
- 影响：一条畸形契约（`duration` 非数字）会让 `_apply_free_effect` 抛 `ValueError` 穿透到调用方；负值 duration 使"长期制度"生命周期语义失效。属"数值边界/类型校验缺失"类真实缺陷（不是风格问题）。
- 验证方式：`& 'D:\codebuddy\.audit-venv\Scripts\python.exe' 'D:\codebuddy\sz\_dev_tools\_scratch\audit-2026\_t4_free_reg_diplo.py'`
- 建议修复：在 `validate_free_effect` 中加 `duration` 校验（须为 0~N 的整数，0=永久），并在 `_apply_free_effect` 用 `try/except (TypeError, ValueError)` 兜底拒绝。

---

### D-17 [P2] `applier_pipeline` 的失败语义含糊：不可写路径抛异常，`rejected` 同时承载两种含义

- 位置：`engine/state_applier.py:760-778`（`apply_to_state` 抛 `KeyError`）、`:798-805`（逐条验证错误进 `errors` 但仍继续应用其余）、`:835-851`（守恒失败返回 `rejected`）、`:880-884`（返回值同时含 `applied` 与 `rejected`）
- 证据：**[确认]** 实测（`_t3_channels.py` 段 H/I）：

```
  [set prefectures.不存在路.mood=50] RAISED KeyError: '状态路径不可写（中间层缺失）: prefectures.不存在路.mood'
=== I. atomicity: batch with one unwritable path ===
      RAISED KeyError: '状态路径不可写（中间层缺失）: prefectures.不存在路.mood'
      prestige 55 -> 55 (unchanged => rolled back)  treasury 1000000->1000000
```

回滚本身**正确**（原子性历史项确实修好）；问题在于失败以异常而非 `{"applied": [], "rejected": [...]}` 形式逸出——与守恒失败路径（:835-851 返回字典）语义不一致。另外 `validate_changes` 的错误只丢弃**单条**变更（:802-805 `errors.extend(errs)` 后仍把 `valid` 加入 `all_valid`），于是最终返回值可能同时有 `applied=[...]` 与 `rejected=[...]`（:880-884）。
- 影响：管道契约不稳定——同一"该批不落地"的语义有时是返回值、有时是异常。当前唯一生产调用方 `ai/client_utils.py:810-812` 用裸 `except Exception` 兜住，用户看到的是"状态应用层异常，已拒绝"（不可归因）；其他未来调用方若只检查 `conservation_failed` 就会把"部分变更被丢弃"误判为完全成功。
- 验证方式：`& 'D:\codebuddy\.audit-venv\Scripts\python.exe' 'D:\codebuddy\sz\_dev_tools\_scratch\audit-2026\_t3_channels.py'`
- 建议修复：把 `_set_path`/`apply_to_state` 的路径不可写也转为 `{"applied": [], "rejected": errors, "conservation_failed": True}` 形式的返回（或在 `applier_pipeline` 内 try/except 统一转换）；并把 `rejected` 拆成 `rejected`（整批未落地）与 `dropped`（单条被丢弃）两个字段。

---

### D-18 [P2] `era_state.` 前缀匹配允许创建任意新子键

- 位置：`engine/state_applier.py:29-54`（白名单）、`:101-117`（`_path_ok`）、`:631-657`（`_locate_path`）
- 证据：**[确认]** `_path_ok` 对 `pat.endswith(".")` 做前缀匹配（:109-110），`"era_state."` 因此放行任意后缀；`_locate_path` 对 dict 容器的未存在键返回 `(dict, key, False, None)`（:655-656），`apply_to_state` 随即创建该键（:752-753）。实测（`_t3_channels.py` 段 F）：

```
  [era_state.任意新键 set 42] applied=1 cons_failed=None errs=[]
      era_state keys: ['commerce','culture','economy_center','military','urban','任意新键']
```

- 影响：AI 可在 `era_state` 下注入任意键值（无枚举、无类型、无范围校验），污染该 dict 的所有遍历方（`era_brief` 按 `ERA_DIMENSIONS` 取，尚不受影响；但存档、UI 直出与 `era_trend` 的 `.get(dim, 50)` 默认值语义会被新键稀释）。属白名单粒度问题：`era_state.` 是唯一使用前缀通配的条目，其余全部是按段的 `*` 通配。
- 验证方式：`& 'D:\codebuddy\.audit-venv\Scripts\python.exe' 'D:\codebuddy\sz\_dev_tools\_scratch\audit-2026\_t3_channels.py'`
- 建议修复：把 `"era_state."` 替换为按维度的显式条目（`era_state.economy_center` 等 5 条，见 `content.data.ERA_DIMENSIONS`），使 `_path_ok` 走段匹配、拒绝新键。

---

### D-19 [P2] 非守恒非负字段穿底静默截断为 0，无错误返回

- 位置：`engine/state_applier.py:693-720`（`_simulate_underflow` 的豁免条件 `:705`）、`:745-749`（静默截断）
- 证据：**[确认]** 实测（`_t3_channels.py` 段 K）：

```
  [defense_lines.X.garrison add -999999] applied=1 cons_failed=None errs=[]
      garrison now: 0
```
stderr：`apply_to_state 非负截断：defense_lines.北线_太原真定.garrison add→0（old=130000）`

代码（:705）刻意把非守恒字段排除出穿底预检，理由是"减少到 0 只是数值钳制，不破坏守恒"；落库时（:745-749）仅 `log.warning` 后 `new = 0`，`applied` 记录里写的却是 `new=0`（与实际钳制后一致，这点是对的），但**调用方拿到的是"成功应用"**。
- 影响：单条 `add -999999` 可把边防守军从 13 万一次性清零，而 `applier_pipeline` 返回 `applied=[...]`、`errs=[]`。灾难以外的场景（AI 误用大负数）不会被任何一层拦截。审计日志记录的 `old→new` 是 130000→0，掩盖了"请求增量 −999999 被截断"这一事实。
- 验证方式：`& 'D:\codebuddy\.audit-venv\Scripts\python.exe' 'D:\codebuddy\sz\_dev_tools\_scratch\audit-2026\_t3_channels.py'`
- 建议修复：在 `applied` 记录里标注 `clamped: True` 与原始目标值；或对非守恒非负字段也返回一条 warning 级错误，使调用方可感知钳制幅度。

---

### D-20 [P2] `NO_CONSERVATION_PATHS` 死常量；`_cascade_farmer_wealth` 空规则体内藏着不可达残骸

- 位置：`engine/state_applier.py:277-283`（注册但恒返空的级联规则）、`:361`（`NO_CONSERVATION_PATHS = None`）、`:293-325`（残骸）
- 证据：**[确认]** AST 实证（`_probe2.py`）显示 `_cascade_farmer_wealth` 的 `lineno 278 → end_lineno 325`，其 body 依次为 `Expr(279) / Return(283) / Expr(293) / If(294) / ... / Return(325)`——`return []` 之后的 6 条语句全部不可达，正是 D-1 中被吞掉的 `_resolve_path_value` 函数体：

```
_cascade_farmer_wealth lineno 278 end 325
   stmt Expr line 279
   stmt Return line 283       # return []  ← 之后全不可达
   stmt Expr line 293
   stmt If line 294
   ...
   stmt Return line 325
```

`NO_CONSERVATION_PATHS = None`（:361）在文件内除注释外无任何引用（含 `_group_of`，其逻辑是"未命中即豁免"，:377-385），属声明式死常量（注释已自认"死代码消除"却仍留了赋值）。
- 影响：本身不改变行为，但它是 D-1 的病根所在：一处"删除死代码"的编辑把注释与 `def` 挤到同一行，静默删除了生产函数，并使 30 行残骸长期驻留在一个被注册的级联钩子里。该文件已无 lint/AST 守卫（`ast.parse` 通过、模块可导入、只有运行到经济路径才炸），说明"删除死代码"类改动缺乏最小验证。
- 验证方式：`& 'D:\codebuddy\.audit-venv\Scripts\python.exe' 'D:\codebuddy\sz\_dev_tools\_scratch\audit-2026\_probe2.py'`
- 建议修复：清理 `_cascade_farmer_wealth` 内不可达残骸并恢复 `_resolve_path_value`；删除 `NO_CONSERVATION_PATHS`；并把 `unused-variable`/`undefined-name` 检查（如 `python -m pyflakes`）纳入 CI —— 本次 D-1 与 D-15/D-20 的多个未引用名字本可被静态检出。

---

## 附：本次实证脚本清单

| 脚本 | 覆盖 |
|---|---|
| `_probe1.py` | AST 函数清单、`compile()` 通过性 |
| `_probe2.py` | `_cascade_farmer_wealth` body 行号展开、`hasattr(sa,'_resolve_path_value')==False` |
| `_t1_pipeline.py` | D-1 最小复现（合法成对钱粮变更 → NameError） |
| `_t2_events.py` | D-3/D-12：两个 active_events 后 resolve 一个；生产者形态逐一比对 |
| `_t3_channels.py` | D-9/D-18/D-19/D-17/D-2 之外的通道行为（含 set/mul/remove 拒绝、通配守恒、酒课补记账 Σ=0、原子回滚、穿底预检） |
| `_t4_free_reg_diplo.py` | D-4/D-7/D-16 及 free_effect 白名单/净额校验/守恒配对 |
| `_t5_mech_edges.py` | D-5/D-6/D-8/D-10/D-14/D-15：era 死写入、空容器丢变更、粮池销毁、焦点欠费停摆、评价、资产钩子 |
| `_t6_mutex.py` | D-13 国策互斥可达性；`_complete_focus` 空树静默丢失 |
| `_t7_push_none.py` | D-2 `push` 无值写入 `None` → `evaluate_game`/`check_game_over` TypeError |

另跑：`pytest test_state_applier.py test_review_p0_conservation.py -q` → `4 failed, 27 passed`。
