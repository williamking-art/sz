# -*- coding: utf-8 -*-
"""M298 · Batch 1 核心循环单元测试：21路宏观物候（四价一荒）+ 朝堂双轨推力与 P3 封驳力谏机制。"""
import pytest
import os
import sys

_GAME = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "game"))
if _GAME not in sys.path:
    sys.path.insert(0, _GAME)

from core.game_state import GameState
from core.domains.economy.macro_climate import (
    ALL_CIRCUITS_21,
    derive_circuit_climate,
    derive_macro_climate,
    vignette_of_circuit,
)
from core.domains.administration.minister_agent import ensure_actor
from core.decree_confirm import (
    STATUS_CONFIRMED,
    STATUS_VETO,
    OUTCOME_VETOED,
    OUTCOME_EXECUTED,
    confirm_decree,
    exec_ledger_of,
    execution_of,
)
from core.settlement_decree import _settle_decrees
from content.ministers.data import MINISTERS


# ============================================================
# 1. 21 路宏观物候测试
# ============================================================
def test_all_circuits_21_exact_count():
    """严守 21 路权威口径：20 经济路 + 黔中路，无重复无遗漏。"""
    assert len(ALL_CIRCUITS_21) == 21
    assert len(set(ALL_CIRCUITS_21)) == 21
    assert "京畿路" in ALL_CIRCUITS_21
    assert "两浙路" in ALL_CIRCUITS_21
    assert "黔中路" in ALL_CIRCUITS_21


def test_derive_macro_climate_coverage():
    """验证 derive_macro_climate 全面覆盖 21 路，指标无缺失。"""
    state = GameState()
    macro = derive_macro_climate(state)
    assert macro["national_summary"]["circuit_count"] == 21
    circs = macro["circuits"]
    assert len(circs) == 21
    for c in ALL_CIRCUITS_21:
        res = circs[c]
        assert res["defined"] is True
        assert res["rice_price"] > 0
        assert res["silk_price"] > 0
        assert res["salt_ratio"] > 0
        assert 0.0 <= res["cash_famine"] <= 1.0
        assert 0.0 <= res["famine_index"] <= 1.0
        assert len(res["vignette"]) > 0
        assert c in res["vignette"]


def test_climate_famine_and_vignette():
    """极端物候模拟：缺粮高粮价触发饥馑警语，沿边触发钱荒警语。"""
    state = GameState()
    # 模拟两浙路粮存耗尽、底层农户贫困
    p = state.prefectures["两浙路"]
    p["grain"] = 100
    p["population"] = 5000000
    p["pops"]["农"]["wealth"] = 100

    clim = derive_circuit_climate(state, "两浙路")
    assert clim["famine_index"] >= 0.40
    assert any(w in clim["vignette"] for w in ("饥民", "暴腾", "腾贵", "艰辛"))

    # 模拟河北路钱荒
    clim_hb = derive_circuit_climate(state, "河北路")
    assert clim_hb["cash_famine"] >= 0.70
    assert "铜钱" in clim_hb["vignette"] or "钱荒" in clim_hb["vignette"]


# ============================================================
# 2. P3 复述门大臣力谏封驳与特旨覆盖测试
# ============================================================
def test_p3_minister_veto_by_faction_conflict():
    """旧党大臣（韩忠彦）承办激进方田新法，触发 STATUS_VETO 封驳。"""
    state = GameState()
    # 韩忠彦建档且在朝有权
    ensure_actor(state, "韩忠彦", authority=1.0)

    decree = {
        "title": "方田均税清丈诏",
        "category": "新法",
        "addressees": ["韩忠彦"],
        "body": "清查豪强隐田，核实税亩",
        "effects": {"treasury": 100000},
    }
    gate = confirm_decree(state, "DEC-TEST-001", "韩忠彦", decree=decree, record=True)
    assert gate["status"] == STATUS_VETO
    assert gate["reason"] == "minister_veto"
    assert "力谏封驳" in gate.get("veto_reason", "") or "封还词头" in gate.get("message", "")


def test_p3_minister_veto_by_extortion_opposition():
    """清廉守正大臣面对苛敛搜括（花石纲/造作局），触发力谏封驳。"""
    state = GameState()
    ensure_actor(state, "陈瓘", authority=1.0)
    decree = {
        "title": "江南造作局花石进奉诏",
        "category": "营建",
        "addressees": ["陈瓘"],
        "body": "广罗奇花异石，搜括东南以充延福宫",
        "effects": {},
    }
    gate = confirm_decree(state, "DEC-TEST-002", "陈瓘", decree=decree, record=True)
    assert gate["status"] == STATUS_VETO
    assert "伏阙力谏" in gate.get("veto_reason", "")


def test_p3_minister_veto_sovereign_override():
    """皇帝降中旨特批（is_zhongzhi 或 override_by_sovereign），突破力谏强制放行。"""
    state = GameState()
    ensure_actor(state, "韩忠彦", authority=1.0)
    decree = {
        "title": "方田均税清丈诏",
        "category": "新法",
        "addressees": ["韩忠彦"],
        "body": "清查豪强隐田，核实税亩",
        "effects": {"treasury": 100000},
        "override_by_sovereign": True,
    }
    _before = state.prestige
    gate = confirm_decree(state, "DEC-TEST-003", "韩忠彦", decree=decree, record=True)
    assert gate["status"] == STATUS_CONFIRMED
    assert gate.get("overridden_by_sovereign") is True
    # 2026-10-17 全审：M325 起「御笔强推」成本为 6（中旨不override 才是 3）；
    # 且 confirm 只扣一次，settlement_decree 不得二次扣。
    assert gate.get("sovereign_prestige_cost") == 6
    assert state.prestige == max(0, _before - 6)


# ============================================================
# 3. 双轨施政（外廷 vs 内廷私局）与结算链路集成测试
# ============================================================
def test_dual_track_outer_court_decay():
    """外廷路线受胥吏衰减，无内廷专权民怨副作用。"""
    state = GameState()
    decree = {
        "title": "修缮汴河疏浚外廷令",
        "track": "outer_court",
        "effects": {"treasury": -5000},
    }
    state.pending_decrees = [decree]
    log = []
    _settle_decrees(state, log)
    # 不向内廷民怨池注水
    stats = getattr(state, "statistics", {}) or {}
    pool = stats.get("inner_court_unrest_pool", {})
    assert len(pool) == 0


def test_dual_track_inner_court_boost_and_unrest():
    """内廷私局路线：突破胥吏衰减，扣减皇威，向两浙民怨池注水。"""
    state = GameState()
    initial_prestige = state.prestige
    decree = {
        "title": "御前应奉局催纲急敕",
        "track": "inner_court",
        "route": "两浙路",
        "effects": {"treasury": -5000},
    }
    state.pending_decrees = [decree]
    log = []
    _settle_decrees(state, log)

    # 皇威扣减
    assert state.prestige == initial_prestige - 2
    # 目标路民怨池注水
    stats = state.statistics.get("inner_court_unrest_pool", {})
    assert stats.get("两浙路", 0) >= 5
    # 日志留痕
    assert any("内廷私局" in line for line in log)


def test_end_to_end_veto_interception_in_settlement():
    """端到端结算验证：大臣封驳成功阻断执行，并记入台账 outcome=vetoed。"""
    state = GameState()
    ensure_actor(state, "韩忠彦", authority=1.0)
    decree = {
        "title": "方田均税新法推行诏",
        "category": "新法",
        "addressees": ["韩忠彦"],
        "body": "推行方田均税",
        "effects": {"treasury": 500000},
    }
    state.pending_decrees = [decree]
    log = []
    _settle_decrees(state, log)

    # 验证被拦截
    assert any("力谏封驳" in line for line in log)
    did = decree.get("decree_id")
    rec = execution_of(state, did)
    assert rec is not None
    assert rec["outcome"] == OUTCOME_VETOED
    assert rec["confirm_status"] == STATUS_VETO
