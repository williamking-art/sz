# core/ai — 双层智能分工与天道裁决引擎

> 承 2026-10-17 架构（原「双层智能分工」2026-10-17 + 天道裁决体系 2026-10-17 修复批）：
> 贯彻「天道定因果骨肉，大模型着春秋笔墨」——**微观高频决策本地纯算（零 Token、确定性）**，
> **宏观叙事交大模型（只出文字，不出数值）**。
> 逐项接线状态见 [`specs/cross-cutting/tiandao-engine/tasks.md`](../../../_dev_tools/game-docs/specs/cross-cutting/tiandao-engine/tasks.md) §2。

## 模块结构

| 模块 | 职责 | 契约与特性 |
|---|---|---|
| `tiandao_engine.py` | 🔴 **天道裁决核心引擎**（`TianDaoEngine`） | 四大裁决：`gate`（天命是非）/ `choose`（造化殊途，Softmax 严格归一）/ `score`（气数品位）/ `dice`（天意机变，显式种子的确定性微扰）。**纯函数**：不写 state、不碰账本、零网络。首参同时接受 `context=` 与旧关键字 `state_context=`。⚠️ 2026-10-21：**全部玩法常数已外置**到 `content/data_tiandao.py`（93 个带口径注释的参数，唯一入口 `PARAMS`）；引擎体内只剩 `0/1` 结构性哨兵与 `threshold=0.5`/`temperature=0.8` 两个签名默认值。 |
| `tiandao_facts.py` | 🔴 **facts 契约（单一读数口径）**（2026-10-21） | 定义天道层**唯一**的上下文表：24 个 canonical 键 × 量纲 × 缺失语义。生产者（门面/吏/商）一律 `build_facts(state)` 或 `canonicalize()`；引擎只读 canonical 主键。附 `validate_facts`（契约守卫）、`facts_digest`（决策留痕摘要）、`to_engine_context`（过渡别名）。**新增读数必须先在此登记**。 |
| `tiandao_facade.py` | 🔴 **全域天道业务门面**（`TianDaoFacade`） | 六域裁决入口（财政/商贸/仓储物流/乡村社会/官僚治理/军事治安）＋三条 AI 管道的事实提炼（`scan_memorial_seeds` / `derive_dialogue_stance` / `summarize_monthly_omen`）＋动态财政安全垫线。所有裁决**显式传 `objective`**，不靠文案子串分派。`build_state_context` 是 facts 契约的**唯一生产入口**（不自算读数）。 |
| `tiandao_decision.py` | **天道 × DecisionService 适配**（P1 2026-10-21；L1 补齐） | 登记 **13 个 objective**（gate/choose/score 三种 mode）：含此前漏登的 `decree_compliance`（生产在用却不进日志）与 `appraisal`（score 模式）。`ObjectiveDef.thresholds` 由 `THRESHOLDS` 单点下传（此前是死字段）；`decide_and_log` 只写 `state.decision_log`（有界 200，含 `facts_digest`），**不改判定/不写账本/不联网**。 |
| `tiandao_backtest.py` | **离线回测器**（L2 2026-10-21） | 消费 `decision_log` + 可选标签，算 `brier` / `reliability_bins`(ECE) / `hit_rate` / `monotonic_check`；CLI：`python -m core.ai.tiandao_backtest <save.json> [--labels labels.json]`。**无标签时不给 Brier/命中率**（不拿 verdict 自证）；空输入一律 `None`，**零网络、零 state 写入**。 |
| `tiandao_labels.py` | **回测标签的纯逻辑层（代理真值）**（2026-10-22） | `metric_vector`（国库/Σ地方府库/太仓/−Σ民怨/−Σ流民）/ `pareto_best`（**唯一支配者**才打标签，不设权重）/ `forced_record`（只改目标 objective）/ `frozen_observe`（冻结观测，否则月结会覆盖注入值）/ `extract_month_labels` / `extract_labels`。**结算驱动由调用方注入**——本模块**不 import** `core.settlement`/`core.commands`/`application`（架构守卫 R2/R3）。CLI 在 `_dev_tools/game-dev/tools/tiandao_labels.py`。 |
| `tiandao_effects.py` | **裁决 → 数值效果的共享读取点**（L3 2026-10-21；2026-10-22 加概率） | `observe_verdict` / `observe_bool`（裁决词）＋ `observe_strength` / `observe_mix`（**概率**：gate 的 p、choose 的分布）＋ `gate_intensity`（超阈归一）＋ `jitter`（确定性天意扰动）。**只读** `state._tiandao_observe`；**缺失 ⇒ None**（缺 ≠ False ≠ 默认档位）；不在白名单 ⇒ None。🔴 `decisions` 按门面方法名存、`strengths`/`distributions` 按 objective id 存，本模块 `_name_keys()` **双向解析**——新增消费方必须走这里，不要自己 `dict.get`（会静默读空）。 |
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
11. 🔴 **facts 契约单一出处**（2026-10-21）：所有裁决上下文一律过 `tiandao_facts`。
    * **新增读数**：先在 `tiandao_facts.py` 登记（`FACT_KEYS` + 注释表 + `build_facts`），再让引擎读；
      引擎里**禁止** `context.get("未登记键")`。
    * **量纲固定**：钱=贯、粮=石、比例 0~1、民怨/淤塞/声望=0~100；`disaster` 对外恒 0~1
      （`state.disaster_severity` 是 0~5 灾级，只在 `build_facts` 里归一）。
      🔴 历史坑：路级 `disaster_level` 曾把 **1~5 灾级**直接喂给引擎，被钳成 1.0 ⇒ **灾级 1 与 5 等价**。
    * **过渡别名**（`stock`/`storage`/`supervision`/`stability`）登记在 `COMPAT_ALIASES`，
      只为旧调用点；新代码读 canonical 键。
12. 🔴 **玩法常数不得内联**（2026-10-21）：引擎与微观决断的一切数值走
    `content/data_tiandao.py`（引擎）或模块顶部常量区（微观域：`clerk_decision.py` /
    `merchant_decision.py`），**每条必须写口径注释**；审计认定缺依据者标 `# 待校准`。
13. 🔴 **生产者不得重复计入**：吏治（`integrity`）与灾情（`disaster`）只在**引擎分支**里生效；
    调用方的 `criteria` 只放结构先验。历史坑：`clerk_decision` 曾两头都算，
    纯 softmax 给 `lenient` 0.458、引擎再偏置成 0.57。
14. 🔴 **数值幅度取概率，不取枚举**（2026-10-22 用户裁定）：
    * gate → `observe_strength`（超阈强度 `(p−thr)/(1−thr)`，p=0.51 与 0.99 幅度不同）；
    * choose → `observe_mix`（概率加权：方向取概率差、强度取并集/期望）；
    * **禁止**「argmax 档位 → 查固定倍率表」的写法（那是把天道降级成开关）；
    * 允许叠加 `jitter(回合,目标,地点)` 做天意扰动——**必须由种子派生**，
      同种子同结果（确定性回放不可破）；
    * 缺失/未定义 ⇒ 中性（乘子 1.0 / 不动作），且与「无观测副本」逐字节一致。

## 已验证（本批回归）

`_dev_tools/game-dev/tests/test_tiandao_engine_core.py`、`test_tiandao_facade_wiring.py`、
`test_ai_narrative_pipelines.py`、`test_decree_pipeline_tiandao.py`、`test_appraisal_and_demagic.py`、
`test_embedded_decision_facade.py` —— 覆盖确定性、缺失值、Softmax 归一、四类抉择非恒定、
贪墨闸门可达性与单调性、考课下考可达性、安全垫线真动态、三管道接线。

2026-10-21 加强批新增：
`test_tiandao_params_contract.py`（40 例：参数外置生效、四缺陷、签名/纯函数/零依赖）、
`test_tiandao_facts_wiring.py`（8 例：`disaster`/`integrity`/`stock`/`block_rate` 口径 + 三方法非恒定）、
`test_tiandao_decision_log_persist.py`（7 例：落盘往返、v4 旧档兼容、脏档降级、只读性、截断）、
`test_tiandao_backtest.py`（20 例：Brier/ECE/命中/单调/CLI 退出码）。

2026-10-22 接线批（L3）新增：
`test_tiandao_effects_reader.py`（7 例：缺失≠False、白名单、错误结构不冒充裁决、只读）、
`test_tiandao_effects_econ.py`（25 例：商贾乘子钳位、田产/赈济成对转移、逃亡放大、无裁决逐字节等价）、
`test_tiandao_effects_granary.py`（19 例：漕运途耗/脚钱/和籴三腿守恒、募兵人守恒、
宋侧逃散放大 + `_flee_after_verdict` 定点、中性逐字节、兵额派生顺序）。
🔴 接线口径与上限见 `_dev_tools/game-docs/specs/cross-cutting/tiandao-engine/tasks.md` §5c。
