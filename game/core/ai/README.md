# core/ai — 双层智能分工与天道裁决引擎

> 承 2026-10-17 架构（原「双层智能分工」2026-10-17 + 天道裁决体系 2026-10-17 修复批）：
> 贯彻「天道定因果骨肉，大模型着春秋笔墨」——**微观高频决策本地纯算（零 Token、确定性）**，
> **宏观叙事交大模型（只出文字，不出数值）**。
> 逐项接线状态见 [`specs/cross-cutting/tiandao-engine/tasks.md`](../../../_dev_tools/game-docs/specs/cross-cutting/tiandao-engine/tasks.md) §2。

## 模块结构

| 模块 | 职责 | 契约与特性 |
|---|---|---|
| `tiandao_engine.py` | 🔴 **天道裁决核心引擎**（`TianDaoEngine`） | 四大裁决：`gate`（天命是非）/ `choose`（造化殊途，Softmax 严格归一）/ `score`（气数品位）/ `dice`（天意机变，显式种子的确定性微扰）。**纯函数**：不写 state、不碰账本、零网络。首参同时接受 `context=` 与旧关键字 `state_context=`。 |
| `tiandao_facade.py` | 🔴 **全域天道业务门面**（`TianDaoFacade`） | 六域裁决入口（财政/商贸/仓储物流/乡村社会/官僚治理/军事治安）＋三条 AI 管道的事实提炼（`scan_memorial_seeds` / `derive_dialogue_stance` / `summarize_monthly_omen`）＋动态财政安全垫线。所有裁决**显式传 `objective`**，不靠文案子串分派。 |
| `tiandao_decision.py` | **天道 × DecisionService 适配**（P1 2026-10-21） | 把 10 个观察 objective 显式登记（mode/options/criteria），`TianDaoDecisionEngine` 映射为 `DecisionResult`；`decide_and_log` 只写 `state.decision_log`（有界 200），**不改判定/不写账本/不联网**；供 `observe_monthly` 记录与后续门面迁移。 |
| `embedded_jev.py` | 兼容薄桩 | `EmbeddedJevEngine = TianDaoEngine`（**别名，不是新类**；旧关键字签名继续可用）。 |
| `decision_facade.py` | 兼容薄桩 | `EmbeddedDecisionFacade = TianDaoFacade`。 |
| `clerk_decision.py` / `merchant_decision.py` | 吏/商个体决断 | 全委派 `EmbeddedJevEngine`（→ 天道）；失败留 warning 并回落兜底。 |

## 契约（改这些等于改契约）

1. **`provider` 值 = `"tiandao_local"`**（2026-10-17 由 `embedded_local` 改名，Jev p=0.994；全库无生产消费方）。
2. **缺失 ≠ 0 ≠ 1.0**：`gate` 无依据时 `verdict=False`、`probability=None`、`defined=False`；
   `score` 无上下文时 `score=None`。取数一律 `is None` 判缺失，**禁止 `x or default`**（会吞掉合法的 `0`）。
3. **`score` 的 `levels` 必须「差 → 好」排列**（如 `("下考","中考","上考")`）；两个分支都归一为"越好分越高"。
4. **Softmax 概率严格归一为 1.0**（舍入残差回填最大项，别再用 `approx(1.0, abs=1e-4)` 掩盖）。
5. **`dice` 必须由调用方给种子**（回合号 / 存档内种子），引擎不自取随机源；同种子跨进程结果一致（splitmix64）。
6. **`objective` 显式优先**：`gate` / `choose` 的旧 `condition` 子串与 `criteria` 键名分派只作向后兼容回退。
7. **零 Token 依赖**：全域高频循环（月度结算、州县微观决策、商人货流）**严禁调用外部大模型 API**；
   文字类输出只走 `game/ai/` 契约。
8. **只出决断不落地**：门面不修改账本；状态变更与物理交割必须回归各业务域与 `ledger` 桥接层。
9. **口径分层（吏治通道）**：`core/decree_effect.py` 的 `clerks_mult` = **吏胥折扣本体**；
   知州遵从度单列 `clerks_compliance`，只在 `effect_mult` 合成层参与——**通道仍是三条，不新增乘数**。
10. **"有实现 + 有单测" ≠ "已生效"**：未接线的门面方法在 `tasks.md` 里显式标注，对外不得描述为已改变玩法。

## 已验证（本批回归）

`_dev_tools/game-dev/tests/test_tiandao_engine_core.py`、`test_tiandao_facade_wiring.py`、
`test_ai_narrative_pipelines.py`、`test_decree_pipeline_tiandao.py`、`test_appraisal_and_demagic.py`、
`test_embedded_decision_facade.py` —— 覆盖确定性、缺失值、Softmax 归一、四类抉择非恒定、
贪墨闸门可达性与单调性、考课下考可达性、安全垫线真动态、三管道接线。
