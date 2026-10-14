# -*- coding: utf-8 -*-
"""M299 · Stage 2 单元测试：田亩四分与四大实体多级产业链。"""
import pytest
import os
import sys

_GAME = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "game"))
if _GAME not in sys.path:
    sys.path.insert(0, _GAME)

from core.game_state import GameState
from core.domains.economy.land_tenure import (
    derive_circuit_tenure,
    derive_national_tenure,
    apply_fangtian_survey,
)
from core.domains.economy.industry_chains import (
    derive_raw_production,
    settle_industry_chains,
    CHAIN_TEXTILE,
    CHAIN_ARMAMENT,
    CHAIN_SALT_TEA,
    CHAIN_CONSTRUCTION,
)
from core.domains.economy.macro_climate import ALL_CIRCUITS_21


def test_circuit_land_tenure_conservation():
    """验证 21 路逐路田亩四分不变量：民田 + 官田 + 庄园隐田 == 总田亩。"""
    state = GameState()
    for c in ALL_CIRCUITS_21:
        res = derive_circuit_tenure(state, c)
        assert res["defined"] is True
        total = res["total_land"]
        sum_tenure = res["min_tian"] + res["guan_tian"] + res["yin_tian"]
        assert abs(sum_tenure - total) < 1e-3, f"{c} 田亩不守恒：{sum_tenure} != {total}"
        assert res["freeholder_pops"] + res["tenant_pops"] >= 0


def test_national_land_tenure_summary():
    """验证全国田亩总览数据自洽。"""
    state = GameState()
    nat = derive_national_tenure(state)
    summary = nat["summary"]
    assert summary["total_land"] > 0
    assert abs((summary["min_tian"] + summary["guan_tian"] + summary["yin_tian"]) - summary["total_land"]) < 1e-3
    assert 0.60 <= summary["min_tian_ratio"] <= 0.80
    assert 0.10 <= summary["guan_tian_ratio"] <= 0.20
    assert 0.10 <= summary["yin_tian_ratio"] <= 0.30


def test_fangtian_survey_clearing_hidden_land():
    """验证方田均税清丈：查出隐田还原为纳税民田，总田亩完全守恒。"""
    state = GameState()
    c = "两浙路"
    before = derive_circuit_tenure(state, c)
    yin_before = before["yin_tian"]
    min_before = before["min_tian"]

    res = apply_fangtian_survey(state, c, intensity=0.30)
    assert res["ok"] is True
    assert res["cleared_land"] > 0
    assert res["conserved"] is True
    assert res["new_yin_tian"] < yin_before
    assert res["new_min_tian"] > min_before
    assert abs((res["new_min_tian"] + res["guan_tian"] + res["new_yin_tian"]) - res["total_land"]) < 1e-3

    # 验证镜像一致
    assert state.prefectures[c]["hidden_land"] == res["new_yin_tian"]


def test_raw_production_derived_from_land_and_terrain():
    """验证原料由田亩与地力内生产出，符合宋代地缘特征。"""
    state = GameState()
    # 两浙路产桑蚕丝丰富
    prod_lz = derive_raw_production(state, "两浙路")
    assert prod_lz["grain"] > 0
    assert prod_lz["silk_raw"] > 1000.0  # 东南蚕丝大宗
    assert prod_lz["salt_raw"] > 5000.0  # 沿海产盐大宗

    # 河北路冶铁丰富
    prod_hb = derive_raw_production(state, "河北路")
    assert prod_hb["iron_ore"] > prod_lz["iron_ore"]
    assert prod_hb["coal"] > prod_lz["coal"]


def test_settle_industry_chains_outputs():
    """验证四大实体多级产业链推进：转化成品、增加专卖税收、登记台账。"""
    state = GameState()
    initial_treasury = state.treasury
    log = []
    res = settle_industry_chains(state, log)

    outputs = res["outputs"]
    assert outputs["silk_cloth_pi"] > 0
    assert outputs["cloth_pi"] > 0
    assert outputs["refined_iron"] > 0
    assert outputs["weapons_pieces"] > 0
    assert outputs["monopoly_tax_coin"] > 0
    assert outputs["barges_built"] > 0

    # 专卖税入并入国库
    assert state.treasury > initial_treasury
    # 台账持久化
    stats = state.statistics.get("industry_chains_ledger", {})
    assert str(state.turn) in stats
    assert len(log) > 0
    assert "四大产业链" in log[0]
