# 天道裁决引擎（TianDao Engine）· 任务与状态

> 名称：`tiandao-engine` ｜ 域：`cross-cutting`（横跨经济/官制/政令/AI 叙事）
> 落地批次：`M324` 之后的 DSH 修复批（2026-10-17）
> 本文**只记当前事实与纪律**，不复制设计正文。设计稿仍在仓库外
> （`~/.gemini/antigravity/brain/.../tiandao_engine_and_llm_coupling_design.md`），
> 引用时以本文与代码为准。

## 1. 定位

「天道」= **纯算、确定性、零 Token** 的本地裁决层；大模型只负责叙事执笔。
两者分工的硬边界：

| 谁 | 做什么 | 不做什么 |
|---|---|---|
| `core/ai/tiandao_engine.py` | gate / choose / score / dice 四类决断（纯函数） | 不写 state、不碰账本、不掷骰（除 `dice` 的显式种子） |
| `core/ai/tiandao_facade.py` | 六大业务域的裁决入口 + 三条 AI 管道的事实提炼 | 不落地物理效果（交业务域结算） |
| 大模型（`game/ai/`） | 奏折、召对、月报、市井风闻的文字 | **不出数值**；一切数值由内核算 |

## 2. 模块与接线状态（逐项，含"未接线"）

| 模块 / 入口 | 状态 | 生产调用方 |
|---|---|---|
| `core/ai/tiandao_engine.py`（gate/choose/score/dice） | ✅ 已落地 | 经 facade；`dice` 生产调用方 = `core/decree_gates.py:113`、`:288`（圣旨执行成败的确定性掷点，`seed=SHA1(did|matter|turn|period|actor)`）。🔴 旧版本此处写「尚无生产调用方」是**文档漂移**，2026-10-21 按实测更正 |
| `core/ai/tiandao_facade.py` · `labor_service_policy` | ✅ 已接线 | `core/domains/economy/procurement.py:113`（`EmbeddedDecisionFacade.labor_service_policy(state_ctx)`；D-9 行号漂移已于 2026-10-22 复核更正：原写 `:107` 实为构造 `state_ctx` 段） |
| `core/ai/tiandao_facade.py` · `circuit_decree_compliance` | ✅ 已接线 | `core/decree_effect.py`（**合成层**，不改 `clerks_mult` 读数） |
| `core/ai/tiandao_facade.py` · `appraisal_score` | ✅ 已接线 | `core/domains/administration/official_appraisal.py`（分档边界仍由考课法守） |
| `core/ai/tiandao_facade.py` · `dynamic_treasury_crisis_line` | ✅ 已接线 | `core/settlement_finance.py`（读数 `statistics["last_monthly_expense"]` 同批补写入方） |
| `core/ai/tiandao_facade.py` · `scan_memorial_seeds` | ✅ 已接线 | `core/commands.py::_memorial_posture` → `generate_memorials` 入参 |
| `core/ai/tiandao_facade.py` · `derive_dialogue_stance` | ✅ 已接线 | `core/commands.py::audience_dialogue` → `dialogue` 的 `state_summary` |
| `core/ai/tiandao_facade.py` · `summarize_monthly_omen` | ✅ 已接线 | `core/commands.py::monthly_report_args` → `monthly_report` 入参 |
| `core/ai/tiandao_facade.py` · `observe_monthly`（**11** 方法只读观察） | 🟡 **只读已接线（2026-10-21；L0 补入第 11 项 `labor_service_policy`）** | `core/settlement.py::run_monthly_settlement` 每月调用；结果挂 `state._tiandao_observe`（诊断、不入存档），**不改数值**；同时写 `state.decision_log`（落盘见 §6） |
| `granary_corruption_check` | ✅ **数值已接线（2026-10-21，Jev B 0.492）** | `settlement_granary._granary_corruption_factor`：False ⇒ 雀鼠耗本色损耗 **×0.5**（不归零；无记录回落 1.0）；钱侧贪腐不动 |
| `reform_compliance_gate` | ✅ **数值已接线（2026-10-21，Jev A 0.464）** | `settlement_decree._reform_compliance_factor`：False ⇒ `finance_rates` 财政改革幅度 **×0.5**（只此一处；无记录回落 1.0） |
| `changping_intervene_gate` | ✅ **数值已接线（2026-10-21，Jev B 0.365 vs A 0.365 近平手，按 B）** | `settlement_granary._changping_sell_allowed`：False ⇒ 本月高价**平粜不卖**（只影响卖粮，不影响平籴/价格公式；无记录回落 True） |
| `tax_collection_stance` | ✅ **数值已接线（2026-10-21，Jev C 0.455）** | `settlement_finance._tax_stance_factor`：strict ⇒ 田赋应征额 ×1.03；lenient ⇒ ×0.97；moderate/无记录 ⇒ 1.0（只此一处） |
| `should_waive_ancient_arrears` | ✅ **数值已接线（2026-10-21，Jev C 0.339 近平手自证）** | `settlement_finance._arrears_waiver_active`：True ⇒ 本月暂停欠税追缴 + 核销 10% 欠税存量；False/无记录 ⇒ 现状；无年龄字段，当前视全部欠税为陈欠（已知局限） |
| `tax_collection_stance` / `should_waive_ancient_arrears` / `merchant_trade_or_hoard` / `changping_intervene_gate` / `canal_reroute_choice` / `granary_corruption_check` / `farmer_destitution_path` / `gentry_charity_vs_annex` / `reform_compliance_gate` / `recruit_refugees_to_soldiers_gate` / `labor_service_policy` | 🟡 **只读接线（2026-10-21，Jev A 0.799；L0 起 11 项）** | `TianDaoFacade.observe_monthly` 每月记录裁决；**数值效果仍未接线**（需逐项定档位→数值映射、上限与 A/B；granary corruption 直接置零须单独裁定）。⚠️ 其中 5 项**已有**数值消费方（见上表逐行），未接线的只是余下 5 项：商贾 / 漕运 / 小农 / 士绅 / 募流民 |
| `embedded_jev.py` / `decision_facade.py` | ✅ 兼容薄桩 | 别名 `EmbeddedJevEngine` / `EmbeddedDecisionFacade` → 天道；**首参同时接受 `state_context=`** |

> 纪律：**"有实现 + 有单测"不等于"已生效"**（`specs/README.md` 状态判定）。
> 🔴 **2026-10-22 起该条已不适用**：11 个门面方法**全部**有数值消费方（L3 批接完最后 5 项，
> 见 §5c）。历史快照：2026-10-21 之前只有 5 个（tax_stance / waive_arrears / changping_open /
> granary_corruption / reform_compliance）有消费方。

## 3. 契约（改这些等于改契约）

| 契约 | 值 / 规则 |
|---|---|
| `provider` 字段 | `"tiandao_local"`（2026-10-17 由 `embedded_local` 改名；Jev p=0.994；全库无生产消费方） |
| `gate` 返回 | `{verdict, probability, provider, basis_undefined, objective, defined}`；**无依据时 `verdict=False`、`probability=None`、`defined=False`** |
| `choose` 返回 | `{verdict, probabilities, provider, objective, defined}`；概率**严格归一为 1.0**（舍入残差回填最大项） |
| `score` 返回 | `{level, score, provider, basis_undefined, defined}`；**`levels` 必须「差→好」排列**，两分支都归一为"越好分越高" |
| `dice` | `dice(seed: int, entropy=0.05) -> float ∈ [-entropy, +entropy]`；splitmix64，纯整数运算跨进程一致 |
| `objective` | 显式枚举优先；未给时按旧 `condition` 子串 / `criteria` 键名回退（仅向后兼容，新代码必须显式传） |
| 缺失值 | 一律 `None` + `defined=False`；`0` 是合法值，**禁止 `x or default`** |
| 吏治通道 | `clerks_mult` = **吏胥折扣本体**；知州遵从度单列 `clerks_compliance`，只在 `effect_mult` 合成层参与（三条通道不增） |

## 4. 本批（2026-10-17）修复的 P0（均已加断言）

| # | 缺陷（修复前实测） | 修复 | 回归用例 |
|---|---|---|---|
| 1 | 薄桩只换类名不换签名 ⇒ `clerk_decision`/`merchant_decision` 用 `state_context=` 调用 **TypeError**，决策静默退化为常量 | 引擎 `_bind_context` 兼容旧关键字 | `test_tiandao_engine_core::test_legacy_keyword_signature_still_works` |
| 2 | `gate(None)` → **True**（无依据撞阈值放行） | 无依据即 `verdict=False`、`probability=None` | `…::test_gate_without_basis_never_passes` |
| 3 | 贪墨闸门 max 概率 0.4455 < 阈值 ⇒ **数学上永不通过**；`integrity=0.0` 被 `or 0.6` 吞 ⇒ 非单调 | 改 `0.20+0.60×(1−integrity)`（有巡按 ×0.2）+ `is None` 判缺失 | `…::test_corruption_gate_reachable_and_monotonic` |
| 4 | 国祚声望 `0` 被 `or 50.0` 吞 | 同上 | `…::test_zero_prestige_is_not_swallowed` |
| 5 | `score` 两分支单调方向相反（灾情 1.0 反评"上考"） | 统一为「差→好」 | `…::test_score_disaster_branch_agrees_with_direction` |
| 6 | Softmax 舍入残差 ⇒ 概率和 0.9999（"严格归一"是假的） | 残差回填最大项 | `…::test_softmax_sums_to_one_exactly` |
| 7 | 三个抉择无引擎分支 ⇒ **恒定档位**（恒典田/恒兼并/恒等疏浚）；`defiant` 永不可达 | 各补分支 | `…::test_{farmer,gentry,canal}_path_is_not_constant`、`…::test_defiant_compliance_reachable` |
| 8 | 考课接入后**下考不可达**（民怨 70/80/100 全判中考）⇒ 罢黜/祠禄失效 | 民怨>60 或清廉<0.35 一票下考；上考需民怨<20 且综合分≥0.72 | `test_appraisal_and_demagic::test_appraisal_demotes_when_unrest_high` |
| 9 | 下考分支调用的 `_officialdom.weed_out_officials` **API 不存在**（正确名 `remove_officials`，且语义不同）⇒ 一旦下考触发就 AttributeError | 改走本模块 `assign_sinecure_retirement`（在岗→祠禄，走 POP 子桥） | 同上（`sinecure_assigned > 0`） |
| 10 | `dynamic_treasury_crisis_line` 读的 `last_monthly_expense` **全库零写入方** ⇒ 恒 5,000,000，"去魔数"空转 | `_settle_finance` 落真实月度支出 + `crisis_line_source` 标注来源 | `test_appraisal_and_demagic::test_monthly_expense_reading_is_actually_written` |
| 11 | 三条 AI 管道函数**零生产调用**（写了没接） | 分别接进奏折 / 召对 / 月报入参 | `test_ai_narrative_pipelines.py`（5 条） |
| 12 | 新验收用例放在 `sz/tests/`（不在官方 pytest 路径、无 conftest）⇒ 默认跑不起来 | 迁入 `_dev_tools/game-dev/tests/` | 全量命令可见 |

## 4.1 本批（2026-10-17 M326）审计缺陷整改与守恒加固

依据《antigravity 批次全量审计（M299–M325）》（`review_antigravity_M298-M325_2026-10-17.md`）与 Jev 裁定（`JEV-DEC-审计整改修复顺序与首批守恒缺陷-2026-10-17`、`JEV-DEC-物权流转与对价扣源职责归属-2026-10-17`、`JEV-DEC-三大悬空模块处置与任务状态降级-2026-10-17`）：

| # | 缺陷 | 修复与机制 | 验证断言 / 用例 |
|---|---|---|---|
| **A-6** | `procurement.py` 双重扣款（Δlocal=−16,000 / paid_total=10,000）且商人物料未扣（物料凭空） | Jev 裁定 A 方案：`transfer_goods_ownership` 作为单点统一结算对价与真扣治所 POP 货源（`pop_goods_sub`）；杜绝重复划款；实付款与报表严格一致 | `test_local_expenditure_order`（2条转绿）<br>`test_land_tax_split_p1`（1条转绿）<br>`test_procurement_order_conservation_laws`（Δlocal+Δ商+Δ工==0, Δ商人物料+Δ官仓==0） |
| **A-4** | 皇威无上限后交子上限 `_jiaozi_ceiling` 随 raw prestige 线性放大（储备200万时 350→1600万，800→3400万） | 准备金率采用有界截断皇威 `min(100, prestige)`，倍率夹紧上限 3.0 倍，单调不降且杜绝货币失控 | `test_audit_critical_fixes::test_a4_jiaozi_ceiling_bounded_by_prestige` |
| **A-7** | 欠饷逃兵 `add_troops(-desert_count)` 扣除兵额后人丁凭空消失（ΣPOP 变化 0） | 逃兵人丁调用 `_return_men(state, u.station, desert_count)` 严格回流本路农 POP 或流民池 | `test_audit_critical_fixes::test_a7_military_desertion_pop_conservation` |
| **A-8** | 科举殿试唱名直写 `state.prestige += 5` 绕过 `change_prestige` 单点 | 改用 `state.change_prestige(5, reason="殿试唱名", is_major=True)`，自动纳入月度上限与 `_prestige_history` 台账 | `test_audit_critical_fixes::test_a8_palace_exam_prestige_through_single_point` |
| **P1** | `logistics_coupler` 船队为 0 时 `0 or 50` 吞 0 反得 50 条；Step 0 破产判定与天道动态线双判据脱节；`corruption=0` 被吞成 0.3 | 修复 None 判断；Step 0 统一改用 `TianDaoFacade.dynamic_treasury_crisis_line`；清廉度判 `is not None` | 全量回归通过 |
| **悬空** | A-1 度量衡、A-2 生产方式 PM、A-3 科举与三年磨勘未接入 `run_monthly_settlement` 主管线 | 依据 Jev 裁定 B 案（p=0.9974），如实将任务卡 M324 / M317 / M318 / M300 降级为 `in_progress` 并注明「模块就绪、待接生产管线」，避免后续误判已生效 | `handover.py check` 0 报错 |

## 5. 未闭合项（下一批）

1. 待接线模块专项推进：M324 度量衡效果与 format_quantity 读数接线、M317/M318 PM 生产方式接作坊管线、M300 科举三级唱名与三年磨勘考课节律接线；
2. 上表 10 个门面方法**已只读接线**（`observe_monthly`，2026-10-21）；下一步逐项接**数值效果**并补真实链路用例
   （档位→数值映射、上限、A/B；granary corruption 直接置零需单独裁定）；
3. 奏折 / 月报契约仍是 `posture` 字符串注入事实签，**没有结构化参数**；若要"数值 100% 可核对"，
   需给 `generate_memorials` / `monthly_report` 增 `facts` 参数并复用 `narrative_guard._build_numeric_ranges`；
4. ~~`crop_shadow` 式的"只读未消费"风险：`dice` 目前无生产调用方，先用或先删，别悬空~~
   —— **已核实为文档漂移**（2026-10-21）：`dice` 有 2 个生产调用方，见 §2 首行；
5. 设计稿里的「中枢会签封驳 / 地方 21 路遵从 / 去魔数清单 / 七年档考课」四块**未实现**，
   且与既有实现重叠（`council_review`、`official_appraisal`、`CANAL_LOSS_*`）需先定归属再动。

## 5b. 2026-10-21 加强批（L0 / L1 / L2）—— 已落地

> 触发：用户问「内置天道可以特化加强吗」。审计（三线实测）结论：引擎本体健康，
> 短板在**输入供给**与**契约统一**，不在模型能力。Jev：A「先修读数键与统一 facts 契约」**0.969**、
> D「训练/微调模型」**0.0146**、命题「主要矛盾在输入侧」**p=0.979**。

| 层 | 落地内容 | 关键文件 |
|---|---|---|
| **L0 接线** | `build_state_context` 改为 facts 契约唯一生产入口：`disaster` 由恒 `None` → `state.disaster_severity/5`；`integrity` 无读数→`None`（原回落 1.0）；`stock` 太仓→常平仓；新增 `block_rate`/`local_treasury`/`faction`/`refugees_max_route`/`monthly_expense`；`observe_monthly` 10→11 项 | `core/ai/tiandao_facts.py`（新）、`tiandao_facade.py` |
| **L1 参数外置** | 132 个内联常数 → `content/data_tiandao.py` **93 个带口径参数**（唯一入口 `PARAMS`，11 处 `# 待校准`）；引擎体内只剩 `0/1` 哨兵与签名默认值 | `content/data_tiandao.py`（新）、`tiandao_engine.py` |
| **L1 缺陷修复** | ①`score` 运算符优先级（`disaster=None` 时 unrest 被丢弃，`score({unrest:160})`=上考1.0）②`granary_corruption` 无 `integrity` 时不再判贪墨 ③`labor_policy` 绝对 5000 贯 → 可支撑月数≥3（无月支读数退路库见底线 200,000，Jev A 0.742）④未知 objective fail-closed | `tiandao_engine.py` |
| **L1 契约统一** | `clerk_decision`/`merchant_decision` 改用 canonical facts；**消除吏治+灾情重复计入**（曾 0.458→0.57）；灾级 1~5 归一化（曾灾级 1 与 5 等价）；常平"重仓"阈值 50,000（恒真）→ 400,000 | `core/ai/clerk_decision.py`、`merchant_decision.py` |
| **L2 日志落盘** | `decision_log` 随档持久化（`schema_version` v4→**v5**，旧档缺键⇒`[]`，脏档⇒`[]`+warning）；记录新增 `facts_digest` | `core/save_load.py` |
| **L2 回测器** | 离线 `brier` / `reliability_bins`(ECE) / `hit_rate` / `monotonic_check` + CLI；无标签时**不给** Brier/命中率 | `core/ai/tiandao_backtest.py`（新） |

**顺带修复**：`save_load.py:549` 与 `application/load_game.py` 各一处「错误分支引用未定义 logger」的
潜伏 `NameError`（`_slog` / `_dlog`）——正常路径不触发，但日历同步或任一下沉迁移失败就会**打断读档**。

**golden 基线**：按 Jev A **0.997** 重建，影响面仅 2 个货币数字
（`treasury` +420 / `imperial_treasury` −16,141，20/20 路与 finance 全同），
变更说明见 `_dev_tools/game-dev/tests/testdata/p0_golden_12m.CHANGELOG.md`。

**仍未做（下一批）**：`SEED_*` 四阈值按地方级量纲重标（`50000` vs 地方府库 27–195 万）；
标签数据源（回测需要上游产出 ground truth）；`clerk_decision` 的 `diligence` 与
`farmer_path` 的 `debt` 仍无生产者（契约登记为 `None`，不臆造）。

## 5c. 2026-10-22 接线批（L3）—— 5 个门面首次影响玩法

> 触发：`继续`。Jev `choose`：**A=接余 5 项门面的数值效果 0.7767** / B=重标 SEED_* 0.1490 /
> C=标签数据源 0.0356 / D=外部 Jev 特化 0.0387。

**共享读取点**：新增 `core/ai/tiandao_effects.py`（`observe_verdict` / `observe_bool`）。
**缺失 ⇒ `None` ⇒ 调用方中性**；`False` 是真裁决、与缺失严格区分；白名单外的值一律 `None`。
存在的理由：多个消费方各抄一份读取逻辑会撞「跨文件相同实现」守卫。

| 裁决 | 消费方（文件:函数） | 效果与上限 | 守恒 |
|---|---|---|---|
| `merchant_trade_or_hoard` | `settlement_econ._settle_civilian_hoard` | 囤抛力度 ×1.20/×0.90，钳位 0.85–1.25（`MERCHANT_TILT_BOUNDS`） | 买卖成对划转，POP wealth 总额不变 |
| `gentry_charity_vs_annex` | `settlement_econ._settle_tiandao_land_relief` | 兼并 0.3%/月（`LAND_CONCENTRATION_CAP`）或义庄赈济 2%/月（`GENTRY_RELIEF_CAP`） | 自耕田→士绅田成对；士绅囤粮→农户成对（走桥） |
| `farmer_destitution_path` | 同上（典田）+ `settlement_granary` 饥荒段（逃亡） | 典田与兼并**共用一条通道与一个月上限**（双命中不叠加）；`flee_refugee` ⇒ 逃散 ×`FLEE_VERDICT_MULT`(1.5)，仍受 5 万人/路上限 | 农 POP size 减 ↔ 流民增，人只在池间移动 |
| `canal_reroute_choice` | `settlement_granary` 漕运段 | 陆路：途耗 ×0.80 + `起运石//100` 贯脚钱（国库→商人 POP）；和籴：途耗 ×0.90 + 3% 补粮（地方府库出钱→民间售粮 POP，粮入太仓），三重封顶「宁少买不造粮」 | 脚钱/粮款均有对手方账户；民间粮 −n ↔ 太仓 +n |
| `recruit_refugees_to_soldiers_gate` | `settlement_granary._recruit_refugees_as_xiangjun` | **必须 `is True`**；2%/路/月、上限 2,000 人；无实体军的路**不扣人、不造单位** | 流民 −n ↔ `ArmyUnit.troops` +n；兵 POP `size` 由 finance 步按 Σtroops 派生（当月对齐、不双计） |

**实测定点（本机）**：中性档 ≡ 无记录 **逐字节相同**（两侧各自 sha256）；6 个月真结算
`M_ALL` 残差本批净贡献约 −1,245（残差主体是既有问题，两条跑法都在）；兵额逐路
`兵.size == Σtroops` 0 违例；人口只在池间移动。

🔴 **别拿 `self_farm+gentry+official+imperial == land` 当验收断言**：`land` 与 `hidden_land`
各自演化，该式在本仓库初始 0/20、6 个月后中性档与真实档**都** 20/20 违例（既有事实）。
正确断言是「转移成对：`Δself == −Δgentry`」。

**golden**：按同一裁定（沿用 A 0.997，属同一类行为变更）重建；概率加权版影响面
`army_troops` +2,980 / `granary` +27,703 / `imperial_treasury` +53,365 / `treasury` −167，
**finance 与 20 路逐路账全同**；变更说明见 `p0_golden_12m.CHANGELOG.md` 第三/四条。

**已知边界**：① 8/20 路无实体军 ⇒ 该路流民不募（要覆盖需建军，属兵制内容）；
② 重灾时逃散已顶 5 万上限 ⇒ 逃亡档只在中度饥荒（缺粮 < 33,333/地）可见（上限是防爆版，不被档位突破）；
③ `statistics["total_expenditure"]` 现混入地方府库支出，已用三个子键 `canal_*` 区分；
④ 三项代价**不计入** `last_monthly_expense`（不改财政刚性口径，属已知读数边界）。

## 5d. 2026-10-22 概率加权（用户裁定：「这不都固定数？权重呢？」）

> 用户当场指出：5.2/5c 的接线只把裁决当**枚举开关**，再查固定倍率表——引擎算出的概率
> （0.674 / 0.428…）与 choose 的整条分布被丢掉了，等于天道只贡献了一个词。
> Jev 复核：命题「choose 类应取**概率加权期望/混合**而非 argmax 后查表」**p=0.995 成立**。

**做法**：

| 环节 | 改法 |
|---|---|
| 观测副本 | `observe_monthly` 新增 `strengths`（gate 的 p）与 `distributions`（choose 的 `{option: p}`）；按 `tiandao_decision.SPECS` 唯一 criteria 重算取概率（~20µs/项） |
| 强度 | gate：**超阈归一** `(p−thr)/(1−thr)`（p=0.51→0.02、0.99→0.98）——让"刚过线"与"高度确定"幅度不同 |
| choose | **概率加权**：商贾 `net=p(hoard)−p(local_sell)` 连续调力度；田产集中取两裁决**并集** `1−(1−p₁)(1−p₂)`；漕运取 `Σ p_o×mult_o` 期望；脚钱/补粮按对应选项概率缩放 |
| 天意机变 | `jitter(回合,目标,地点)` ∈ [1−e, 1+e]（splitmix64 派生，**同种子可复现**，不是真随机）；e 按域：商贾/田产/逃散 0.10、漕运 0.05、募兵 0.12 |
| 缺失 | 强度/分布缺失 ⇒ 中性（乘子 1.0 / 不动作），与「无观测副本」**逐字节一致**（实测 sha256） |

**踩坑留档**：观测副本里 `decisions` 按**门面方法名**存（`farmer_destitution_path`），
`strengths`/`distributions` 按 **objective id** 存（`farmer_path`）。消费方只按一种写法读就会
**静默读空、效果永不生效**（实测：`observe_strength("recruit_refugees_to_soldiers_gate")`
返回 None ⇒ 全月零募兵，`army_troops` 回到接线前值）。现 `_name_keys()` 双向解析，
两侧写法都能读——**新增消费方务必用 `tiandao_effects` 的读取函数，不要自己 `dict.get`**。

## 6. 复跑

```powershell
$py = "D:\codebuddy\.audit-venv\Scripts\python.exe"
$env:PYTHONPATH=""; $env:CODEBUDDY_SAFE_DELETE_ENABLED="0"; cd D:\codebuddy\sz
& $py -m pytest _dev_tools/game-dev/tests -q -p no:cacheprovider          # 全量
& $py -m pytest _dev_tools/game-dev/tests/test_tiandao_engine_core.py -q  # 引擎契约
& $py -m pytest _dev_tools/game-dev/tests/test_tiandao_facade_wiring.py -q
& $py -m pytest _dev_tools/game-dev/tests/test_ai_narrative_pipelines.py -q
```

## 5e. 2026-10-22 民怨动力学 + 奏报阈值重标（Jev B 0.757）

> 起因：本要按 Jev B 重标 `SEED_*` 四阈值，实测发现**根因不在阈值**——
> 民怨只会被「治安支出」单向抵减（该项按**军费份额**算）⇒ 有实体军的 12 地一年内归零，
> **无实体军的 8 地永久冻结在初始值**（实测利州路/广南西路 24 个月恒 24.0，相关性零例外）。
> 于是内容里 `situation_seeds`(>=30/85)、`local_agent_decisions`(>=30/45/60/85)、
> `settlement_econ:274`(>=20) 的档位**永不可达**。Jev：B=补上行动力让 0–100 可用 **0.757**
> （A 只重标 0.143 / C 只解耦治安支出 0.100）。

**民怨动力学（新）**：`settlement_econ._unrest_pressure_target` + `_settle_region_deepen` 第 6 项——
民怨每月向「压力目标」缓动 10%（与本函数 `fiscal`/`public_support` 同型，非增量累加）：
粮价溢价 ×20 / 灾情级 ×8 / 流民占比(满 10%)×25 / 治理不足 ×20，目标与结果都钳 [0,100]。
权重标 `# 待校准`（无历史数据可标定）。

**实测**：太平 24 月民怨中位 15→4.1；危机（灾5+粮价×3）12 月升到 26→58，
30/45 档**首次可达**；60/85 需持续 2 年以上极端灾情（目标 90 时 24 月到 83、36 月到 87）。
**8 地全部解冻**（新增测试 `test_frozen_routes_are_unfrozen` 逐地断言）。

**奏报阈值重标**：绝对贯数/人数改为**相对锚**（缺失读数则该地不计）：
- 财政签：府库不足 **0.1 月本地月税**（≈三日支应），见底深度定序
  —— 原「民怨>40 **且** 府库<5 万」实测两条件从不同时成立（太平 24 月里 19 月府库见底、
  其间民怨最高 11.3；危机 12 月府库一次不见底）⇒ 结构性死签；改判据经 Jev **p=0.994**；
- 军事签：流民 **> 本地人口 0.4%**（原绝对 3,000 人）；
- 政务签：民怨 **> 50**（0–100 刻度，现可达）；太平年景仍走 routine。

**golden**：重建（沿用同类裁定）；概率加权→民怨动力学的影响面仅
`army_troops −64` / `granary +72` / `imperial_treasury +8` / `treasury +9`，finance 与 20 路全同。
🔴 这反过来说明**民怨几乎无经济下游消费者**（"档位可达"的价值在局势/推演分支，不在账本）。

**验收**：新增 `test_unrest_dynamics.py`（14 例：压力目标单调/缺失不动作/太平回落/8 地解冻/
危机达档/缓动不跳变/确定性/四类签可达性与缺失不计）。全量 4412 tests / 0 failed / 0 errors。

## 5f. 2026-10-22 回测标签数据源（Jev B 0.684）

> 缺口：`tiandao_backtest` 能算 Brier/ECE/命中率，但仓库**没有真值**，只能报分布；
> 没有它，`data_tiandao.py` 与 `tiandao_effects` 那些参数（含 9 个压力/扰子参数）无从验证。

**新增** `core/ai/tiandao_labels.py`（纯逻辑）＋ `_dev_tools/game-dev/tools/tiandao_labels.py`
（结算驱动 + CLI；**故意不放在 core/ai**——它要驱动月结算/读档，而 `core/ai` 不得反向依赖
`core.settlement`/`core.commands`/`application`，架构守卫会拦，且守卫要求「改代码而不是加白名单」）：

1. 月初取**自然**观测副本 `R`（不重观测）；
2. 对某 objective 的每个候选分支：`deepcopy(月初state)`，只把 `R` 里该 objective 强制成该分支
   （choose ⇒ `distributions[obj]={o:1.0}`；gate ⇒ `decisions[method]=bool` + `strengths[obj]=1.0/0.0`），
   **冻结观测**（`observe_monthly` 置空操作，否则月结 Step 0 会覆盖注入值），同种子跑一个月；
3. 度量向量 `(国库, Σ地方府库, 太仓, −Σ民怨, −Σ流民)`（**越大越好**，全为既有读数，缺一项则弃该试验）；
4. **只有唯一帕累托支配者**（全面不劣且至少一项更优）才打标签；并列/互有胜负 **跳过**
   —— 不设权重、不臆造真值。

**实测（本机）**：1 个月 4 标 / 7 跳（11.7s）；6 个月 22 标 / 44 跳，端到端回测
`标签覆盖率 0.3333、重复 0、未匹配 0`，并首次给出可解释数字：
`farmer_path` Brier 0.1425 命中 2/2、`changping_open` Brier 0.5147 命中 0/2（该 gate 明显过自信，
ECE 0.7147）。⚠️ 这是**代理真值**（"事后哪种做法让国计民生更好"），能度量校准≠证明因果。

**踩坑留档**：标签 `turn` 必须取观测副本的 `turn`，不能用 `state.turn or (i+1)`
——首月 `state.turn == 0` 被 falsy 判成 1，导致与 `decision_log` 错位、并产生重复
`(objective, turn)` 标签（实测覆盖率从 0.33 掉到 0.27 且 `duplicate_labels=4`）。

**验收**：新增 `test_tiandao_labels.py`（15 例：帕累托判定/缺读数不计/只改目标 objective/
turn 对齐/确定性/观测还原/CLI 退出码/与回测器对接）。

**下一步（本档未做）**：拿这份 Brier/ECE 回标 `UNREST_*` 与 `MERCHANT_TILT_SPAN` 等参数；
标签覆盖率要靠"更细的度量维度"或"多步视野（t+3 月）"提升。

## 5g. 2026-10-22 外部审查处置批（B1 阻断 + 9 项建议）

> 来源：`outputs/songzuo-review-20261022/宋祚变更审查报告_2026-10-22.md`（只审不改的独立审查）。
> 处置：**全部阻断与高/中建议当轮修复并复验**，逐条状态见该报告整理版「问题清单」。

### 5g-1 B1（阻断）：概率加权只落地 5/11 个消费点

审查指出契约第 14 条明令禁止「argmax 档位→固定倍率表」，而**此前已接线的 5 个消费点**
仍是裁决词查表（新接的 5 项才是概率版）。这是真漏洞——我当时只改了新接的，漏了旧的。

| 消费点 | 改前 | 改后 |
|---|---|---|
| `settlement_finance._tax_stance_factor` | strict ×1.03 / lenient ×0.97 | `1 + 0.03×(p_strict−p_lenient)×jitter` |
| `settlement_finance._arrears_waiver_active`（→`_arrears_waiver_ratio`） | 布尔全免 | `ratio=strength∈[0,1]`：核销=存量×10%×ratio、追缴×(1−ratio) |
| `settlement_decree._reform_compliance_factor` | False ⇒ ×0.5 | `0.5 + 0.5×strength`（p≥阈值时 **≡ p**） |
| `settlement_granary._changping_sell_allowed`（→`_changping_sell_ratio`） | 布尔开关 | 平粜量 = 既有公式 × `strength` |
| `settlement_granary._granary_corruption_factor` | False ⇒ ×0.5 | `1 − (1−strength)×0.5` |

- **旧格式兼容**：有 `decisions` 但无 `strengths`（旧观测副本/手写注入）时**回退旧二值**
  （Jev A **p=0.993**）——否则缺概率的注入会静默失去效果；生产 `observe_monthly` 两条同批写，实机无此形态。
- 三个旧审计测试（`test_audit_20261021_{tax_stance,arrears_waiver,reform_gate}.py`）
  原本钉的就是被判定违规的旧契约，已**按新契约重写**（保留"消费者真的咬住"的原意）。

### 5g-2 其余建议（逐项）

| 编号 | 内容 | 处置 |
|---|---|---|
| F1 | 商贾 net=0 时乘子仍 ≠1.0 且日志误报「居奇囤积」 | **已修**：`1 + SPAN×net×jitter`（扰子乘增量）+ 日志条件改 `net > 0` |
| F2 | 漕运 `wait_dredge` 期望 1.0 仍吃扰子（实测 1.0218） | **已修**：期望==1.0 直接返回 1.0（容差 1e-9） |
| F3/S1 | 观测失败残留上月副本（跨月消费旧裁决） | **已修**：`observe_monthly` 进入先置 None，`build_state_context` 包 try，失败⇒中性 |
| F4 | 两侧逃散公式不一致（宋侧 p=0.1 时 26% 回合反向） | **已修**：两侧统一 `1+(MULT−1)×p×jit`；`FLEE_JITTER` 收敛到 `tiandao_effects` 单点 |
| S2 | 国库直写绕过 `change_treasury` 单点 | **已修**：走单点取实际生效 Δ，未到账部分退回 |
| S3 | `grain_add(...) is None` 死分支；计划段读 raw `.grain` | **已修**：删死分支、计划段改 `grain_get` |
| D-1/E4 | 阈值三源（THRESHOLDS / 门面默认 / 消费方硬编码 0.5） | **已修**：`tiandao_effects.objective_threshold()` + 门面 `_gate_threshold()` 均读 `THRESHOLDS` |
| D-2/E5 | `appraisal`/`decree_compliance` 登记但不进日志 | **已处置**：`NON_OBSERVED_OBJECTIVES` 显式声明理由 + 测试断言 `SPECS == 观测 ∪ 已声明` |
| D-3/E6 | 回测单调 O(n²) + 截断契约未实现 + 空 violations | **已修**：分组判定 O(n log n)；任一侧超 `MAX_VIOLATIONS` 即 `truncated`；非单调必给 violations |
| F5 | 缺项分布被当 0 概率 | **记档（低）**：`observe_mix` 不补 0，但消费方 `.get(opt,0)` 仍可能把缺项读成 0；生产分布恒定完整，当前不可达 |
| F6 | `jitter` 默认 entropy=0.12 是跨域陷阱 | **已加固**：守卫测试扫描全库，`jitter` 调用必须显式传 entropy |
| F7 | 效果层常数无锁值 | **已加固**：`test_effect_constants_are_locked` 逐值断言（改数即变红） |
| F8 | 和籴计划段读数口径 | **已修**（同 S3） |

### 5g-3 golden

本批影响面（对上一版基线）：`imperial_treasury −824` / `treasury +57`，**finance 与 20 路全同**
——因为多数概率落在阈值下方与改前擦肩（蠲免 p=0.464<0.5 ⇒ 0、平粜 p≈0.2–0.35 ⇒ 0、
贪墨 p=0.428<0.5 ⇒ ×0.5、田赋 net≈−0.029 ⇒ ×0.9991）。基线已重建并留 CHANGELOG。

## 5h. 2026-10-22 结算幂等守卫（审查遗留的唯一硬项）

> 审查方原话：「`econ_probe.py` 的连续两次 `run_monthly_settlement` 实际是推进两个月，
> **不能作为同回合重试幂等证据**」——即「结算成功但响应丢失 → 重发」会双推一个月。
> Jev `choose`：**B=按 `expect_turn` 判重 0.514** / A=幂等令牌 0.244 / C=只钉已知行为 0.242
> —— **三近手**，按纪律自己再论证后择 B（理由：`settlement_log` 本就按回合索引，重放无需新状态，
> 且令牌同样要前端配合，却多一层不透明状态）。

**实现**：`run_monthly_settlement(state, seed_offset=0, expect_turn=None)` +
`commands.settle_local(state, expect_turn=None)`。语义表见机制文档 §1.1。

**关键实现点**：
- `expect_turn=None` ⇒ 与改前逐字节一致（老调用方零改动；同时用测试钉住"无参数仍会推进"的旧行为）；
- 重放返回 `list(settlement_log[turn])` **副本**——顺带修掉一个既有别名：
  改前 `state.settlement_log.append(log)` 与 `return log` 是同一对象，调用方就地修改会污染存档历史；
- `expect_turn > state.turn` 拒绝推进（跳过一月比多推更危险）。

**踩坑留档（新）**：`run_monthly_settlement` 被 `@_isolated_rng` 装饰，装饰器用 `functools.wraps`
⇒ `inspect.signature` 跟随 `__wrapped__` **显示新签名**，但 wrapper 只转固定参数，
运行时抛 `unexpected keyword argument: expect_turn`，表现为「签名看着对、调用却报错」，
极易误判为字节码缓存。**给被装饰函数加形参后，必须确认装饰器转发 kwargs。**

**未做（如实标注）**：前端/HTTP 层未传 `expect_turn` ⇒ 守卫**待启用**，不能宣称"已防住重发"；
接线需要在结算请求里带上 UI 正在展示的回合（属前后端契约变更）。

**验收**：新增 `test_settle_idempotency.py`（9 例：旧行为钉住/重试不推进且日志一致/
返回值是副本/连续回合正常推进/超前拒绝/过期无日志拒绝/垃圾值退化/装饰器转发 kwargs）。
