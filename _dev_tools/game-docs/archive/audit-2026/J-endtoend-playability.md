# J · 端到端可玩性实测

- 项目根：`D:\codebuddy\sz\game`（《宋祚》北宋徽宗治国模拟器）
- 解释器：`D:\codebuddy\.audit-venv\Scripts\python.exe`（Python 3.13）
- 审计脚本目录：`D:\codebuddy\sz\_dev_tools\_scratch\audit-2026\`（**未改动 `game/` 与 `_dev_tools/game-dev/tests/` 下任何文件**）
- 接线方式：真实 `core.commands` 管线（`new_game` → `advance_and_settle` → `settle_local` / `finish_turn`）+ `tests/fake_ai_backend.FakeAIClient` 派生替身，替身 `dialogue()` 复刻 `ai/client.py:1007-1038` 的「AI 返回 tool_calls → 程序端 `_tool_dispatch` 执行 → 二次回奏」真实路径。所有 `game/` 侧观测均为进程内 monkeypatch（取证后原样抛出/返回），零源文件改动。

---

## 一、结论（能否正常游玩 + 阻断项）

**结论：在「AI 已正确配置」的前提下，回合制主干可以跑通、不崩、不脏档，可玩；但在本工作区（无 `ai_config.json`）一回合都推进不了；且「AI 结构化 changes 落库」这条被文档宣称为主通道的能力，在生产回合里实际只挂在召对赈济一个工具上，而该工具因 P0 必然失败——即「AI 改状态」这条主线当前整体不可用。**

**能否正常游玩（分场景）：**

| 场景 | 判定 | 依据 |
|---|---|---|
| 本工作区现状（无 `ai_config.json`） | **不可玩** | `advance_and_settle` → `AIRuntimeError: 未接入 AI…`，回合不推进（状态完整回滚）。设计为强制 AI（`core/commands.py:247-274`） |
| AI 已配置 + 只走 12 步结算/圣旨/召对叙事 | **可玩** | 4 组 24 回合 + 1 组 60 回合实测：0 异常、0 NaN、无负数国帑、无死锁、无脏档 |
| AI 已配置 + 大臣使用赈济办差（`relief_grant`） | **不可用** | P0：`NameError` → 整批 changes 丢弃、玩家可能看到「臣已发赈济」而国帑/民心分文未动 |
| 长局（≥36 回合）数值健康 | **不健康** | 货币总量净增（+0.52M/月）、`active_events` 无上限累积、内帑 60 回合涨 106 倍 |

**阻断项（P0）：**
1. `engine/state_applier.py` 的 `_resolve_path_value` 函数体被吞进 `_cascade_farmer_wealth`（`def` 行在 `:292` 被注释），任何**钱/粮组 `add`** 的 changes 批次一律 `NameError`，整批丢弃且 `rejected` 为空。
2. 程序侧**没有**「叙事文本 ↔ 数值变化」一致性护栏：工具回执虽已回传给 AI，但 AI 若回奏「已办妥」而无任何程序侧拦截——实测可稳定复现「叙事说办了、数值没动」。

---

## 二、P0 影响面验证（AI changes 落库情况 / 玩家可见表现 / 是否欺骗性成功）

### 2.1 结论速览

| 问题 | 答案 | 证据 |
|---|---|---|
| changes 是整批丢弃，还是降级/静默忽略/记入 `rejected`？ | **整批丢弃**；`rejected` **为空**（异常在 `_simulate_underflow` 抛出，早于任何 `rejected` 汇总路径） | V2/V3/V4 实测 `applied=0 rejected=0 state_changed={}` |
| 玩家看到什么？ | 工具回执为 `赈济未能落地（状态应用层异常，已拒绝）`（**诚实的程序文案**），但：① 该文案只回到 AI 上下文，**不是弹窗**；② 大臣回奏（=玩家实际看到的叙事）完全由 AI 决定；③ **`minister_memory` 与记忆图谱仍记为已办** | 实测工具回执 + `minister_memory={'郑居中': ['赈 两浙路']}` + 图谱边 `promises` |
| 是否欺骗性成功？ | **存在且可稳定复现**（属"模型是否诚实"依赖，非程序拦截）。同一输入下：说谎脚本 → 「叙事称已办·数值未动」；诚实脚本 → 「赈济未能落地，臣不敢妄称已办」 | 见 2.4 对照实验 |
| 结算/回合推进是否中断？ | **不中断**。`applier_pipeline` 在生产中**只有** `ai/client_utils.py:793` 一个调用点（召对赈济），不在 `advance_month`/12 步结算路径上；异常被 `_tool_dispatch` 就地捕获 → 本月照常结算 | 4 组 24 回合 + 1 组 60 回合：`advance_and_settle` 抛异常次数 = **0**；`applier_pipeline` 调用次数 == 召对次数 |
| 哪些 AI 契约恰好还能落地（更隐蔽）？ | **只含非守恒字段的批次能落地**（`prestige` / `population_satisfaction` / `factions.*.satisfaction|influence` / `prefectures.*.mood|refugees`…）；**混合批（豁免字段 + 钱/粮 add）连合法字段一并作废** | V1/V8/V9 applied=2/1/2；V4 混合批 applied=0 |

> 结构性问题（[确认]，独立于 P0 本身）：`engine/state_applier.py:10-15` 文档称本模块是"AI 契约 changes → 校验/守恒/落库"的唯一应用层入口，但全库 `applier_pipeline` 调用点只有 `ai/client_utils.py:793`（`relief_grant` 工具）。正常回合的 AI 输出走的是 `_economy_ai`/`_military_ai` 等**槽位 → 12 步结算**（`core/settlement_steps.py`），**不经过 state_applier**。因此 P0 不影响月度结算，但也意味着"AI 可以直接改状态"这条主线除赈济外全是死通道。

### 2.2 静态与 AST 取证

```
[静态] hasattr(state_applier, '_resolve_path_value') = False
[静态] 被注释掉的 def 行号 = 292: # 已整体移除。def _resolve_path_value(state, path: str):
[AST ] module-level `def _resolve_path_value` present: False
[AST ] _cascade_farmer_wealth: lines 278-325, body stmts = 8
       line 279  Expr     '农 wealth 变化 → 微调役钱可征…'
       line 283  Return   return []            ← 函数在此返回，其后代码全为不可达
       line 293  Expr     '按 path 解析状态中的当前值…'   ← 被吞的 _resolve_path_value 函数体
       line 294..311..325  If/Assign/Return
[AST ] _simulate_underflow body references _resolve_path_value: True   调用行: [710]
[AST ] _apply_op         body references _resolve_path_value: True   调用行: :677（经 apply_to_state 传 cur 参数 → 生产不可达）
```

`applier_pipeline:855` 无条件调用 `_simulate_underflow`：

```
Traceback (most recent call last):
  File ".../j_p0.py", line 29, in _call
    r = sa.applier_pipeline(state, agent_changes)
  File "D:\codebuddy\sz\game\engine\state_applier.py", line 855, in applier_pipeline
    under = _simulate_underflow(state, merged)
  File "D:\codebuddy\sz\game\engine\state_applier.py", line 710, in _simulate_underflow
    base = _resolve_path_value(state, path)
NameError: name '_resolve_path_value' is not defined
```

### 2.3 变体矩阵（实测）

| 变体 | 输入（摘要） | 异常 | applied | rejected | 状态是否变化 |
|---|---|---|---|---|---|
| R1 用户最小复现 | `treasury +100000` ↔ `两浙路商人wealth -100000`（钱组闭合） | **NameError** | 0 | **0** | 无 |
| V1 仅非守恒字段 | `prestige +3`、`population_satisfaction set 60` | 无 | **2** | 0 | satisfaction 55→60、prestige 55→58 |
| V2 钱组闭合 add | `treasury +5000` ↔ `京畿路农wealth -5000` | **NameError** | 0 | 0 | 无 |
| V3 粮组闭合 add | `granary +1000` ↔ `京畿路storage -1000` | **NameError** | 0 | 0 | 无 |
| V4 混合批 | `prestige +5` **+** `treasury +7000` ↔ `商人wealth -7000` | **NameError** | 0 | 0 | 无（连合法 prestige 一并作废） |
| V5 钱组 set | `treasury set 9000000` | 无 | 0 | **1** | 无（守恒层可读拒绝，对照） |
| V6 单边 treasury add（reason 无关键词） | `treasury -50000` | 无 | 0 | **1** | 无（守恒层可读拒绝，对照） |
| V7 单边 treasury add（reason=俸禄→补记账） | `treasury -50000, reason=俸禄` | **NameError** | 0 | 0 | 无 |
| V8 非守恒非负字段 | `两浙路refugees add -3000`（现值 440） | 无 | **1** | 0 | 440→**0**（实际只减 440，增量被静默截断，仍记 applied） |
| V9 豁免字段 | `新党satisfaction +4`、`河北路mood set 40` | 无 | **2** | 0 | 已落地 |

> V7 说明：`apply_conservation_fix` 的补记账（`engine/state_applier.py:543-622`）会先补出合法的钱组配对，随后仍落到同一个 `_simulate_underflow` → 仍 `NameError`。即"AI 报单边变更"这条容错链也一并失效。

### 2.4 生产路径实测（唯一入口 `relief_grant`）

```
J-2 · 生产唯一入口 relief_grant（ai/client_utils.py:793 applier_pipeline）
{
 "tool_result": [["call_1", "赈济未能落地（状态应用层异常，已拒绝）"]],
 "state_changed": {},
 "minister_memory": {"郑居中": ["赈 两浙路"]},          ← 记忆记为「已赈」
 "mem_relations": ["minister_郑居中->tool_relief_grant_relief_grant(promises)"]
}
```

* `ai/client_utils.py:794-802` 传入的批次为 `treasury -cost` / `农 +0.6cost` / `工匠 +0.4cost` / `refugees -…`；钱组 ΣΔ=0 **必然通过守恒**，随后必然在 `_simulate_underflow:710` 抛 `NameError`。**即：只要大臣调用赈济办差且地域能落到 20 路，该功能 100% 失败**（成本档位无关）。
* 异常被 `ai/client_utils.py:810-812` 的 `except Exception` 就地吞掉 → 玩家/UI 得不到任何异常信号；`state.population_satisfaction` 的 `+grain*2` 民心奖励（`:806-807`）不执行。
* **但 `:813` `mem.setdefault(...).append(f"赈 {region}")` 与 `:860-862` 的记忆图谱写入在 except 之外/之后照常执行** → 记忆库把一次未发生的事件记为"大臣已承诺/已办差"。

**对照实验（叙事一致性，24 回合实测）：**

| 组 | AI 二次回奏文案 | 工具回执 | 数值变化 | 判定 |
|---|---|---|---|---|
| `j_turns_seed1/2/3`（说谎脚本） | 「臣已发两浙路仓廪赈济，流民得食，民心稍纾，国帑所费不过六十万缗。」 | 「赈济未能落地（状态应用层异常，已拒绝）」 | `treasury` 不变、`民心` 不变 | **叙事称已办·数值未动（欺骗性）**——重复 5/4/5 次全部命中 |
| `j_turns_honest`（诚实脚本） | 「赈济未能落地，臣不敢妄称已办。」 | 同上 | 无 | 一致 |

> 关键结论：工具回执**确实**回传给 AI（`ai/client.py:1019-1021` 以 `role:"tool"` 追加），所以诚实模型会如实回奏；但**程序侧没有任何校验/拦截/标记**，玩家最终看到的叙事是否等于数值事实，完全取决于模型是否配合。这正是"最严重的欺骗性失败"的成立条件。

---

## 三、逐回合观测表

运行：`python j_turns.py --turns 24 --seed 1 --relief-turns 2,5,9,14,20`（玩家不颁诏、不处理事件，纯推进；替身 AI 固定档位）

| 回合 | 异常 | applied | rejected | treasury | 民心 | 皇威 | ΣPOP−population | 叙事与数值一致? |
|---|---|---|---|---|---|---|---|---|
| 起始 | - | - | - | 5,000,000 | 55 | 55 | 80,750,000 − 80,000,000 = +750,000 | - |
| 1 | - | 0 | 0 | 4,807,889 | 53 | 54 | +893,095 | 一致 |
| 2 | - | 0 | 0 | 4,601,426 | 50 | 53 | +1,010,291 | **欺骗性（召对）** |
| 3 | - | 0 | 0 | 4,381,955 | 49 | 52 | +1,186,133 | 一致 |
| 4 | - | 0 | 0 | 4,229,896 | 48 | 51 | +1,320,319 | 一致 |
| 5 | - | 0 | 0 | 4,061,116 | 46 | 50 | +1,435,913 | **欺骗性（召对）** |
| 6 | - | 0 | 0 | 3,881,269 | 45 | 49 | +1,549,641 | 一致 |
| 7 | - | 0 | 0 | 3,696,233 | 44 | 48 | +1,649,872 | 一致 |
| 8 | - | 0 | 0 | 3,438,306 | 42 | 47 | +1,743,131 | 一致 |
| 9 | - | 0 | 0 | 3,144,970 | 41 | 46 | +1,829,971 | **欺骗性（召对）** |
| 10 | - | 0 | 0 | 2,860,115 | 40 | 45 | +1,941,011 | 一致 |
| 11 | - | 0 | 0 | 2,591,838 | 38 | 44 | +2,002,542 | 一致 |
| 12 | - | 0 | 0 | 2,383,739 | 32 | 43 | +1,971,836 | 一致 |
| 13 | - | 0 | 0 | 2,181,288 | 25 | 42 | +1,891,078 | 一致 |
| 14 | - | 0 | 0 | 1,992,070 | 18 | 41 | +1,759,053 | **欺骗性（召对）** |
| 15 | - | 0 | 0 | 1,763,178 | 17 | 40 | +1,871,596 | 一致 |
| 16 | - | 0 | 0 | 1,614,962 | 16 | 39 | +1,790,831 | 一致 |
| 17 | - | 0 | 0 | 1,467,724 | 14 | 38 | +1,700,955 | 一致 |
| 18 | - | 0 | 0 | 1,332,427 | 13 | 37 | +1,607,669 | 一致 |
| 19 | - | 0 | 0 | 1,201,654 | 12 | 36 | +1,503,592 | 一致 |
| 20 | - | 0 | 0 | 1,016,219 | 10 | 35 | +1,386,017 | **欺骗性（召对）** |
| 21 | - | 0 | 0 | 799,600 | 9 | 34 | +1,268,459 | 一致 |
| 22 | - | 0 | 0 | 593,105 | 8 | 33 | +1,143,564 | 一致 |
| 23 | - | 0 | 0 | 394,927 | 0 | 32 | +943,803 | 一致 |
| 24 | - | 0 | 0 | 600,634 | 1 | 31 | +807,557 | 一致 |

补充（同表数据的机器判读）：
- `active_events` 轨迹（0→21）：`[0,0,0,1,2,3,4,…,20,21]` **单调不减**，60 回合组到 **58**。
- `treasury` 轨迹：4,807,889 → 600,634，最低 394,927，**从未为负**（B3 禁穿底生效）。
- `民心` 轨迹：53 → 0 → 1（clamp 下限），**民心 0 不触发终局**（`core/evaluation.py:172-204` 只在 deficit/退位/收束年/京城陷落判负）。
- `applier_pipeline` 累计：`{calls: 5, ok: 0, exc: 5, applied: 0, rejected: 0}`（5 次调用 = 5 次召对，全部异常）。
- 4 组运行（seed1/2/3 + honest）**异常数全为 0**；60 回合组同样 0。
- `ΣPOP − population`：初始 +750,000（流民/口径差，`core/settlement.py:434-436` 只校正 population），此后稳定在 +0.8~2.0M 区间，**未发散**。

---

## 四、静默失败普查

AST 全量扫描 `game/`（`core/ engine/ ai/ memory/ backend/ content/ ui/ telemetry/`，排除 `__pycache__`/`prompts`）：

```
分类合计： {"pass": 133, "return": 67, "continue": 10, "log_only": 8, "handled": 127}
```

即 **218 处 handler 不产生任何玩家可见的错误信号**（`pass`/`continue`/`break`/仅日志），其中 `except` 类型为**裸 `except Exception`** 的占绝大多数。

### 4.1 会直接造成「玩家看到虚假成功」的重点条目

| 文件:行 | 代码 | 会掩盖什么 | 玩家可见后果 |
|---|---|---|---|
| `engine/state_applier.py:855,710` → `ai/client_utils.py:810` | `under=_simulate_underflow(...)` 抛 `NameError`；`except Exception: res="赈济未能落地（状态应用层异常，已拒绝）"` | changes 整批未落地的**具体原因**（无 `rejected`、无异常类型） | 大臣回奏可能称已赈（见 2.4）；记忆库仍记「已办差/已承诺」 |
| `core/commands.py:517-522` | `if state.month==1 or state.game_over: try: save_game(state, slot=0) except Exception: pass` | **自动存档失败** | 玩家以为每年正月已自动存盘（README/UI 口径），实际无档；崩溃即丢全局 |
| `ai/client_utils.py:867-868` | `except Exception: pass`（记忆图谱写入） | 召对办差的事实未入图谱 | 记忆图谱缺边，AI 后续"记不住"已办之事（无任何提示） |
| `ai/client_utils.py:813`（`except` 之后无条件执行） | `mem.setdefault(minister_name, []).append(f"赈 {region}")` | ——**反向问题**：失败也记成功 | 召对记忆注入「卿旧事」时把未发生的事当既成事实 |
| `engine/state_applier.py:745-749` | `if _is_non_neg(path) and new<0: log.warning(...); new=0` | 非守恒非负字段的**超量**截断（V8：-3000 实际只减 440） | 返回体仍标 `applied`（old=440,new=0），AI/审计以为变更完全生效，差值被静默吞掉 |
| `core/commands.py:439-452` | `except Exception as _e: print("[memorials] 上折未成")` | 本回合奏折生成失败 | `state.memorials` 保留旧值，奏折面板显示过期内容（无错误提示） |
| `core/commands.py:277-313` | `_flush_ai_token` 整段 `try/except: pass` | 本回合 AI 用量未入账 | 「治务·AI计量」面板数字偏少（虚低），与真实计费不一致 |
| `core/commands.py:507-515` | `记忆库落盘异常 → log.warning` | 记忆库未随档持久化 | 主档可读，但读档后记忆库缺该回合内容（静默半损坏） |
| `core/save_load.py:22-29` | `state.memory.save(slot)` 失败仅 `log.warning`，主存档继续且 `save_game` 仍 `return True` | 存档不含记忆库 | 玩家看到"保存成功"，实际记忆库缺失/过期（与 §五 J-10 同源） |
| `core/settlement_steps.py:1054-1096`（5 处 `pass`） | `settle_minister_estate` / `settle_investments` / `settle_era_links` / `settle_industry_shift` / `tech_build_bonus` | 整步子机制静默跳过 | 最重者：**投资分期回报**若不回款，玩家投的国帑无声蒸发；建筑→科技/时代加成静默少算 |
| `core/settlement.py:149-153 / 161-165` | `settle_legacies` / `settle_focus` `except: pass` | 帝国修正、国策树月度效果不结算 | 国策点了没效果（面板照显已解锁），玩家无从判断是 bug 还是设计 |
| `core/settlement_steps.py:2693-2696` | `try: _settle_hidden_pop(...) except Exception: pass` | 隐户/逃户/归籍动态跳过 | 人口结构静默失真，后续按人口比例的税基/增长全部连带偏移 |
| `core/commands.py:41-75` | 开局邸报 / `init_legacies` / `init_focus_tree` / 记忆基线 **4 处** `except: 置空` | 各子系统初始化失败 | 开局面板（邸报/帝国修正/国策树）空置，玩家以为是设计如此 |
| `core/settlement_steps.py:1390-1396` / `:1455-1460` | 图谱写入、兵额/分支重算 `except: pass` | 外交记忆、军队编制不同步 | 军队面板兵额与真实 troops 不一致 |

> 说明：`return` 类 67 处中包含大量**合理**的拒绝式返回（如 `core/save_load.py:231-239` 损坏档返回 `None`），并非全部为缺陷；上表只列有实际玩家可见后果者。完整明细见 `j_silent_result.json`。

---

## 五、存档往返 / 旧档 / 损坏档

运行：`python j_save.py`（槽位 21-24 为审计专用，测后已删除）

| 用例 | 结果 |
|---|---|
| **往返**（4 回合存档 → 篡改 `treasury-765432`、`prestige+17` → 再跑 2 回合 → `load(21)`） | `treasury/imperial_treasury/granary/population/ΣPOP/grain_price/民心/皇威/active_events/event_history/longterm_effects/longterm_public/longterm_secret/pending_decrees/treasury_deficit` **全部一致 ✅**；**唯一不一致：`mem_entities` 109 → 110** ❌ |
| **记忆库落盘** | `slot_21.db` 生成（77,824 B）✅ |
| **缺字段旧档**（只给 `{year,month,turn,treasury,population}`） | `load` 返回可用 `GameState`，`treasury=123456` 保留、其余走默认，**不崩 ✅** |
| **损坏档**（截断 JSON） | `load → None`，并自动备份 `slot_23.json.corrupt`，`log.error` 提示 ✅（`core/save_load.py:228-243`） |
| **schema_version=99** | `load → None`，明确拒绝 ✅（`core/save_load.py:245-250`） |
| **不存在槽位** | `load → None` ✅ |

**`mem_entities` 差异归因（[确认]）**：`core/save_load.py:22-29` 的 `save_game` 会 `state.memory_slot = slot` 且 `memory.save(slot)` 内部把 `self._slot = slot`（`memory/memory_graph.py:641`）设为**粘性**；此后每回合 `finish_turn`（`core/commands.py:507-513`）发现 `_slot is not None` 就再次写同一槽位。于是"存档 JSON 定格在 turn 4，而记忆库 DB 被后续回合持续覆盖到 turn 6" → 读档得到 **turn 4 的世界 + turn 6 的记忆**。属真实不一致，非测试假象。

---

## 六、详细条目

### J-1 [P0] `_resolve_path_value` 缺失 → 钱/粮 changes 整批丢弃，且无 `rejected` 诊断
- 位置：`engine/state_applier.py:292`（被注释的 `def`）、`:293-325`（函数体被困在 `_cascade_farmer_wealth` 内、位于 `return []` 之后）、`:710`（调用点）、`:855`（无条件调用）
- 证据：[确认] AST：`_cascade_farmer_wealth` 跨 278-325 行共 8 条语句，`line 283 return []` 之后仍有 6 条语句；`module-level def _resolve_path_value present: False`。实测：
  ```
  [静态] hasattr(state_applier, '_resolve_path_value') = False
  R1 raised=NameError msg="name '_resolve_path_value' is not defined"（栈：855 → 710）
  V2/V3/V4 raised=NameError  applied=0  rejected=0  state_changed={}
  V1/V8/V9 raised=None       applied=2/1/2
  ```
- 影响：
  1. **任何含钱/粮组 `add` 的 AI changes 批次 100% 抛 `NameError`**，整批不落地（含同批合法的非守恒字段一并作废，V4）；
  2. `rejected` 为空 → 上层拿不到可读拒绝原因，只能吞（`ai/client_utils.py:810-812` 固定文案）；
  3. 生产唯一入口 `relief_grant`（`ai/client_utils.py:793`）因此**完全不可用**，且失败后仍写 `minister_memory`/记忆图谱（`:813`、`:860-862`）；
  4. 不影响 `advance_and_settle`（该函数不调用 applier）→ 缺陷被"回合照常跑通"长期掩盖。
- 验证方式：
  ```
  python D:\codebuddy\sz\_dev_tools\_scratch\audit-2026\j_p0.py     # 变体矩阵 + relief_grant 实测
  python D:\codebuddy\sz\_dev_tools\_scratch\audit-2026\j_ast.py    # AST 取证
  ```
- 建议修复：把 `engine/state_applier.py:292-325` 恢复为模块级函数——删除 `:292` 行首的 `# 已整体移除。` 注释并把 `def _resolve_path_value(state, path: str):` 顶格重写（其后 293-325 行整段去缩进 4 空格）。修后必须补回归：① `_resolve_path_value` 对 `treasury` / `prefectures.X.pops.农.wealth` / `*` 通配 / 中间层缺失的返回值；② `applier_pipeline` 钱组、粮组、混合批三条路径的 `applied/rejected`；③ `relief_grant` 端到端（`_tool_dispatch` → 国帑减少、民心 +grain×2、流民减少）。

### J-2 [P0] 「叙事说办了、数值没动」无程序侧护栏（欺骗性成功）
- 位置：`ai/client.py:1007-1038`（tool_calls → `_tool_dispatch` → 二次回奏）、`ai/client_utils.py:810-812`、`ai/client_utils.py:813`、`core/commands.py:965-979`
- 证据：[确认] 同一失败输入，仅更换替身的二次回奏文案：
  ```
  说谎：[召对] 回奏='臣已发两浙路仓廪赈济，流民得食，民心稍纾，国帑所费不过六十万缗。'
        工具回执=['赈济未能落地（状态应用层异常，已拒绝）'] 数值变化={}
        → 判定「叙事称已办·数值未动（欺骗性）」（seed1/2/3 共 14 次命中）
  诚实：[召对] 回奏='赈济未能落地，臣不敢妄称已办。'  工具回执同上 数值变化={} → 一致
  ```
- 影响：玩家看到的大臣回奏与实际状态可以完全脱节，且**没有任何程序侧信号**（无弹窗、无日志、无 rejected）能让玩家或后续逻辑察觉。这是本次审计认定的最严重"欺骗性失败"。
- 验证方式：`python j_turns.py --turns 24 --seed 1 --relief-turns 2,5,9,14,20`（默认说谎）与 `--honest` 对照。
- 建议修复：① 修复 J-1 使失败不再发生（首要）；② 在 `_tool_dispatch` 的失败分支把结果**结构化**（如 `{"ok": false}`）并由 `audience_dialogue_apply` 强制在回奏前置标注（如 `〔办差未成〕`），或在 `narrative_guard` 增加"本回合状态未变却出现办妥类断言"的检测；③ 失败时**不写** `minister_memory`/`promises` 边（`ai/client_utils.py:813,860-862` 现为无条件执行）。

### J-3 [P1] 无 AI 配置时游戏完全无法推进（本工作区现状）
- 位置：`core/commands.py:247-274`（`settle_turn` 拒绝式）、`backend/server.py:124-138`（`_build_ai` 无配置 → `AIClient()` 不可用）
- 证据：[确认]
  ```
  AIClient().available = False
  advance_and_settle → AIRuntimeError: 未接入 AI：请配置 OpenAI 兼容 API（base_url/api_key/model）
  回合号 0 → 0（回滚生效=True）  events=None log=None report=None
  ```
- 影响：优点——**拒绝式而非伪造**，且 `advance_and_settle` 的快照回滚生效（事件/状态/回合号全还原，无幽灵事件）；缺点——工作区无 `ai_config.json`，任何玩家一回合都推不动，前端只会收到错误。属于"设计如此"，但必须让玩家可见地知道"未配置 AI"而不是黑屏/无响应。
- 验证方式：`python j_misc.py`（J-6a 段）。
- 建议修复：保持拒绝式；在 UI 首屏做 AI 可用性探测（`AIClient.probe()`）与明确引导，避免"点了下一回合没反应"。

### J-4 [P1] `resolve_event` 清理失效 → `active_events` 无上限累积
- 位置：`core/commands.py:602-607`（清理逻辑）vs `core/commands.py:238`（写入格式）
- 证据：[确认]
  ```
  写入格式：{"title": ev.title, "message": ev.desc}      # core/commands.py:238
  清理判定：if title not in e.get("message", "")          # core/commands.py:607  ← 拿 title 去 desc 里找
  实测：title='翰林画院新作' message='翰林图画院呈上新作，画艺精湛' → `title in message` = False
        按 UI 正常路径处理 9/9 个事件后：active_events=9（一条都没删）event_history=0
        60 回合：active_events=58，event_history=0
  ```
- 影响：① 事件面板永不收敛（玩家处理过的事件继续在场，可能被重复抉择）；② `active_events` 全量进入 `get_state_summary()`（`core/game_state.py:1093`），AI 上下文体积无上限增长（实测 turn12=1,082 字符 → turn60=7,603 字符，约 +126 字符/回合）；③ 存档体积同步增长；④ 副作用见 J-5。
- 验证方式：`python j_misc.py`（J-6b 段）、`python j_events.py`。
- 建议修复：写入时把 `title` 也放进 `message`（或清理时按 `e.get("title")` 比对）：`state.active_events = [e for e in state.active_events if e.get("title") != title]`；并给 `active_events` 加长度上限/超期淘汰（如仅保留最近 N 条在场，其余转 `event_history`）。

### J-5 [P1] 「库藏空虚」危机因 J-4 只触发一次
- 位置：`core/settlement.py:346-363`
- 证据：[确认]（代码推理 + J-4 实测）判据 `not any(e.get("title")=="库藏空虚" for e in state.active_events)`；事件一旦 append 便因 `resolve_event` 清理失效而**永不被移除**，故该分支此后永假。
- 影响：国库危机事件在整局中最多触发一次，玩家无法反复面对财政崩坏抉择；`core/commands.py:606` 的同类清理（`resolve_event`）同样受影响。
- 验证方式：`j_probe.py` 60 回合运行中 `active_events` 内含首条「库藏空虚」后不再新增。
- 建议修复：随 J-4 一并修复；另建议此类"一次性状态标记"改用独立布尔/时间戳字段，而非寄生在 `active_events` 列表里。

### J-6 [P1] 长局货币总量净增（每月约 +0.52M 贯）+ 内帑单极膨胀
- 位置：`core/settlement_steps.py:2150-2156`（作坊产肉 `state.imperial_treasury += int(yld*MEAT_PRICE)`）、`core/settlement.py:118-140`（`org_economy` `change_treasury(net)`）、`core/settlement_steps.py:3016`（`imperial_treasury` 累加）、`core/game_state_econ.py:517-521`（`calc_imperial_treasury`）
- 证据：[确认] 60 回合货币账（`treasury + imperial_treasury + Σ 六阶层 wealth`）：
  ```
  t=0   合计 292,599,947
  t=30  合计 285,449,795   （期间为负漂移）
  t=60  合计 294,257,386   treasury=39  imperial=106,114,428  民钱=188,142,919
  t=30→60 每月 Δ合计：+519,335 / +613,014 / +859,863 / … / +622,755（30 个月累计 +20,1M）
  treasury 自 t=30 起恒为 39，而 imperial_treasury 每月 +1.82~2.91M
  ```
  逐步差分（`j_probe2.py`，暖机 30 回合后单回合）：
  ```
  步骤                     Δtreasury    Δimperial         Δ民钱        Δ合计
  _settle_extensions             +0           +0       -254,989     -254,989
  _settle_granary                +0           +0       +554,949     +554,949   ← 无对应来源
  _settle_finance               -39     +1,778,670   -1,599,295     +179,336   ← 酒课入内帑 vs 民间扣款不等
  _settle_workshops              +0        +40,000           +0      +40,000   ← 直接造币入内帑
  _settle_org_economy           +39           +0            +0          +39
  step 合计 Δ合计 = +519,335
  calc_imperial_treasury 返回 [{'net': -204414.0, 'imp_share': 0.0, 'wine': 1,778,688.0}]  ← 亏损月仍抽走 178 万
  ```
- 影响：① 单极货币创造（内帑 60 回合 1,000,000 → 106,114,428，**106 倍**）而国库长期停在 39 贯——玩家看到"内帑巨富、国用枯竭"，且该差异并非来自任何玩家决策；② 通胀/物价与内帑脱钩，长局经济含义失真；③ `wine_tax` 自身也被作坊推高（初始 100,000 → 暖机 30 回合后 1,852,800），形成正反馈。
- 备注：`_settle_org_economy` 的 +39 与 `_settle_workshops` 的肉产折钱有代码内自述（`core/settlement.py:122-124`、`core/settlement_steps.py:2153-2156`），可视为"记账设计"；但 **`_settle_granary` +554,949 与 `_settle_finance` 酒课差额 +179,336 未找到等价来源**，属 [疑似] 造币（已定位到步骤，未逐行追到具体泄漏点）。
- 验证方式：`python j_probe.py --turns 60 --seed 7`、`python j_probe2.py --warm 30 --seed 7`。
- 建议修复：给 `treasury + imperial_treasury + Σwealth (+ coin/jiaozi)` 加月度守恒断言（与 `_settle_finance:3025` 的财政恒等断言同级），把漂移变成**响亮失败**而不是静默累积；`imperial_treasury` 抽成应先冲抵国库亏空，避免亏损月仍抽 178 万入内帑。

### J-7 [P1] 自动存档失败静默（玩家以为已存）
- 位置：`core/commands.py:516-522`
- 证据：[确认]
  ```python
  if state.month == 1 or state.game_over:
      try:
          from core.save_load import save_game
          save_game(state, slot=0)
      except Exception:
          pass  # 自动存档失败不阻断结算
  ```
- 影响：每年正月与终局自动写槽 0；失败无任何提示，玩家看到"存档槽有档"的错觉，实际可能是上一年或不存在。结合 J-10（记忆库粘性槽位），失败场景更隐蔽。
- 验证方式：代码定位（`grep "自动存档失败不阻断结算"`）；运行期每次正月由 `j_turns.py` 触发（可在 `SAVE_DIR` 置只读目录复现实测失败，本次未做破坏性验证，[疑似] 该分支未被实跑触发）。
- 建议修复：失败改为至少 `log.error` + `state.last_save_error` 字段（供 UI 显示「自动存档失败」），不要用裸 `pass`。

### J-8 [P2] 非负截断吞掉超量增量却仍记 `applied`
- 位置：`engine/state_applier.py:745-755`（配合 `_simulate_underflow:705` 对非守恒路径的**有意豁免**）
- 证据：[确认] V8：`prefectures.两浙路.refugees add -3000`（现值 440）→ 返回 `applied=1`、记录 `old=440 new=0`；stderr：`apply_to_state 非负截断：prefectures.两浙路.refugees add→0（old=440）`。
- 影响：`applied` 语义失真（"已应用 -3000"实为 -440）；差额既不入账也不报错，AI 视角以为赈济安置了 3000 人。
- 验证方式：`python j_p0.py`（V8）。
- 建议修复：截断时把实际增量写回 change 记录（`delta_applied`）并记入 `rejected`/`warnings` 供叙事层提示；或对 refugees 等非负字段也做穿底预检并拒绝整单。

### J-9 [P2] 结算子机制被 `except: pass` 静默跳过（投资回报风险最高）
- 位置：`core/settlement_steps.py:1054-1096`（estate/investments/era_links/industry_shift/tech_bonus）、`core/settlement.py:149-153,161-165`（legacies/focus）、`core/settlement_steps.py:2693-2696`（隐户动态）、`:1455-1460`（兵额重算）、`ai/client_utils.py:867`（记忆图谱）
- 证据：[确认]（AST 位置 + 代码）`{"pass": 133}` 中上述 8 处的 handler body 均为单一 `pass`。
- 影响：任一子机制抛错即整步静默跳过，玩家既看不到错误也不知道该功能已失效；`settle_investments` 若失败则**玩家已投出的国帑分期回报静默蒸发**（该分支本次未实跑，[疑似]，因 `invest` 无生产调用方见 `core/agent_router.py:164`）。
- 验证方式：`python j_silent.py`（AST 明细）。
- 建议修复：改为 `log.warning` + `state._settle_warnings` 列表（随月报/日志呈现），至少让"少算"可被观测；对 `settle_investments` 这类涉及玩家资产的步骤应升级为可见错误。

### J-10 [P2] 存档 JSON 与记忆库 DB 回合水位不一致
- 位置：`core/save_load.py:22-29`（`state.memory.save(slot)` → `memory/memory_graph.py:641` 设 `self._slot`）、`core/commands.py:507-513`（`finish_turn` 依据粘性 `_slot` 每回合续写）
- 证据：[确认] 4 回合存档 → 再跑 2 回合 → `load`：世界状态回到 turn 4（全字段一致），而 `mem_entities` 109 → **110**（记忆库已被 turn 6 覆盖）。
- 影响：读档后"世界 = turn 4，记忆 = turn 6"，AI 回忆包含未来情报；若两次存档间隔较久，偏差更大。
- 验证方式：`python j_save.py`（[3] 段差异输出）。
- 建议修复：`memory.save(slot)` 写盘后不要留下跨存档粘性（或读档时按 `state.turn` 对记忆做 `rollback_after`）；`save_game` 应把记忆库快照与主档放在同一"存档版本"内。

### J-11 [P2] 开局子系统初始化失败静默置空
- 位置：`core/commands.py:41-45`（`opening_gazette`）、`:47-51`（`legacies`）、`:53-57`（`focus_tree`）、`:59-75`（记忆基线）
- 证据：[确认]（代码）四处 `except Exception` 分别落到 `state.xxx = {}` / `pass`。
- 影响：邸报/帝国修正/国策树面板静默为空，玩家无法区分"设计如此"与"初始化失败"。
- 验证方式：代码定位；`python -c` 读 `core/commands.py:41-75`。
- 建议修复：失败时记 `state.init_warnings`，UI 显示"帝国修正未能载入"。

### J-12 [P2] 民心/皇威触底不单独判负，长局以"退位"收场
- 位置：`core/evaluation.py:137-159`（`check_abdication` 需 ≥2 条理由）、`:172-204`（`check_game_over`）
- 证据：[确认] seed1：民心 turn23 = **0**（`active_events`=20、treasury=394,927）时 `game_over=False` 继续推进；60 回合组 turn53 才因「民怨沸腾 + 国库亏空」两条同时成立而 `game_over=True`（`game_result='被迫退位——民怨沸腾、国库亏空'`）。
- 影响：民心 0（万民离心）不构成终局条件，玩家可在民心 0 的状态下无限拖局；同时 `min` 钳制使民心显示为 0/1 抖动（`core/settlement_steps.py` 多处 `max(0,…)`）。
- 验证方式：`python j_turns.py --turns 24 --seed 1`（民心列）、`python j_probe.py --turns 60 --seed 7`（终局行）。
- 建议修复：把"民心 = 0 持续 N 月"纳入 `check_game_over`（或纳入 `check_abdication` 的第二条理由），使崩盘有明确终点。

### J-13 [P2] `advance_month` 事件永不入 `event_history`（史册缺载）
- 位置：`core/commands.py:236-238`（只 append 到 `active_events`）；全库唯一 `event_history.append` 在 `core/settlement_steps.py:2641`（仅皇帝风险事件）
- 证据：[确认] 60 回合：`active_events=58` 而 `event_history=0`。
- 影响：史册/回顾面板缺少全部历史与随机事件记录；存档重载后这些事件只以"在场事件"形式存在（且永不清理，见 J-4）。
- 验证方式：`python j_events.py`、`python j_probe.py`。
- 建议修复：事件触发时同步 `event_history.append(...)`，`active_events` 只保留未处理项。

---

## 附：可复现命令清单（全部实际执行过）

```powershell
$env:PYTHONPATH=''; $env:PYTHONIOENCODING='utf-8'; $env:PYTHONDONTWRITEBYTECODE='1'
cd D:\codebuddy\sz\game
& 'D:\codebuddy\.audit-venv\Scripts\python.exe' D:\codebuddy\sz\_dev_tools\_scratch\audit-2026\j_p0.py        # P0 变体矩阵 + relief_grant
& 'D:\codebuddy\.audit-venv\Scripts\python.exe' D:\codebuddy\sz\_dev_tools\_scratch\audit-2026\j_ast.py       # AST 取证
& 'D:\codebuddy\.audit-venv\Scripts\python.exe' D:\codebuddy\sz\_dev_tools\_scratch\audit-2026\j_turns.py --turns 24 --seed 1 --relief-turns 2,5,9,14,20 --out j_turns_seed1.json
& 'D:\codebuddy\.audit-venv\Scripts\python.exe' D:\codebuddy\sz\_dev_tools\_scratch\audit-2026\j_turns.py --turns 24 --seed 2 --lie-report --relief-turns 3,8,13,18 --out j_turns_seed2_lie.json
& 'D:\codebuddy\.audit-venv\Scripts\python.exe' D:\codebuddy\sz\_dev_tools\_scratch\audit-2026\j_turns.py --turns 24 --seed 3 --honest --relief-turns 4,12,20 --out j_turns_honest.json
& 'D:\codebuddy\.audit-venv\Scripts\python.exe' D:\codebuddy\sz\_dev_tools\_scratch\audit-2026\j_turns.py --turns 60 --seed 7 --relief-turns 2,10,25,40,55 --out j_long_seed7.json
& 'D:\codebuddy\.audit-venv\Scripts\python.exe' D:\codebuddy\sz\_dev_tools\_scratch\audit-2026\j_probe.py --turns 60 --seed 7
& 'D:\codebuddy\.audit-venv\Scripts\python.exe' D:\codebuddy\sz\_dev_tools\_scratch\audit-2026\j_probe2.py --warm 30 --seed 7
& 'D:\codebuddy\.audit-venv\Scripts\python.exe' D:\codebuddy\sz\_dev_tools\_scratch\audit-2026\j_save.py
& 'D:\codebuddy\.audit-venv\Scripts\python.exe' D:\codebuddy\sz\_dev_tools\_scratch\audit-2026\j_silent.py
& 'D:\codebuddy\.audit-venv\Scripts\python.exe' D:\codebuddy\sz\_dev_tools\_scratch\audit-2026\j_misc.py
& 'D:\codebuddy\.audit-venv\Scripts\python.exe' D:\codebuddy\sz\_dev_tools\_scratch\audit-2026\j_events.py
& 'D:\codebuddy\.audit-venv\Scripts\python.exe' D:\codebuddy\sz\_dev_tools\_scratch\audit-2026\j_view.py
```

产物（同一目录）：`j_p0_result.json`、`j_turns_seed1.json`、`j_turns_seed2_lie.json`、`j_turns_honest.json`、`j_long_seed7.json`、`j_probe_result.json`、`j_probe2_result.json`、`j_save_result.json`、`j_silent_result.json`、`j_misc_result.json`、`j_smoke.json`。

## 附：进程与文件清理

- 本次审计启动的后台作业共 4 个（`j_turns.py` seed1/seed2/long-seed7/honest），均为**前台一次性 Python 进程、运行结束已自然退出**（`job_list` 全部 `completed`）；审计脚本不启动任何常驻服务（**未启动 FastAPI/Electron/Vite**），我名下无遗留进程。
- 环境中现存 4 个 `python -m backend.server` 进程（PID 19824/8112，起于 20:53:07，父 8600；PID 2828/18652，起于 20:54:19，父 16868）**不是本次审计启动的**（本次从未执行 `backend.server`），应为同工作区其他会话所起，**未触碰**。
- 存档清理：槽位 21-24（含 `slot_21.db`、`slot_23.json.corrupt`）已删除；测试期间由"每年正月自动存档"产生的 `slot_0.json` / `slot_0.db` 已确认**测试前不存在**（`j_save_result.json → pre_existing: {"0": false}`），已移出存档目录并备份至 `_scratch\audit-2026\_saves_backup\`（可还原）。`slot_0_dialogue.db*`（被上述 server 进程占用句柄，无法删除）与 `slot_1/2/4/5/6/9.db` 非本次独占产物，未触碰。
- `game/` 与 `_dev_tools/game-dev/tests/` 下**零文件改动**（仅进程内 monkeypatch）。
