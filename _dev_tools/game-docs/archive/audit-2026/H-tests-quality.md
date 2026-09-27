# H · 测试质量与盲区审查

> 审查对象：《宋祚 Songzuo》测试套件（`_dev_tools/game-dev/tests`，48 个 `test_*.py`，390 项）
> 审查方式：全量跑测 + `--cov` + 逐行读测试/源文件 + 独立探针复现（全部探针置于 `_scratch/audit-2026/h_*.py`）
> 审查原则：**未修改 `game/` 与 `tests/` 下任何文件**（纯审查）
> 基线实跑（本次独立复现）：**379 passed / 11 failed / 390 collected**，与委派基线完全一致
> 解释器：`D:\codebuddy\.audit-venv\Scripts\python.exe`（3.13），跑前清 `PYTHONPATH` + `CODEBUDDY_*` 变量

---

## 结论速览

| 编号 | 严重度 | 一句话 | 位置 | 证据类型 |
|---|---|---|---|---|
| H-1 | **P0** | `_resolve_path_value` 被整段删除留下 2 处悬空引用，使 `applier_pipeline` **成功路径 100% NameError**，生产唯一调用方 `relief_grant` 完全失效（被裸 `except` 吞成用户文案） | `engine/state_applier.py:677,710`；调用方 `ai/client_utils.py:794,810` | [确认] 实跑探针 |
| H-2 | **P0** | 测试套件向**真实用户存档目录** `Documents\宋祚\saves` 写入 slot 0/1/2/3/4/5/6/7/9，清理只删 `.json` 不删 `.db`；跑一次测试即覆盖玩家存档（含默认槽 1 与自动档 0） | 11 个测试文件（见 H-2）；`core/commands.py:520`；`core/save_load.py:12,25` | [确认] 文件时间戳 + 代码 |
| H-3 | **P0** | B3 重构把 `TREASURY_CRISIS_LINE` 从「负国库下界 −500万」反转成「累计亏空深度 +500万」，**测试与机制文档同步过期**——这是 5 项失败（#5/#7/#8/#9/#10）的唯一根因 | `content/data.py:360-370`；`docs/游戏机制说明.md:476` | [确认] 文档 + 实跑 |
| H-4 | P1 | 零 CI、无 `conftest.py`、逐文件手写 `sys.path` hack；`test_state_applier.py:5` 插入了**错误目录**，单跑即 collect error，全量跑只因收集顺序依赖其它文件的 `sys.path` 副作用而"侥幸通过" | `tests/test_state_applier.py:5` | [确认] 两种 runner 实测对比 |
| H-5 | P1 | `backend/server.py` **469 语句 0% 覆盖**：19 个 `/api/*` 端点 + 鉴权 `_require_auth` 无任何测试；`/docs`、`/redoc`、`/openapi.json`、`/health` 未鉴权；`httpx` 不在任何 requirements → 当前**写不了** TestClient 测试 | `backend/server.py:80,312-787,826` | [确认] 路由表实测 + requirements |
| H-6 | P1 | `ai/client.py` **29%**、`client_utils.py` 43%：真实 HTTP 传输 `_http_post_json` 在**全部**测试中被 monkeypatch，超时/401/403/畸形 JSON 等真实传输路径零覆盖 | `ai/client_utils.py:43`；`tests/test_t1_state_tools.py:86,120` | [确认] grep + 覆盖率 |
| H-7 | P1 | 测试替身 `FakeAIClient` **缺 6/9 个 agent 方法**，用它的"AI 结算"测试实际跑的是 **AI 全失败 → 模板降级**路径，且降级被 try/except 静默吞掉 | `tests/fake_ai_backend.py:6-26`；使用点 `test_core_logic.py:171,239` | [确认] 探针捕获警告 |
| H-8 | P1 | 号称"钱粮守恒"的断言容差 **5000 万贯**，而实测单月净变化最大仅 1226 万（容差的 24.5%）→ 俸禄指数化黑洞（−4.4 万/月）、市舶关税双计（数十万/月）这类**真实守恒破缺**全部静默放过 | `tests/test_core_logic.py:244` | [确认] 同口径复算 |
| H-9 | P1 | 前端 **10,864 行 TS/TSX 零测试**：无 `test` script、无 vitest/jest/playwright 依赖与配置、无任何 `*.test.*`，唯一自动化是 `tsc --noEmit` | `frontend/package.json` scripts/devDeps | [确认] 目录与配置实查 |
| H-10 | P2 | 弱断言/伪绿 **20 条**：`assert out >= 0`、`assert isinstance(x, float)`、`assert game_over in (True, False)`（恒真）、文档承诺守恒而断言只查非负等 | 见 §四 | [确认] 逐行读码 |
| H-11 | P2 | 实现细节/过拟合断言：用 `inspect.getsource` 断言**源码文本**、断言"并行模块不并行"、镜像常量自身值 | `test_review_p0_conservation.py:93-99`；`test_parallel_settlement.py:94`；`test_finance_decide.py:23-34` | [确认] 逐行读码 |
| H-12 | P2 | 全局状态与顺序耦合：`CHANGE_LOG` 模块级全局无 fixture 复位、`random.seed` 全局播种、`finish_turn` 无条件自动存档（写真实槽 0） | `engine/state_applier.py:780-784`；`test_state_applier.py:75,90` | [确认] 代码 |
| H-13 | P2 | 存档损坏/旧档迁移覆盖不全：`.corrupt` 备份分支、`schema_version>2` 拒绝分支、槽位损坏标记分支均**无测试**（被覆盖率标为未执行） | `core/save_load.py:228-250,606-612` | [确认] 覆盖率 missing 行 |
| H-14 | P2 | **无版本控制**（`D:\codebuddy\sz` 下无 `.git`）→ 任何回归都无法 bisect / 归因，这是"11 项失败长期无人发现"的结构性放大因子 | 仓库根 | [确认] 实查 |
| H-15 | P2 | 7 个测试文件的 `__main__` 手工跑测入口已腐化；`test_core_logic.py:251` 调用已改名函数，直接运行即 `NameError` | `tests/test_core_logic.py:251` | [确认] 实跑 |
| H-16 | P2 | `memory/*` 的 SQLite 并发/WAL/`busy_timeout` 无测试；已有的事务回滚测试质量**很好**（应作为范式推广） | `memory/memory_graph.py:611-625`；`test_memory_sqlite.py:138-164` | [确认] 读码 |
| H-17 | P2 | 生产代码 `relief_grant` 失效的同时，**整个 `engine/state_applier.py`（402 语句）只有 1 个生产调用点**；"AI 契约 → 守恒 → 原子写库"这套被文档当作核心架构的管线，实际只为 1 个工具服务 | `ai/client_utils.py:794`（唯一） | [确认] 全库 grep |

**条目统计：P0 × 3，P1 × 6，P2 × 8（共 17 条）**

---

## 一、11 项失败复核分类

### 先给结论：不是 11 个独立缺陷，而是 **2 次重构波 + 1 次通道删除** 的残留

我把 11 项失败映射到 3 个根因簇，这是本次审查最重要的结构性发现：

| 簇 | 触发重构 | 失败项 | 计数 |
|---|---|---|---|
| **簇 A：B3 财政语义反转**（−500万国库下界 → +500万亏空深度） | `content/data.py:360-370` 的 B3 修复 | #5, #7, #8, #9, #10 | 5 |
| **簇 B：D 修复删死代码时误删活函数** | `engine/state_applier.py:286-292` 的 D 修复 | #1, #2, #3, #4, #6 | 5 |
| **簇 C：B1 修复删除市舶关税双计通道** | `core/settlement_steps.py:1023-1026` 的 B1 修复 | #11 | 1 |

三处源码注释**都完整记录了重构意图**，但没有一处同步了测试。

### 逐项复核表

| # | 测试 | 我的基线结论 | 我的复核（新增证据） | 最终分类 | 修复应落在 |
|---|---|---|---|---|---|
| 1 | `test_state_applier.py::test_pipeline_apply_log` | NameError `_resolve_path_value` | **测试期望完全正确，代码是坏的。** 探针证实 `hasattr(state_applier,'_resolve_path_value') == False`；`state_applier.py:292` 的注释行**把 `def` 一行一起吞进了注释块**：`# 已整体移除。def _resolve_path_value(state, path: str):`，而其函数体（293-322 行）仍以活代码形式留在后面。677、710 两行是活代码引用（探针 [E] 逐行列印）。710 行在 `_simulate_underflow` 内，而 855 行**无条件**调用它 → 凡是守恒校验通过的正常成对变更，**100% 抛 NameError**。 | **[代码缺陷]** | **代码**（恢复函数或改调 `_locate_path`） |
| 2 | `test_state_applier.py::test_pipeline_rejected_collected` | 同上 | 同上。该用例断言"合法成对执行 + 非法收集"，走的是 855 行之后才被拒的**正常路径**，因此必然先撞 NameError。 | **[代码缺陷]** | 代码 |
| 3 | `test_state_applier.py::test_underflow_reject_no_mint` | 同上 | 同上。**这是 P0-6 穿底防护的核心用例**——它想验证"穿底即整单拒绝"，但 `_simulate_underflow` 自己就是崩的那个函数，于是防线的**测试与实现同时失效**，无任何信号。 | **[代码缺陷]** | 代码 |
| 4 | `test_review_2026_09_fixes.py::test_relief_region_resolve_and_refuse` | 同上的现场表现 | **升级为独立 P0（H-1）。** 探针 [C] 走真实生产入口 `ai.client_utils._tool_dispatch(..., 'relief_grant', region='两浙路')`，实测返回 `'赈济未能落地（状态应用层异常，已拒绝）'`、国库 Δ=0。即 **`relief_grant` 工具在真实游戏中 100% 无法落地**（不是测试问题）。`ai/client_utils.py:810` 的裸 `except Exception` 把它降级成一句文案，日志与 UI 均无异常痕迹。 | **[代码缺陷]** | 代码（并收窄裸 except） |
| 5 | `test_regression_2026_08.py::test_treasury_stays_above_crisis_line` | 36 月第 1 月即 `treasury=4,817,977 < 5,000,000` | **量纲错配，非结构性财政赤字回归**——详见下方专节。 | **[测试过期]** | **测试**（断言改判 `deficit_depth()`） |
| 6 | `test_state_applier.py::test_cascade_faction_power` | `[]`（规则已删） | **代码正确，测试未同步。** `state_applier.py:286-291` 用 6 行注释论证了删除理由（① `factions.*.power` 不在 `VALID_PATHS`，`validate_changes` 会先拒；② `FactionState` 根本没有 `power` 字段）。即该 cascade 规则**永不可能被触发**，删除是正确的。测试第 68 行 `assert extra and all("influence" in e["path"] ...)` 锁的是一个**从未存在过的行为**。 | **[测试过期]** | **测试**（删除或改测现有 cascade 规则） |
| 7 | `test_briefing.py::test_briefing_desensitized` | `s.treasury = -6e6` 无效 | **测试构造了一个物理上不可达的状态。** `core/briefing.py:77-78` 已改读 `s.treasury_deficit`；而 `game_state.py:744-750` 的 `deficit_depth()` 与 `content/data.py:363-365` 注释明确"国库写入全链路禁止穿底，负余额永不存在"。测试第 41 行直接给 `s.treasury` 赋负值，**绕过了 `change_treasury` 的 `max(0,…)`**，构造出现实中不可能出现的 state。正确写法是 `s.treasury_deficit = TREASURY_CRISIS_LINE + 1`。 | **[测试过期]** | **测试** |
| 8 | `test_briefing.py::test_briefing_urgent_flags` | 同上 | 同上（第 55 行同样 `s.treasury = -6_000_000`）。附带：该用例第 64 行 `assert all(a.get("goto") in ("decree","army") for a in urgent)` 是**过约束**——`briefing.py` 的 border 急务 `goto` 是 `ARMY`、`mood` 急务 `goto` 是 `DECREE`，但若将来新增一个 `goto=TECH` 的急务，此断言会假失败而与被测缺陷无关。 | **[测试过期]** | 测试 |
| 9 | `test_core_logic.py::test_game_over_treasury_collapse` | 常量量纲变了 | **测试同时踩了两个坑。** ①`evaluation.py:174-179` 已改判 `state.deficit_depth() > TREASURY_COLLAPSE_LINE`；②测试第 112 行 `s.treasury = TREASURE_COLLAPSE_LINE - 1 = 19,999,999` 不但没设 `treasury_deficit`，反而把国库设成**近 2000 万**（巨额盈余）——语义完全颠倒。正确写法：`s.treasury_deficit = TREASURY_COLLAPSE_LINE + 1`。 | **[测试过期]** | **测试** |
| 10 | `test_core_logic.py::test_game_over_abdication` | 仍用负国库旧语义 | **证据更硬：该用例需要"2 个退位理由"，而新语义下只凑得出 1 个。** `evaluation.py:142-147` 的理由是 `satisfaction<20` 与 `deficit>CRISIS_LINE`。测试设 `satisfaction=10`（✓ 1 个）与 `treasury=-6e6`（✗ 不再计入）。第 157 行 `if len(reasons) >= 2` 不成立 → 返回 False。修复只需把 `s.treasury=-6e6` 换成 `s.treasury_deficit = TREASURY_CRISIS_LINE + 1`。 | **[测试过期]** | **测试** |
| 11 | `test_pop_identity.py::test_maritime_trade_ledger_closed` | 双计通道已删 | **实测断言失败值极具说明性：`dT=0`，期望 `166666`。** 即 `_settle_extensions` 现在**一分钱关税都不入国库**（不再是"少算"，而是"零"）。`settlement_steps.py:1023-1026` 注释逐字写明：关税的**唯一**入账通道是 `_settle_finance`（该函数在 `settlement_steps.py:2808-2812` 把 `maritime_tax` 汇入 `monthly_tax` → 国库），原 `state.treasury += 关税` 属"第二次全额入账且无对手账户（凭空增币）"。测试文档字符串 `"""市舶贸易钱账本闭口：关税抽解入国库…"""` 描述的正是被删除的行为。 | **[测试过期]** | **测试** |

### 最终分类计数

> **[代码缺陷] 4 项**（#1 #2 #3 #4）· **[测试过期] 7 项**（#5 #6 #7 #8 #9 #10 #11）· **[真实回归] 0 项**

**"0 项真实回归"本身是个重要结论**：这套 390 项测试里，当前 11 个红灯**没有一个**在报告真实的行为退化——全部是"代码进化、测试没跟上"或"测试守着一个已坏的生产功能"。这意味着红灯数量与产品健康度**完全脱钩**，红灯被当成噪音是理性的，而这恰恰是最危险的测试文化。

---

### 第 5 项专项复核：是"结构性财政赤字回归"还是"测试阈值不合理"？

**我的独立判断：这是测试阈值不合理（量纲错配 + 起手值恰等阈值），不是结构性财政赤字回归。** 五条独立证据：

#### 证据 1：断言与被断言的量纲根本不是同一个东西 [确认]

```
content/data.py:360-370
# 破产兜底：**累计亏空深度**的两档阈值（贯，正数）
#   TREASURY_CRISIS_LINE：累计亏空超过此深度触发"库藏空虚"危机事件…
# B3 修复（原为负值 −500万 / −2000万）：国库写入全链路禁止穿底
#   （GameState.change_treasury 与 _settle_finance 均 max(0,…)），负余额永不存在，
#   原阈值针对「state.treasury < 负数」判定 → 两条线与全部消费方均为死分支
TREASURY_CRISIS_LINE = 5_000_000      # ← 单位是「亏空深度」
```

而测试 `test_regression_2026_08.py:66`：

```python
assert s.treasury > TREASURY_CRISIS_LINE, f"国库触危机线：{s.treasury}"
#      ↑ 单位是「国库余额」
```

**把余额和亏空深度比大小，是范畴错误。** 正确的等价判据是 `state.deficit_depth() <= TREASURY_CRISIS_LINE`（`core/evaluation.py:51`、`core/briefing.py:77`、`core/settlement.py:341,346` 三个生产消费方全部用 `deficit_depth()`，无一处用 `treasury` 与该常量比较）。

#### 证据 2：`TREASURY_START == TREASURY_CRISIS_LINE`——断言在**开局第 0 步就已为假** [确认]

```
content/data.py:155  TREASURY_START      = 5_000_000
content/data.py:369  TREASURY_CRISIS_LINE = 5_000_000
```

探针 `h_probe_treasury.py` 直接打印：`开局 treasury = 5,000,000 vs CRISIS_LINE = 5,000,000 -> 开局即不满足 > 断言: False`

一个 `>` 断言而初始值 `==` 阈值，**只要第一个月净支出 1 文钱就必然失败**。第 1 月净变化实测 `−182,023`（探针逐月剖面）。这与财政是否健康毫无关系——**断言在设计上就不可能通过**。这正是委派说明里说的"过拟合/自相矛盾阈值"。

#### 证据 3：10 个 seed × 36 月的国库分布——**没有崩盘，只有高位回落** [确认]

`h_probe_treasury.py`（`seed_offset ∈ {100,1,7,13,42,2026,999,3,55,808}`）：

| seed | M1 国库 | M36 国库 | 36 月内 `max(deficit_depth)` | 真实触危机线? | 断言失败? |
|---|---|---|---|---|---|
| 100 | 4,817,977 | 1,747,520 | **0** | 否 | 是 |
| 1 | 4,817,986 | 2,866,123 | **0** | 否 | 是 |
| 7 | 4,817,987 | 3,281,099 | **0** | 否 | 是 |
| 13 | 4,817,987 | 3,236,973 | **0** | 否 | 是 |
| 42 | 4,817,987 | 2,264,453 | **0** | 否 | 是 |
| 2026 | 4,817,977 | 3,032,813 | **0** | 否 | 是 |
| 999 | 4,817,982 | 1,807,556 | **0** | 否 | 是 |
| 3 | 4,817,983 | 3,639,572 | **0** | 否 | 是 |
| 55 | 4,817,978 | 3,330,251 | **0** | 否 | 是 |
| 808 | 4,817,987 | 2,447,669 | **0** | 否 | 是 |

**真实触发「库藏空虚」判据（`deficit_depth() > CRISIS_LINE`）的 seed 数：0/10。断言失败的 seed 数：10/10。**
两个数字的背离本身就是判决：**被测系统的健康指标 100% 通过，测试断言 100% 失败** → 错的是断言。

#### 证据 4：120 月长程回放——国库**回升到 1900~2400 万**，亏空深度恒为 0 [确认]

`h_probe_horizon.py`（5 seed × 120 月）：

| seed | 国库归零@月 | 触危机线@月 | 触破产线@月 | M36 国库 | **M120 国库** | M120 亏空深度 |
|---|---|---|---|---|---|---|
| 100 | 无 | 无 | 无 | 1,747,520 | **22,039,276** | 0 |
| 7 | 无 | 无 | 无 | 3,281,099 | **19,054,292** | 0 |
| 42 | 无 | 无 | 无 | 2,264,453 | **21,846,227** | 0 |
| 3 | 无 | 无 | 无 | 3,639,572 | **24,181,309** | 0 |
| 999 | 无 | 无 | 无 | 1,807,556 | **22,603,282** | 0 |

把时间窗从 36 月拉到 120 月，国库从 175 万涨到 **2200 万（开局的 4.4 倍）**，且 120 个月内 `deficit_depth()` **恒为 0**——连危机的边都没碰到。

**所以"36 月末国库低于起手值"是真实的，但它是"中盘回落"而非"死亡螺旋"**：国库在 30~40 月附近见底，随后反转向上。测试把"不能低于起手值"当成健康标准，是**把单调性当成守恒律**。

#### 证据 5：设计意图的三方对照——**文档比测试更过时** [确认]

| 来源 | 对 `TREASURY_CRISIS_LINE` 的表述 | 语义 |
|---|---|---|
| `docs/游戏机制说明.md:476` | `TREASURY_CRISIS / COLLAPSE \| -500万 / -2000万贯 \| 危机/崩坏线` | **旧**（负值/国库余额） |
| `analysis/review_2026-08-31.md:20` | `国库：500 万 → 608 万（中间最低 -215 万，贴近危机线 -500 万）` | **旧**（负值） |
| `analysis/review_2026-08-31.md:120` | `国库：15/15 稳定（327~698 万），不再贴近危机线` | **旧**（负值） |
| `content/data.py:360-370` | `**累计亏空深度** 的两档阈值（贯，正数）…B3 修复（原为负值 −500万/−2000万）` | **新**（正值/亏空深度） |
| `analysis/code_review_report_2026-08-17.md:26` | `TREASURY_CRISIS_LINE(-500万) 与 COLLAPSE_LINE(-2000万) 在正常游玩中**永不可达**…财政压力从游戏中消失` | **动机** |

**因果链闭合**：
1. 2026-08-17 报告指出负值阈值是**死分支**（`treasury` 永不为负 → 破产/危机/财政评分三档全不可达）；
2. B3 修复把它改成"盈亏深度"正值语义，让判据真实可达；
3. `test_regression_2026_08.py` 是 2026-08-31 报告**为锁定旧语义而新增**的（报告 §七 明确写"新增 `tests/test_regression_2026_08.py`（5 用例）…国库不触危机线"）；
4. 该用例在**旧语义下**（`treasury > -5,000,000`）恒真 → 当时"384 全绿"是**真实且诚实的**；
5. B3 落地后语义反转，断言从"恒真"变成"恒假"，**无人重跑** → 一直红到现在。

所以既不是"财政崩了"，也不是"测试写错了"，而是**测试锁定的语义被设计变更整体推翻，而没有任何机制强制重跑**。这恰好把 §三 的流程问题推到台面。

#### 还剩一个真实但次要的观察 [疑似]

36 月内国库从 500 万单调滑到 175~364 万（月均约 −4 万~−9 万），期间无任何机制把它拉回——即"**中盘约 30 个月的单向失血**"。这是真实存在的现象，值得单独确认是设计意图（玩家须靠诏令开源）还是调参失衡。**但它是 P2 平衡观察项，不是 P0 回归**，且与本次红灯无关。另注：该 scenario 只注入 `_economy_ai` 桩、**无真实 AI 诏令收入**，与 2026-08-31 报告所称"中档 AI 注入 → 327~698 万"场景不可直接比较，故我标 [疑似] 而不下结论。

---

## 二、覆盖率表

**总体覆盖率（`--cov=core,engine,ai,memory,backend`，在 `game/` 下运行）**

```
TOTAL    11803 stmts    5261 miss    55%
```

> 命令与原始输出：`_scratch/audit-2026/_cov.txt`、`cov.json`（`--cov-report=term-missing --cov-report=json`）

### 2.1 零覆盖模块（6 个，972 语句，0%）

| 模块 | Stmts | 说明 | 风险 |
|---|---|---|---|
| `backend/server.py` | **469** | FastAPI 参考后端，19 个 `/api/*` 端点 + 鉴权中间件 | **最高**：可导入、可测（fastapi/uvicorn 已装），纯粹没有测试 |
| `backend/client.py` | **222** | `LocalBackend` / `HttpBackend`，服务端 100% 复用它的业务逻辑 | 高：前端与后端的唯一边界 |
| `ai/semantic.py` | 117 | 本地语义检索（可选依赖） | 中：依赖未装，属"可选增强" |
| `ai/vector_store.py` | 103 | sqlite-vec 向量库 | 中：同上 |
| `ai/model_setup.py` | 32 | 模型下载入口 | 低：运维脚本 |
| `core/external_view.py` | **29** | 外邦视图（供前端/舆图） | 中：**非可选依赖却零覆盖**，最可疑 |

> 注：`backend/server.py` 的 0% **不是**依赖缺失造成——探针 `h_be_probe.py` [2] 实测 `import backend.server` 成功并打印出完整路由表。faastapi 0.141.1 / uvicorn 0.53.0 / pydantic 2.13.5 均已安装（它们在 `requirements.txt` 里）。

### 2.2 低覆盖关键模块（< 50%）

| 模块 | Stmts | Miss | Cover | 关键未覆盖区间（节选） |
|---|---|---|---|---|
| `core/focus_mechanic.py` | 146 | 117 | **20%** | 273-509（机制主干几乎全空） |
| `core/legacy_mechanic.py` | 104 | 80 | **23%** | 29-112、185-242 |
| `ai/client_narrative.py` | 45 | 33 | **27%** | 14-86（全部叙事 agent 调用） |
| **`ai/client.py`** | **1510** | **1070** | **29%** | 950-1059、1278-1335、1376-1439、1553-1581、1646-1700、1830-1882、1887-1963、1968-2022、2225-2299、2306-2344… |
| `core/asset_context.py` | 212 | 140 | **34%** | 55-63、148-184、226-274、366-409 |
| `core/settlement.py` | 240 | 154 | **36%** | **65-115（`run_monthly_settlement` 主体）、178-211、216-312（异常回滚！）** |
| `ai/schemas.py` | 21 | 13 | **38%** | 100-112 |
| `ai/token_meter.py` | 86 | 53 | **38%** | 122-167 |
| `memory/dialogue_memory.py` | 127 | 76 | **40%** | 95-108、118-165、190-226 |
| `core/commands_decree.py` | 412 | 244 | **41%** | 143-191、242-280、560-659 |
| `ai/client_utils.py` | 521 | 296 | **43%** | 28-83（`_http_post_json` 传输层）、540-598、672-745、1036-1070 |

### 2.3 中覆盖但含高危未测区间

| 模块 | Cover | 高危未测行 |
|---|---|---|
| `engine/state_applier.py` | 62% | **711-720（`_simulate_underflow` 判定体）、732-785（`apply_to_state` 原子写入 + 回滚）、827-835、856-879** |
| `core/save_load.py` | 72% | **27-29、192-198、231-243（损坏备份路径）、591-615（槽位损坏标记）** |
| `core/evaluation.py` | 80% | **53-59（财政评分分档）、177-179（game_over 塌陷分支）** |
| `memory/memory_graph.py` | 79% | 611-625 附近建表/WAL 分支 |

**关键读法**：`engine/state_applier.py` 的 62% 具有极强误导性——**它最核心的 4 个区间（守恒预检、原子写入、回滚、结果组装）全部在 missing 列表里**，而 NameError 正藏在 711-720 之中。覆盖率在这里不是"还行"，而是"看着还行、实际最脆"。

### 2.4 前端

| 维度 | 数值 |
|---|---|
| `frontend/src` TS/TSX | 57 文件 / **10,864 行**（+ 341 行 CSS） |
| 测试文件 (`*.test.*` / `*.spec.*` / `__tests__` / `e2e`) | **0** |
| 测试框架（vitest/jest/playwright/cypress）：依赖 | **无** |
| 测试框架：配置 | **无** |
| `package.json` 的 `test` script | **不存在**（仅 `dev`/`build`/`preview`/`build:topo`/`typecheck`/`dist`） |
| 唯一自动化 | `npm run typecheck`（`tsc --noEmit`） |

即：**前端只做类型检查，运行时行为零验证。**

---

## 三、盲区与"假绿"分析

### 3.1 为什么 390 项里 11 项失败却长期无人发现？

**根因不是"疏忽"，而是这条流水线上没有任何一个环节会强制发现问题。** 六条互相加固的结构性缺口：

#### (a) 没有 CI，也没有任何自动触发点 [确认]

```
D:\codebuddy\sz\ 下：无 .github/、无 .gitlab-ci.yml、无 Jenkinsfile、无任何 CI 配置
D:\codebuddy\sz\ 下：无 .git           ← 连版本控制都没有
```

`game/pytest.ini` 仅 4 行（`testpaths` / `python_files` / `addopts = -q`），**没有 `conftest.py`**（全仓库 0 个）。
结论：**测试只有在"某个人类主动想起来跑"时才跑。** 而 B3/B1/D 三次重构都没有人跑。

#### (b) 跑测试有一条**必须靠人肉记住**的脆弱前置 [确认]

`game/README.md:231` 逐字记载：

> **测试注意**：本机 CodeBuddy 注入 sitecustomize shim（PYTHONPATH）会干扰测试（大量假失败）——跑 pytest 前先 `$env:PYTHONPATH=''` 并删 `CODEBUDDY_TOOL_CALL_ID`/`CODEBUDDY_SAFE_DELETE_BULK_STATE_DIR` 环境变量。

`README.md:43` 亦写 "pytest 回归脚本（test_*.py；**本机跑前先清 PYTHONPATH**）"。

这段说明的危害被严重低估：**它教会开发者"红灯可能是环境噪音"**。当套件本来就常常"大量假失败"时，新增的真实失败无法从噪音中分辨——**狼来了效应**。11 个红灯被当作"又是环境问题"是这条前置条件直接训练出来的行为。

#### (c) 连"怎么跑"都不唯一，且其中一个跑法直接崩 [确认]

`test_state_applier.py:5` 计算的是**错误的目录**：

```python
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# __file__ = ...\_dev_tools\game-dev\tests\test_state_applier.py
# dirname        → ...\_dev_tools\game-dev\tests
# dirname²       → ...\_dev_tools\game-dev          ← 不是 game！
```

而其它 40+ 个测试文件都写成正确的 `join(dirname, "..", "..", "..", "game")`。

实测（两种 runner，同一文件、同一 CWD=`game`）：

| 命令 | 结果 |
|---|---|
| `python -m pytest <tests>\test_state_applier.py` | `4 failed, 14 passed`（`python -m` 会把 CWD 塞进 `sys.path`，**掩盖**了错误） |
| `pytest.exe <tests>\test_state_applier.py` | **`ModuleNotFoundError: No module named 'core'` → 收集中断** |
| `pytest.exe <tests>`（全量） | `11 failed, 379 passed` —— 该文件**竟然成功收集并运行了** |

全量能过，是因为 pytest 按文件名**字母序**收集，`test_agent_p1.py` 等更早的文件已把正确的 `_GAME_ROOT` 写进全局 `sys.path`（`sys.path` 是**进程级可变全局**）。也就是说：

> **`test_state_applier.py` 能否被导入，取决于"有没有别的测试文件先跑过"——一个隐藏的、与 runner 选择耦合的收集顺序依赖。**

这不是理论推演，上表是三行实测输出的直接结论。**任何一次"先跑单个文件"的调试都会看到 collect error**，从而进一步强化"这测试本来就跑不起来"的印象。

#### (d) 测试替身不完整，导致"AI 测试"实际在测 AI 失败 [确认]

`tests/fake_ai_backend.py:6-26` 的 `FakeAIClient` 只有 **3 个方法**（`free_effect_decide` / `economy_decide` / `monthly_report`），而 settle/route 链路实测需要 **9 个**：

```
economy_decide             OK
free_effect_decide         OK
monthly_report             OK
diplomacy_decide           *** MISSING ***
military_decide            *** MISSING ***
relief_decide              *** MISSING ***
faction_decide             *** MISSING ***
narrative_decide           *** MISSING ***
emperor_personal_decide    *** MISSING ***
```

探针 `h_probe_tolerance2.py` [C] 捕获到运行时真实警告：

```
Agent diplomacy 唤醒失败: 'FakeAIClient' object has no attribute 'diplomacy_decide'
Agent faction  唤醒失败: 'FakeAIClient' object has no attribute 'faction_decide'
Agent military 唤醒失败: 'FakeAIClient' object has no attribute 'military_decide'
Agent relief   唤醒失败: 'FakeAIClient' object has no attribute 'relief_decide'
```

**这意味着 `test_core_logic.py:171`（`settle_turn(s2, ai_client=FakeAIClient())`）与 `:239`（`test_settlement_money_conservation_no_silent_jump`）自认为在测"AI 正常推演下的回合结算"，实际测的是"5 个 agent 全部抛 AttributeError → 被 try/except 静默降级为模板兜底"。** 测试全绿，因为降级被设计成不报错。这是教科书级的**假绿**：测试名、测试意图、实际执行路径三者分离。

佐证：探针 [A] 用 `random.seed(1/7/100/2026)` 跑 `settle_turn(FakeAIClient())`，4 个 seed 的 `before/after/delta` **完全相同**（`307,807,398 → 303,123,924, Δ=−4,683,475`）——因为 agent 全挂就没有任何随机决策被消费。**这些 `random.seed` 是装饰性的。**

#### (e) "守恒"断言容差大到抓不住任何真实守恒破缺 [确认]

`test_core_logic.py:244`：

```python
assert abs(after - before) < 50_000_000     # 5000 万贯
```

我按**逐行相同口径**（`test_core_logic.py:226-234` 的 `_money_snapshot`）复算（`h_probe_tolerance2.py` [A]）：

| 指标 | 实测值 | 占容差 |
|---|---|---|
| 最大单月 \|Δ\| | 12,262,028 贯 | **24.5%** |
| 平均单月 \|Δ\| | 6,481,390 贯 | **13.0%** |

被 2026-08-31 报告点名的两个真实守恒缺陷：**俸禄指数化黑洞 −44,035 贯/月**（报告的 P1-1，原话"每月凭空消失"）、**市舶关税双计约数十万贯/月**（B1 修复对象）。二者分别只有容差的 **0.09%** 和约 **1%**。

> **结论：这条自称"P2 回归：经济守恒——单月结算不应凭空增删钱粮总量"的断言，对上述两个已确认的真实守恒缺陷 100% 无感。**
> 只有当单月凭空增减超过 5000 万贯（≈ 整个国库的 10 倍）时才会亮红。

这直接回答了 2026-08-31 报告 §五 的自问"为何 379 全绿却没抓到 P0"——**因为"守恒测试"的判定门限比缺陷本身大 2~3 个数量级。**

#### (f) 文档声称的"全绿"数字是**诚实的，但是陈旧的** [确认]

数字自洽性核对：

| 时点 | 文档表述 | 算术 |
|---|---|---|
| `review_2026-08-31.md:3` | "379 项 pytest 全绿复跑" | 修复前基线：379 |
| `review_2026-08-31.md:117` | "新增 `test_regression_2026_08.py`（5 用例）" | 379 + 5 = **384** |
| `review_2026-08-31.md:105` | "（2026-08-31 已完成，**384 项测试全绿**）" | = 384 ✓ |
| 本次实测 | 390 collected / 379 passed / 11 failed | 384 + 6 = **390** |

**384 这个数字在写下时大概率是真的**（当时 `TREASURY_CRISIS_LINE` 还是 −500万，`:66` 的断言恒真）。之后：新增 6 个测试 + B3/B1/D 三次重构，套件从"384 全绿"漂成"390 中 11 红"，**而报告再未更新**。

所以"文档说全绿 vs 实际 11 红"的差距，**不是谎言，是没有机制在变更后重跑并刷新结论**。这是 (a)(b)(c) 的必然产物。

### 3.2 覆盖盲区：没有任何测试触及的高风险路径

#### 1) 真实 AI 管线 —— 结论：**几乎全是 fake/monkeypatch，"真实调用路径"零覆盖**

| 层级 | 是否被真实覆盖 | 证据 |
|---|---|---|
| HTTP 传输 `client_utils._http_post_json`（真实 socket） | **否，全部 monkeypatch** | `tests/test_t1_state_tools.py:86,120` 均 `monkeypatch.setattr("ai.client._http_post_json", fake_post)`；全库 grep 无任何测试调用真实 `_http_post_json` |
| 超时 / 连接拒绝 / 401 / 403 / 5xx / 畸形 JSON 响应 | **否** | `ai/client.py` 覆盖率 29%，`client_utils.py` 43%；`client_utils.py:28-83`（含 `_http_post_json` 定义 43-83 行）在 missing 列表 |
| `AIClient._call` 编排（重试/降级/JSON 模式探测） | **部分**：`monkeypatch` 替换 `_call` 或 `_http_post_json` | `test_ai_contract.py:84,126`、`test_diplomacy_treaty.py:46`、`test_t1_state_tools.py:86,120` |
| `ai/semantic.py` + `ai/vector_store.py`（本地语义检索） | **否，0%** | 覆盖率 0/117、0/103 |
| `ai/client_narrative.py` | **否，27%** | 覆盖率 |
| 真实 `AI_NOT_CONFIGURED` 路径 | **是**（唯一被真测的 AI 错误路径） | `test_narrative_fallback.py:65`、`test_contract_adapter.py:44-46` |

**具体盲区**：`ai/client.py` 有 1510 语句（文件 2455 行），其中 `950-1059`（110 行）、`1830-1882`、`1887-1963`、`2225-2299`、`2306-2344` 等大块**从未执行**。这些区间对应的是真实推演/契约回喂/角色 agent 逻辑。**一旦接上真实 LLM，这些代码是首次运行。**

而 README 明说 `contract_adapter.py`（34 契约统一视图）"**待接线**：有 T5 测试覆盖，尚无生产调用方"，`async_ai.py` 亦标"**未接线**"。即 **AI 管线的大头是"有测试但无生产调用方"，被测试真跑的那小头又"全是 monkeypatch"** ——测试覆盖与真实风险几乎不相交。

#### 2) `backend/server.py` HTTP 端点 —— **零端到端、零 TestClient、鉴权零测试**

探针 `h_be_probe.py` 实测导出完整路由表（19 个业务端点 + 5 个框架端点）：

```
METHOD   PATH                         有鉴权?
GET,HEAD /openapi.json                *** NO ***     ← 未鉴权
GET,HEAD /docs                        *** NO ***     ← 未鉴权
GET,HEAD /docs/oauth2-redirect        *** NO ***
GET,HEAD /redoc                       *** NO ***     ← 未鉴权
GET      /health                      *** NO ***
POST     /api/new_game                YES
POST     /api/advance                 YES
POST     /api/action                  YES
POST     /api/resolve_event           YES
POST     /api/save                    YES
POST     /api/load                    YES
GET      /api/save_slots              YES
GET      /api/readouts                YES
GET      /api/meter                   YES
POST     /api/meter/reset             YES
POST     /api/conclude                YES
POST     /api/council_review          YES
POST     /api/decree/polish           YES
POST     /api/decree/draft            YES
POST     /api/decree/discard          YES
POST     /api/monthly_report          YES
GET      /api/ai_config               YES
POST     /api/fetch_models            YES
POST     /api/ai_config               YES
```

- **鉴权覆盖**：19/19 业务端点都调了 `_require_auth`（`server.py:80-102`），代码本身写得不错（`hmac.compare_digest` 防时序侧信道、非回环无 token 即 401）。但 **`_require_auth` 一条测试都没有**，包括它最关键的"未配 token + 非回环 → 401"分支（该分支的注释 `:88-90` 还专门说明这是修复过的**绕过漏洞**）。**一个修过的安全漏洞，没有任何回归测试。**
- **未鉴权的 `/docs`、`/redoc`、`/openapi.json`**：`server.py:830` 允许 `SONGZUO_SERVER_HOST=0.0.0.0`（只要设了 token）。此时 token 保护 `/api/*`，但 `/openapi.json` 会把**完整 API 契约**（端点、请求/响应模型、字段名）匿名吐出。属**信息泄露**（不构成鉴权绕过），我定 P2。
- **工作区无任何测试引用 backend**：grep 全测试目录，`backend`/`server`/`TestClient` 零命中。
- **且当前连写都写不了**：`h_be_probe.py` [1][3] 实测 `httpx` **未安装**，`fastapi.testclient` 直接报
  `The starlette.testclient module requires the httpx2 package to be installed.`
  而 `httpx` **不在** `requirements.txt`、**不在** `requirements-extras.txt`、**不在** `_dev_tools/game-dev/requirements-dev.txt`（后者只有 `pytest` + `pytest-cov`）。
  → **backend 端到端测试的缺失，一半原因是没有测试依赖。**

#### 3) `engine/state_applier` 的守恒/回滚失败路径

`state_applier.py` 覆盖率 62%，但 **missing 列表恰好覆盖了全部关键防线**：

| 防线 | 行区间 | 覆盖 | 测试 |
|---|---|---|---|
| 守恒预检 `_simulate_underflow` | **711-720** | **未执行** | 唯一想测它的 `test_underflow_reject_no_mint` 因 NameError 而失败 |
| 原子写入 + 逆序回滚 `apply_to_state` | **732-785** | **未执行** | 无任何测试构造"写入中途失败 → 回滚" |
| wildcard 展开后重校验 | 827-835 | 未执行 | — |
| pipeline 结果组装 | 856-879 | 未执行 | — |

**最讽刺的一点**：`apply_to_state` 的整段回滚逻辑（`:760-778`，含"回滚失败需人工检查"的 `log.error`）从未被执行过一次。而这个项目**恰恰以"守恒/原子性"为其质量叙事**（`state_applier.py:11` 的自述："路径白名单 + ΣΔ 守恒 + 原子写库 + 回滚"）。

#### 4) 存档损坏 / 旧档迁移

| 路径 | 位置 | 测试 |
|---|---|---|
| 损坏 JSON → 备份为 `.corrupt` 并返回 `None` | `save_load.py:228-239` | **无**（missing 行 231-243） |
| 顶层非 dict → 拒绝 | `save_load.py:240-243` | **无** |
| `schema_version > 2` → 拒绝加载 | `save_load.py:245-250` | **无** |
| `get_save_slots` 损坏槽标记 `{"corrupt": True}` | `save_load.py:606-612` | **无**（missing 行 591-615） |
| 旧档字段回填 | `save_load.py:245-586` | **部分**：`test_imperial_action.py:402-415` 测了 legacy personal action 迁移（唯一一个） |

`save_load.py` 72% 覆盖率里，**损坏与迁移这两类"只在出事时才走"的分支恰好是没被走的那部分**。而 `content/data.py` 的 `treasury_deficit` 这类**新增字段**只靠 `data.get("treasury_deficit", 0)` 逐个手写兜底——**没有任何测试断言"旧档缺哪些字段仍能安全加载"**，也没有字段清单可核对。这是**静默数据丢失**的温床。

#### 5) 并发 / 锁

| 对象 | 有无机制 | 有无测试 |
|---|---|---|
| `memory_graph` SQLite | **有**：`PRAGMA busy_timeout = 3000`、`PRAGMA journal_mode=WAL`（`memory_graph.py:622-624`）、单事务 `with conn:` 原子写 | **无并发测试**（只有单线程事务回滚） |
| `dialogue_memory` SQLite | `PRAGMA journal_mode=WAL`（`dialogue_memory.py:46`） | **无** |
| 后端 | `threading.Lock()`（`server.py:57`，全局单锁串行化） | **无**（backend 0%） |
| `async_ai` 线程池 | 有 `_EXECUTOR` | `test_parallel_settlement.py` 只测**串行化**（见 H-11） |

**结论**：并发机制**写了但从未验证**。WAL + `busy_timeout` 的存在说明作者意识到并发问题，但没有一个测试并发写、锁竞争或 `database is locked` 的恢复。

#### 6) 前端 —— **零测试**

见 §2.4：57 个 TS/TSX 文件、10,864 行、0 测试文件、0 测试框架、`package.json` 无 `test` script。前端唯一的自动门是 `tsc --noEmit`。

结合 `README.md:218-220` 称舆图"已完整"（`MapView.tsx` / `mapController.ts` / `layers.ts` / `markers.ts`，MapLibre）——**这是一块 4 文件的地图渲染栈，运行时零验证**，且 §3.1(d) 的假绿说明后端契约测试也不覆盖它的数据消费路径。

### 3.3 测试会不会因环境而假失败 / 假通过？

逐项实测/读码结论：

| 机制 | 判定 | 证据 |
|---|---|---|
| **`sys.path` 注入方式** | **会假失败（严重）** | 40+ 文件各自手写 `sys.path.insert`；`test_state_applier.py:5` 路径算错。**同一文件在 `python -m pytest` 下 14 passed，在 `pytest.exe` 下单跑直接 collect error。** 无 `conftest.py` 统一处理 → 这是最脆的一环 |
| **依赖收集顺序** | **会假通过** | `test_state_applier.py` 全量跑能过，纯粹因为字母序更早的文件已污染全局 `sys.path`。反过来，任何"只跑这个文件"的调试都是 ERROR。**结果依赖于"跑了哪些别的文件"** |
| **`random.seed` 确定性** | **会假通过（误导性）** | 19 处 `random.seed(N)`，但 `settle_turn(FakeAIClient())` 下 4 个不同 seed 结果**逐位相同**（Δ 恒为 −4,683,475）——因为 agent 全挂，没有随机决策被消费。若干 seed 化是"装饰性的"，给人"覆盖了随机性"的错觉。另：`random` 是**进程级全局**，测试间互相影响 |
| **`monkeypatch` 泄漏** | **良好** | pytest 的 `monkeypatch` fixture 自动回滚，未见手写全局替换（`test_regression_2026_08.py:92-99` 用 try/finally 手动还原 `_settle_civilian_hoard`，写法正确但不如 `monkeypatch.setattr` 稳） |
| **测试间共享全局状态** | **有风险** | `engine/state_applier.py:780-784` 的 `CHANGE_LOG` 是**模块级全局**（上限 5000 条），`test_state_applier.py:75,90` 用 `before = len(CHANGE_LOG)` + `CHANGE_LOG[before:]` 切片。**无 fixture 复位**；若其它测试追加超 5000 条触发 `del CHANGE_LOG[:len-5000]`，`before` 索引即失准 |
| **临时目录清理** | **严重缺陷（P0 级副作用）** | 见下方专节 |
| **生产状态泄漏到真实用户目录** | **确认发生** | 见下方专节 |
| **跑测结果可复现性** | **良好** | 两次独立全量跑（`--cov` 一次、`pytest.exe` 一次）失败集**完全一致**（同 11 项），无 flaky。**问题不是不稳定，是稳定地错** |

#### 专项：测试污染真实用户存档目录 [确认] —— 独立列为 P0

`core/save_load.py:7,12` → `SAVE_DIR = <用户文档>/宋祚/saves`，实测：

```
SAVE_DIR = C:\Users\william/Documents/宋祚/saves
```

**11 个测试文件直接对该目录读写，未做 `tmp_path` 隔离**：

| 测试文件:行 | 写入槽位 |
|---|---|
| `test_succession_mode.py:84` | **slot=1**（`save_game` 的**默认槽位**） |
| `test_four_mechanisms.py:159` | slot=2 |
| `test_branch_registry.py:115` | slot=3 |
| `test_era_interaction.py:96` | slot=4 |
| `test_free_effect.py:95`、`test_diplomacy_treaty.py:114` | slot=5 |
| `test_inner_transfer.py:62`、`test_diplomacy_treaty.py:209` | slot=6 |
| `test_army_branches.py:91`、`test_diplomacy_treaty.py:226` | slot=7 |
| `test_three_schemes.py:108`、`test_identity.py:195` | slot=9 |
| **`test_async_ai.py:209` → `core/commands.py:517-520`** | **slot=0（自动存档槽，无条件覆盖）** |

> 唯一做对的是 `test_imperial_action.py:383-386`：
> ```python
> def _patch_save_dir(tmp_path, monkeypatch):
>     monkeypatch.setattr(save_load, "SAVE_DIR", str(tmp_path))
>     monkeypatch.setattr("memory.memory_graph.SAVE_DIR", str(tmp_path))
> ```
> 这个 helper **存在且正确**，但只有 2 个用例用了它。

**时间戳实证**（我的 `--cov` 全量跑在 20:51:52 结束）：

```
slot_4.db   2026/9/18 20:51:09
slot_2.db   2026/9/18 20:51:11
slot_6.db   2026/9/18 20:51:14
slot_0.db   2026/9/18 20:51:14   ← finish_turn 自动存档
slot_1.db   2026/9/18 20:51:32   ← 默认槽 1
slot_9.db   2026/9/18 20:51:33
```

**全部落在 pytest 运行窗口内（20:51:09–20:51:33）。**

三个叠加后果：

1. **数据破坏**：`test_succession_mode.py:84` 的 `save_game(s, slot=1)` 会**静默覆盖玩家 slot 1 的真实存档**；`finish_turn` 的自动存档同理覆盖 slot 0。跑一次测试 = 抹掉玩家的存档。**这是运行测试套件的直接副作用。**
2. **清理不完整，永久泄漏**：所有清理都是 `if os.path.exists(_slot_path(N)): os.remove(_slot_path(N))`，而 `_slot_path` **只返回 `.json` 路径**（`save_load.py:10-12`），但 `save_game` 内部会 `state.memory.save(slot)`（`:25`）生成 **`slot_N.db`（SQLite 记忆库）**。**`.db` 永不被删除。** 实测残留：`slot_3.json`、`slot_3.db`、`slot_4.db`、`slot_6.db`、`slot_9.db`、`slot_0.db`、`slot_1.db`、`slot_2.db` 全在用户在 Documents 里。
3. **无 `try/finally`**：清理写在断言之后，**断言失败则清理不执行**，残留物进一步堆积。（唯二例外是 `test_memory_graph.py:114-117` 与 `test_imperial_action.py`。）

**项目其实知道这个风险**——`test_memory_graph.py:101` 的注释：

> `# 用安全槽位 78：真实存档目录可能有 slot_4.db 残留，避免撞真实存档`

这句话同时证明了：① 作者知道测试写的是真实目录；② 作者知道 `.db` 会残留；③ **作者选择在一个用例里绕开，而没有修根因**。这是"局部打补丁代替系统性修复"的典型样本，也是"为什么 11 项失败无人发现"的一个镜像——**没人敢随便跑测试，因为跑测试会动真实存档**。

---

## 四、弱断言 / 过拟合断言清单

**抽查范围**：24 个测试文件（逐行读），列其中 20 条问题断言。
**抽查文件**：`test_state_applier.py`、`test_regression_2026_08.py`、`test_briefing.py`、`test_core_logic.py`、`test_review_2026_09_fixes.py`、`test_pop_identity.py`、`test_memory_sqlite.py`、`test_memory_graph.py`、`test_branch_registry.py`、`test_flow_summary.py`、`test_price_stabilizer.py`、`test_parallel_settlement.py`、`test_tuning_fixes.py`、`test_identity.py`、`test_agent_router.py`、`test_desensitize.py`、`test_inner_transfer.py`、`test_finance_decide.py`、`test_async_ai.py`、`test_imperial_action.py`、`test_events_a6.py`、`test_t1_state_tools.py`、`test_review_p0_conservation.py`、`fake_ai_backend.py`

### 4.1 弱断言（恒真 / 近恒真 / 不校验具体值）

| # | 文件:行 | 断言 | 问题类型 | 为什么抓不到缺陷 |
|---|---|---|---|---|
| 1 | `test_async_ai.py:210` | `assert s.game_over in (True, False)` | **恒真（布尔只可能是这两种）** | 100% 不可能失败。写作意图（注释 `:209` "不抛即可"）是"只测不抛异常"，于是把一整条终局判定链的验证降级为零 |
| 2 | `test_identity.py:64` | `assert out >= 0` | **恒真** | `out = (army_g+off_g+clerk_g)*pay + corr_g*pay`，全为非负量之和，永远 `>= 0`。注释自承"此处仅校验公式自洽"——但它**连自洽都没校验**（没有对照另一路计算） |
| 3 | `test_identity.py:81` | `assert isinstance(net_new, float)` | **恒真** | `net_new = new_in - new_out` 恒为 float。而该用例名 `test_treasury_net_direction` 与 docstring"收入>支出时结余为正，反之负"承诺的是**符号方向**——**完全未断言**。这才是能抓财政缺陷的那个断言，却写成了类型检查 |
| 4 | `test_identity.py:117` | `assert isinstance(log, list)` | 近恒真 | 用例名 `test_full_settlement_no_assertion_break`，注释"确认恒等断言不触发"——即**只验证"不崩"** |
| 5 | `test_identity.py:119` | `assert -50_000_000 < s.treasury < 50_000_000` | 区间过宽 | 跨度 1 亿贯。国库起手 500 万，正常单月变化 ±20 万。该区间允许国库变成 −4900 万到 +4900 万而不报错 |
| 6 | **`test_price_stabilizer.py:102`** | `assert _lt_total >= 0, "府库不为负"` | **伪绿：注释承诺守恒，断言不查** | 上一行注释 `:100` 明写"**常平 ΣΔ==0（粮+钱守恒）：仓增量×价 ≈ 府库减量**"，但实现是 `>= 0`。而 `local_treasury` 被预置为 `10_000_000 × 20 路 = 2 亿`（`:89`），**永远 >= 0**。`_lt_total` 前面的 `:97-98` 更有一段空注释"（买粮后 local_treasury 减少，验证未超预算）"——**声明要验证的东西一行没写**。对比：同项目 `test_review_p0_conservation.py:163-194` 用 `==` 精确验证了同一类守恒，证明作者知道正确写法 |
| 7 | `test_flow_summary.py:35` | `assert t["month_in"] >= 0 and t["month_out"] >= 0` | 恒真 | 开局快照的收支字段是非负整数/浮点。同用例 `:34` 和 `:36` 有更强断言，此行为填充 |
| 8 | `test_briefing.py:34` | `assert isinstance(actions, list) and actions` | 弱 | 用例名 `test_briefing_no_ai_dependency` 想验证"不触网、不读 ai_client"。但**断言只查"返回了非空 list"**——一个会去联网的实现同样能通过（联网失败后走 fallback 也返回非空 list）。真正该做的是 monkeypatch `_http_post_json` 抛异常或断言无网络调用 |
| 9 | `test_briefing.py:26` | `assert a1 == a2` | 弱（同义反复） | 连续调用两次纯函数比较相等。**任何确定性函数都通过**；只有引入随机/时间/IO 才会失败。用例名 `test_briefing_deterministic` 名不副实——它验证的是"不存在随机源"，而这类缺陷罕见且通常被其它测试捕获 |
| 10 | `test_review_2026_09_fixes.py:51-52` | `assert isinstance(r1, dict) and isinstance(r2, dict)` … | 弱 | 文档字符串 `:28` 说"拟旨链 dict 摘要：**不崩** + 不把精确国库写进 prompt"。第 51-52 行只断言"返回 dict"（不崩），第 53-55 行的脱敏断言被包在 `if captured.get("all"):` 里——**若 `_NoNet._call` 未被调用（未来重构改了内部路径），该脱敏断言会被整体跳过，测试仍绿**。条件断言是隐蔽的假绿 |
| 11 | `test_branch_registry.py:117` | `assert s2 is not None` | 弱 | 存档往返测试。幸而 `:118-120` 有实质断言，此行为哨兵。但对照 `test_inner_transfer.py:64-65`（`assert s2.pending_inner_transfer == {...}`）可见**同类测试质量参差** |
| 12 | `test_state_applier.py:48-49` | `assert len(valid) == 0` / `assert len(errors) == 4` | 中等 | 只数**条数**，不断言**拒绝理由**。4 条非法输入分别因"非法 path / 缺 reason / 负数 / 类型错"被拒，若实现因单一原因（如把 4 条全当非法 path）拒绝，测试仍绿 |
| 13 | `test_agent_router.py:35-38` | `for u in s.army_units[:1]: u.morale = 20` | 构造过弱 | 只改**第一支**军队的士气来验证"morale<30 → 唤醒 military"。若实现实际检查的是"全部军队 morale < 30"（AND 语义），该测试仍通过；反之只改一支不足以区分 AND/OR 语义 |
| 14 | `test_finance_decide.py:82-89` | `assert "非法" not in states` / `assert all(isinstance(v, str) for v in states)` | **伪绿：命名行为完全未测** | 用例名 `test_finance_reject_bad_states`、docstring"economy_decide 金融字段**拒绝式**：缺失/非法 → None（不默认填充）"。但函数体第 86 行自承"**validator 不可直达**"，于是断言退化成"常量表里没有'非法'这个词"+"元素都是字符串"。**被命名的拒绝行为一行都没测**——这正是 H-7 类假绿的另一实例 |

### 4.2 过拟合断言（把当前实现的偶然数值/细节写死）

| # | 文件:行 | 断言 | 问题类型 | 为什么抓不到缺陷 / 何时假失败 |
|---|---|---|---|---|
| 15 | **`test_regression_2026_08.py:66`** | `assert s.treasury > TREASURY_CRISIS_LINE` | **过拟合 + 量纲错配（本次核心）** | 见 §一 专项。起手值恰等于阈值 → 断言恒假；且比的是余额 vs 亏空深度。**这是"把实现常量写进 `>` 断言"的教科书案例** |
| 16 | **`test_review_p0_conservation.py:93-99`** | `src = inspect.getsource(m.run_settlement_ai)`<br>`assert "_EXECUTOR.submit(_call_guarded" not in src`<br>`assert "as_completed" not in src` | **测实现细节（源码文本）** | 断言的是**源码字符串**，不是行为。① 善意重构（重命名 `_call_guarded`、或用 `as_completed` 消除忙等）会**假失败**；② 真实的"嵌套 submit 死锁"若通过别的辅助函数/别名实现，**断言查不到**（假通过）。正确写法：注入一个记录 `submit` 调用栈的假 executor，断言 worker 内不再 submit |
| 17 | **`test_parallel_settlement.py:94`** | `assert fake.max_active == 1, "同 client 锁内串行化"` | **测实现细节，且与模块名矛盾** | 模块名/docstring（`:2`"并行执行升级测试：`run_settlement_ai` **线程池并行**"）承诺并行，断言却**固化了"不并行"**。真正有价值的断言是"多 agent 结果完整、失败隔离"（这些 `:86,:112` 已做）；`max_active == 1` 把"用全局锁"这一**性能妥协**钉死。若将来真做并行（正是该模块名的目标），测试立刻假失败 |
| 18 | `test_finance_decide.py:23-34` | `assert FINANCE_DECIDE_BASE["jiaozi_trust"]["cap"] == 5`（×7）+ `FINANCE_STATES[...] == (...)`（×5） | **镜像常量自身（数据测试，非行为测试）** | 断言"常量 P 等于值 V"。这不是在检验任何代码行为，而是把配置文件抄进测试。**抓不到任何缺陷**：改常量它失败（但那不是缺陷），删掉整个消费常量的逻辑它照样通过。真正该测的是"CAP 真的生效"——同文件 `:37-57` 才是在做这件事 |
| 19 | `test_tuning_fixes.py:35` / `:45` | `assert trade >= 2_000_000` / `assert 1.0 <= grain_per <= 8.0` | 魔数阈值 + 8 倍宽区间 | `:45` 的区间宽达 8 倍（1.0~8.0 石/人），而 docstring 说设计值是"月产×0.02（≈1~2 月口粮缓冲）"。**8 倍的容忍区间意味着：把 0.02 改成 0.06 或 0.008 都能通过。** 阈值被放宽到"只要还在这个量级就不管"，与"防回归"目的相悖 |
| 20 | `test_finance_decide.py:50-52` | `base = max(0.05, sh0 - 0.005 - 0.05 - 0.01)`<br>`assert base <= s.coin["shortage"] <= base + 0.02` | 容差即效应，掩盖回归 | 注释 `:50` 自承区间上界 `+0.02` 是为了容纳"家产聚敛窖藏（蔡京/童贯 聚敛≥70 → shortage 增，量级 <0.02）"这一**未建模的副作用**。把"效应量级"直接当成容差，等于**宣告该副作用不可观测**。若该聚敛逻辑从 0.02 恶化到 0.021 或崩到 0.019，测试察觉不到 |

### 4.3 值得肯定的对照样本

为免报告失衡，明确记录质量**高**的测试，应作为改造范式：

| 文件 | 亮点 |
|---|---|
| `test_review_p0_conservation.py` | **最佳**。`test_changping_trade_conserves_grain_and_money`（`:163-194`）用 `g1 == g0` / `m1 == m0` **精确**验证粮/钱两本账，且**双向**（平粜 sell + 平籴 buy）；`test_levy_and_return_men_conserves_population`（`:197-220`）验证征补+裁汰的**往返守恒**；每个用例 docstring 都写明"原实现如何错" |
| `test_desensitize.py` | 断言具体字符串（`"80万缗" in s`、`== "几无余财"`）与具体常量（`_org_width("户部","treasury") == 0.08`），边界值齐全（0/负/无 prev/有 prev） |
| `test_memory_sqlite.py:138-164` | 事务回滚测试**断言具体值**（`int(v[0]) == 20`、`n == len(...)`），而非"不抛异常" |
| `test_inner_transfer.py` | 守恒写成显式等式：`assert (s.treasury - t0) == (i0 - s.imperial_treasury) == 500000`（`:36`） |
| `test_events_a6.py:75-77` | 档位换算断言精确数值（`t0 + 800_000`、`ps0 - 3`、`p0 - 2`） |

**这 5 个文件证明团队具备写出高质量守恒测试的能力。** 问题不在能力，在于**这套标准没有被强制到全部 48 个文件**，也没有 CI 来兜住未达标的部分。

---

## 五、建议新增用例（按性价比排序）

排序依据：**能抓住的真实缺陷量 / 实现成本**。前 6 条直指本次审查已确认的 P0/P1，属"立刻做"。

| # | 用例名 | 断言什么 | 覆盖盲区 | 成本 |
|---|---|---|---|---|
| **1** | `test_applier_pipeline_happy_path_applies`<br>`(test_state_applier.py)` | 守恒闭合的成对变更（`treasury +10万 / 商人 −10万`）必须 `applied` 非空、`treasury == t0 + 100000`、`CHANGE_LOG` 追加 1 条且 `new == old + 100000` | **H-1 悬空引用（直接钉死本 P0）** | 5 分钟 |
| **2** | `test_relief_grant_tool_lands_in_real_dispatch`<br>（新文件 `test_tool_dispatch_e2e.py`） | 走**真实** `ai.client_utils._tool_dispatch`（不 patch 任何 applier/except），`relief_grant(region="两浙路", grain=1)` → 返回串含 `"已发 两浙路"`、`treasury == t0 - 200000`、该路 `农/工匠 wealth` 增加、`refugees` 减少 | **H-1 的生产影响 + `ai/client_utils.py:810` 裸 except 掩盖崩溃**。这是"工具级端到端"，与 `#1` 互补（`#1` 测函数，`#2` 测接线） | 15 分钟 |
| **3** | `test_no_test_writes_to_real_save_dir`<br>（`conftest.py` + 守卫用例） | ①在 `game/pytest.ini` 同级加 `conftest.py`，autouse fixture 把 `save_load.SAVE_DIR` 与 `memory.memory_graph.SAVE_DIR` 重定向到 `tmp_path_factory`；②新增用例：跑完一整个回合/存档往返后，断言**真实 `SAVE_DIR` 的文件集合未变化** | **H-2（运行测试抹玩家存档 + `.db` 永久泄漏）**。改 `conftest.py` 一次性修好 11 个文件的隔离问题 | 30 分钟 |
| **4** | `test_save_load_corrupt_and_migrate` | ①截断 JSON → `load_game` 返回 `None` 且生成 `.corrupt` 备份；②顶层为 list → 返回 `None`；③`schema_version=3` → 返回 `None`；④**用当前 `GameState` 全字段快照删掉 3 个新字段（如 `treasury_deficit`/`branch_registry`/`timeline`）后加载，断言不抛且关键字段取到默认值** | **存档损坏/旧档迁移**（`save_load.py:231-250,591-615` 全 missing） | 45 分钟 |
| **5** | `test_require_auth_matrix`（新文件 `test_backend_auth.py`） | 用 `fastapi.testclient.TestClient` 覆盖 5 条分支：①设 token + 无 header → 401；②设 token + 错 token → 401；③设 token + 对 token → 非 401；④未设 token + 非回环 → 401；⑤未设 token + 回环 → 非 401。**parametrize 覆盖全部 19 个 `/api/*` 端点** | **H-5 鉴权零测试（含一个修过的绕过漏洞）**。**前置：`httpx` 必须加进 `requirements-dev.txt`**（当前缺失，TestClient 无法导入） | 45 分钟（含加依赖） |
| **6** | `test_settlement_money_conservation_exact`（替换/加强 `test_core_logic.py:244`） | 按科目逐项记账：`Δtreasury == (本月实际到库税 − 本月实际支出)`，且 `Δ(POP wealth 总额) == −Δtreasury + 明确外部流入/流出项`。**用 `==` 不用 5000 万容差**，无来源差额必须为 0 | **H-8（守恒断言容差大 2~3 个数量级）**，亦直接回归 2026-08-31 报告的 P1-1 俸禄黑洞（−4.4 万/月）与 B1 市舶双计 | 2 小时 |
| **7** | `test_fake_ai_client_implements_full_agent_contract` + `test_settle_turn_with_complete_fake` | ①断言 `FakeAIClient` 实现 `agent_router`/`async_ai` 实际调用的**全部** agent 方法（用 `inspect.getsource` 扫调用名或直接硬编码清单）；②补齐 6 个方法后，断言 `settle_turn` 期间**无 "唤醒失败" 日志**（`caplog`） | **H-7（FakeAIClient 缺 6/9 方法 → "AI 测试"实为降级测试）**。第 ① 条能防止替身再次腐化 | 1 小时 |
| **8** | `test_http_post_json_transport_contracts` | 用本地 `http.server`（或 `socket` 假服务器，非 monkeypatch）覆盖 `client_utils._http_post_json` 的真实传输：超时→`None`/特定码、连接拒绝、HTTP 401/403/500、**非 JSON body**、超长响应、缺 `usage` 字段 | **H-6（真实 HTTP 传输零覆盖；`client_utils.py:28-83` 全 missing）** | 2 小时 |
| **9** | `test_apply_to_state_rollback_on_mid_write_failure` | 构造 3 条变更，第 3 条指向一个**中间层缺失**的路径（触发 `save_load.py:739` 的 `KeyError`），断言：①抛异常；②**前 2 条的写入被完整逆序回滚**（state 逐字段等于初始快照）；③`CHANGE_LOG` **未追加任何记录** | **`apply_to_state` 原子/回滚全未执行（`:732-785` missing）**；这是项目质量叙事（"原子写库+回滚"）的核心，却从未跑过 | 1 小时 |
| **10** | `test_state_applier_underflow_blocks_mint`（加强 `test_underflow_reject_no_mint`） | 穿底场景：`treasury=50`，`add −100` + 配对方 `add +100` → 断言 `conservation_failed is True`、`treasury == 50`（未截断造币）、`rejected` 含"余额不足"文案。**再补一条边界**：`treasury=100`、`add −100`（恰好归零）→ 应**允许落地** | **`_simulate_underflow` 判定体 `:711-720` 未执行**（H-1 修复后即可测）；边界值区分 `<0` 与 `<=0` 语义 | 30 分钟 |
| **11** | `test_memory_sqlite_concurrent_writes` | 起 4 个线程同时对同一 slot `MemoryGraph.save()`，断言：①无异常逃逸；②最终 DB 可读且 `entities` 数等于某次完整快照（非半写）；③`busy_timeout` 生效（无 `database is locked` 未捕获） | **并发/WAL/`busy_timeout` 无测试**（`memory_graph.py:622-624` 写了机制但从未验证） | 1.5 小时 |
| **12** | `test_game_state_serialization_field_completeness` | 序列化一个"跑过 12 个月"的 `GameState`，得到字段集 A；构造 `GameState("史实")` 得字段集 B；断言 `A ⊆ B ∪ {运行期瞬态白名单}`。**对 `save_load.py` 里每一个 `data.get(key, …)` 反查 key 是否真的存在于 `to_dict` 输出** | **旧档迁移的静默数据丢失**：当前靠逐个手写 `get(..., default)` 兜底，无清单可核对；新增字段忘记加 `to_dict` 或忘记加默认值不会被发现 | 1.5 小时 |
| **13** | `test_graveyard_source_text_assertion` 的**替换版**：`test_run_settlement_ai_worker_does_not_nest_submit` | 用假 `_EXECUTOR`（记录 `submit` 调用栈深度）验证 worker 内部不再 submit；而非断言源码文本 | 修正 H-11/`test_review_p0_conservation.py:93-99` 的"测文本不测行为" | 45 分钟 |
| **14** | `test_briefing_offline_no_network`（加强） | monkeypatch `ai.client_utils._http_post_json` 抛 `AssertionError("不应触网")`，调用 `build_briefing_actions`，断言不抛且结果非空；再断言具体急务项的 `key`/`title`/`goto` 三元组 | 修正弱断言 #8：把"返回非空 list"升级为"证明不触网" | 20 分钟 |

**总成本估计：约 14 小时**，其中前 6 条（约 4 小时）即可消掉本次审查的 3 个 P0 与 3 个 P1。

### 建议顺带做的三件工程改造（非测试用例，但决定上述用例能否长期存活）

1. **加 `conftest.py`（仓库级，1 个文件）**：统一 `sys.path`、autouse 重定向 `SAVE_DIR`、autouse 复位 `CHANGE_LOG`、autouse 固定 `random.seed`。**这一步同时解决 H-2、H-4、H-12 三条中的大部分。**
2. **加最小 CI（GitHub Actions / 或本地 pre-commit 钩子）**：一条 `python -m pytest` 即可。**没有它，本报告的 14 条新用例会在下一次重构后重蹈 11 项失败的覆辙。**
3. **`requirements-dev.txt` 补 `httpx`**（TestClient 前置）**与 `jsonschema`/`tiktoken`**（`ai/schemas.py`、`ai/token_meter.py` 的 38% 覆盖很大程度源于依赖缺失导致的功能静默关闭）。

---

## 六、详细条目

### H-1 [P0] `_resolve_path_value` 悬空引用导致 `applier_pipeline` 成功路径 100% 失效，`relief_grant` 生产不可用

**位置**
- 悬空引用：`engine/state_applier.py:677`（`_apply_op` 默认分支）、`engine/state_applier.py:710`（`_simulate_underflow`）
- 被注释吞掉的 `def`：`engine/state_applier.py:292`
- 触发链：`applier_pipeline` → `state_applier.py:855` `under = _simulate_underflow(state, merged)`
- 生产唯一调用方：`ai/client_utils.py:793-812`（`relief_grant`），裸 `except` 在 `:810-812`

**证据 [确认]**

```
# 探针 h_probe_nameerror.py [E] 逐行列印 state_applier.py 中的引用点
 292  [注释/文档]  # 已整体移除。def _resolve_path_value(state, path: str):
 677  [**活代码**]  cur = _resolve_path_value(state, path)
 710  [**活代码**]  base = _resolve_path_value(state, path)

# [A]
hasattr(sa, '_resolve_path_value') = False

# [B] 守恒闭合的成对变更（本该成功落地）
*** NameError：name '_resolve_path_value' is not defined
  File "...\engine\state_applier.py", line 710, in _simulate_underflow
    base = _resolve_path_value(state, path)
国库变化: 5000000 → 5000000（Δ=0）      ← 变更全部未落地

# [C] 走真实生产入口
工具返回: [('1', '赈济未能落地（状态应用层异常，已拒绝）')]
国库: 5000000 → 5000000（Δ=0）

# [D] 第二颗地雷
*** NameError：name '_resolve_path_value' is not defined  （677 行分支同样悬空）
```

**机理**：`state_applier.py:286-292` 的 D 修复注释本意是"删掉永不触发的死 cascade 规则"，但注释文本 `# 已整体移除。def _resolve_path_value(state, path: str):` **把函数定义行一起注释掉了**，而其函数体（293-322 行，含 docstring 与 `if parts[0] == "prefectures"` 等）仍以**活代码**形式留在文件中——只是不再有 `def` 头。于是它变成了两处调用点的未定义名。

**为什么严重**：
- `_simulate_underflow` 在 `applier_pipeline:855` **无条件**调用（不在任何 try 内），所以**只要守恒校验通过或经补记账通过，就必然抛 NameError** → **`applier_pipeline` 的成功路径 100% 崩溃**。
- 而 `applier_pipeline` 在**全库只有 1 个生产调用方**：`ai/client_utils.py:794` 的 `relief_grant`（全库 grep 确认）。因此这个 P0 的**全部生产影响面就是 `relief_grant` 工具失效**——玩家点赈济，系统回一句"状态应用层异常，已拒绝"，钱粮不动，民心不涨。**游戏功能静默缺失。**
- `ai/client_utils.py:810-812` 的裸 `except Exception` 把它降级为用户可见文案，**同时吞掉 traceback**——只在日志层面消失，UI 层面看不出是崩溃。

**修复应落在代码**（测试的期望是正确的）：
1. 恢复 `def _resolve_path_value(...)`（其实现体仍在 293-322 行）；或
2. 改为复用同文件已有的 `_locate_path`（`:642-657`）——它做的是同一件事（按 path 取当前值），且已有 677/710 之外的使用者，属更干净的收敛。
3. 顺带把 `ai/client_utils.py:810` 的裸 `except Exception` 收窄为具名异常并 `log.exception`，否则同类崩溃仍会静默。

**关联失败项**：#1 #2 #3 #4（4 项）。

---

### H-2 [P0] 测试套件向真实用户存档目录写入，清理只删 `.json` 不删 `.db`

**位置**
- `core/save_load.py:7,10-12`：`from content.data import SAVE_DIR`；`_slot_path()` 仅返回 `.json`
- `core/save_load.py:25`：`save_game` 内部 `state.memory.save(slot)` → 生成 `slot_N.db`
- `core/commands.py:517-520`：`finish_turn` 在 `state.month == 1 or state.game_over` 时 `save_game(state, slot=0)`
- 11 个未隔离的测试文件：见 §3.3 专项表格

**证据 [确认]**

```
SAVE_DIR = C:\Users\william/Documents/宋祚/saves

# 我的 --cov 全量跑于 20:51:52 结束，目录内容时间戳：
slot_4.db   2026/9/18 20:51:09
slot_2.db   2026/9/18 20:51:11
slot_6.db   2026/9/18 20:51:14
slot_0.db   2026/9/18 20:51:14
slot_1.db   2026/9/18 20:51:32
slot_9.db   2026/9/18 20:51:33
slot_3.db   2026/9/18 20:54:30
slot_3.json 2026/9/18 20:54:30
```

> 严格性说明：`slot_0/1/2/4/6/9.db` 的时间戳（20:51:09–20:51:33）**全部落在我这次 pytest 运行窗口内**（`_cov.txt` 写入于 20:51:52），可归因于测试套件。`slot_3.db`/`slot_3.json`（20:54:30）在此窗口**之后**，可能来自同工作区的另一次运行（其它审计脚本），故我不把它作为本次 pytest 的直接证据——但 `test_branch_registry.py:115` 的 `save_game(s, slot=3)` 是明确的代码证据，且该目录中存在 `.json` 与 `.db` **配对残留**，正是"H-2 清理只删 `.json`"的直接体现。

**对照：项目已知此风险但只做局部规避**——`test_memory_graph.py:101`：

```python
# 用安全槽位 78：真实存档目录可能有 slot_4.db 残留，避免撞真实存档
```

而唯一正确的隔离写法存在于 `test_imperial_action.py:383-386`，但只服务 2 个用例。

**后果**：
1. `test_succession_mode.py:84` 的 `save_game(s, slot=1)` 覆盖**默认槽 1**；`finish_turn` 覆盖**自动存档槽 0**。运行测试会破坏玩家存档。
2. 清理只 `os.remove(_slot_path(N))`（`.json`），**`slot_N.db` 永久残留**——实测 8 个 `.db` 残留文件。
3. 清理排在断言之后、无 `try/finally` → 断言失败则残留更多。
4. 这与"没人愿意跑测试"互为因果（§3.1(b)）。

**修复**：新增仓库级 `conftest.py`，autouse fixture 重定向 `save_load.SAVE_DIR` 与 `memory.memory_graph.SAVE_DIR` 到 `tmp_path_factory`（复用 `test_imperial_action.py:383-386` 的写法），并把清理改为 `tmp_path` 自动回收。

**关联**：§3.1、§3.3。

---

### H-3 [P0] B3 财政语义反转：测试与机制文档同步过期

**位置**
- 代码（新语义）：`content/data.py:360-370`；消费方 `core/evaluation.py:51,146,176`、`core/briefing.py:77-78`、`core/settlement.py:341,346`、`core/game_state.py:744-750`
- 机制文档（旧语义，未更新）：`_dev_tools/game-docs/docs/游戏机制说明.md:476` → `TREASURY_CRISIS / COLLAPSE | -500万 / -2000万贯 | 危机/崩坏线`
- 历史报告（旧语义）：`analysis/review_2026-08-31.md:20,120`
- 修复动机：`analysis/code_review_report_2026-08-17.md:26`
- 过期测试：#5 #7 #8 #9 #10

**证据 [确认]** 见 §一 第 5 项专项（5 条证据：量纲、起手值相等、10 seed 分布、120 月回放、三方文档对照）。

**结论**：7 项失败中的 5 项、以及"384 全绿"与"390 中 11 红"的落差，全部由这一次语义反转 + **无重跑机制**造成。**代码是对的**（B3 修复让原本不可达的破产/危机/财政评分三档变得可达，是正确方向），**测试与文档是旧的**。

**修复应落在测试（+ 文档）**：
- `test_regression_2026_08.py:66` → `assert s.deficit_depth() <= TREASURY_CRISIS_LINE`
- `test_briefing.py:41,55` → `s.treasury_deficit = TREASURY_CRISIS_LINE + 1`
- `test_core_logic.py:112` → `s.treasury_deficit = TREASURY_COLLAPSE_LINE + 1`
- `test_core_logic.py:127` → `s.treasury_deficit = TREASURY_CRISIS_LINE + 1`
- `docs/游戏机制说明.md:476` → 改为 `+500万 / +2000万（累计亏空深度）`
- 建议补一条**元测试**：断言"任何测试文件都不得对 `s.treasury` 赋负值"（负余额在新语义下物理不可达，出现即为过期测试）。

**关联失败项**：#5 #7 #8 #9 #10。

---

### H-4 [P1] 零 CI、无 `conftest.py`、逐文件 `sys.path` hack，且一个文件的路径算错

**位置**：`game/pytest.ini`（4 行，无 `conftest.py` 于全仓库）；`tests/test_state_applier.py:5`

**证据 [确认]** 三行实测（同一 CWD、同一文件、仅换 runner）：

```
python -m pytest <tests>\test_state_applier.py   →  4 failed, 14 passed
pytest.exe       <tests>\test_state_applier.py   →  ModuleNotFoundError: No module named 'core'  (收集中断)
pytest.exe       <tests>  (全量)                  →  11 failed, 379 passed   ← 该文件被成功收集
```

第三行能成功，是因为 pytest 按字母序收集，`test_agent_p1.py` 等更早的文件已把正确的 `_GAME_ROOT` 写入**进程级全局** `sys.path`。

**修复**：加 `conftest.py` 做一次 `sys.path.insert(0, <game root>)`；或改成 `pyproject.toml` + `pip install -e .`。

---

### H-5 [P1] `backend/server.py` 0% 覆盖：19 个端点 + 鉴权零测试；`/docs` 未鉴权；`httpx` 缺失

**位置**：`backend/server.py:80-102`（`_require_auth`）、`:312-787`（19 端点）、`:826-833`（`main`）；`_dev_tools/game-dev/requirements-dev.txt`

**证据 [确认]**：路由表（§3.2-2）、`httpx` 缺失（`h_be_probe.py` [1][3]：`fastapi.testclient` 因缺 `httpx` 不可用；`requirements.txt`/`requirements-extras.txt`/`requirements-dev.txt` 三者均无 `httpx`）。`backend/server.py` 0% 是**真无测试**（import 成功，依赖齐全）。

---

### H-6 [P1] 真实 HTTP 传输零覆盖（全 monkeypatch）

**位置**：`ai/client_utils.py:43-83`（`_http_post_json`）；patch 点 `tests/test_t1_state_tools.py:86,120`、`tests/test_ai_contract.py:84,126`、`tests/test_diplomacy_treaty.py:46`

**证据 [确认]**：`ai/client.py` 29%、`ai/client_utils.py` 43%；`client_utils.py:28-83` 全在 missing；全测试目录无任何真实调用 `_http_post_json` 的用例（grep）。超时/401/403/5xx/畸形 JSON 全无测试。

---

### H-7 [P1] 测试替身 `FakeAIClient` 缺 6/9 agent 方法 → "AI 结算"测试实为 AI 降级测试

**位置**：`tests/fake_ai_backend.py:6-26`；使用点 `tests/test_core_logic.py:171,239`、`tests/test_memory_graph.py:134-139`

**证据 [确认]**：探针 `h_probe_tolerance2.py` [B] 列出 6 个缺失方法；[C] 捕获真实运行警告 `Agent diplomacy/faction/military/relief 唤醒失败: ... has no attribute ...`；[A] 4 个不同 `random.seed` 得到逐位相同的结果（证明无随机决策被消费）。

**修复**：补齐替身 + 加"替身契约完整性"守卫测试（§五 #7）。

---

### H-8 [P1] "守恒"断言容差 5000 万，比真实守恒缺陷大 2~3 个数量级

**位置**：`tests/test_core_logic.py:221-244`（断言在 `:244`）

**证据 [确认]**：探针 `h_probe_tolerance2.py` [A]，**逐行复用** `test_core_logic.py:226-234` 的快照口径：

| 指标 | 实测 | 占容差 |
|---|---|---|
| 最大单月 \|Δ\| | 12,262,028 贯 | 24.5% |
| 平均单月 \|Δ\| | 6,481,390 贯 | 13.0% |
| 报告的 P1-1 俸禄黑洞 | −44,035 贯 | 0.09% |
| B1 市舶关税双计 | 约数十万贯 | ~1% |

---

### H-9 [P1] 前端 10,864 行零测试，无框架、无 `test` script

**位置**：`frontend/package.json`（scripts: `dev`/`build`/`preview`/`build:topo`/`typecheck`/`dist`；devDeps 无任何测试框架）；`frontend/src`（57 个 `.ts/.tsx`，10,864 行）

**证据 [确认]**：递归查找 `*.test.*`/`*.spec.*`/`__tests__`/`e2e` → 0 命中；`vitest.config.*`/`jest.config.*`/`playwright.config.*`/`cypress.config.*` → 0 命中。

---

### H-10 [P2] 弱断言/伪绿 20 条

**位置与详情**：见 §四。代表性最强三条：
- `test_async_ai.py:210` `assert s.game_over in (True, False)` —— **布尔恒真**
- `test_price_stabilizer.py:102` `assert _lt_total >= 0` —— 上一行注释明写"ΣΔ==0 守恒"，断言不查
- `test_finance_decide.py:82-89` `test_finance_reject_bad_states` —— 命名行为"拒绝式"一行未测

---

### H-11 [P2] 实现细节/过拟合断言

**位置**：`test_review_p0_conservation.py:93-99`（`inspect.getsource` 断言源码文本）；`test_parallel_settlement.py:94`（断言"不并行"，与模块名"并行执行升级"矛盾）；`test_finance_decide.py:23-34`（镜像常量自身）；`test_regression_2026_08.py:66`（起手值恰等阈值）。详见 §4.2。

---

### H-12 [P2] 全局状态与顺序耦合

**位置**：`engine/state_applier.py:780-784`（模块级 `CHANGE_LOG`，上限 5000，未复位）；`tests/test_state_applier.py:75,90`（依赖 `len(CHANGE_LOG)` 切片）；19 处 `random.seed`（进程级全局）；`core/commands.py:517-520`（`finish_turn` 无条件自动存档）。

**证据 [确认]**：读码 + §3.3 表。`CHANGE_LOG` 的截断逻辑（`del CHANGE_LOG[:len-5000]`）会让"跑了很多测试之后再切片"的索引失准。

---

### H-13 [P2] 存档损坏/旧档迁移覆盖不全

**位置**：`core/save_load.py:228-239`（`.corrupt` 备份）、`:240-243`（顶层非 dict）、`:245-250`（`schema_version>2` 拒绝）、`:606-612`（槽位损坏标记）。

**证据 [确认]**：以上行区间全部出现在覆盖率 missing 列表（`_cov.txt` 中 `core\save_load.py … 231-239, 241-243, 591-615`）。唯一被测的迁移是 `test_imperial_action.py:402-415`。

---

### H-14 [P2] 无版本控制

**位置**：`D:\codebuddy\sz`（`Test-Path .git` → False；`game/.git` → False）

**影响**：任何回归都无法 `git bisect` 归因，"B3 何时落地""哪个 commit 引入 NameError"这类问题在本仓库**原理上不可回答**。这是 §3.1 "长期无人发现"的结构性放大因子。

---

### H-15 [P2] `__main__` 手工跑测入口腐化

**位置**：`tests/test_core_logic.py:251` 调用 `test_execution_rate_direct_wolf_bonus_penalty()`，而该函数已在 `:57` 改名为 `test_execution_rate_direct_no_wolf_penalty`。

**证据 [确认]**：

```
$ python tests/test_core_logic.py
  File "...\test_core_logic.py", line 251, in <module>
    test_execution_rate_direct_wolf_bonus_penalty()
NameError: name 'test_execution_rate_direct_wolf_bonus_penalty' is not defined.
Did you mean: 'test_execution_rate_direct_no_wolf_penalty'?
```

脚本化巡检确认 **48 个文件中仅此 1 个**存在该问题。

---

### H-16 [P2] SQLite 并发/WAL 机制已写但零验证

**位置**：`memory/memory_graph.py:611-625`（`PRAGMA busy_timeout = 3000`、`PRAGMA journal_mode=WAL`、`with conn:` 单事务）；`memory/dialogue_memory.py:46`（WAL）；`backend/server.py:57`（`threading.Lock`）。

**证据 [确认]**：读码确认机制存在；全测试目录无任何并发/锁竞争用例。已有的事务回滚测试（`test_memory_sqlite.py:138-164`）质量**很好**（断言 `turn == 20` 与实体数），但只覆盖**单线程注入异常**，未覆盖并发与 DB 文件损坏。

---

### H-17 [P2] `engine/state_applier.py` 402 语句只有 1 个生产调用点

**位置**：`ai/client_utils.py:794`（全库唯一生产调用方）；模块自述 `engine/state_applier.py:11`

**证据 [确认]**：全库 grep `applier_pipeline|apply_to_state|_simulate_underflow` → 生产侧仅 `ai/client_utils.py:794`；其余命中均为测试与 scratch。

**影响**：README/模块注释把该管线描述为"AI 契约 changes → 路径白名单 + ΣΔ 守恒 + 原子写库 + 回滚"的核心架构，但**它当前只为 `relief_grant` 一个工具服务**，而该工具正因 H-1 而不可用。即：**这套精心设计的守恒/原子性设施，当前生产收益为零。** 这解释了为什么 H-1 这样一个"成功路径全崩"的缺陷能存活如此之久——没有真实流量经过它。

---

## 附录：本次审查实际执行的验证命令

```powershell
# 环境前置（每个 shell 会话）
$env:PYTHONPATH=''; $env:PYTHONIOENCODING='utf-8'
Remove-Item Env:CODEBUDDY_TOOL_CALL_ID -ErrorAction SilentlyContinue
Remove-Item Env:CODEBUDDY_SAFE_DELETE_BULK_STATE_DIR -ErrorAction SilentlyContinue
cd D:\codebuddy\sz\game

# 1) 全量 + 覆盖率（原始输出 _cov.txt / cov.json）
& D:\codebuddy\.audit-venv\Scripts\python.exe -m pytest -q -p no:cacheprovider `
  --cov=core --cov=engine --cov=ai --cov=memory --cov=backend `
  --cov-report=term-missing --cov-report=json:D:\codebuddy\sz\_dev_tools\_scratch\audit-2026\cov.json

# 2) 收集总数确认
& D:\codebuddy\.audit-venv\Scripts\python.exe -m pytest -p no:cacheprovider --collect-only -q <tests>
#   → 390 tests collected

# 3) runner 差异 / sys.path 脆弱性（H-4）
& D:\codebuddy\.audit-venv\Scripts\python.exe -m pytest -q <tests>\test_state_applier.py   # 4 failed, 14 passed
& D:\codebuddy\.audit-venv\Scripts\pytest.exe      -q <tests>\test_state_applier.py        # ModuleNotFoundError: core
& D:\codebuddy\.audit-venv\Scripts\pytest.exe      -q <tests>                              # 11 failed, 379 passed

# 4) 探针（全部位于 _dev_tools\_scratch\audit-2026\，不改动 game/ 与 tests/）
& ...python.exe D:\codebuddy\sz\_dev_tools\_scratch\audit-2026\h_probe_nameerror.py            # H-1
& ...python.exe D:\codebuddy\sz\_dev_tools\_scratch\audit-2026\h_probe_treasury.py             # H-3 证据3
& ...python.exe D:\codebuddy\sz\_dev_tools\_scratch\audit-2026\h_probe_horizon.py              # H-3 证据4（120月）
& ...python.exe D:\codebuddy\sz\_dev_tools\_scratch\audit-2026\h_be_probe.py                   # H-5
& ...python.exe D:\codebuddy\sz\_dev_tools\_scratch\audit-2026\h_probe_tolerance2.py           # H-8 + H-7
& ...python.exe D:\codebuddy\sz\_dev_tools\game-dev\tests\test_core_logic.py                   # H-15

# 5) 真实存档目录污染取证（H-2）
Get-ChildItem "C:\Users\william\Documents\宋祚\saves" | Sort-Object LastWriteTime |
  Select-Object Name, Length, LastWriteTime
Get-Item D:\codebuddy\sz\_dev_tools\_scratch\audit-2026\_cov.txt | Select-Object LastWriteTime

# 6) 前端零测试取证（H-9）
Get-ChildItem D:\codebuddy\sz\game\frontend -Recurse -Include *.test.ts,*.test.tsx,*.spec.ts,*.spec.tsx
Get-ChildItem D:\codebuddy\sz\game\frontend -Recurse -Directory -Filter "__tests__"
Get-Content D:\codebuddy\sz\game\frontend\package.json -Raw     # scripts 中无 test

# 7) 版本控制取证（H-14）
Test-Path D:\codebuddy\sz\.git ; Test-Path D:\codebuddy\sz\game\.git    # 均 False
```

**产物清单**（均在 `D:\codebuddy\sz\_dev_tools\_scratch\audit-2026\`）：
`_cov.txt`（覆盖率原始输出）、`cov.json`、`h_probe_nameerror.py/.txt`、`h_probe_treasury.py`、`h_probe_horizon.py`、`h_be_probe.py/.txt`、`h_probe_tolerance2.py/.txt`、`h_probe_conservation_tolerance.py`（含一处 format 字符串 bug，已被 `h_probe_tolerance2.py` 取代）、本报告 `H-tests-quality.md`
