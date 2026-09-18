# 宋祚 · 测试套件整理（2026-09-18）

> 缘起：用户指出「现有测试项不一定符合现在的游戏情况，先整理一遍」。
> 方法：`pytest --collect-only` 全量清点 + 逐个失败项归因 + 按「是否对应**当前**游戏行为」分类。
> 环境：`D:\codebuddy\.audit-venv\Scripts\python.exe`，前置 `PYTHONPATH=''`＋清 `CODEBUDDY_*`。
> 基线：**47 文件 / 390 用例 / 11 失败**。
>
> **第二轮（2026-09-18 晚）**：用户再问「检查一遍测试项，看看哪些是没用的，哪些还没测」。
> 方法升级为 **覆盖率驱动 + AST 结构扫描**（`coverage 7.16.1` 全量 + 逐函数缺口映射）。
> 基线与结果见 [§九 第二轮体检](#九第二轮体检2026-09-18-晚覆盖率驱动)。**当轮又抓出 4 处货币守恒破坏**——
> 全部躲过了既有账本测试（原因见 §9.4「镜像覆盖 ≠ 路径覆盖」）。

---

## 一、结论速览

| 类别 | 数量 | 性质 |
|---|---|---|
| **A. 真实缺陷（红）** | **4** | 代码有 bug，测试是对的 → **修代码** |
| **B. 测试过期（红）** | **7** | 代码是对的，测试断言的是**旧语义** → **改测试** |
| **C. 绿但无效** | **≈25 用例** | 测的是**无生产调用方**的模块 → 永远拦不住真实回归 |
| **D. 弱断言** | **20 条** | 断言过宽（`>=0` / 恒真 / 断言源码文本）→ 抓不到缺陷 |
| **E. 没覆盖的路径**（第二轮新增） | **关键函数大面积零覆盖** | 步骤被镜像覆盖，但**触发状态从未被造出** → 步骤内的钱路从未执行 |

> **最危险的从来不是红测试，而是 C 类**：它们绿着，给人"这块有保护"的错觉，实际保护的是没人调用的代码。
> **E 类更隐蔽**：步骤在镜像里、覆盖率也不是 0，但关键分支从未被走到（见 §9.4）。

---

## 二、A 类 · 真实缺陷（4 项，同一 P0 根因）

全部由 `engine/state_applier.py` 的 `_resolve_path_value` 悬空引用引起（详见 [review_2026-09-18.md](review_2026-09-18.md) P0-1）：

| 用例 | 表现 |
|---|---|
| `test_state_applier.py::test_pipeline_apply_log` | `NameError: _resolve_path_value` |
| `test_state_applier.py::test_pipeline_rejected_collected` | 同上 |
| `test_state_applier.py::test_underflow_reject_no_mint` | 同上 |
| `test_review_2026_09_fixes.py::test_relief_region_resolve_and_refuse` | 生产表现："赈济未能落地（状态应用层异常，已拒绝）" |

**处置**：修代码（阶段 1.1），测试不动。

---

## 三、B 类 · 测试过期（7 项）——逐条给出正确断言语义

### B1. 破产判据 B3 语义反转（5 项）

`TREASURY_CRISIS_LINE` / `TREASURY_COLLAPSE_LINE` 已由「**负国库下界**」改为「**正累计亏空深度**」（`game_state.deficit_depth()`）。生产侧三处消费方全部用新判据：

- `core/evaluation.py:146`（退位）与 `:176`（game over）
- `core/briefing.py:77`（库藏告急急务）
- `core/settlement_steps.py:3055`、`core/settlement.py:341-346`

| 用例 | 现断言（旧语义） | 应改为 |
|---|---|---|
| `test_briefing.py::test_briefing_desensitized` | `s.treasury = -6_000_000` | `s.treasury_deficit = 6_000_000`（并保留"文本不得出现 6000000"的脱敏断言） |
| `test_briefing.py::test_briefing_urgent_flags` | `s.treasury = -6_000_000` | 同上 |
| `test_core_logic.py::test_game_over_treasury_collapse` | `s.treasury = TREASURY_COLLAPSE_LINE - 1` | `s.treasury_deficit = TREASURY_COLLAPSE_LINE + 1` |
| `test_core_logic.py::test_game_over_abdication` | `s.treasury = -6_000_000` ＋满意度 10 | `s.treasury_deficit = TREASURY_CRISIS_LINE + 1` ＋满意度 10（`check_abdication` 需 **≥2 条**理由，见 `evaluation.py:141-158`） |
| `test_regression_2026_08.py::test_treasury_stays_above_crisis_line` | `assert s.treasury > TREASURY_CRISIS_LINE` | 改为断言**真实危机判据**：`s.deficit_depth() <= TREASURY_CRISIS_LINE`，并补一条"国库永不穿底"（`s.treasury >= 0`）。**注意**：`TREASURY_START == TREASURY_CRISIS_LINE == 5,000,000`，故 `>` 断言在开局第 0 步即为假；且**国库开局下滑属游戏设定**（用户口径），不是回归 |

### B2. 市舶关税入账通道变更（1 项）

`test_pop_identity.py::test_maritime_trade_ledger_closed` 期望 `_settle_extensions` 把关税入国库。R2-5 已删除该**重复计账**通道，唯一入账通道改为 `_settle_finance`（见 `settlement_steps.py:1023-1027` 注释与 `:2808-2829`）。

**应改为**：断言 `_settle_extensions` 阶段 **Δtreasury == 0**（不在此入账）、商人仍得外贸利润，并另行断言 `_settle_finance` 的 `tax_breakdown["maritime"] > 0`（唯一通道生效）。

### B3. 已拍板废弃的规则（1 项）

`test_state_applier.py::test_cascade_faction_power` —— 测的 `factions.*.power` cascade 规则**已按决策 1 正式废弃**（该 path 不在白名单、`FactionState` 无 `power` 字段，规则永不触发）。

**处置**：**删除该用例**，并在 `state_applier.py` 的删除处保留白纸化注释（已有）。

---

## 四、C 类 · 绿但无效：测「无生产调用方」的模块（≈25 用例）

| 测试文件 | 用例 | 被测模块的接线状态 |
|---|---|---|
| `test_async_ai.py` | 12 | `core/async_ai.py` —— **未接线**，全库无生产调用方；其线程纪律以**已删除的 Tkinter `ui.after`** 为前提（`游戏机制说明.md` §〇 明载） |
| `test_contract_adapter.py` | 6 | `ai/contract_adapter.py` —— **待接线**，有 T5 覆盖、尚无生产调用方 |
| `test_t1_state_tools.py` | 4 | `ai/state_tool_schemas`（`STATE_TOOL_SCHEMAS`）—— **预留契约**，`_call_with_tools` 暂无生产调用方 |
| `test_improvements.py` | 1（第 111 行） | 引用 `core.async_ai` |
| `test_parallel_settlement.py` | 1（第 70 行） | 引用 `core.async_ai` |
| `test_review_p0_conservation.py` | 1（第 96 行） | 引用 `core.async_ai` |

**处置（不删，但必须标注）**：这些用例**不是错的**（保留为「接线前的参照实现」回归），但**不能被当作已生效能力的保护**。建议：

1. 在文件 docstring 顶部加显式标注：
   `> ⚠️ 未接线模块的回归保护。`async_ai`/`contract_adapter`/`STATE_TOOL_SCHEMAS` 当前无生产调用方，本文件绿**不代表**任何线上路径受保护。`
2. 在测试里加一条"接线状态断言"，**接线状态一旦变化即报警**（把"未接线"从隐含知识变成可检查事实）：

```python
def test_async_ai_is_still_unwired():
    """若 async_ai 被接线，本断言会失败，提示同步更新文档与本文类。"""
    import pathlib
    root = pathlib.Path(__file__).resolve().parents[3] / "game"
    hits = [p for p in root.rglob("*.py")
            if "async_ai" in p.read_text(encoding="utf-8", errors="ignore")
            and p.name != "async_ai.py" and not p.name.startswith("test_")]
    assert not hits, f"async_ai 已出现生产引用，请更新接线状态文档：{hits}"
```

（`contract_adapter` / `STATE_TOOL_SCHEMAS` 同理。）

---

## 五、D 类 · 弱断言（20 条）

完整清单见 [H-tests-quality.md](../../_scratch/audit-2026/H-tests-quality.md)（14 条弱断言 ＋ 6 条过拟合）。代表：

| 位置 | 问题 |
|---|---|
| `test_async_ai.py:210` | `assert game_over in (True, False)` —— **布尔恒真**，永不失败 |
| `test_price_stabilizer.py:102` | 注释承诺"ΣΔ==0 守恒"，断言只查 `>= 0` |
| `test_finance_decide.py:82-89` | 用例名含"拒绝式"，却一行都没测拒绝路径 |
| `test_review_p0_conservation.py:93-99` | 用 `inspect.getsource` **断言源码文本** —— 改实现即假失败，且不验证行为 |

**处置**：随对应功能批次逐条收紧（不单独开批，避免"为改测试而改测试"）。

### D′ 类 · 过宽容差掩盖错误（3 处，**2026-09-18 阶段 B-2 收尾已结案**）

比"弱断言"更危险的一类：断言方向没错，但**容差大到把错误调整项一起放行**。复核 `test_pop_identity.py` 两处 `3_000_000` 后发现——容差大不是残差大，而是**容差里同时睡着两个错误**：

| # | 位置 | 掩盖的错误 | 实测 | 改正 |
|---|---|---|---|---|
| 1 | `test_pop_identity.py::test_global_ledger_total` | `expected` 仍加 `meat_revenue` —— A-4 后作坊产肉已是 POP→内帑 **守恒转移**，该步 ΔW ≡ 0；加回去等于把已修的造币 bug 当预期 | 仅此一项即偏 ~4 万贯 | 删项；容差 **3,000,000 → 200** |
| 2 | 同上 | `dW - lt_delta` 扣常平府库净变化 —— 常平钱粮互换在含 `local_treasury` 的 W 里本来净额为 0，剔一侧只减钱、不加回 POP 粮侧，**凭空造出假残差** | **−443,397**（占容差 14.8%，占真实残差 99.9%） | 取消扣减 |
| 3 | `test_pop_identity.py::test_wealth_ledger_no_hoard` | `Δchangping × grain_price` 代理不成立（同月多路双向平粜/平籴、各路价不同、步后价已改写） | 真实 ΔW ∈ [−103,−100] | 直接断言 `|ΔW| ≤ 200` |

**同批补强**：`_STEPS` 逐步审计镜像**漏了 `region_deepen` 与 `upkeep` 两步**，比真实管线弱 —— 补齐后实测两步 `ΔW == 0`（用 40 个随机种子扫描确认）。**镜像不完整的账本测试会给"新结算步偷偷漏钱"留后门**，故新增结算步时必须同步镜像。

**方法论（写入本文件）**：**容差不是安全垫，而是未解释残差的藏身处**。任何 >1,000 的账本容差都必须附实测依据；收紧容差本身就是一次审计。

---

## 六、分文件状态表（47 文件 / 390 用例）

图例：✅ 与当前游戏行为一致 ｜ 🔴 红（A 缺陷 / B 过期）｜ ⚠️ 需标注或收紧

| 文件 | 用例 | 状态 | 备注 |
|---|---|---|---|
| test_agent_p1.py | 5 | ✅ | |
| test_agent_router.py | 4 | ✅ | |
| test_ai_contract.py | 11 | ✅ | 08-25 较旧，随批次复核 |
| test_army_branches.py | 8 | ✅ | |
| test_async_ai.py | 12 | ⚠️ | **测未接线模块**；含恒真断言 |
| test_branch_registry.py | 7 | ✅ | |
| test_briefing.py | 6 | 🔴 B1×2 | 断言旧破产语义 |
| test_building_tech.py | 4 | ✅ | |
| test_codex_data.py | 6 | ✅ | |
| test_contract_adapter.py | 6 | ⚠️ | **测待接线模块** |
| test_core_logic.py | 18 | 🔴 B1×2 | 断言旧破产语义 |
| test_desensitize.py | 8 | ✅ | 08-18 最旧，随批次复核 |
| test_diplomacy_panel.py | 4 | ⚠️ | 名称含 UI；Tk 面板已删，需确认实际测什么 |
| test_diplomacy_treaty.py | 16 | ✅ | |
| test_era_interaction.py | 6 | ✅ | |
| test_events_a6.py | 7 | ✅ | |
| test_finance_decide.py | 4 | ⚠️ | 名称含"拒绝式"未测 |
| test_flow_summary.py | 5 | ✅ | |
| test_four_mechanisms.py | 8 | ✅ | 09-18 最新 |
| test_free_effect.py | 8 | ✅ | |
| test_identity.py | 15 | ✅ | |
| test_imperial_action.py | 20 | ✅ | |
| test_imperial_action_ui.py | 5 | ⚠️ | 同上 UI 命名 |
| test_improvements.py | 10 | ⚠️ | 引用 `async_ai` |
| test_industry_scale.py | 5 | ✅ | |
| test_inner_transfer.py | 5 | ✅ | |
| test_memory_graph.py | 8 | ✅ | 自身绑定 `SAVE_DIR`（已由 conftest 统一重定向） |
| test_memory_sqlite.py | 21 | ✅ | 同上 |
| test_minister_cards.py | 4 | ⚠️ | UI 卡片命名 |
| test_ministers_traits.py | 3 | ✅ | |
| test_narrative_fallback.py | 15 | ✅ | |
| test_parallel_settlement.py | 5 | ⚠️ | 引用 `async_ai` |
| test_persona_alignment.py | 6 | ✅ | |
| test_pop_identity.py | 20 | 🔴 B2×1 | 市舶通道变更 |
| test_pop_panel.py | 5 | ⚠️ | UI 命名 |
| test_price_plan.py | 6 | ✅ | |
| test_price_stabilizer.py | 15 | ⚠️ | 守恒断言过宽 |
| test_regression_2026_08.py | 5 | 🔴 B1×1 | 起手值==危机线，`>` 断言必假 |
| test_review_2026_09_fixes.py | 6 | 🔴 A×1 | P0 生产表现 |
| test_review_p0_conservation.py | 13 | ⚠️ | 引用 `async_ai`；`inspect.getsource` 断言 |
| test_state_applier.py | 18 | 🔴 A×3 ＋ B3×1 | P0 ＋ 已废弃 cascade 用例 |
| test_succession_mode.py | 5 | ✅ | |
| test_t1_state_tools.py | 4 | ⚠️ | **测预留契约**（无生产调用方） |
| test_three_schemes.py | 6 | ✅ | |
| test_tier_seven.py | 4 | ✅ | |
| test_token_meter.py | 6 | ✅ | |
| test_tuning_fixes.py | 2 | ✅ | |
| conftest.py（新增） | — | — | 2026-09-18 安全网：SAVE_DIR 重定向 ＋ sys.path 统一 ＋ 全局态复位 |

---

## 七、本轮整理动作（可验收）

| # | 动作 | 验收 |
|---|---|---|
| 1 | **删除** `test_state_applier.py::test_cascade_faction_power` | 用例数 390 → 389 |
| 2 | **同步 B1×5**：断言由「负国库」改为「累计亏空深度」 | `test_briefing.py`、`test_core_logic.py`、`test_regression_2026_08.py` 相关用例转绿 |
| 3 | **同步 B2×1**：市舶关税断言改为「`_settle_extensions` 不入账 ＋ `_settle_finance` 唯一入账」 | `test_pop_identity.py` 该用例转绿 |
| 4 | **标注 C 类**：在 3 个未接线测试文件加"未接线"抬头 ＋ 接线状态断言 | 故意接线后断言会失败（可演示） |
| 5 | 整理后基线：**应只剩 4 项 A 类红**（待阶段 1.1 修 P0 后归零） | `pytest` 输出 4 failed / 385 passed |

### 追加动作（2026-09-18 · 阶段 B 收尾）

| # | 动作 | 验收 |
|---|---|---|
| 6 | **D′×3 收紧**：三处 3,000,000 容差 → **200**，并删除两个不成立的调整项（`meat_revenue`、`lt_delta`）与一个不成立的代理公式（`Δchangping×价`） | `test_pop_identity.py` 20 例全绿，且**真实残差暴露为 ~141 贯** |
| 7 | **逐步审计镜像补全**：`_STEPS` 补入 `region_deepen`、`upkeep` | 40 seed 扫描：`granary ΔW ∈ [−103,−100]`、`upkeep`/`region_deepen` ΔW ≡ 0 |
| 8 | **新增** `test_asset_upkeep.py`（4 例）：守恒转移 / 按实付欠费 / 资产比例放大 / 月度结算确实调用 | 含**防"写了没接上"**的日志断言；套件 389 → **393** |
| 9 | **同步 A-4/B-2′ 语义**：`test_wealth_ledger_no_hoard` workshops 分支改为断言 `ΔW == 0`（原断言把"畜栏产肉造币"bug 当预期） | 该例由红转绿 |
| 10 | **当前基线** | `pytest` **393 passed / 0 failed / 0 error**；`ruff F821,F601` 零命中 |

---

## 八、与修复计划的衔接

- 本整理属修复计划 **阶段 0.3/0.4（安全网）与阶段 2（测试对齐）** 的合并执行。
- **顺序**：先整理测试（本轮）→ 再修 P0（阶段 1.1）→ 此时套件应**全绿**，才具备后续批次（货币口径 / 官制）的安全基线。
- 之后每批仍按「验收三连」：`pytest` ＋ `ruff F821/F601` ＋ 60 月回放；阶段 B 起追加第四项：**货币对账残差**。
- **阶段 B 已收口**（B-1 观测 → B-2 守恒 → B-2′ 军俸/欠饷 → B-3 L1 维持费），下一步进入 **阶段 C 官制**。第 6–9 项动作**已按原计划随功能批次完成**，未另开测试批。

---

## 九、第二轮体检（2026-09-18 晚，覆盖率驱动）

> 用户再问：「检查一遍测试项，看看那些是没用的，那些还没测。」
> 方法从"人工归类"升级为**工具驱动**：
> ① `pytest --collect-only` 清点（52 文件 / 443 用例）；
> ② `coverage 7.16.1` 全量跑（`--include` 限定 `game/` 生产目录）→ 逐 **函数** 映射缺口；
> ③ AST 结构扫描：无断言用例 / 恒真断言 / 重复体 / 引用未接线模块的用例。

### 9.1 「没用的」——逐条证据

| # | 位置 | 问题 | 处置 |
|---|---|---|---|
| 1 | `test_async_ai.py:210` | `assert s.game_over in (True, False)` —— **布尔恒真** | ✅ 改为 `assert s.game_over is False`（开局一月不可能终局），并把被"不抛即可"注释掩盖的语义写回 |
| 2 | `test_price_stabilizer.py:166` | `assert s.statistics["coin_melted"] > s.statistics.get(...) - 1 or True` —— `or True` + 自己比自己减 1，**恒真** | ✅ 改为真正的"第二次熔化累计额应增加"（先存 `_after_first` 再比） |
| 3 | `test_middle_calibration.py:199` | `assert money.m_all(s) - m0 != 0 or True` —— **恒真**（**本轮我自己写的**，体检时被自己的扫描抓到） | ✅ 删除，改为**验证回流去向**（工匠/商人 POP 确有入账）——守恒的直接证据，而非间接残差 |
| 4 | `test_price_stabilizer.py::test_changping_buy_ratio_cap` | 注释承诺「平籴支出 ≤ 府库 50%」「常平 ΣΔ==0：仓增量×价 ≈ 府库减量」，**两条都没断言**；唯一断言是 `local_treasury >= 0` | ✅ 按注释补齐两条真断言（预算上限 ＋ 钱粮守恒） |
| 5 | `test_finance_decide.py::test_finance_reject_bad_states` | 用例名承诺"拒绝式：缺失/非法 → None"，**一行都没测拒绝路径**（只断言常量形状） | ✅ 改为**真驱动** `economy_decide`：正向对照 + 5 字段 × 3 种非法（非法词/缺失/非字符串）全部拒绝 |
| 6 | `test_contract_adapter.py`（6 例） | `ai/contract_adapter.py` **无生产调用方**（AST 核实） | ⚠️ 加"接线状态"抬头（不删：映射表契约本身仍有价值，但不得当作线上验证） |
| 7 | `test_async_ai.py`（12 例） | `core/async_ai.py` **无生产调用方** | ⚠️ 加抬头 ＋ 新增 **接线哨兵** `test_async_module_is_not_wired_yet`（AST 判定；接线即失败提醒复核）<br>· 实现细节：首版用文本扫描，被 `contract_adapter.py` 文档串里的"待接线"提及**误判**，改 AST 后通过 |
| 8 | `test_review_p0_conservation.py::test_async_settlement_no_nested_submit` | 断言**源码文本**（`inspect.getsource`）＋ 测的是未接线模块 | ⚠️ 标注；**建议**：接线时改为"跑真实路径 + 超时失败"的行为断言，否则可删 |
| 9 | 22 处 `assert x is not None` | 弱断言；多数是 `load_game` 守卫（失败后紧跟真断言，非无用） | ⏸️ 保留（弱但有用），仅记录 |

> **A 类（无任何 assert 的用例）= 0**；**D 类（用例体完全重复）= 0** —— 这两项干净。

### 9.2 「还没测的」——覆盖率地图

**总体：65.45%（12,670 语句 / 未覆盖 4,377）；零覆盖函数 0 个**（每个函数都被碰到过），
但**关键函数大面积零覆盖**：

| 模块 | 覆盖率 | 最大缺口（体检前） |
|---|---|---|
| `content/geo_admin.py` | **18.2%** | `validate_geo` 缺 **147/148** |
| `core/legacy_mechanic.py` | **23.8%** | `_estimate_progress` 缺 19/21、各效果/消除条件 |
| `ai/client_narrative.py` | 26.7% | — |
| `ai/client.py` | 29.1% | 缺 1,070 语句（AI 客户端，需 mock） |
| `core/settlement.py` | **34.1%** | `_apply_reform_result` 缺 **58/60**、`settle_reform` 缺 27/29、`_fallback_reform` 缺 19/21 |
| `core/settlement_steps.py` | 74.2% | `_state_grain_trade` 缺 **70/72**、`_settle_projects` 缺 **40/43** |
| `core/commands_decree.py` | 40.8% | `merge_drafts` 17/19、`preview_draft` 13/15 |
| `core/save_load.py` | 72.7% | `load_game` 缺 62/283（旧档迁移分支） |
| `core/events.py` | 70.5% | `get_strategic_branch` 9/11、`get_pending_break_event` 8/10 |

### 9.3 本轮补测与修复（体检直接产出）

| # | 动作 | 结果 |
|---|---|---|
| 1 | 新增 `test_step_gap_fills.py`（15 例）：`legacy_mechanic` 标签型修正/消除条件、`focus_mechanic` 全生命周期/取消/锁定拒绝/分支效果、`institution.apply_reform` 逐项拒绝与损坏态回退、**工程款/皇帝行动/和亲嫁妆/政府粮食交易的守恒** | 套件 443 → **459** |
| 2 | **补测当场抓出真 bug**：`core/institution.py::get` 文档承诺"绝不抛"，但 `institution_params` 为**真值非 dict**（损坏/旧档）时 `cur.get` 抛 `AttributeError` —— 而它被官制/吏制/维持费**每步结算**调用，破档即整月结算崩 | ✅ 改为显式类型判定 |
| 3 | **覆盖率提升**：`legacy_mechanic` **23.8% → 76.2%**、`focus_mechanic` **69.5% → 83.1%**、`institution` **80.5% → 89.3%**、`settlement_steps` **74.2% → 77.3%**；总体 **65.45% → 66.73%** | — |

### 9.4 方法论：**镜像覆盖 ≠ 路径覆盖**（本轮最大教训）

补测工程款守恒时发现：`_settle_projects` **在 `_STEPS` 镜像里**（上一轮刚补全镜像一致性断言），
但**回放与全部用例中 `state.projects` 恒为空** → 该步骤内的**钱路从未被执行**。
于是同一个"无对手方销毁货币"缺陷在**四个地方**同时存活，且全部躲过账本测试：

| 位置 | 症状 | 实测 | 修复 |
|---|---|---|---|
| `_settle_projects` `cost_coin` | 裸 `state.treasury -= coin_need` | 单项工程 500,000 贯 → **ΔM_ALL = −500,000** | ✅ 支出回流（国库 → 工匠40%/商人60% POP） |
| `_settle_emperor_personal` `base_cost` | 裸 `change_treasury(-paid)` / `内帑 -= paid` | 皇帝行动 80,000 贯 → 无对手方 | ✅ 同上（宫廷支出口径） |
| `_settle_projects` `wine_coin_add` | 裸 `内帑 += 收益`（**无买方**，同审查 A-4） | 属预留路径（当前无工程用），但契约错误 | ✅ 改为向民间守恒征收（实收才入账） |
| `diplomacy_treaty` 和亲嫁妆 | `内帑 -= dowry` **未登记 burn** | 外流未登记 → 月度对账报"未解释残差" | ✅ `register_flow(state,"burn",…)` |

> **结论**：账本测试的"镜像完整性"只保证**步骤被调用**，不保证**步骤内的分支被走到**。
> 因此 §八 的新增纪律要再加一条：**账本镜像一致性是必要条件，不是充分条件**；
> 对"只在特定状态下才动钱"的步骤（工程 / 皇帝行动 / 外交 / 研发），必须**造出触发状态**再断言守恒。

### 9.5 仍未测的部分（诚实清单）

| 项目 | 状态与理由 |
|---|---|
| `core/settlement.py` 的**机构改制**路径（`settle_reform` / `_apply_reform_result` / `_fallback_reform`，缺 58/60 等） | ⏳ **未补**：依赖 `AI 契约 + 机构改制状态机`，需较大 mock 工程量；属**下一步优先级最高**的缺口（改制直接影响官额/机构，是 C 批次的交互面） |
| `ai/client.py`（缺 1,070 语句） | ⏳ 未补：需系统化 mock AI 响应；本轮只在 `test_finance_decide` 里打通了 `economy_decide` 一条真实路径（**该模式可复制推广**） |
| `content/geo_admin.validate_geo`（缺 147/148） | ⏳ 未补：数据校验器，价值取决于舆图数据是否会被玩家/脚本改动 |
| `core/commands_decree.py`（40.8%） | ⏳ 未补：拟旨/会签/密旨分支 |
| `core/save_load.load_game` 旧档迁移分支（缺 62/283） | ⏳ 未补：**建议优先**——旧档兼容是发布风险点 |
| C 类两文件（`async_ai` / `contract_adapter`）仍测未接线模块 | ⏳ 已标注接线状态哨兵；**是否接线由用户决定**（不接线 = 这些用例价值有限） |
| `test_review_p0_conservation.py` 的源码文本断言 | ⏳ 已标注；建议随接线一并改造或删除 |
