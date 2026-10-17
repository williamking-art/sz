# antigravity 批次全量审计（M298–M325 · 2026-10-17）

> 审计人：DSH ｜ 范围：`f6688d7c80..1c9ff50c80`（M299–M325，含 M298 的产出）
> 方法：静态缺陷模式扫描 ＋ 逐 API 接线审计 ＋ 运行时探针 ＋ 全量测试归属 ＋ 高风险新代码抽读
> 口径依据：[`specs/README.md`](../specs/README.md) 状态判定（**"已实现"须有生产调用路径**）、根 `AGENTS.md` §3、`songzuo-review` skill §2/§6

## 0. 覆盖范围（先说没审的）

| 已审 | 未审 / 不在本审范围 |
|---|---|
| 57 个 `game/**/*.py` 生产文件（M299–M325 全部改动） | 12 个 `frontend/src/**` 前端文件（M301 舆图/UI 只做了代码存在性，未做像素级/. 交互核对） |
| 208 条 handover 记录（tasks/decisions/worklog） | 88 个 `game/content/ministers/**` 立绘资产（美术质量不在审查范围） |
| 全量 pytest 结果与 27 条红的归属 | M298 之前的历史批次（本次只审本区间） |
| 运行时探针 9 组（交子上限/存档往返/度量衡/采购守恒/管线语义/预stige/连署/船队/科举） | 长局（240 月）平衡性复跑（未跑，需 `SONGZUO_LONG_RUN=1`） |

## 1. 结论摘要

1. **多张"已 done"的任务卡在生产里没有调用路径** —— 按 `specs/README.md` 的判定，它们只能是"模块/数据就绪"，不是"机制生效"：
   - **M324 度量衡**：`MetrologyEngine` 5 个公开 API **全部零外部调用**；5 个体制效果字段（制造 ×1.3 / 物流损耗 −25% / 清丈抗漏 +15% / 吏胥抗拒 / 士绅民怨）**0 消费方**；`format_quantity`（公制显示）**0 消费方**。
   - **M317/M318 生产方式（PM）**：`production_methods` 8 个公开 API 全部零外部调用；`stats["seat_production_methods"]` 只写不读。
   - **M300 科举 + 三年磨勘考课**：`imperial_exam` 整模块**零引用**（`run_palace_exam`/`run_provincial_exam` 全库 0 命中）；`official_appraisal.run_triennial_appraisal` 也**零生产调用**，`last_appraisal_turn` 只写不读。
2. **副作用已经外溢到别的模块**：`administrative_efficiency` 的唯一写入方就在上述死模块里 ⇒ 该读数在生产中**永远缺失**（正是天道月报 `admin_efficiency=None` 的根源）。
3. **M325「皇威无上限」被一个线性乘数接走了**：`_jiaozi_ceiling` 用 `2.0+(prestige−50)/50` ⇒ 交子可发上限随皇威**无界**（实测储备 200 万贯：皇威 100→600 万、350→1600 万、800→3400 万）。货币口径（M1/M2、物价公式）未同步，无测试锁定。
4. **M309 声明式管线的容错语义改了回滚保障**：49 步里只有 **13 步 critical**，其余 36 步异常被 WARN 吞掉后继续 ⇒ 可能出现"半结算月"；而唯一验证"整月回滚"的用例因 `monkeypatch` 打在旧函数对象上**已经失效变红**（`DID NOT RAISE`）。
5. **M307/M308 政府采购仍破坏守恒**（上一轮已证，仍红）：一笔 10,000 贯订单 ⇒ 府库实扣 **16,000**、报表 `paid_total=10000`、官仓 +3,000 物料但商人物权未减（物料凭空）。

## 2. 必修（P0）

| # | 位置 | 现象（证据） | 成因 | 改法 | 验收断言 |
|---|---|---|---|---|---|
| **A-1** | `core/foundation/metrology.py` | 5/5 API 零外部引用；`get_system_effects` 的 5 个效果字段、`format_quantity` 全库 **0 消费**；`metrology_system_id` 只有本模块自己读 | 只做了引擎与单测，没接任何结算/建筑/UI | 要么接线（制造倍率→作坊产出、途耗→物流、清丈→田税、吏胥抗拒→clerks），要么在 `tasks.md` 明写"未接线"并把 `apply_reform` 标为**未暴露**的能力 | 每个效果字段至少 1 条**真实链路**用例（从 `run_monthly_settlement` 进）；`M324` 状态改 🟡 |
| **A-2** | `core/domains/economy/production_methods.py` | 8/8 API 零外部引用；`seat_production_methods` 只写 | M317 的 PM 架构只落在自包含模块里 | 接 `civil_building`/`settlement_workshops`（产出 = f(PM, throughput)），或标注未接线 | 作坊产出随 PM 切换而变化（≥2 条用例） |
| **A-3** | `core/domains/administration/imperial_exam.py`、`official_appraisal.py` | `imperial_exam` 文件名全库 **0 命中**；`run_triennial_appraisal` 仅自身 2 处；`last_appraisal_turn` / `last_exam_turn` 只写不读；`administrative_efficiency` 唯一写入方在死模块 | 两大"人事闭环"只写了模块与单测 | ① 在结算管线加 `appraisal`/`exam` 步（36 月/3 年节律）；② 或把 `administrative_efficiency` 的写入挪到已接线的 `settlement_officialdom` | 跑满 36 月后 `promoted+demoted > 0` 且 `administrative_efficiency` 有值；`last_appraisal_turn` 有读方 |
| **A-4** | `core/game_state_econ.py:221-224` × M325 | `_jiaozi_ceiling` 随皇威**无界线性**放大（储备 200 万：prestige 100→600 万 / 350→1600 万 / 800→3400 万） | M325 取消 `PRESTIGE_MAX` 物理上限，但没检查"谁在消费 raw prestige" | 交子上限改为**有界**映射（如 `min(3.0, ratio)` 或改成分档），并同步 `货币口径规范_M0M1M2.md` | 新用例：prestige 50/100/350 的交子上限有上界且单调不降；物价恒等式仍成立 |
| **A-5** | `core/settlement_pipeline.py:44-70` | 49 步中 36 步 `critical=False` ⇒ 异常仅 WARN 后继续（旧行为：任何步异常 → 整月回滚） | M309 引入容错隔离时未区分"可容错的装饰步"与"账目步" | 把**动账本的步**全部标 critical（收益/支出/产出/拨付/仓储），只留纯读数/叙事步容错；并补回滚用例 | 注入 `_settle_finance` 失败 ⇒ `settle_local` 抛错且 `statistics`/POP/国库逐字段回滚 |
| **A-6** | `core/domains/economy/procurement.py:142-199` + `spatial_warehouse_bridge.transfer_goods_ownership` | 一笔 10,000 贯单：`Δlocal=−16,000`、`paid_total=10,000`、`Δ商=+12,000`、官仓 +3,000 铁而商人物权未减 | `settle_procurement_order` 先付款，又把 `money_consideration` 传给内部**再付一次**的函数；`transfer_goods_ownership` 只写台账不动物权（docstring 却称"保证 ΔStock==0"） | ① 只付一次；② 物权转移真扣源（走 `material_holding.consume_for_seat`）；③ `paid_total` = 实付 | 3 条既有守恒用例转绿；新增 `Δlocal+Δ商+Δ工==0`、`Δ商人物料+Δ官仓==0` |
| **A-7** | `core/settlement_military.py`（M325 新增段） | `u.add_troops(-100)`：`troops 60,000→59,900`，而 **ΣPOP 变化 0** | 逃亡减员只改编制，无处落（不回流民/农 POP） | 逃亡者落 `流民`（或农 POP + 民怨），并加守恒断言 | `Δ(兵编制) + Δ(兵POP/流民) == 0`；欠饷 25 万贯时月逃亡可观测 |
| **A-8** | `core/domains/administration/imperial_exam.py:234` | `state.prestige = int(...)+5` 直写，绕过 `change_prestige`（月变上限 8/事件 15/下限 0/**历史台账**） | 绕单点 | 改 `state.change_prestige(+5, reason="殿试唱名", is_major=True)` | 同月累计不可超上限；`_prestige_history` 有该笔 |

## 3. 应修（P1）

| # | 位置 | 现象 | 改法 |
|---|---|---|---|
| B-1 | `core/domains/economy/logistics_coupler.py:151,223` | `int(stats.get("barges_pool", 50) or 50)` ⇒ 船队归 **0** 时反而得到 **50 条**（`0 or 50`） | `v = stats.get("barges_pool"); v = 50 if v is None else int(v)` |
| B-2 | `core/settlement.py:465,470` × M321 | Step 0 破产/危机判定仍用死常量 `TREASURY_COLLAPSE_LINE`/`TREASURY_CRISIS_LINE`，而 `_settle_finance` 已用天道动态线 ⇒ **同一概念两套判据** | Step 0 改用 `TianDaoFacade.dynamic_treasury_crisis_line`（或反之统一回常量），二选一并写明 |
| B-3 | `core/decree_effect.py`（M325 增补） | `cs_factor = 0.35 + 0.65×连署率` 作为**二级乘数**再压 `clerks_compliance`（下限 0.35），幅度未纳口径；`s.get("countersigned", True)` 是**缺失即"已连署"** | ① 把连署因子写进口径注释与 `specs/cross-cutting/tiandao-engine/tasks.md`；② 缺失改 `is None` 显式处理（当前 136 治所都有该字段，故只是防御） |
| B-4 | `core/domains/administration/prefect_officials.py` | `check_countersign`（真正的连署判定）/ `appoint_prefect_official` / `jinshi_to_county` 仅自身引用 ⇒ **知通互掣只有读数、没有判定**；M325 的连署率只能读 `countersigned` 静态字段 | 接 `check_countersign` 到诏令执行，或标注未接线 |
| B-5 | `core/domains/economy/mineral_deposit.py` | `init_circuit_minerals`/`derive_national_mineral_status`/`get_circuit_minerals` 仅自身引用（`industry_chains` 只用了 `consume`/`reserve` 一类）；M313 的"官方民间双轨垦荒"未接 | 开局初始化 + 月度耗竭接进对应步 |
| B-6 | `core/domains/economy/land_tenure.py`、`land_reclamation.py` | `apply_fangtian_survey`/`derive_national_tenure`/`reclaim_land_government`/`get_circuit_wasteland` 仅自身引用 ⇒ 方田清丈与垦荒无生产入口；但 `p["land"]/["guan_tian"]/["min_tian"]/["yin_tian"]` 有写方（待确认写方是否可达） | 接进 settlement 或标注未接线；确认田亩四分字段的真实写点 |
| B-7 | `core/domains/economy/livestock_and_escort.py`、`logistics_coupler.py`、`macro_climate.py` | `advance_livestock_production`、`dispatch_industry_logistics`/`survey_logistics_coupling`、`derive_macro_climate`/`vignette_of_circuit` 仅自身引用（`derive_circuit_climate` 已接 `pop_livelihood`） | 同上：接线或标注；M298 的"四价一荒"只有部分气候派生生效 |
| B-8 | `core/settlement_military.py`（M325） | 新魔数 `100000`/`250000`/`//100`/`300`、`(abil−0.5)*3`、`(corr−0.2)*2` 无来源常量、无注释 | 常量入 `content/data_constants.py` 并注明取中依据 |
| B-9 | `core/settlement_military.py` | `float(c_info.get("corruption", 0.3) or 0.3)`：`corruption=0`（极清廉）会被吞成 0.3 ⇒ 反向扣士气（当前 250 人数据里未出现 0，属潜在） | `is None` 判缺失 |
| B-10 | `content/geo_admin.py` / 数据层 | 黔中路已全套补齐但 `game_unit=None`（账目/舆图层，不可玩）；文档未写明 ⇒ 实现者按"21 路"遍历 `state.prefectures` 会漏或炸 | 在 `specs` 与机制说明写明"20 可玩 / 21 账目"双层 |

## 4. 可选（P2）

1. 天道 `score`/`gate` 里我把 `prestige` 钳到 [0,100]，与 M325"物理无上限"不一致（裁决层是否该吃 raw 值需与 M325 口径一起定）。
2. M325 的 5 条用例（`test_prestige_authority_military_coupling.py`）断言具体、质量 OK，但**没测**交子上限、长局累积、连署因子幅度。
3. `paperdoll`/`portrait_*`（M301/M304）只做了"文件存在 + 服务层 API 有测"，未做视觉验收（本机无 WebGL，需真机）。

## 5. 测试项

| 类型 | 用例 | 理由 | 处置 |
|---|---|---|---|
| 应改 | `test_declarative_pipeline.py:25,111`（48→49） | 新增 `spatial_logistics` 步是**真实变更**，不是回归 | 改成 49 并注明新增步 |
| 应改 | `test_econ_price_review.py::test_failed_settlement_rolls_back_whole_month` | `monkeypatch.setattr(_S, "_settle_finance", _boom)` 打在旧模块对象上，管线注册的是**函数对象引用** ⇒ 注入无效，用例变红（`DID NOT RAISE`） | 改为替换 `get_default_pipeline()` 里对应 step 的 `func`，否则"整月回滚"**重新变成无覆盖** |
| 应改 | `test_domains_administration_b19.py:160`（14→15） | M324 新增 `metrology_system_id` 参数 | 改成 `>= 14` 或显式列出并注明来源 |
| 应补 | 交子上限 × 皇威边界（M325） | 无界乘数无测试 | 见 A-4 验收断言 |
| 应补 | 回滚用例（打 critical step） | 见 A-5 | — |
| 应补 | 悬空模块"接线哨兵" | 模块写了但没人调，测试全绿会误导 | 对未接线模块加 `pytest.mark.skip(reason="未接线")` 或由审计脚本 `audit_tests.py` 报 |
| 豁免 | `test_prestige_authority_military_coupling.py` | 断言具体、方向正确 | 保留 |

## 6. 误报澄清（看着像缺陷、实测没问题）

| 项 | 结论 |
|---|---|
| `industry_chains.py:397` 商人物权直写 | **合规**：`pop_obj_add(..., "wealth", -paid)` 在前，直写只是桥未下沉时的回落（项目规定写法） |
| 存档往返丢字段 | **误报**：探针第一次写错了 `load_game` 签名（它返回新 state）。改正后 `prestige=350 / institution_params / mineral / land` 全部往返一致 |
| 度量衡变法"死路" | **不是死路**：`AUTHORITY_MATTERS` 里确有「度量衡」，持有机构 = **工部** ⇒ 经圣旨可执行；问题只在"执行后没有任何玩法效果"（A-1） |
| 黔中路数据 | 21 路地脉表全覆盖、`ROAD_YIELD`/`CASH_CROP_LAND` 相符、可航档为「弱」⇔ 通用表一致 ✓ |
| `official_appraisal.assign_sinecure_retirement` 直写 on_post | **合规**：先 `_pop_obj_add` 再回落 |
| 天道批次（M319–M322） | 已由 DSH 上一轮修完（12 条 P0），本轮不重复计 |

## 7. 证据（可复核）

```powershell
$py = "D:\codebuddy\.audit-venv\Scripts\python.exe"
$env:PYTHONPATH=""; $env:CODEBUDDY_SAFE_DELETE_ENABLED="0"; cd D:\codebuddy\sz
git log --oneline f6688d7c80..HEAD            # 18 个提交
git diff --name-only f6688d7c80..HEAD -- "game/**/*.py"   # 57 个生产文件
& $py -m pytest _dev_tools/game-dev/tests -q -p no:cacheprovider   # 27 failed（归属见下）
```

静态扫描与探针产物：`D:\codebuddy\_scratch\ag_scan.json`、`ag_wiring2.json`、`ag_probe.json`、`ag_probe2.json`、`ag_probe3.json`

关键实测数字：
- 交子上限 vs 皇威：0→200 万、50→400 万、100→600 万、150→800 万、200→1000 万、350→1600 万、800→3400 万（储备 200 万）
- 皇子逃亡：`troops −100`，ΣPOP **±0**
- 采购：`Δlocal −16,000` / `paid_total 10,000` / `Δ商 +12,000` / 官仓 +3,000
- 管线：49 步，`critical=True` **13** 步
- 零外部调用（已逐个 grep 确认）：`MetrologyEngine`(5/5)、`production_methods`(8/8)、`imperial_exam`(7/7)、`run_triennial_appraisal`、`check_countersign`、`init_circuit_minerals`、`apply_fangtian_survey`、`advance_livestock_production`、`derive_macro_climate`

### 27 条红的归属

| 归属批次 | 条数 | 用例 |
|---|---|---|
| M307/M308 政府采购与四仓 | 5 | `test_local_expenditure_order`×2、`test_land_tax_split_p1`、`test_stock_flow_identity`、`test_m36_5_ai_wiring` |
| M309 声明式管线 + 新增步 | 8 | `test_declarative_pipeline`×2、`test_econ_price_review`×2、`test_middle_calibration`、`test_inspection_*`×2、`test_b2r4_agri_supply` |
| M311 读数看板 | 3 | `test_m81_readout_hub_wiring`、`test_m83_readouts_endpoint_hub`、`test_readouts_endpoint` |
| M315/M316 原料商品化 | 2 | `test_goods_dims_catalog`、`test_holder_rules_gameplay` |
| M323/M324/M325 与内容/资产 | 9 | `test_domains_administration_b19`、`test_clerks`、`test_audit_batch6_fixes`、`test_faction_voice`、`test_workshop_owner`、`test_portrait_service`×2、`test_m36_4_evidence_bridge`×2 |

## 8. 建议处置顺序

1. **先改 3 条测试的过期断言**（48→49、参数 14→15、回滚 monkeypatch 目标）——否则"回滚保障"继续无覆盖；
2. **修 A-6 采购守恒**（会直接影响玩家账目）；
3. **修 A-4 交子上限上界 + A-7 逃亡落点 + A-8 皇威单点**；
4. **A-1/A-2/A-3 三大悬空模块**：要么接线，要么把任务状态从 done 降为 🟡 并在 `tasks.md` 写明"模块就绪、未接线"；
5. A-5 管线 critical 划分重审（动账步必 critical）；
6. B 组按模块认领。
