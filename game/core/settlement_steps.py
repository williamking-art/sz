# -*- coding: utf-8 -*-
"""宋祚 · 月度结算各步骤实现（Step 1 ~ Step 11）——**唯一公共入口**。

本模块承载 run_monthly_settlement 流水线中除"主流程/机构改制/五层承接层"之外的
全部 Step 函数。实现已按业务领域拆到 `core/settlement_*.py`，此处统一 import
并 re-export，保持 `from core.settlement_steps import X` 兼容。

拆分映射：
  - settlement_common.py     共享守恒工具 / P1 档位常量
  - settlement_decree.py     诏令执行与长期政务
  - settlement_econ.py       经济基础与外部经济 / 作坊 / 士绅囤抛
  - settlement_finance.py    财政与货币信用
  - settlement_granary.py    仓廪漕运与灾荒
  - settlement_tech.py       科技攻关与工程
  - settlement_officialdom.py 官制吏制与资产维持
  - settlement_military.py   军事外交 / 派系 / 事件
  - settlement_imperial.py   皇帝个人与隐藏状态
主流程见 core/settlement.py。
"""
from __future__ import annotations

import random  # noqa: F401 — 兼容 monkeypatch（settlement_steps.random）

# 原模块顶部 re-export 的 content.data 常量 / 官制入口（保持 `from core.settlement_steps import X` 兼容）
from content.data import (  # noqa: F401
    get_prestige_level, EVENT_CATEGORIES,
    CANAL_MONTHLY_RATE, SPARROW_RAT, CANAL_LOSS_BASE, CANAL_LOSS_CORRUPT_WEIGHT,
    CHANGPING_HIGH, CHANGPING_LOW,
    ECONOMY_PRESSURE_THRESHOLD_GRANARY, ECONOMY_PRESSURE_THRESHOLD_PRICE,
    COMMERCE_TAX_RATE_MIN, COMMERCE_TAX_RATE_MAX,
    MATERIAL_PRICE_BASE, RESOURCE_DIMS,
    GOODS_DEMAND,
    GRAIN_CONSUME_PER_CAPITA, HIDDEN_CONSUME_PER_CAPITA, GOODS_CONSUME_RATE,
    FARMER_SELL_FLOOR, POP_FLOW_RATE, URBAN_SPLIT,
    BOOM_MULT, TIER_RANGE,
    FINANCE_DECIDE_BASE,
    SEED_GRAIN_PER_MU, FARMER_STORE_CAP, FARMER_SPOIL_RATE,
    MEAT_PRICE,
    TAX_COEFF_MIN, TAX_COEFF_MAX, TAX_POLL_RATIO,
    COMMERCE_TAX_RATE_DEFAULT, PAY_CASH_BASE, MONTHLY_EXP_CIVIL_BASE,
    SUI_GONG_ANNUAL, GRAIN_PRICE_MIN, GRAIN_PRICE_MAX,
    ARREARS_COLLECT_RATE, OFFICIAL_SERVICE_TAX_RATIO,
    DISASTER_RELIEF_GRAIN,
    HOARD_SUPPLY_SQUEEZE, HOARD_SPOIL_RATE, HOARD_DRAW_RATE,
    HOARD_CAP_MULT, HOARD_COPPER_RATIO_BASE,
)
from core import officialdom as _officialdom  # noqa: F401

from core.settlement_econ_helpers import (  # noqa: F401 — re-export 兼容
    _distribute_pop_wealth, _settle_mint,
)

from core.settlement_common import (  # noqa: F401 — re-export 兼容
    transfer_public_funds_to_pops,
    _distribute_cash,
    _collect_from_pops,
    _avg_corruption,
    _recalc_region_price,
    _state_grain_trade,
    _changping_trade,
    _levy_men,
    _return_men,
    _tier7,
    _TA,
    _TB,
    _P1_ATT_DELTA,
    _P1_ARM_DELTA,
    _P1_TRAIN_DELTA,
    _P1_LEVY_COST,
    _P1_RELIEF,
    _P1_REFUGEE,
)

from core.settlement_decree import (  # noqa: F401 — re-export 兼容
    _settle_decrees,
    _apply_decree_effect,
    _settle_longterm_decrees,
)

from core.settlement_econ import (  # noqa: F401 — re-export 兼容
    _settle_economy,
    _settle_land_local,
    _settle_econ_prices,
    _settle_literacy,
    _settle_region_deepen,
    _settle_extensions,
    _ext_econ_phases,
    _settle_external_economy,
    _settle_workshops,
    _buyer_pool,
    _sell_to_buyers,
    _settle_civilian_hoard,
)

from core.settlement_finance import (  # noqa: F401 — re-export 兼容
    _refresh_jiaozi_credit,
    _settle_bank_credit,
    _settle_jiaozi_term,
    _settle_coin_melt,
    _settle_jiaozi_cycle,
    _settle_melt_copper,
    _settle_stabilizer_recycle,
    _settle_treasury,
    _settle_tax_grain_sale,
    _settle_arrears_repayment,
    _settle_finance,
    _settle_bank_stock,
)

from core.settlement_granary import (  # noqa: F401 — re-export 兼容
    _settle_granary,
    _normalize_disaster_region,
    _settle_disaster,
)

from core.settlement_tech import (  # noqa: F401 — re-export 兼容
    _research_rate_mult,
    _settle_tech_research,
    _settle_projects,
)

from core.settlement_officialdom import (  # noqa: F401 — re-export 兼容
    _settle_officialdom,
    _settle_clerks,
    _settle_clan,
    _settle_upkeep,
)

from core.settlement_military import (  # noqa: F401 — re-export 兼容
    _settle_military_diplomacy,
    _settle_events,
    _trigger_event,
    _settle_factions,
)

from core.settlement_imperial import (  # noqa: F401 — re-export 兼容
    _settle_emperor_personal,
    _imp_split_tier,
    _imp_tier_delta,
    _apply_imperial_action,
    _apply_imperial_effects,
    _settle_hidden,
    _settle_hidden_pop,
)


# ------------------------------------------------------------
# Step 3.7b: 外部政权简单模拟（按发育曲线 × 难度缓变）
# ------------------------------------------------------------
def _simulate_external(state, log):
    presets = state.difficulty_presets.get(state.difficulty, {})
    mult = presets.get("external_growth", 1.0)
    regime = getattr(state, "external_regimes", {})
    for key, ex in regime.items():
        curve = ex.get("growth_curve", {"expansion": 0.0, "power_growth": 0.0})
        ex["power"] = max(0, ex.get("power", 0) + curve.get("power_growth", 0) * 100 * mult)
        ex["population"] = max(0, ex.get("population", 0) + curve.get("expansion", 0) * 100 * mult)
        ex["storage"] = max(0, ex.get("storage", 0) + curve.get("power_growth", 0) * 40 * mult)
        att = ex.get("attitude", 50)
        ex["attitude"] = max(0, min(100, att + random.randint(-2, 2)))
        # 记忆知识库（Phase 3a）：外部政权态度推演写入图谱（stance）
        try:
            state.memory.add_entity(f"external_{key}", "external_power", key, turn=state.turn)
            state.memory.upsert_relation(f"external_{key}", "宋", "stance",
                                         weight=1.0 + att / 100.0, turn=state.turn,
                                         note=f"态度{att}")
        except Exception:
            pass
        # 审查 2026-09：六阶 POP 与省份运行态随国人口/兵额演化（参与月度结算）。
        #   - 国 population(万) 变化 → pop 各阶层 size 等比重算；
        #   - 省份人口/兵力按权重与国一致重摊；
        #   - 与外邦交战（treaty "_at_war"）或态度恶劣时，兵 POP 与省兵力月耗减（战争损耗）。
        try:
            from content.data import external_pop_shares
            _sh = external_pop_shares(str(ex.get("type", "")))
            _total = max(0, int(ex.get("population", 0))) * 10000
            pop = ex.get("pop")
            if not isinstance(pop, dict):
                pop = {}
                ex["pop"] = pop
            for _kl, _share in _sh.items():
                _sz = int(_total * _share)
                _slot = pop.setdefault(_kl, {"size": 0, "wealth": 0, "grain": 0})
                _slot["size"] = _sz
            _troops_total = int(_total * _sh.get("兵", 0))
            # 战争损耗：交战(sui_x bian/战争标记) 或态度<30 的敌意国，兵 P OP/省兵力每月损耗 0.5%
            # 战争损耗：交战（diplomacy_treaty 战争标记 state._at_war）或态度<30 的敌意国，
            # 兵 POP/省兵力每月损耗 0.5%（进攻方国力/人口亦受战损影响，参与结算）
            _at_war = bool((getattr(state, "_at_war", {}) or {}).get(key))
            _hostile = att < 30
            if _at_war or _hostile:
                _loss = max(1, int(_troops_total * 0.005))
                _troops_total = max(0, _troops_total - _loss)
                _bs = pop.get("兵") or pop.setdefault("兵", {"size": 0, "wealth": 0, "grain": 0})
                _bs["size"] = max(0, _bs.get("size", 0) - _loss)
            provinces = ex.get("provinces")
            provinces = ex.get("provinces")
            if isinstance(provinces, list):
                _tot_w = sum(p.get("weight", 1.0) for p in provinces) or 1.0
                for _p in provinces:
                    _w = float(_p.get("weight", 0)) / _tot_w
                    _p["population"] = int(_total * _w)
                    _p["troops"] = int(_troops_total * _w)
                    # 2026-09-22：三政权省域 POP 同步重派生（size 按该省**精确人口**
                    # × type 份额，wealth/grain 保持演化值不动——只对齐 size）
                    _ppops = _p.get("pops")
                    if isinstance(_ppops, dict):
                        for _kl, _share in _sh.items():
                            _psz = int(_p.get("population", 0) * _share)
                            _slot = _ppops.setdefault(_kl, {"size": 0, "wealth": 0, "grain": 0})
                            _slot["size"] = _psz
                        # 省内兵 size 对齐该省 troops（三元一致：兵==省兵力==军队）
                        _pbs = _ppops.get("兵")
                        if isinstance(_pbs, dict):
                            _pbs["size"] = int(_p.get("troops", 0) or 0)
            # 兵 POP 对齐 Σ省兵力（int 截断差归零，三元一致）
            _eb = ex.setdefault("pop", {}).get("兵")
            if isinstance(_eb, dict):
                _eb["size"] = sum(int(p.get("troops", 0) or 0) for p in provinces)
            # 军队实体化同步：每支军队按其驻地省份 troops 重算 branches/兵额，
            # 与省兵力、兵 POP 三元一致（损耗/扩张后同步）。
            _armies = ex.get("armies")
            if isinstance(_armies, list) and isinstance(provinces, list):
                _prov_by_name = {p.get("name"): int(p.get("troops", 0) or 0) for p in provinces}
                for _a in _armies:
                    _target = int(_prov_by_name.get(_a.get("station"), 0))
                    if _target <= 0:
                        _a["branches"] = {}
                        _a["troops"] = 0
                        continue
                    _br = _a.get("branches") or {}
                    _cur = sum(_br.values())
                    _scale = (_target / _cur) if _cur > 0 else 0.0
                    _nb = {k: int(v * _scale) for k, v in _br.items()}
                    _d = _target - sum(_nb.values())
                    if _d and _nb:
                        _nb[max(_nb, key=_nb.get)] = max(0, _nb[max(_nb, key=_nb.get)] + _d)
                    _nb = {k: n for k, n in _nb.items() if n > 0}
                    if not _nb and _target > 0:
                        _nb = {(_a.get("tier") or "轻步兵"): _target}
                    _a["branches"] = _nb
                    _a["troops"] = sum(_nb.values())
        except Exception:
            pass


# ------------------------------------------------------------
# Step 6.5: 历史改写位评估
# ------------------------------------------------------------
def _evaluate_timeline_breaks(state, log):
    """检测玩家成效是否达成改写史实的条件（不直接改写历史）。"""
    tl = state.timeline
    pb = state.pending_breaks
    jin = state.external.get("金", {})
    liao = state.external.get("辽", {})

    if "jin_crushed" not in tl and "jin_crushed" not in pb and jin.get("power", 100) <= 25:
        pb["jin_crushed"] = {"year": state.year, "label": "女真已衰，可趁势灭其于萌芽"}
        log.append("[军机] 女真部族已遭重创，枢密院已具密奏，候陛下朱批定夺")

    if "liao_ally" not in tl and "liao_ally" not in pb and liao.get("attitude", 0) >= 70:
        pb["liao_ally"] = {"year": state.year, "label": "辽主示好，可许盟南北夹击"}
        log.append("[军机] 辽主亲善，枢密院已具密奏，候陛下朱批定夺")

    from core.army_models import _army_power_total
    army_str = int(_army_power_total(state.army_units, state.tech.get("gunpowder", 20)) / 1000.0)
    if ("no_jingkang" not in tl and "no_jingkang" not in pb
            and "jin_crushed" not in tl and "jin_crushed" not in pb
            and state.prestige >= 70 and army_str >= 280
            and jin.get("invasion_will", 100) < 40):
        pb["no_jingkang"] = {"year": state.year, "label": "社稷可固，靖康之祸可消弭于未然"}
        log.append("[军机] 国势鼎盛、甲兵方强，枢密院已具密奏，候陛下朱批定夺")


# ------------------------------------------------------------
# 流水线步骤序列（元数据；执行仍由 run_monthly_settlement 按固定顺序直接调用，
# 本表供 test_pop_identity `_STEPS` 镜像与调试逐步比对。命名与顺序不得改。）
# ------------------------------------------------------------
_STEPS = [
    ("decrees", _settle_decrees),
    ("factions", _settle_factions),
    ("economy", _settle_economy),
    ("land_local", _settle_land_local),
    ("region_deepen", _settle_region_deepen),
    ("literacy", _settle_literacy),
    ("longterm", _settle_longterm_decrees),
    ("external", _simulate_external),
    ("projects", _settle_projects),
    ("workshops", _settle_workshops),
    ("upkeep", _settle_upkeep),
    ("granary", _settle_granary),
    ("officialdom", _settle_officialdom),
    ("clan", _settle_clan),
    ("clerks", _settle_clerks),
    ("finance", _settle_finance),
    ("external_economy", _settle_external_economy),
    ("extensions", _settle_extensions),
    ("econ_prices", _settle_econ_prices),
    ("treasury", _settle_treasury),
    ("military", _settle_military_diplomacy),
    ("timeline", _evaluate_timeline_breaks),
    ("events", _settle_events),
    ("disaster", _settle_disaster),
    ("emperor", _settle_emperor_personal),
    ("hidden", _settle_hidden),
    ("bank_stock", _settle_bank_stock),
]


def __getattr__(name):
    """延迟 re-export `run_monthly_settlement`（实现于 core.settlement，避免循环 import）。"""
    if name == "run_monthly_settlement":
        from core.settlement import run_monthly_settlement as _rms
        return _rms
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__():
    return sorted(set(globals()) | {"run_monthly_settlement"})
