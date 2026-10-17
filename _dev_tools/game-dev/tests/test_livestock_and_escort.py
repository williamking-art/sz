# -*- coding: utf-8 -*-
"""测试 M315 畜牧马政、镖局走镖护送与原料商品物权化。"""

import types
import pytest

from core.domains.economy import livestock_and_escort as le
from core.domains.economy import logistics_coupler as lc
from core.domains.economy.macro_climate import ALL_CIRCUITS_21


def _create_mock_state():
    state = types.SimpleNamespace()
    state.treasury = 500000
    state.canal_block = 10
    state.turn = 1
    state.in_transit_batches = []
    state.statistics = {"barges_pool": 60}
    state.prefectures = {}
    for r in ALL_CIRCUITS_21:
        state.prefectures[r] = {
            "unrest": 25,
            "govern": 45,
            "seats": {
                f"{r}_seat_1": {
                    "name": f"{r}府",
                    "warehouses": {
                        "public_depot": {"stocks": {}},
                        "public_granary": {"stocks": {}},
                        "civilian_depots": {"stocks": {}},
                        "private_storage": {"stocks": {}},
                    }
                }
            },
            "pops": {
                "农": {"size": 2000000, "wealth": 800000.0},
                "商人": {"size": 300000, "wealth": 1500000.0},
            }
        }
    return state


def test_livestock_production_and_horse_admin():
    state = _create_mock_state()
    # 河北路北方马政与畜牧
    res = le.advance_livestock_production(state, "河北路")

    assert res["meat"] > 0
    assert res["leather"] > 0
    assert res["war_horses"] > 0
    assert res["draught_horses"] > 0

    # 验证战马与生革物理确权写入官料场与民间货栈
    wh = state.prefectures["河北路"]["seats"]["河北路_seat_1"]["warehouses"]
    assert wh["public_depot"]["stocks"].get("战马", 0) > 0
    assert wh["public_depot"]["stocks"].get("生革", 0) > 0
    assert wh["civilian_depots"]["stocks"].get("meat", 0) > 0


def test_bandit_risk_and_escort_guard_hiring():
    state = _create_mock_state()
    # 河北路民怨高 (unrest=25, govern=45)，盗贼风险应超过 10%
    risk = le.calculate_route_bandit_risk(state, "河北路")
    assert risk >= 0.10

    # 注入物料发起长途物流调拨
    wh = state.prefectures["河北路"]["seats"]["河北路_seat_1"]["warehouses"]
    wh["public_depot"]["stocks"]["熟铜"] = 30000.0

    res = lc.dispatch_industry_logistics(
        state,
        origin_circuit="河北路",
        target_circuit="京畿路",
        goods_dim="熟铜",
        amount=15000.0,
        owner="state:treasury",
    )

    assert res["ok"] is True
    batches = state.in_transit_batches
    assert len(batches) == 1
    b = batches[0]

    # 验证沿线盗贼风险自动触发商帮雇佣镖局走镖护卫
    assert b.get("escorted") is True
    assert b.get("escort_fee") > 0
    assert b.get("security_bonus") == 0.85

    # 验证镖局行业账本统计
    mkt = le.survey_escort_market(state)
    assert mkt["total_escorted_batches"] >= 1
    assert mkt["total_fees_paid"] > 0
