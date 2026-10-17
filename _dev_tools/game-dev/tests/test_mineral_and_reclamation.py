# -*- coding: utf-8 -*-
"""测试 M313 地脉矿藏储量、铜煤真账与官方民间双轨垦荒机制。"""

import types
import pytest

from core.domains.economy import mineral_deposit as md
from core.domains.economy import land_reclamation as lr
from core.domains.economy.macro_climate import ALL_CIRCUITS_21


def _create_mock_state():
    state = types.SimpleNamespace()
    state.treasury = 500000
    state.imperial_treasury = 100000
    state.grain_price = 1.2
    state.turn = 1
    state.prefectures = {}
    for r in ALL_CIRCUITS_21:
        state.prefectures[r] = {
            "land": 20000000.0,
            "min_tian": 14000000.0,
            "guan_tian": 2000000.0,
            "yin_tian": 4000000.0,
            "wasteland": 5000000.0,
            "clerks_detail": {"grip": 0.40},
            "pops": {
                "农": {"size": 1500000, "wealth": 800000.0, "grain": 500000.0},
                "商人": {"size": 200000, "wealth": 1200000.0},
            },
        }
    return state


def test_mineral_deposits_initialization_and_reserves():
    state = _create_mock_state()
    md.init_circuit_minerals(state)

    # 验证江西与河东铜矿
    jx_mines = md.get_circuit_minerals(state, "江南西路")
    assert md.DIM_COPPER in jx_mines
    assert jx_mines[md.DIM_COPPER]["reserves"] > 100000000.0

    # 验证河东与磁州石炭/煤矿
    hd_mines = md.get_circuit_minerals(state, "河东路")
    assert md.DIM_COAL in hd_mines
    assert hd_mines[md.DIM_COAL]["reserves"] >= 3000000000.0


def test_mineral_extraction_and_reserves_depletion():
    state = _create_mock_state()
    md.init_circuit_minerals(state)

    init_res = state.mineral_deposits["河东路"][md.DIM_COAL]["reserves"]
    res = md.extract_circuit_minerals(state, "河东路", rate_mult=1.0, clerk_grip=0.40)

    assert md.DIM_COAL in res
    extracted = res[md.DIM_COAL]["physical_extracted"]
    assert extracted > 0.0

    # 验证真实储量物理扣减守恒
    curr_res = state.mineral_deposits["河东路"][md.DIM_COAL]["reserves"]
    assert curr_res < init_res
    assert res[md.DIM_COAL]["gov_monopoly_share"] > 0.0
    assert res[md.DIM_COAL]["tax_coin"] > 0.0


def test_government_reclamation_budget_and_guan_tian():
    state = _create_mock_state()
    lr.init_circuit_wasteland(state)

    init_t = state.treasury
    init_land = state.prefectures["河北路"]["land"]
    init_waste = state.prefectures["河北路"]["wasteland"]

    # 官方拨款 16,000 贯，目标开垦 20,000 亩
    rec = lr.reclaim_land_government(state, "河北路", target_mu=20000.0, silver_funding=16000.0)
    assert rec["ok"] is True
    assert rec["reclaimed_mu"] == 20000.0
    assert rec["cost_silver"] == 16000

    # 验证土地转化与国库真扣
    assert state.treasury == init_t - 16000
    assert state.prefectures["河北路"]["land"] == init_land + 20000.0
    assert state.prefectures["河北路"]["wasteland"] == init_waste - 20000.0
    assert state.prefectures["河北路"]["guan_tian"] == 2000000.0 + 20000.0


def test_civilian_spontaneous_reclamation_and_tenure_split():
    state = _create_mock_state()
    lr.init_circuit_wasteland(state)

    init_waste = state.prefectures["两浙路"]["wasteland"]
    rec = lr.reclaim_land_civilian_spontaneous(state, "两浙路", clerk_grip=0.50, grain_price=1.3)

    assert rec["reclaimed_total"] > 0.0
    assert rec["to_min_tian"] > 0.0
    assert rec["to_yin_tian"] > 0.0
    # 严格守恒：民田 + 隐田 == 辟荒总量
    assert abs((rec["to_min_tian"] + rec["to_yin_tian"]) - rec["reclaimed_total"]) < 0.1
    # 荒地相应减少
    assert state.prefectures["两浙路"]["wasteland"] == init_waste - rec["reclaimed_total"]
