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
| `core/ai/tiandao_engine.py`（gate/choose/score/dice） | ✅ 已落地 | 经 facade；`dice` **尚无生产调用方**（仅契约测试） |
| `core/ai/tiandao_facade.py` · `labor_service_policy` | ✅ 已接线 | `core/domains/economy/procurement.py:107` |
| `core/ai/tiandao_facade.py` · `circuit_decree_compliance` | ✅ 已接线 | `core/decree_effect.py`（**合成层**，不改 `clerks_mult` 读数） |
| `core/ai/tiandao_facade.py` · `appraisal_score` | ✅ 已接线 | `core/domains/administration/official_appraisal.py`（分档边界仍由考课法守） |
| `core/ai/tiandao_facade.py` · `dynamic_treasury_crisis_line` | ✅ 已接线 | `core/settlement_finance.py`（读数 `statistics["last_monthly_expense"]` 同批补写入方） |
| `core/ai/tiandao_facade.py` · `scan_memorial_seeds` | ✅ 已接线 | `core/commands.py::_memorial_posture` → `generate_memorials` 入参 |
| `core/ai/tiandao_facade.py` · `derive_dialogue_stance` | ✅ 已接线 | `core/commands.py::audience_dialogue` → `dialogue` 的 `state_summary` |
| `core/ai/tiandao_facade.py` · `summarize_monthly_omen` | ✅ 已接线 | `core/commands.py::monthly_report_args` → `monthly_report` 入参 |
| `core/ai/tiandao_facade.py` · `observe_monthly`（10 方法只读观察） | 🟡 **只读已接线（2026-10-21）** | `core/settlement.py::run_monthly_settlement` 每月调用；结果挂 `state._tiandao_observe`（诊断、不入存档），**不改数值** |
| `granary_corruption_check` | ✅ **数值已接线（2026-10-21，Jev B 0.492）** | `settlement_granary._granary_corruption_factor`：False ⇒ 雀鼠耗本色损耗 **×0.5**（不归零；无记录回落 1.0）；钱侧贪腐不动 |
| `reform_compliance_gate` | ✅ **数值已接线（2026-10-21，Jev A 0.464）** | `settlement_decree._reform_compliance_factor`：False ⇒ `finance_rates` 财政改革幅度 **×0.5**（只此一处；无记录回落 1.0） |
| `changping_intervene_gate` | ✅ **数值已接线（2026-10-21，Jev B 0.365 vs A 0.365 近平手，按 B）** | `settlement_granary._changping_sell_allowed`：False ⇒ 本月高价**平粜不卖**（只影响卖粮，不影响平籴/价格公式；无记录回落 True） |
| `tax_collection_stance` / `should_waive_ancient_arrears` / `merchant_trade_or_hoard` / `changping_intervene_gate` / `canal_reroute_choice` / `granary_corruption_check` / `farmer_destitution_path` / `gentry_charity_vs_annex` / `reform_compliance_gate` / `recruit_refugees_to_soldiers_gate` | 🟡 **只读接线（2026-10-21，Jev A 0.799）** | `TianDaoFacade.observe_monthly` 每月记录裁决；**数值效果仍未接线**（需逐项定档位→数值映射、上限与 A/B；granary corruption 直接置零须单独裁定） |
| `embedded_jev.py` / `decision_facade.py` | ✅ 兼容薄桩 | 别名 `EmbeddedJevEngine` / `EmbeddedDecisionFacade` → 天道；**首参同时接受 `state_context=`** |

> 纪律：**"有实现 + 有单测"不等于"已生效"**（`specs/README.md` 状态判定）。
> 上表末段的 10 个方法一律按"未接线"理解，别在文档/汇报里写成已生效。

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
4. `crop_shadow` 式的"只读未消费"风险：`dice` 目前无生产调用方，先用或先删，别悬空；
5. 设计稿里的「中枢会签封驳 / 地方 21 路遵从 / 去魔数清单 / 七年档考课」四块**未实现**，
   且与既有实现重叠（`council_review`、`official_appraisal`、`CANAL_LOSS_*`）需先定归属再动。

## 6. 复跑

```powershell
$py = "D:\codebuddy\.audit-venv\Scripts\python.exe"
$env:PYTHONPATH=""; $env:CODEBUDDY_SAFE_DELETE_ENABLED="0"; cd D:\codebuddy\sz
& $py -m pytest _dev_tools/game-dev/tests -q -p no:cacheprovider          # 全量
& $py -m pytest _dev_tools/game-dev/tests/test_tiandao_engine_core.py -q  # 引擎契约
& $py -m pytest _dev_tools/game-dev/tests/test_tiandao_facade_wiring.py -q
& $py -m pytest _dev_tools/game-dev/tests/test_ai_narrative_pipelines.py -q
```
