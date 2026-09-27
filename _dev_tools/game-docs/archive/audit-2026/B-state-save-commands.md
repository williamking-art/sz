# B · 状态 / 存档 / 命令时序审查

- 审查对象：《宋祚 Songzuo》`core/game_state.py`(1216)、`core/save_load.py`(615)、`core/commands.py`(1296)、`core/commands_decree.py`(762)
- 解释器：`D:\codebuddy\.audit-venv\Scripts\python.exe`（Python 3.13.14）
- 一次性实证脚本目录：`D:\codebuddy\sz\_dev_tools\_scratch\audit-2026\`（**未修改 game 下任何源文件**；所有存档读写均重定向到 scratch 下的临时 SAVE_DIR）
- 标记约定：**[确认]** = 有代码定位或实跑输出；**[疑似]** = 仅推理，未验证

---

## 结论速览

| 编号 | 严重度 | 一句话 | 文件:行 | 证据类型 |
|------|--------|--------|---------|----------|
| B-1 | P1 | 读档后记忆库水位由 DB 决定，可超前存档 turn 数十回合，AI 月报/召对注入「未来」史实 | `core/save_load.py:258-260` + `core/commands.py:507-513` | 确认（C4/A13 实跑） |
| B-2 | P1 | `int(data.get("schema_version",1))` 未包在 try 内：非整数 schema_version 直接抛 ValueError 穿透读档，且损坏档被移走 | `core/save_load.py:245` | 确认（A4 实跑） |
| B-3 | P2 | 存档字段值为 `null` 时读档「成功」但下一回合结算必崩（`treasury`/`statistics`/`turn`） | `core/save_load.py:281,415,428` | 确认（A9/F1 实跑） |
| B-4 | P2 | A2 记忆回滚按「水位 T」截断，而失败回合写入用的正是 T → 对失败回合写入恒为空转；真正生效的是被文档判定为「不可深拷贝」的 MemoryGraph 整体深拷贝，对话库仍不受保护 | `core/commands.py:403-418` + `core/settlement.py:441-443` | 确认（D1/D2/D3 实跑） |
| B-5 | P2 | 快照回滚打断 `pending_imperial_trip is imperial_action` 的同一性，两者静默分叉 | `core/commands.py:379-385,396-402` + `core/game_state.py:390` | 确认（C1/D5 实跑） |
| B-6 | P2 | `_run_fixed` 对 6 类非法入参静默 `return None`，调用方仍回执「即时施行」，并向玩家暴露英文类别名 | `core/commands_decree.py:65-66,91-97,110-112,453-455` | 确认（I1/I2 实跑） |
| B-7 | P2 | AI 契约 `params["amount"]` 只校验「是 dict」，`int()` 无防护：字符串→ValueError(400)，null/dict→TypeError(500) | `core/commands_decree.py:49` + `ai/client.py:1296` | 确认（F2 实跑） |
| B-8 | P2 | 内帑金额解析：负号被吞、中文数字前缀匹配导致量级错误（`五亿`→5）、任意数字误取；且**全库无调用方**（死代码），真实通道走 `int(amount)` 拒绝一切中文金额 | `core/commands_decree.py:743-760` | 确认（B1/B3/B4 实跑） |
| B-9 | P2 | 存档 `.tmp` 用固定名：并发写同槽位 `os.replace` 抛 PermissionError（WinError 32），`finish_turn` 又静默吞掉自动存档失败 | `core/save_load.py:187,191-198` + `core/commands.py:517-522` | 确认（G3/G6 实跑） |
| B-10 | P2 | 损坏档备份后槽位在 `/api/save_slots` 里显示 `empty` 而非 `corrupt`；`.corrupt` 固定名会覆盖上一次备份 | `core/save_load.py:236` + `589-615` | 确认（E3/A7 实跑） |
| B-11 | P2 | 每回合 2 次全量深拷贝快照（`advance_and_settle` 内 + `settle_local` 内），新局 ~15ms、图 400 关系 ~51ms/次，且内外层完全冗余 | `core/commands.py:430,471` | 确认（D6 实跑） |
| B-12 | P2 | `run_monthly_settlement` 无条件 `random.seed(...)` 且不还原全局 RNG（同类 P3 修复只落在 `advance_month`） | `core/settlement.py:331` vs `core/commands.py:216-234` | 确认（F5 实跑） |
| B-13 | P2 | 国库崩坏终局分支 `return log` 不推进回合；此后每次 `/api/advance` 都是同一结果（turn 停滞） | `core/settlement.py:341-345` | 确认（C5 实跑） |
| B-14 | P2 | 未接线核对：`AGENT_DEFS` 全库**没有任何 `wired` 键**，`wired is False` 守卫恒不触发 → `finance` agent 照常唤醒烧 token，而结算侧 `_finance_ai` 消费者数=0；`settle_local`/`advance_month`/`async_ai` 无生产调用方 | `core/agent_router.py:35-44,159-165,232-233` + `core/commands.py:459` | 确认（E2/实跑+grep） |

补充（低价值/范围外，见文末「附录」）：`_state_to_dict` 的 `_ai_failures` 分支不可达；`pending_public_decrees`/`_prestige_history` 死字段；`defense_lines` 重复键；槽位未做范围校验。

---

## 详细条目

### B-1 [P1] 读档后记忆库水位可超前存档 turn，AI 叙事注入「未来」史实

- 位置：`core/save_load.py:258-260`、`core/commands.py:507-513`、`memory/memory_graph.py:720-723`
- 证据：**[确认]**（实跑 `a_saveload.py` A13 / `c_rollback.py` C4）

```python
# core/save_load.py:258-260
state.memory_slot = slot
state.memory.turn = data.get("turn", 0)   # 先按存档 turn 对齐……
state.memory.load(slot)                   # ……随即被 DB 里的 turn 覆盖
# memory/memory_graph.py:720-723（_load_from_db）
self.schema_version = int(self._state_get(conn, "schema_version") or _SCHEMA_VERSION)
self.turn = int(self._state_get(conn, "turn") or 0)      # ← 覆盖上面那行
```
```python
# core/commands.py:507-513（finish_turn：每个回合都把记忆库写回“最近一次 load/save 的槽位”）
mg = state.memory
_slot = getattr(mg, "_slot", None) or getattr(state, "memory_slot", None)
if _slot is not None:
    ok = mg.save(_slot)
```
实跑输出（`_saves_a/_saves_c`）：
```
存档 turn = 0 | 记忆库 turn = 20
超前关系: ['future_src']
读回 state.turn = 0 ；读回 memory.turn = 20 ；记忆库中 turn > state.turn 的关系条数: 1
```
成因：主存档 JSON 只在**手动存档/每年正月(slot 0)** 时更新，而记忆库每回合都 `mg.save(mg._slot)`。所以「手动存槽1 → 继续玩 20 回合 → 读槽1」会得到「state 回到第 0 回合、记忆库停在第 20 回合」。
- 影响：`monthly_report_args`（`commands.py:525-554`）以此为 AI 上下文：`retrieve_hierarchical(subject="event", period=state.turn//12)` 与 `mg.query(..., time_window=24, top_k=6)` 都是按 `self.turn`（=20）取窗与算衰减（`memory_graph.py:245,264,271`），于是失败/超前回合的事件、决策被注入月报的「【近期朝局】」；`audience_dialogue_prepare` 的「【卿前番之言】」同理会引用该时间线里尚未发生的召对。即**读旧档后 AI 会「记得」未来**。
- 验证方式：
  `python c_rollback.py`（C4 段）、`python a_saveload.py`（A13 段）
- 建议修复：`load_game` 在 `state.memory.load(slot)` **之后**按存档 turn 截断/回退水位，例如 `state.memory.rollback_after(int(data.get("turn",0)))` + `state.memory.turn = int(data.get("turn",0))`；或让记忆库按存档 turn 存快照（`.db` 也分「存档点」）。至少要保证 `memory.turn == state.turn`。

---

### B-2 [P1] `schema_version` 非整数时 `int()` 抛 ValueError 穿透读档

- 位置：`core/save_load.py:245`
- 证据：**[确认]**（实跑 `a_saveload.py` A4）

```python
# core/save_load.py:228-245（try 只包住 json.load，int() 在 try 之外）
try:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
except (OSError, ValueError) as e:
    ... 备份 .corrupt; return None
if not isinstance(data, dict): ... return None
_ver = int(data.get("schema_version", 1) or 1)     # ← 未受保护
```
实跑：
```
A4 schema_version 非整数（'abc'） -> !! CRASH: ValueError("invalid literal for int() with base 10: 'abc'")
```
- 影响：P1-9「损坏档不再崩溃式失败」的修复在这条路径上有洞。`/api/load` 会把 ValueError 抛成 500（`backend/server.py:402-404` 无 try），且**不会**备份损坏档、不会返回 None，槽位从此既读不了也清不掉。触发面：手改档、其它工具/版本写出的档、被截断后仍能解析成 JSON 的文件（如 `{"schema_version": "0.1.0"}` 这类把 `version` 写进 schema_version 的迁移档）。
- 验证方式：`python a_saveload.py`（A4 段，脚本内直接 `json.dump({"schema_version":"abc"})` 到临时槽位后调用 `load_game`）
- 建议修复：`_ver = data.get("schema_version", 1)`，用 `try: _ver = int(_ver or 1) except (TypeError, ValueError): _ver = 1`（或因版本号异常而按损坏档处理，走同一 `.corrupt` 备份分支）。

---

### B-3 [P2] 字段值为 `null` 的存档「读档成功」但下一回合必崩

- 位置：`core/save_load.py:281`(`treasury`)、`415`(`active_events`)、`428`(`statistics`)、`263-265`(`turn`)；`load_game` 内 123 处 `data.get(...)` 中有 98 处未跟 `or/if` 兜底（机械统计），「键存在但值为 null」一律原样落到 state
- 证据：**[确认]**（实跑 `a_saveload.py` A9 / `f_exceptions.py` F1）

```
A9 字段值为 null 的档 -> load ok: True
  state.treasury = None   state.active_events = None   state.pending_decrees = None
  state.turn = None       state.statistics = None
F1 null 字段档 → 月度结算崩溃
  turn        -> TypeError: unsupported operand type(s) for *: 'NoneType' and 'int'   (settlement.py:331)
  statistics  -> AttributeError: 'NoneType' object has no attribute 'get'
  treasury    -> TypeError: '>' not supported between instances of 'NoneType' and 'float'
```
对照：**真正「缺字段」不崩**（A2 只给 `{"year":1105,"turn":3}` → 正常加载；A3 `{}` → 全默认值）——说明「旧档缺字段」这条路径是好的，漏的是「键存在但值为 null」。
- 影响：读档被视为成功（`/api/load` 返回 200），随后 `/api/advance` 在结算内部崩（500），玩家存档无法自救；若这种 state 再被 `save_game` 写回，null 会被持久化，污染固化。
- 验证方式：`python a_saveload.py`（A9）、`python f_exceptions.py`（F1）
- 建议修复：在 `load_game` 末尾加一层「关键标量非 None」校验（或对每个字段统一 `data.get(k) if data.get(k) is not None else default`）；至少对 `turn/year/month/treasury/imperial_treasury/statistics/active_events/pending_decrees` 做类型与空值兜底。

---

### B-4 [P2] A2「记忆库按水位截断」实际空转；真正生效的机制与文档描述相反

- 位置：`core/commands.py:371-385`(`_snapshot_state`)、`388-418`(`_restore_state`)、`core/settlement.py:441-443`
- 证据：**[确认]**（实跑 `d_snapshot.py` D1/D2/D3、`c_rollback.py` C2/C3）

```python
# core/commands.py:384  快照记录的水位 = 结算开始前（推进之前）的 turn
snap["__mem_turn__"] = int(getattr(state, "turn", 0) or 0)
# core/commands.py:403-418 回滚
_turn = snap.get("__mem_turn__")
... _fn(int(_turn))      # 各库 rollback_after(turn)
# memory/memory_graph.py:190-193 / dialogue_memory.py:98-101 → 只删 “turn > turn”
# core/settlement.py:441-443  回合推进发生在整条流水线的最后一步
state.settlement_log.append(log)
state.turn += 1
```
结算步骤里的记忆写入全部用 `turn=state.turn`（`settlement_steps.py:1358-1359,1391-1392,2476,2643`），而此刻 `state.turn` 仍是水位 T → **`rollback_after(T)` 删不到任何失败回合的写入**。实跑（注入结算异常后统计）：
```
D2 回滚前关系数: 5 → 回滚后关系数: 3   | state.memory 对象未变: False     ← 图被整体替换成深拷贝
D3 失败结算期间写入的对话库：对话库行数 0 -> 1，最近行 [('司马光', 5, '失败回合召对')]   ← 残留在 SQLite 里
D1 copy.deepcopy(state.memory) -> 成功（与 _snapshot_state docstring 声称的『含 SQLite 连接必被跳过』不符）
   可深拷贝字段数: 126   跳过字段: ['_dialogue_memory']
```
即：`MemoryGraph` 根本不含活的 sqlite 连接（每次 `_connect` 用完即关），所以它被整份深拷贝、随字段回滚一起还原（对象身份都换了）；而**真正不可深拷贝的 `_dialogue_memory`（持 `sqlite3.Connection`）才是 A2 想保护的对象**，它只能靠 `rollback_after`，而该调用在水位语义下恒为空转。
- 影响：(1) docstring 与实现不符，A2 修复的「防重复 upsert / 防污染卿前番之言」在对话库上不成立——**若将来有任何结算步骤写召对，失败重试会累加幻影召对**（当前结算路径无 `add_dialogue` 调用方，故现阶段无可见症状，仅 1 行残留需注入才能复现）；(2) `state.memory` 在每次回滚后被替换为新对象，任何长期持有旧引用的模块会静默失联（G4 实查：现有代码都是即时读取，暂未踩雷）；(3) 每次失败都白做一次整图深拷贝 + 两次空转的 DB DELETE。
- 验证方式：`python d_snapshot.py`（D1/D2/D3）、`python c_rollback.py`（C2/C3）
- 建议修复：把水位语义改成「删 `>= T`」（`rollback_after(turn - 0)` 或新增 `rollback_since`），或在水位里直接存「结算前已写入的最大 turn」；同时修正 `_snapshot_state` 的注释，并把「memory 会被深拷贝」显式化（或在 `MemoryGraph` 上挂哨兵对象让它真的被跳过，避免每回合重复深拷贝整图）。

---

### B-5 [P2] 回滚破坏 `pending_imperial_trip` 与 `imperial_action` 的同一性

- 位置：`core/commands.py:379-385`（逐字段 deepcopy）、`core/game_state.py:390`（声明「同一 dict」）、`core/settlement_steps.py:2517-2526`
- 证据：**[确认]**（实跑 `c_rollback.py` C1 / `d_snapshot.py` D5）

```
快照前同一: True
回滚后同一: False
——模拟 Step9 推进准备期（只改 pending_imperial_trip）——
pending_imperial_trip.pending_months = 1
imperial_action.pending_months       = 2      ← 两者分叉
```
`copy.deepcopy` 对 `imperial_action` 与 `pending_imperial_trip` 各产生一份独立副本，`_restore_state` 分别 `setattr` → 文档承诺的「同一 dict 指针」（`game_state.py:390`、`save_load.py:406-407`）在**任何一次结算失败回滚后**即失效。
- 影响：当前调用图里，Step 9 读 `act = state.imperial_action`（`settlement_steps.py:2511`）后只递减 `pending_imperial_trip`，两者数值差异在本次结算内不改变结果；但 `choose_imperial_action` 的「准备中不可另定行止」判据只看 `pending_imperial_trip`，而任何按 `imperial_action` 判断/展示/落档的逻辑会拿到旧值。属**静默不变量破坏**（未观察到用户可见后果，故 P2），一旦后续新增「改 `imperial_action` 即同步准备期」的代码就会出错。
- 验证方式：`python c_rollback.py`（C1）、`python d_snapshot.py`（D5）
- 建议修复：`_snapshot_state`/`_restore_state` 对别名对做特判（回滚后重建 `state.pending_imperial_trip = state.imperial_action if pending_months>0 else None`），或把 `pending_imperial_trip` 改成 `state.imperial_action` 的 property。

---

### B-6 [P2] `_run_fixed` 静默空转 + 假成功回执 + 英文内部名外泄

- 位置：`core/commands_decree.py:46-112`（`_run_fixed`）、`443-457`（`issue_free_decree` 即时分支）
- 证据：**[确认]**（实跑 `i_silent.py` I1/I2、`i2_instant.py`）

```python
# commands_decree.py:65-66 / 91-97 / 110-112
if not amt or not target:
    return                      # ← 返回 None，调用方不检查
_dst = _SRC_DST.get(target)
if _dst is None:
    return                      # ← 未知目标：静默
if _src == _dst:
    return                      # ← 同库同名：静默
elif cat == "fixed_army":
    pass                        # ← 永远空转
```
```python
# commands_decree.py:453-455
if mode == "instant":
    _run_fixed(state, cat, params)
    return f"〔{parse_result.get('title','诏')}〕即时施行：{cat}"   # ← 无条件回执“已施行”
```
实跑：
```
{'amount': 0, 'target': '内藏'} → None     {'target': '内藏'} → None     {'amount': 100} → None
{'amount': 100, 'target': '国库'} → None   {'amount': 100, 'target': '不存在的库'} → None
回执: 〔移库诏〕即时施行：fixed_finance    国库/内帑: (100000, 1000000) -> (100000, 1000000)（未变）
fixed_tech / fixed_construction / fixed_army 三者 _run_fixed 均 None，回执均为「即时施行：<cat>」
```
- 影响：玩家看到「已即时施行」但国库/内帑一分未动（`fixed_tech`/`fixed_construction`/`fixed_army` 的 instant 语义**根本没有实现**）；同时把内部英文类别名 `fixed_finance` 直接显示给玩家，违反项目「玩家可见文案不直出内部标识」的既有约定（同文件 538-539 行对此有明确修复先例）。这是「吞掉失败后继续推进」的典型形态。
- 验证方式：`python i_silent.py`、`python i2_instant.py`
- 建议修复：`_run_fixed` 统一返回 `(ok, msg)` 或明确的失败串；`issue_free_decree` 依返回值组装回执，空转时回执「此令未落地（参数不备/类别不支持）」；对外文案用 `FIXED_PROCEDURES[cat]["label"]`。

---

### B-7 [P2] AI 契约 `params["amount"]` 无类型防护：ValueError→400、TypeError→500

- 位置：`core/commands_decree.py:49`（`amt = int(params.get("amount", 0))`）、上游校验在 `ai/client.py:1296`
- 证据：**[确认]**（实跑 `f_exceptions.py` F2）

```python
# core/commands_decree.py:48-49
if cat == "fixed_finance":
    amt = int(params.get("amount", 0))     # str→ValueError；None/dict→TypeError
# ai/client.py:1296
o["params"] = o.get("params", {}) if isinstance(o.get("params"), dict) else {}
# —— 只保证是 dict，amount 原样透传
```
实跑：
```
{'amount': '50万', 'target': '州郡'} -> ValueError: invalid literal for int() with base 10: '50万'
{'amount': None,   'target': '州郡'} -> TypeError: int() argument must be … not 'NoneType'
{'amount': {'x': 1},'target': '州郡'} -> TypeError: … not 'dict'
```
`backend/server.py:358-361` 只捕获 `ValueError`（转 400 并回显英文原文），`TypeError` 直接 500。
- 影响：AI 对「钱粮调度」类圣旨给出中文/空/结构化金额（LLM 常见）时，玩家收到 500 或带英文的 400，且这一回合的诏令状态半途而废（`_run_fixed` 之前的 `new_material`/`rename` 已落地，见下条同源问题）。
- 验证方式：`python f_exceptions.py`（F2）
- 建议修复：`amount` 走 `parse_inner_amount` 或 `_coerce_int(x) -> int|None`，非法即 `return "数额不明确，此令不行"`（拒绝式，与 `allocate_payraise` 同款写法）；服务端对 `TypeError` 也兜底。

---

### B-8 [P2] 内帑金额解析：负号丢失、前缀匹配致量级错误、任意数字误取；且全库无调用方

- 位置：`core/commands_decree.py:721-760`
- 证据：**[确认]**（实跑 `b_amount.py` B1/B3/B4）

```
'-500'          -> 500          ← 负号被 \d+ 吞掉（符号丢失）
'发内帑 -500 贯'  -> 500
'五亿'           -> 5            ← [零一二两三四五六七八九十百千万]+ 匹配“五”即返回，量级差 1 亿倍
'3.5万'          -> 50000        ← \d+\s*万 从“5万”处起匹配，丢掉整数部分 3
'去年1102年内帑'  -> 1102         ← 文中任意数字都会当金额
'拨3个州'         -> 3
'99999999999999999999万' -> 1e24  ← 无上界（上游 propose 会拦，但解析层不设界）
'五亿'/'壹万'     -> 5 / None     ← 未登记“亿”“壹”，要么错要么 None
```
```python
# commands_decree.py:747-756
m = re.search(r"(\d+)\s*万", t)          # 无边界、无符号、从串中任意位置起匹配
...
m = re.search(r"[零一二两三四五六七八九十百千万]+", t)   # 同样只匹配“能匹配的前缀”
```
另外：**`parse_inner_amount` / `_parse_inner_amount` 全库无生产调用方**（仅本文件定义与别名；`backend/client.py:207-208` 的真实通道是 `propose_inner_transfer(s, p.get("amount", 0))` → `int(amount)`，实测 `'50万'`/`'五十万'` 一律被拒为「金额须为整数贯」）。因此中文金额解析目前是**死的兼容代码**，而它声称支持的「五十万」在真实链路上全部失败。
- 影响：解析正确性无实际收益（未接线）；一旦接线，`五亿→5`、`-500→500`、`拨3个州→3 贯` 会直接造成错额调拨（`propose` 只校验正数与余额，不会发现量级错）。
- 验证方式：`python b_amount.py`
- 建议修复：接线到 `propose_inner_transfer`（前端/AI 文本 → 金额）；解析改为「全串锚定 + 白名单符号」：`re.fullmatch(r'[正]?(\d+(\.\d+)?|[零一二两三四五六七八九十百千万亿壹贰叁…]+)万?贯?', t)`，未知单位（亿）→ 明确拒绝而非取前缀；`_CN_NUM` 补 `亿/壹/贰…`；返回值统一为上界钳制（如 `min(v, 10**12)`）。

---

### B-9 [P2] 并发写同一槽位：固定 `.tmp` 名导致 `os.replace` 失败，自动存档被静默吞掉

- 位置：`core/save_load.py:187`（`tmp = f"{path}.tmp"`）、`191`（`os.replace`）、`192-198`（失败清理）；调用方 `core/commands.py:517-522`
- 证据：**[确认]**（实跑 `g_invariants.py` G3、`g6_tmprace.py` G6）

```python
# core/save_load.py:187-198
tmp = f"{path}.tmp"                      # ← 固定名，非“每写者唯一”
try:
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)
except Exception:
    try:
        if os.path.exists(tmp):
            os.remove(tmp)               # ← 也可能删掉别的写者正在写的 tmp
    except OSError:
        pass
    raise
```
G3（3 进程 × 15 次写同一槽位）：每个进程都反复抛
```
worker 异常: PermissionError [WinError 32] 另一个程序正在使用此文件…
```
G6（确定性复现：另一写者持有 `slot_6.json.tmp` 时调 `save_game`）：
```
File "D:\codebuddy\sz\game\core\save_load.py", line 191, in save_game
    os.replace(tmp, path)
PermissionError: [WinError 32] …: 'slot_6.json.tmp' -> 'slot_6.json'
残留 .tmp: True    目标档存在: False
```
- 影响：Windows 下「目标/临时文件被另一句柄占用」时 `os.replace` 失败 → `save_game` 抛异常。`/api/save` 变 500；而 `finish_turn` 的自动存档是 `except Exception: pass`（`commands.py:517-522`），于是**每年正月的自动存档会静默失败**，玩家毫不知情。触发前提是两个写者（两个后端实例 / 两个窗口 / 外部备份工具占用）。同盘/跨盘语义在此不是问题（同目录 rename），真正的问题是 tmp 名不唯一。
- 验证方式：`python g_invariants.py`（G3）、`python g6_tmprace.py`（G6）
- 建议修复：`tmp = f"{path}.{os.getpid()}.{uuid4().hex[:8]}.tmp"`，`os.replace` 失败时重试；`finish_turn` 的自动存档失败至少 `_flog.warning`（与记忆库写盘失败同规，勿静默）。

---

### B-10 [P2] 损坏档的「损坏」状态不可持续，且 `.corrupt` 备份会被覆盖

- 位置：`core/save_load.py:228-239`（备份并返回 None）、`589-615`（`get_save_slots`）
- 证据：**[确认]**（实跑 `e_wiring.py` E3、`a_saveload.py` A7）

```
A7  第一次 load_game(3) -> None ；slot_3.json 存在: False ；slot_3.json.corrupt 存在: True
E3  第一次 load_game(2) -> None
    load 之后 get_save_slots()[2] = {'slot': 2, 'empty': True}
```
`get_save_slots` 的 `corrupt: True` 分支（`save_load.py:606-612`）要求文件**仍然存在**，而 `load_game` 已经把损坏档 `os.replace` 走了 → 前端下次轮询看到的是「空槽」，P3 修复想给的「存档损坏」提示实际只在读档失败那一次性的 500/返回值里，随后彻底消失。
另：`path + ".corrupt"` 也为固定名，第二次损坏会覆盖上一次的证据文件（`j_corrupt.py` 实跑）：
```
load#1: None | .corrupt 内容: {"first_broken":
load#2: None | .corrupt 内容: {"second_broken":   ← 上一次的损坏档样本已被覆盖
```
- 影响：玩家看到空槽 → 以为档没了或直接覆盖存新档，损坏档的事后排查证据丢失。
- 验证方式：`python e_wiring.py`（E3）、`python a_saveload.py`（A7）、`python j_corrupt.py`
- 建议修复：备份名带时间戳（`slot_2.20260918-2055.json.corrupt`）；`get_save_slots` 除文件存在性外再扫描 `.corrupt`，把对应槽标为 `corrupt: True` 并提供「恢复备份」入口。

---

### B-11 [P2] 每回合两次全量深拷贝快照（且内外层冗余）

- 位置：`core/commands.py:430`（`advance_and_settle` 内快照）、`471`（`settle_local` 内再快照）
- 证据：**[确认]**（实跑 `d_snapshot.py` D6）

```
_snapshot_state 单次 ≈ 51.3 ms（关系 400 条）
新开局 state 单次快照 ≈ 15.0 ms
state 字段数: 126 （含 prefectures 21 路 × pops / external_regimes 41 政权）
advance_and_settle 内一次 + settle_local 内一次 = 每回合 2 次全量深拷贝
```
而 `/api/advance` 的路径正是 `LocalBackend.advance → cmd.advance_and_settle → settle_turn → settle_local`，`settle_local` 的快照被外层完全覆盖（外层覆盖范围严格更大）。此外 `state.memory` 整图也在深拷贝之列（B-4 的 D1），随长期游玩线性增长。
- 影响：同步端点全程持 `_lock`（`server.py:334`），每回合无条件多付 30–100ms 且随图增长；纯浪费，不是正确性问题。
- 验证方式：`python d_snapshot.py`（D6）
- 建议修复：`settle_local(state, _outer_snap=None)`，由 `advance_and_settle` 传入已有快照复用；或改为写时复制（只对即将被写入的字段做快照）。

---

### B-12 [P2] `run_monthly_settlement` 污染全局随机状态（同类修复有残留）

- 位置：`core/settlement.py:331`，对照已修版本 `core/commands.py:213-234`
- 证据：**[确认]**（实跑 `f_exceptions.py` F5）

```python
# core/settlement.py:331
random.seed(state.turn * 1000003 + seed_offset)     # 无 stash/restore
# core/commands.py:216-234（advance_month，审查 P3 已修同款问题）
_stash = _rnd.getstate()
try:
    _rnd.seed(_seed); ...事件...
finally:
    _rnd.setstate(_stash)
```
实跑：
```
advance_month 后全局 RNG 是否还原: True
run_monthly_settlement 后全局 RNG 是否还原: False
```
- 影响：结算之后、下一次 `advance_month` 之前的随机调用（`issue_kouyu` 的口谕走样 `random.random()`、`commands_decree.py:613,619`；`issue_kouyu` 等 UI 动作）继承的是「按 turn 派生的确定流」，跨存档/跨玩家可复现，且与调用次数耦合。可复现性本身是设计意图（docstring 明说），但与同类 P3 修复的口径不一致，属**未收口**。
- 验证方式：`python f_exceptions.py`（F5）
- 建议修复：与 `advance_month` 同规（stash/seed/restore），确定性由 `seed_offset` 参数显式保证，而不是靠改写进程级 RNG。

---

### B-13 [P2] 国库崩坏终局分支不推进回合 → `turn` 停滞

- 位置：`core/settlement.py:341-345`
- 证据：**[确认]**（实跑 `c_rollback.py` C5）

```python
if state.deficit_depth() > TREASURY_COLLAPSE_LINE:
    state.game_over = True
    state.game_result = "..."
    log.append("[民生] 国库崩坏至不可复救…")
    return log                    # ← 唯一不在末尾推进 turn 的出口
```
实跑：
```
log: ['[民生] 国库崩坏至不可复救，国用耗竭，天下鼎沸！']   turn: 3 (未推进) game_over: True
再次调用 log 相同: True   turn: 3
```
- 影响：终局后 `state.turn` 不再前进，`finish_turn` 的「每 6/12 回合压缩」「每 3 回合召对总结」不再触发，`settlement_log` 也不再追加（`state.settlement_log.append(log)` 在 return 之后）。幂等性上无害（不会重复计征），但与「回合推进收敛到结算内部」的声明不符，且 `finish_turn` 的自动存档仍会在 `game_over` 时写盘——存下来的档 turn 与实际月份不一致。
- 验证方式：`python c_rollback.py`（C5）
- 建议修复：把 `state.turn += 1` / 月份推进提到崩坏判定之前（或在该分支内显式推进一次），保证「一次结算 = 一个回合」不变式。

---

### B-14 [P2] 未接线核对：`wired` 守卫不存在、`finance` 白烧 token、`settle_local` 绕过强制 AI

- 位置：`core/agent_router.py:35-44,156-165,232-233,271`；`core/commands.py:459-478`；`backend/client.py:142-156`
- 证据：**[确认]**（实跑 `e_wiring.py` E2 + 全库检索）

```
AGENT_DEFS 中带 wired 标志的: {}          ← 全库只有 (agent_router.py:232,271) 两处读取，无任何一处写入
route_agents('减免税赋') -> ['diplomacy','finance','economy','faction','narrative']
route_agents('整顿盐法') -> ['diplomacy','finance','economy','faction','narrative']
注入结果: ['finance'] | state._finance_ai = {'tax': '增'}
结算侧是否读取 _finance_ai: settlement.py=0 次, settlement_steps.py=0 次
```
```python
# core/agent_router.py:42-43 注释
# 审查 P2-36（登记，未停用）：结算侧暂无消费者（_settle_finance 不读 _finance_ai）
# → 唤醒结果会被丢弃（白烧 token）。接线需先设计消费语义，见 PENDING_CONTRACTS。
# core/agent_router.py:232-233
if adef.get("wired") is False:
    continue  # 审查 P2-36：契约未接线（结算侧不消费）→ 不唤醒，避免白烧 token
```
守卫代码存在，但**没有任何 agent 定义设置 `wired`**，所以 `finance` 照样被唤醒、照样调 `finance_decide`（真实网络/token 消耗）、结果被写进 `state._finance_ai` 后无人消费。另 `PENDING_CONTRACTS`（159-165）中 `("_reform_ai","reform_decide","core/settlement.py::_apply_reform")` 的消费者名不准（实际消费点是 `settle_reform`，`settlement.py:205`；`_apply_reform` 不存在）。
另外接线状态：`LocalBackend.advance_month` / `LocalBackend.settle_local` / `core/async_ai.run_settlement_ai` 全库无生产调用方（`backend/server.py` 只有 `/api/advance → _backend.advance`）—— `async_ai` 的 docstring 也已自认未接线（`async_ai.py:3-12`）。潜在风险：若照 T6 计划接上 `LocalBackend.settle_local`，它走的是 `cmd.settle_local`（无 AI 可用性门禁、无 `_ai_prelude`、无月报），会**绕过 `settle_turn` 的「AI 缺失即拒绝式」** 全游戏级不变量（`commands.py:258-259`），在无 AI 时静默结算。
- 影响：持续 token 浪费（每次涉及税法字样的诏令都白跑一次 finance 推演）；登记表与实现漂移，掩盖真实接线状态。
- 验证方式：`python e_wiring.py`（E2）；`python -c` 检索 `_finance_ai` 计数
- 建议修复：给 `finance` 定义加 `"wired": False`（或从 `AGENT_DEFS` 摘除，仅留 `PENDING_CONTRACTS` 登记）；修正登记条目的消费者名；给 `settle_local` 加 AI 门禁或标注 `_internal`。

---

## 附录 A · 低价值观察与范围外发现

| # | 观察 | 位置 | 证据 |
|---|------|------|------|
| A-1 | `_state_to_dict` 中 `_ai_failures` 专用分支**不可达**：循环第一行 `if k.startswith("_"): continue` 先于 `k == "_ai_failures"`，故「AI 失败对玩家全静默」的修复实际未生效（实跑：快照无 `ai_failures` 键） | `backend/server.py:202-203` vs `217-225`（**范围外文件**，但它是 `state._ai_failures` 的唯一消费者） | 确认（E1） |
| A-2 | 声明但从不落档的字段：`pending_public_decrees`（全库仅初始化处出现，无写方无读方）、`_prestige_history`（仅 `change_prestige` 追加，无读取方）。其余 7 个未落档字段均可解释（`_dialogue_memory`/`memory`/`memory_slot`/`pending_imperial_trip`/`difficulty_presets`/`_price_mult`/`_emperor_ai`） | `core/game_state.py:191,375` | 确认（H1/H4） |
| A-3 | `save_game` 的 `data` 字典里 `"defense_lines"` 出现两次（`:101` 与 `:163`），后者胜出；前者是死代码，无实际影响 | `core/save_load.py:101,163` | 确认（H1） |
| A-4 | 槽位未做范围/类型校验：`SlotReq(slot=-5)` 被接受并写出 `slot_-5.json`（`get_save_slots` 只列 1–5，永远不会再露出）；`_slot_path` 用 f-string 拼名，若**内部**调用方传字符串则 `../` 可穿越（HTTP 层 Pydantic `int` 已挡住 `"../../x"`） | `core/save_load.py:10-12`、`backend/server.py:275-276` | 确认（A10/A11） |
| A-5 | 自动存档(slot 0)发生在 `finish_turn`，而 `memorials` 在 `advance_and_settle` 末尾生成（`commands.py:439-452`）→ 每年正月的自动档不含本月奏折；同理记忆库落盘也早于本次上折 | `core/commands.py:516-522` vs `434-452` | 疑似 |
| A-6 | 已核无缺陷（历史修复确认有效）：① 人口总账 Step10.5：12 回合逐月 `population == ΣPOP+流民` 全对齐；② 内帑调拨确认前复检余额有效；③ `advance_and_settle` 事件+结算同快照，AI 缺失回滚后 `active_events`/`turn`/字段全部还原；④ 结算断言（太仓恒等/财政恒等）抛错时回滚且 turn 不推进；⑤ 双端「非幂等端点不自动重试」纪律真实存在（`backend/client.py:326-346`、`frontend/src/renderer/api/client.ts:213-217,229-232`、`Dock.tsx:49` 的 `advancing` 守卫），未发现重复推演通道；⑥ `pending_inner_transfer` 负额/超额/非法额均拒绝式处理 | 见右列位置 | 确认（G1/G2/C2/C7/B3） |

## 附录 B · 本轮实际运行的验证命令

统一前置（CodeBuddy shim 规避）：

```powershell
$env:PYTHONPATH=''; $env:PYTHONIOENCODING='utf-8'
Remove-Item Env:CODEBUDDY_TOOL_CALL_ID -ErrorAction SilentlyContinue
Remove-Item Env:CODEBUDDY_SAFE_DELETE_BULK_STATE_DIR -ErrorAction SilentlyContinue
cd D:\codebuddy\sz\game
```

| 脚本 | 覆盖 | 关键结论 |
|------|------|----------|
| `python D:\codebuddy\sz\_dev_tools\_scratch\audit-2026\a_saveload.py` | 存档往返/缺字段/空档/损坏档/schema_version/路径注入/并发线程 | A1 往返一致；A2/A3 缺字段不崩；**A4 崩**；A7 备份后原档消失；A9 null 字段变 None；A11 字符串槽位被 Pydantic 拒；A12 单进程 8 线程未复现；A13 记忆库超前 |
| `...\b_amount.py` | 内帑金额解析与调拨边界（32 例） | 负号丢失、`五亿→5`、`3.5万→50000`、任意数字误取；解析器无调用方 |
| `...\c_rollback.py` | 快照别名/异常注入回滚/重试权重/水位/崩坏分支/双次推进/AI 缺失回滚 | C1 别名断裂；C2 字段回滚完整；C4 记忆库超前；C5 turn 停滞；C6 无双重计数；C7 事件与 turn 均回滚 |
| `...\d_snapshot.py` | 深拷贝覆盖/对象替换/对话库回滚/瞬态键/别名/耗时 | D1 memory 可深拷贝；D3 对话库残留；D4 瞬态键不被清；D5 别名断裂；D6 15–51ms/次×2 |
| `...\e_wiring.py` | `ai_failures` 下发/`wired` 守卫/损坏槽显示/None 档/字段覆盖 | E1 分支不可达；E2 finance 白烧 token；E3 损坏槽显示 empty |
| `...\f_exceptions.py` | null 字段结算崩溃/`_run_fixed` 入参/未知 category/回滚自身异常/全局 RNG | F1 三种 null 崩；F2 ValueError+TypeError；F5 RNG 未还原 |
| `...\g_invariants.py` | 人口不变量/断言回滚/多进程并发写/`state.memory` 别名检索 | G1 12 回合全对齐；G2 回滚有效；G3 并发 PermissionError |
| `...\g5_conc.py`、`...\g6_tmprace.py` | 并发写定位 | G6 精确定位 `save_load.py:191 os.replace` WinError 32 |
| `...\h_fields.py` | state 字段 vs 落档键机械核对 | 127 字段中 123 落档，9 个未落档字段逐个可解释 |
| `...\j_corrupt.py` | `.corrupt` 备份名固定 → 覆盖验证 | 第二次损坏覆盖第一次的备份样本 |
| `...\i_silent.py`、`...\i2_instant.py` | 即时诏令空转与假回执 | `fixed_tech/construction/army` instant 全部空转却回执「已施行」 |

> 全部脚本只读 game 源码；存档读写均通过替换 `content.data.SAVE_DIR` / `core.save_load.SAVE_DIR` / `memory.memory_graph.SAVE_DIR` 重定向到 `_dev_tools\_scratch\audit-2026\_saves_*`，未触碰 `Documents\宋祚\saves`。
